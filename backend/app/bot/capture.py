import secrets
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import copy
from app.bot.active_stop import place_for_date
from app.bot.pending import close_pending, create_pending, load_pending
from app.bot.render import (
    BatchRow, BotReply, batch_card, buttons_reply, cat_label, expense_card, fmt_money,
    settlement_card, text_reply,
)
from app.cashback import net_amount
from app.categories.catalog import CATEGORIES
from app.db.models import Category, Movement, User
from app.fx import convert_to_usd, fx_reference_date, map_fx_source
from app.textnorm import fold, load_proper_nouns, normalize_description

_CONF_THRESHOLD = 0.6
_BATCH_MAX = 10  # más que esto huele a alucinación del parser (y revienta el mensaje)


def _cat_names() -> list[str]:
    return [c[0] for c in CATEGORIES]


async def load_categories(session: AsyncSession) -> list[tuple[str, str | None]]:
    """(name, description) desde la DB, en orden estable — para el prompt del parser."""
    rows = (await session.execute(
        select(Category.name, Category.description).order_by(Category.sort_order)
    )).all()
    # Sin seed todavía (tests con FakeLLM): caer al catálogo.
    return [(n, d) for n, d in rows] or [(n, d) for n, _, d in CATEGORIES]


async def load_city_names(session: AsyncSession) -> list[str]:
    """Paradas del itinerario para el prompt del parser, en orden del recorrido.
    Incluye las locales (Pititas): nombrar una parada es intención explícita y
    vale para los dos, aunque la imputación por fecha siga siendo por remitente."""
    from app.db.models import Stop
    rows = (await session.execute(
        select(Stop.name)
        .where(Stop.is_candidate.is_(False), Stop.is_archived.is_(False))
        .order_by(Stop.order)
    )).scalars().all()
    return list(rows)


async def _category_id(session: AsyncSession, name: str | None) -> int | None:
    if not name:
        return None
    return (await session.execute(select(Category.id).where(Category.name == name))).scalar_one_or_none()


# Alias histórico: la política vive en app/fx.py, único dueño del mapeo.
_map_source = map_fx_source


async def all_users(session: AsyncSession) -> list[User]:
    return (await session.execute(select(User).order_by(User.id))).scalars().all()


async def other_user(session: AsyncSession, user: User) -> User | None:
    return (await session.execute(
        select(User).where(User.id != user.id).order_by(User.id)
    )).scalars().first()


async def user_by_username(session: AsyncSession, username: str) -> User | None:
    return (await session.execute(
        select(User).where(User.username == username)
    )).scalar_one_or_none()


async def resolve_place(session, ref_date: date, explicit_city: str | None,
                        username: str | None = None):
    """(stop_slug, city_name, currency_code) para un gasto. La ciudad SIEMPRE sale
    de una parada del itinerario o es None (General): nunca texto libre.

    - Ciudad explícita que matchea una parada: esa.
    - Ciudad explícita que no matchea (day-trip "Sintra"): la parada base de
      `ref_date` — donde se hace base/duerme ese día.
    - Sin ciudad: parada de `ref_date` solo si cae en rango (misma semántica
      estricta que la API web). Antes del viaje, gaps o post-viaje => General.

    `ref_date` es efímero: la fecha del mensaje ("ayer") o hoy — solo sirve para
    mirar el itinerario, no se persiste en el movimiento.

    `username` es el remitente: define qué paradas propias imputa la fecha (p.ej.
    Pititas solo a su dueña). Nombrar una parada es intención explícita y matchea
    para cualquiera de los dos: Bruno puede mandar un gasto a Pititas si le pagó
    algo de ese tramo. Sin mencionarla, él sigue cayendo en Portugal.
    """
    if explicit_city:
        from app.db.models import Stop
        # Mismo universo que `load_city_names` (lo que el parser puede nombrar):
        # imputar a una parada archivada o candidata la resucitaba de atrás.
        stops = (await session.execute(
            select(Stop).where(Stop.is_candidate.is_(False), Stop.is_archived.is_(False))
        )).scalars().all()
        wanted = fold(explicit_city.strip())
        for s in stops:
            if fold(s.name or "") == wanted:
                return s.slug, s.name, (s.currency_code or "USD")

    stop = await place_for_date(session, ref_date, username)
    if stop is None:
        return None, None, "USD"
    return stop.slug, stop.name, (stop.currency_code or "USD")


async def owner_split(session, stop_slug: str | None, payer: User, split: str) -> str:
    """Split efectivo según el dueño de la parada.

    Una parada con `owner_username` (Pititas→Katia, Portugal→Bruno) implica que
    sus gastos son, por default, de esa persona: no se reparten 50/50 como en el
    resto del viaje. Sin necesidad de aclararlo en el mensaje.

    Solo pisa el default: si el usuario pidió explícitamente un split individual
    (`payer_only`/`other_only`), se respeta — `shared` es la señal de "no aclaró".
    El valor es relativo al pagador: si paga el dueño → `payer_only`; si paga el
    otro → `other_only` (en un libro de 2, el no-pagador es el dueño). Vale para
    los dos remitentes: si Bruno manda un gasto a Pititas, igual queda de Katia.
    """
    if not stop_slug or split != "shared":
        return split
    from app.db.models import Stop
    owner = (
        await session.execute(select(Stop.owner_username).where(Stop.slug == stop_slug))
    ).scalar_one_or_none()
    if not owner:
        return split
    return "payer_only" if owner.lower() == payer.username.lower() else "other_only"


_INSTALLMENTS_MAX = 4
_TWO = Decimal("0.01")


def expand_installments(parsed, today: date) -> list | None:
    """UN gasto pagado en etapas → clones autocontenidos, uno por parte, con
    montos que CIERRAN exacto con el total (el redondeo es server-side, nunca
    del LLM): cada etapa se calcula de su percent/amount y la ÚLTIMA absorbe el
    remanente. La etapa 'el resto' (sin percent ni amount) va última.

    Sufijo ' (i/n)' en la descripción para distinguirlas. Devuelve None si las
    etapas no son válidas (sin total, remanente <= 0, más de un 'resto'…): el
    gasto entra entero por el camino de siempre.
    """
    from dataclasses import replace
    from decimal import ROUND_HALF_UP

    insts = parsed.installments
    if not insts or len(insts) < 2 or len(insts) > _INSTALLMENTS_MAX:
        return None
    if parsed.is_settlement:
        return None

    # El cashback aplica al gasto entero. Un cashback en % se replica a cada etapa
    # (un % de cada parte cierra solo). Un cashback de MONTO FIJO + cuotas es una
    # combinación marginal que no tiene un reparto obvio: se descarta en las partes
    # (limitación documentada).
    cb_kind = parsed.cashback_kind if parsed.cashback_kind == "pct" else None
    cb_value = parsed.cashback_value if cb_kind else None

    # Modo directo: TODAS las etapas traen monto explícito ('34 usd hoy y el
    # resto 134 gbp al ingresar'). No hay aritmética que hacer, no hace falta
    # un total único, y cada etapa puede venir en su propia moneda — el batch
    # convierte cada una a USD.
    if all(i.amount is not None for i in insts):
        ordered = sorted(insts, key=lambda i: i.pay_date or today)
        if any(i.amount <= 0 for i in ordered):
            return None
        n = len(ordered)
        base_desc = parsed.description or "gasto"
        # place_date: todas las partes se imputan a UNA parada — la del gasto.
        # La referencia es la fecha de la ÚLTIMA etapa (cuando se usa lo que se
        # está pagando: el check-in del hostel), no la de hoy, que mandaría a
        # General un gasto de una parada futura. Ver ParsedMessage.place_date.
        place_date = parsed.payment_date or ordered[-1].pay_date or today
        return [
            replace(parsed, amount=i.amount, currency=i.currency or parsed.currency,
                    payment_date=i.pay_date, place_date=place_date,
                    description=f"{base_desc} ({idx}/{n})",
                    cashback_kind=cb_kind, cashback_value=cb_value,
                    installments=[], batch=[])
            for idx, i in enumerate(ordered, start=1)
        ]

    # Modo clásico (percent / 'el resto' a calcular): requiere total único en
    # UNA moneda — con monedas mezcladas no hay total contra el que calcular.
    total = parsed.amount
    if total is None or total <= 0:
        return None
    if any(i.currency and parsed.currency and i.currency != parsed.currency for i in insts):
        return None

    rests = [i for i in insts if i.percent is None and i.amount is None]
    if len(rests) > 1:
        return None
    ordered = sorted(
        (i for i in insts if i.percent is not None or i.amount is not None),
        key=lambda i: i.pay_date or today,
    ) + rests

    # Guarda anti-replicación: si TODAS las etapas traen la MISMA fecha, el LLM
    # replicó la fecha del mensaje en cada una ("12% de seña y el resto el
    # 6-oct" no son dos pagos el 6-oct). Dos pagos el mismo día no son etapas:
    # la fecha es solo de la ÚLTIMA; las anteriores se pagan hoy.
    pay_dates = [i.pay_date for i in ordered]
    if len(set(pay_dates)) == 1 and pay_dates[0] is not None:
        pay_dates = [None] * (len(ordered) - 1) + [pay_dates[-1]]

    amounts: list[Decimal] = []
    for inst in ordered[:-1]:
        if inst.amount is not None:
            amt = inst.amount
        else:
            amt = (total * inst.percent / Decimal(100)).quantize(_TWO, rounding=ROUND_HALF_UP)
        if amt <= 0:
            return None
        amounts.append(amt)
    remainder = total - sum(amounts)
    if remainder <= 0:
        return None
    amounts.append(remainder)

    n = len(ordered)
    base_desc = parsed.description or "gasto"
    place_date = parsed.payment_date or pay_dates[-1] or today
    return [
        replace(parsed, amount=amt, payment_date=pay_date, place_date=place_date,
                description=f"{base_desc} ({idx}/{n})",
                cashback_kind=cb_kind, cashback_value=cb_value,
                installments=[], batch=[])
        for idx, (pay_date, amt) in enumerate(zip(pay_dates, amounts), start=1)
    ]


def _declares_installments(parsed) -> bool:
    """¿El mensaje pidió pagar en etapas? (aunque después no se puedan expandir)"""
    return bool(parsed.installments) and not parsed.is_settlement


def _installment_notes(parsed, parts) -> list[str]:
    """Avisos de lo que se perdió al expandir las etapas. Hoy solo el cashback
    de monto fijo: no tiene un reparto obvio entre cuotas y se descarta — pero
    en silencio hacía que el neto no cerrara con lo que el usuario tipeó."""
    if parsed.cashback_kind == "amount" and len(parts) > 1:
        return [
            f"{copy.H_WARN} El *cashback fijo* no lo repartí entre las cuotas. "
            "Si aplica al total, decímelo como porcentaje (_2% de cashback_)."
        ]
    return []


def _payment_status(payment_date: date | None, today: date) -> str:
    """pending = se paga en el futuro con TC proxy; la liquidación lazy (app/due.py)
    lo confirma con el TC real cuando llega la fecha."""
    return "pending" if payment_date is not None and payment_date > today else "confirmed"


async def _persist(session, *, payer, parsed, amount_usd, rate, src, stop_slug, city_name,
                   cat_id, created_by, raw, status="confirmed"):
    mv = Movement(
        type="settlement" if parsed.is_settlement else "expense",
        amount=parsed.amount, currency=parsed.currency, amount_usd=amount_usd,
        fx_rate=rate, fx_source=_map_source(src, parsed.currency), paid_by=payer.id, split=parsed.split,
        description=parsed.description, category_id=cat_id, stop_slug=stop_slug, city_name=city_name,
        payment_date=parsed.payment_date, status=status,
        cashback_kind=parsed.cashback_kind, cashback_value=parsed.cashback_value,
        created_by=created_by.id, raw_message=raw,
    )
    session.add(mv)
    await session.commit()
    return mv


async def handle_capture(session, user: User, wa_id: str, text: str, today: date,
                         *, parsed=None, llm_client=None) -> BotReply:
    if parsed is None:
        from app.llm.parser import parse_message
        users = await all_users(session)
        parsed = await parse_message(
            text, today=today, category_names=_cat_names(),
            usernames=[u.username for u in users], sender=user.username, client=llm_client,
            city_names=await load_city_names(session),
        )

    if parsed.batch:
        # Descripciones repetidas entre gastos distintos del mensaje ('Hostel'
        # de Fort William y 'Hostel' de Portree, con la ciudad ya extraída a
        # `city`): devolverles la ciudad para poder referenciarlos después.
        from collections import Counter
        desc_counts = Counter((it.description or "").casefold() for it in parsed.batch)
        for it in parsed.batch:
            if desc_counts[(it.description or "").casefold()] > 1 and it.city:
                it.description = f"{it.description or 'gasto'} {it.city}"
        # Todo descarte se avisa: un mensaje que entra a medias sin decirlo es
        # peor que uno rechazado, porque el total del viaje queda mal callado.
        notes: list[str] = []
        kept = parsed.batch[:_BATCH_MAX]
        if len(parsed.batch) > _BATCH_MAX:
            notes.append(
                f"{copy.H_WARN} Me mandaste *{len(parsed.batch)} gastos* y guardé los "
                f"primeros {_BATCH_MAX}. Mandame el resto en otro mensaje."
            )
        # Un ítem del multi-gasto puede a su vez pagarse en etapas ('34 usd
        # hostel X hoy, el resto 134 gbp al ingresar'): expandirlo en sus
        # partes antes de persistir el batch.
        # El tope de _BATCH_MAX se aplica a los GASTOS, no a las partes: cortar
        # después de expandir partía un gasto por la mitad (3 gastos × 4 cuotas =
        # 12 ítems → se guardaban 10) y el total no cerraba, sin ningún aviso.
        items = []
        for item in kept:
            parts = expand_installments(item, today)
            if parts is None:
                if _declares_installments(item):
                    notes.append(
                        f"{copy.H_WARN} *{item.description or 'Un gasto'}* lo guardé "
                        "entero: no me cerraron las etapas de pago."
                    )
                items.append(item)
                continue
            notes.extend(_installment_notes(item, parts))
            items.extend(parts)
        return await handle_capture_batch(session, user, wa_id, text, today,
                                          items=items, notes=notes)

    # Pago en etapas: N movimientos hermanos por el camino batch (batch_key
    # compartido => "borrar" ofrece las cuotas juntas, una sola transacción).
    if (parts := expand_installments(parsed, today)) is not None:
        return await handle_capture_batch(session, user, wa_id, text, today, items=parts,
                                          notes=_installment_notes(parsed, parts))
    if _declares_installments(parsed):
        # El mensaje declara etapas pero no cierran (falta el total, el resto da
        # <= 0, dos 'restos'…). Guardar el total como gasto único deja mal la
        # fecha de pago y el status: mejor no escribir nada y pedir la aclaración.
        return text_reply(copy.INSTALLMENTS_UNCLEAR)

    if parsed.amount is None:
        return text_reply(f"{copy.H_WARN} No le pesqué el *monto*. Probá: _cena 20 euros_.")
    if parsed.amount <= 0:
        # Paridad con la API (`MovementIn.amount` gt=0): un 0 o un negativo
        # rompía el balance sin que nada lo frenara en el camino del bot.
        return text_reply(copy.NON_POSITIVE_AMOUNT)

    parsed.description = normalize_description(
        parsed.description, await load_proper_nouns(session)
    )

    # La fecha del mensaje elige la parada mirando el itinerario (un gasto futuro
    # en Interlaken cae en la parada del 3-sep) y además se persiste como fecha
    # de pago. La ciudad la define el remitente, no el pagador: si Katia carga
    # "pagó bruno 30" desde Pititas, el gasto ocurrió donde está ella.
    stop_slug, city_name, place_currency = await resolve_place(
        session, parsed.payment_date or today, parsed.city, user.username
    )
    if parsed.currency is None:
        parsed.currency = place_currency

    # Un saldo nunca lleva ciudad, fecha diferida ni cashback: general y de hoy.
    if parsed.is_settlement:
        stop_slug, city_name = None, None
        parsed.payment_date = None
        parsed.cashback_kind, parsed.cashback_value = None, None

    payer = user
    if parsed.paid_by and parsed.paid_by != user.username:
        payer = (await user_by_username(session, parsed.paid_by)) or user
    other = await other_user(session, payer)

    # Gastos en paradas con dueño (Pititas/Portugal) van al dueño por default.
    if not parsed.is_settlement:
        parsed.split = await owner_split(session, stop_slug, payer, parsed.split)

    # Regla: TC de la fecha de pago, capeada a hoy — pasada => histórico
    # Frankfurter; futura => proxy de hoy (se ajusta al liquidar, app/due.py).
    # El neto (bruto - cashback) es el que se convierte; amount guarda el bruto.
    status = _payment_status(parsed.payment_date, today)
    net = net_amount(parsed.amount, parsed.cashback_kind, parsed.cashback_value)
    amount_usd, rate, src = await convert_to_usd(
        session, net, parsed.currency, fx_reference_date(parsed.payment_date, today)
    )

    # Categoría ambigua → pending con botones (solo gastos, no settlement).
    if not parsed.is_settlement and parsed.confidence < _CONF_THRESHOLD and len(parsed.category_candidates) >= 2:
        payload = {
            "amount": str(parsed.amount), "currency": parsed.currency, "amount_usd": str(amount_usd),
            "fx_rate": str(rate), "fx_source": _map_source(src, parsed.currency), "split": parsed.split,
            "description": parsed.description, "stop_slug": stop_slug, "city_name": city_name,
            "payment_date": parsed.payment_date.isoformat() if parsed.payment_date else None,
            "status": status,
            "cashback_kind": parsed.cashback_kind,
            "cashback_value": str(parsed.cashback_value) if parsed.cashback_value is not None else None,
            "paid_by": payer.id, "raw_message": text,
        }
        token = await create_pending(session, owner=user.username, payload=payload, kind="cat_pick")
        buttons = []
        for name in parsed.category_candidates[:3]:
            cid = await _category_id(session, name)
            buttons.append((f"cat_pick:{token}|{cid}", cat_label(name)))
        return buttons_reply(
            f"{copy.H_HUH} ¿Qué categoría? _{parsed.description or 'gasto'}_ · "
            f"*{fmt_money(parsed.amount, parsed.currency, amount_usd)}*", buttons
        )

    cat_id = None if parsed.is_settlement else await _category_id(session, parsed.category_name)
    mv = await _persist(session, payer=payer, parsed=parsed, amount_usd=amount_usd, rate=rate, src=src,
                        stop_slug=stop_slug, city_name=city_name, cat_id=cat_id,
                        created_by=user, raw=text, status=status)
    other_name = other.username if other else "el otro"
    if parsed.is_settlement:
        reply = text_reply(settlement_card(mv, payer.username, other_name))
    else:
        reply = text_reply(expense_card(mv, parsed.category_name, payer.username, other_name))
    reply.movement_id = mv.id
    return reply


async def handle_capture_batch(session, user: User, wa_id: str, text: str, today: date,
                               *, items, notes: list[str] | None = None) -> BotReply:
    """N movimientos de un mensaje multi-gasto, en UNA transacción (o entran todos
    o ninguno; si algo falla, el borde de dispatch descarta y el usuario reintenta).

    Sin pendings acá: la categoría dudosa se guarda igual (marcada ❓ en el card) y
    se corrige por el flujo edit de siempre — WhatsApp da 3 botones por mensaje y
    encadenar pendings deja gastos en el limbo.

    `notes` son avisos de lo que NO entró (tope de gastos, etapas que no cerraron,
    cashback descartado): se muestran al pie del card, nunca se omiten.
    """
    notes = list(notes or [])
    # Montos no positivos: la API los rechaza (gt=0) y acá entraban derecho.
    invalid = [it for it in items if it.amount is None or it.amount <= 0]
    if invalid:
        items = [it for it in items if it not in invalid]
        nombres = ", ".join(f"*{it.description or 'sin descripción'}*" for it in invalid)
        notes.append(f"{copy.H_WARN} No guardé {nombres}: el monto no era válido.")
    if not items:
        return text_reply(copy.NON_POSITIVE_AMOUNT)
    # Red de seguridad: los callers ya acotan por gasto (_BATCH_MAX), y un gasto
    # aporta a lo sumo _INSTALLMENTS_MAX partes. Cortar acá nunca debería partir
    # un gasto al medio.
    items = items[:_BATCH_MAX * _INSTALLMENTS_MAX]
    batch_key = secrets.token_hex(8)
    users = await all_users(session)
    usernames = [u.username for u in users]
    nouns = await load_proper_nouns(session)

    movements: list[Movement] = []
    rows: list[BatchRow] = []
    for item in items:
        item.description = normalize_description(item.description, nouns)
        stop_slug, city_name, place_currency = await resolve_place(
            session, item.place_date or item.payment_date or today, item.city, user.username
        )
        currency = item.currency or place_currency
        if item.is_settlement:
            stop_slug, city_name = None, None
            item.payment_date = None
            item.cashback_kind, item.cashback_value = None, None
        payer = user
        if item.paid_by and item.paid_by != user.username:
            payer = (await user_by_username(session, item.paid_by)) or user
        # Gastos en paradas con dueño (Pititas/Portugal) van al dueño por default.
        split = item.split if item.is_settlement else await owner_split(
            session, stop_slug, payer, item.split
        )
        # Regla: TC de la fecha de pago, capeada a hoy (proxy si es futura).
        # El neto (bruto - cashback) es lo que se convierte a USD.
        status = _payment_status(item.payment_date, today)
        net = net_amount(item.amount, item.cashback_kind, item.cashback_value)
        amount_usd, rate, src = await convert_to_usd(
            session, net, currency, fx_reference_date(item.payment_date, today)
        )
        cat_name = None if item.is_settlement else item.category_name
        cat_id = None if item.is_settlement else await _category_id(session, cat_name)
        mv = Movement(
            type="settlement" if item.is_settlement else "expense",
            amount=item.amount, currency=currency, amount_usd=amount_usd,
            fx_rate=rate, fx_source=_map_source(src, currency), paid_by=payer.id,
            split=split, description=item.description, category_id=cat_id,
            stop_slug=stop_slug, city_name=city_name,
            payment_date=item.payment_date, status=status,
            cashback_kind=item.cashback_kind, cashback_value=item.cashback_value,
            created_by=user.id, raw_message=text, batch_key=batch_key,
        )
        uncertain = (not item.is_settlement and item.confidence < _CONF_THRESHOLD
                     and len(item.category_candidates) >= 2)
        movements.append(mv)
        rows.append(BatchRow(mv=mv, cat_name=cat_name, payer_name=payer.username,
                             uncertain=uncertain))

    session.add_all(movements)
    await session.commit()
    card = batch_card(rows, usernames)
    if notes:
        card += "\n\n" + "\n".join(notes)
    reply = text_reply(card)
    reply.movement_id = movements[-1].id
    return reply


async def _repriced_pending(session, data: dict, amount: Decimal, cb_kind, cb_value,
                            payment_date: date | None, today: date | None):
    """TC del pending de categoría al CONFIRMAR, no al preguntar.

    Entre el mensaje y el tap pueden pasar horas (o cruzarse la medianoche del
    viaje): persistir el snapshot a ciegas dejaba un gasto con la tasa de otro
    día. Se recotiza con la misma regla de siempre (fecha de pago capeada a hoy)
    y, si el proveedor está caído, se conserva la tasa buena del snapshot —
    misma guarda que `fx.reprice_movement` y `due.py`.
    """
    snapshot = (Decimal(data["amount_usd"]), Decimal(data["fx_rate"]), data["fx_source"])
    if today is None:
        return snapshot
    currency = data["currency"]
    net = net_amount(amount, cb_kind, cb_value)
    amount_usd, rate, src = await convert_to_usd(
        session, net, currency, fx_reference_date(payment_date, today)
    )
    if src == "fallback" and data.get("fx_source") != "fallback":
        return snapshot
    return amount_usd, rate, _map_source(src, currency)


async def apply_category_pick(session, user: User, token: str, category_id: int,
                              today: date | None = None) -> BotReply:
    data = await load_pending(session, token, owner=user.username, kind="cat_pick")
    if data is None:
        return text_reply("⚠️ Expiró: ese pending ya no está disponible.")
    payer_id = int(data.get("paid_by") or user.id)
    pay_date = data.get("payment_date")
    payment_date = date.fromisoformat(pay_date) if pay_date else None
    amount = Decimal(data["amount"])
    cb_kind = data.get("cashback_kind")
    cb_value = Decimal(data["cashback_value"]) if data.get("cashback_value") else None
    amount_usd, rate, src = await _repriced_pending(
        session, data, amount, cb_kind, cb_value, payment_date, today,
    )
    mv = Movement(
        type="expense", amount=amount, currency=data["currency"],
        amount_usd=amount_usd, fx_rate=rate,
        fx_source=src, paid_by=payer_id, split=data["split"],
        description=data.get("description"), category_id=category_id,
        stop_slug=data.get("stop_slug"), city_name=data.get("city_name"),
        payment_date=payment_date,
        status=data.get("status") or "confirmed",
        cashback_kind=cb_kind, cashback_value=cb_value,
        created_by=user.id, raw_message=data.get("raw_message"),
    )
    # Sin commit intermedio: el movimiento y el cierre del pending entran en la
    # MISMA transacción (la de `close_pending`). Commitear el movimiento primero
    # dejaba una ventana en la que un doble tap del botón encontraba el pending
    # todavía abierto y guardaba el gasto dos veces.
    session.add(mv)
    await close_pending(session, token)
    cat = (await session.execute(select(Category).where(Category.id == category_id))).scalar_one_or_none()
    payer = (await session.execute(select(User).where(User.id == payer_id))).scalar_one_or_none() or user
    other = await other_user(session, payer)
    reply = text_reply(expense_card(mv, cat.name if cat else "Otros", payer.username,
                                    other.username if other else "el otro"))
    reply.movement_id = mv.id
    return reply
