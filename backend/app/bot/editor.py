from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import copy
from app.bot.capture import (
    _category_id, _map_source, other_user, owner_split, resolve_place, user_by_username,
)
from app.bot.pending import close_pending, create_pending, load_pending, new_token
from app.bot.render import (
    BotReply, ar_number, buttons_reply, cashback_text, cat_label, edit_card, fmt_date,
    fmt_money, movement_summary, split_label, text_reply,
)
from app.cashback import net_amount, normalize_cashback
from app.config import get_settings
from app.db.models import Category, Movement, User
from app.due import next_status_for_date
from app.fx import fx_reference_date, reprice_movement
from app.textnorm import fold, load_proper_nouns, normalize_description

_SEARCH_LIMIT = 50  # movimientos recientes donde buscar referencias


async def summary_lines(session: AsyncSession, movements: list[Movement]) -> str:
    """Desglose de los movimientos (para confirmar qué se borró), antes de borrarlos."""
    users = {u.id: u.username for u in (await session.execute(select(User))).scalars().all()}
    cats = {c.id: c.name for c in (await session.execute(select(Category))).scalars().all()}
    return "\n".join(
        movement_summary(m, cats.get(m.category_id), users.get(m.paid_by, "?"))
        for m in movements
    )


async def handle_delete_command(session: AsyncSession, user: User) -> BotReply:
    """Fast path `borrar`: ofrece el último movimiento DEL REMITENTE con
    confirmación. Filtra por `created_by` igual que `recent_movement`: son dos
    chats contra el mismo ledger y "borrar" nunca puede agarrar lo del otro."""
    last = (await session.execute(
        select(Movement).where(Movement.created_by == user.id).order_by(Movement.id.desc())
    )).scalars().first()
    if last is None:
        return text_reply(f"{copy.H_WARN} Nada que borrar: no hay movimientos cargados por vos.")

    # "borrar" justo después de un mensaje multi-gasto casi siempre significa
    # "me equivoqué con ese mensaje" → ofrecer el batch entero (con confirmación).
    if last.batch_key:
        siblings = (await session.execute(
            select(Movement).where(Movement.batch_key == last.batch_key).order_by(Movement.id)
        )).scalars().all()
        if len(siblings) > 1:
            # Tokens pre-generados: cada pending lleva el del otro para que
            # confirmar uno (o cancelar) mate también al hermano — si no, el
            # token no usado seguía vivo y un re-tap borraba de nuevo.
            t_all, t_last = new_token(), new_token()
            summary = await summary_lines(session, siblings)
            await create_pending(
                session, owner=user.username,
                payload={"ids": [m.id for m in siblings], "siblings": [t_last]},
                kind="del_confirm", token=t_all,
            )
            await create_pending(
                session, owner=user.username,
                payload={"ids": [last.id], "siblings": [t_all]},
                kind="del_confirm", token=t_last,
            )
            return buttons_reply(
                f"{copy.H_WARN} Eso entró como *{len(siblings)} gastos juntos*. "
                f"¿Borrar? Es irreversible.\n{summary}",
                [
                    (f"del_confirm:{t_all}", f"Borrar los {len(siblings)} 🗑️"),
                    (f"del_confirm:{t_last}", "Solo el último"),
                    (f"del_cancel:{t_all}", "Cancelar"),
                ],
            )

    # Rama single: también por pending, nunca con el id crudo en el botón. Un
    # `del_confirm:<id>` no tiene TTL ni dueño: cualquier card viejo del
    # historial borraba de verdad al re-tocarlo meses después.
    token = await create_pending(
        session, owner=user.username, payload={"ids": [last.id]}, kind="del_confirm",
    )
    desc = last.description or last.type
    return buttons_reply(
        f"{copy.H_WARN} ¿Borrar *{desc}* ({fmt_money(last.amount, last.currency, last.amount_usd)})?\n"
        "Es irreversible.",
        [(f"del_confirm:{token}", "Borrar 🗑️"), (f"del_cancel:{token}", "Cancelar")],
    )


async def recent_movement(session: AsyncSession, *, ttl_minutes: int,
                          created_by: int | None = None,
                          include_settlements: bool = False) -> Movement | None:
    """El último gasto cargado POR ESE remitente, si es lo bastante fresco como
    para esperar una corrección. Sirve de contexto al parser: apenas guardado, un
    mensaje que ajusta monto/ciudad/categoría/división/pagador casi seguro lo
    corrige, no carga uno nuevo.

    El filtro por `created_by` importa porque son dos chats distintos contra el
    mismo ledger: sin él, un 'no, eran 45' de Bruno podía terminar editando el
    gasto que Katia acababa de cargar desde su teléfono. Las referencias
    explícitas ('el taxi') siguen alcanzando los movimientos de los dos —
    `find_candidates` no filtra.

    `include_settlements` suma los pagos de saldo: "le pasé 80" seguido de "no,
    eran 50" no tenía contexto y el parser lo leía como un gasto NUEVO de 50.
    Un settlement solo se corrige en monto/pagador, pero eso es justo lo que se
    equivoca al tipearlo.

    El corte es por created_at UTC-naive, igual criterio que find_candidates."""
    cutoff = datetime.utcnow() - timedelta(minutes=ttl_minutes)
    types = ("expense", "settlement") if include_settlements else ("expense",)
    q = select(Movement).where(Movement.type.in_(types), Movement.created_at >= cutoff)
    if created_by is not None:
        q = q.where(Movement.created_by == created_by)
    return (await session.execute(
        q.order_by(Movement.id.desc()).limit(1)
    )).scalars().first()


async def describe_recent(session: AsyncSession, mv: Movement) -> str:
    """Resumen compacto del último movimiento para el prompt del parser (una línea)."""
    payer = (await _payer_name(session, mv)).capitalize()
    other = await other_user(session, (await session.execute(
        select(User).where(User.id == mv.paid_by))).scalar_one())
    other_name = other.username.capitalize() if other else "el otro"
    if mv.type == "settlement":
        return (f"pago de saldo {payer}→{other_name} · "
                f"{mv.currency} {ar_number(mv.amount)}")
    parts = [
        mv.description or "gasto",
        f"{mv.currency} {ar_number(mv.amount)}",
        mv.city_name or "sin ciudad",
        f"pagó {payer}",
        split_label(mv.split, payer, other_name),
    ]
    cat = await _cat_name(session, mv)
    if cat:
        parts.append(f"categoría {cat}")
    return " · ".join(parts)


# Alias histórico: el folding vive en app/textnorm.py.
_fold = fold


def _score(mv: Movement, ref_tokens: set[str]) -> int:
    """La descripción pesa más que ciudad/raw: los hermanos de un batch comparten
    raw_message ('cena 40, taxi 12…') y empatarían solo por él."""
    desc = _fold(mv.description or "")
    rest = _fold(f"{mv.city_name or ''} {mv.raw_message or ''}")
    return sum(3 if t in desc else (1 if t in rest else 0) for t in ref_tokens)


async def find_candidates(session: AsyncSession, *, ref_last: bool, ref_text: str | None,
                          ref_date: date | None) -> list[Movement]:
    """Movimientos que matchean la referencia, mejor primero. Sin referencia => el último.

    'el museo de ayer' = cargado ayer: la referencia por fecha filtra por día de
    created_at (corte UTC — aceptable para un bot de dos personas en viaje)."""
    q = select(Movement).order_by(Movement.id.desc()).limit(_SEARCH_LIMIT)
    if ref_date is not None:
        q = (select(Movement).where(func.date(Movement.created_at) == ref_date.isoformat())
             .order_by(Movement.id.desc()).limit(_SEARCH_LIMIT))
    movements = (await session.execute(q)).scalars().all()
    if not movements:
        # La fecha del parser es una pista, no un filtro duro: si no hay nada
        # cargado ese día ("el museo de ayer" con la fecha mal adivinada),
        # reintentar la búsqueda sin fecha antes de dar el dead-end.
        if ref_date is not None:
            return await find_candidates(
                session, ref_last=ref_last, ref_text=ref_text, ref_date=None
            )
        return []

    # ref_text manda: si el mensaje nombra un movimiento ('el taxi'), el match
    # por texto va primero aunque el parser también haya marcado ref_last. El
    # último queda como fallback (ref_last o sin match usable).
    if ref_text:
        ref_tokens = {t for t in _fold(ref_text).split() if len(t) > 2}
        if ref_tokens:
            scored = [(m, _score(m, ref_tokens)) for m in movements]
            best = max(s for _, s in scored)
            if best > 0:
                return [m for m, s in scored if s == best]
            if ref_date is not None:
                # El texto no aparece en lo cargado ese día: probar sin fecha.
                return await find_candidates(
                    session, ref_last=ref_last, ref_text=ref_text, ref_date=None
                )
        if ref_last:
            return movements[:1]
        return []
    return movements[:1]


async def _payer_name(session, mv: Movement) -> str:
    u = (await session.execute(select(User).where(User.id == mv.paid_by))).scalar_one_or_none()
    return u.username if u else "?"


async def _cat_name(session, mv: Movement) -> str | None:
    if mv.category_id is None:
        return None
    return (await session.execute(
        select(Category.name).where(Category.id == mv.category_id)
    )).scalar_one_or_none()


async def apply_changes(session, mv: Movement, changes: dict, today: date,
                        username: str | None = None) -> list[tuple[str, str, str]]:
    """Aplica cambios a un movimiento con recálculo en cascada. Devuelve diffs (label, antes, después)."""
    diffs: list[tuple[str, str, str]] = []

    if "description" in changes:
        new_desc = normalize_description(
            changes["description"], await load_proper_nouns(session)
        )
        if new_desc != mv.description:
            diffs.append(("📝", mv.description or "—", new_desc))
            mv.description = new_desc

    if "category" in changes:
        old = await _cat_name(session, mv)
        if changes["category"] != old:
            diffs.append(("🏷️", cat_label(old) if old else "—", cat_label(changes["category"])))
            mv.category_id = await _category_id(session, changes["category"])

    if "paid_by" in changes:
        old_name = await _payer_name(session, mv)
        if changes["paid_by"] != old_name:
            new_payer = await user_by_username(session, changes["paid_by"])
            if new_payer is not None:
                diffs.append(("👤", f"Pagó {old_name.capitalize()}", f"Pagó {new_payer.username.capitalize()}"))
                mv.paid_by = new_payer.id
                # El dueño de un gasto individual no cambia por cambiar el
                # pagador: el split (relativo al pagador) se da vuelta para
                # conservarlo, salvo que el edit también pida otro reparto.
                if (mv.split in ("payer_only", "other_only")
                        and "only_user" not in changes and "split" not in changes):
                    mv.split = "other_only" if mv.split == "payer_only" else "payer_only"

    # only_user ('shared' | username) → split concreto contra el pagador EFECTIVO
    # (ya con new_paid_by aplicado): la aritmética relativa es del server.
    if "only_user" in changes:
        from app.llm.parser import split_for
        changes["split"] = split_for(
            None if changes["only_user"] == "shared" else changes["only_user"],
            await _payer_name(session, mv),
        )

    if "split" in changes and changes["split"] != mv.split:
        payer = await _payer_name(session, mv)
        other = await other_user(session, (await session.execute(
            select(User).where(User.id == mv.paid_by))).scalar_one())
        other_name = other.username.capitalize() if other else "el otro"
        diffs.append(("÷", split_label(mv.split, payer.capitalize(), other_name),
                      split_label(changes["split"], payer.capitalize(), other_name)))
        mv.split = changes["split"]

    # Ciudad explícita: se re-resuelve contra el itinerario (day-trip incluido,
    # usando la fecha nueva si también viene). Un edit de fecha SOLA no toca la
    # ciudad: "poné que se paga hoy" no debe arrastrar el gasto a otra parada.
    new_date = changes.get("date")
    date_changed = False
    if "city" in changes and mv.type != "settlement":
        slug, city, _cur = await resolve_place(
            session, new_date or today, changes["city"], username
        )
        if (slug, city) != (mv.stop_slug, mv.city_name):
            diffs.append(("📍", mv.city_name or "Sin ciudad", city or "Sin ciudad"))
            mv.stop_slug, mv.city_name = slug, city
            # Paridad con la captura (invariante 8): mover un gasto COMPARTIDO a
            # una parada con dueño lo hace de esa persona, igual que si hubiera
            # nacido ahí. Solo pisa el default: un split individual explícito —
            # sea de este mismo edit o el que ya tenía— se respeta.
            if (mv.split == "shared" and "only_user" not in changes
                    and "split" not in changes):
                payer = (await session.execute(
                    select(User).where(User.id == mv.paid_by)
                )).scalar_one_or_none()
                new_split = await owner_split(session, slug, payer, mv.split) if payer else mv.split
                if new_split != mv.split:
                    other = await other_user(session, payer)
                    other_name = other.username.capitalize() if other else "el otro"
                    diffs.append(("÷", split_label(mv.split, payer.username.capitalize(), other_name),
                                  split_label(new_split, payer.username.capitalize(), other_name)))
                    mv.split = new_split
    if new_date is not None and mv.type != "settlement" and new_date != mv.payment_date:
        diffs.append(("📅", fmt_date(mv.payment_date or mv.created_at.date()), fmt_date(new_date)))
        mv.payment_date = new_date
        mv.status = next_status_for_date(mv.status, new_date, today)
        date_changed = True

    # Cashback (kind, value) — None,None lo saca. Cambia el neto ⇒ recalcula USD.
    # El techo del fijo se valida contra el monto que va a quedar (el nuevo si el
    # mismo mensaje lo cambia): el parser no ve el movimiento, así que acá es el
    # único lugar donde "ponele 50 de cashback" a un gasto de 20 se puede frenar.
    cashback_changed = False
    if "cashback" in changes and mv.type != "settlement":
        target_amount = Decimal(changes.get("amount", mv.amount))
        new_kind, new_value = normalize_cashback(*changes["cashback"], target_amount)
        if (new_kind, new_value) != (mv.cashback_kind, mv.cashback_value):
            diffs.append(("💸", cashback_text(mv.cashback_kind, mv.cashback_value, mv.currency),
                          cashback_text(new_kind, new_value, mv.currency)))
            mv.cashback_kind, mv.cashback_value = new_kind, new_value
            cashback_changed = True

    # Monto/moneda → recalcular USD.
    money_changed = False
    if "amount" in changes and changes["amount"] != mv.amount:
        diffs.append(("💰", f"{mv.currency} {ar_number(mv.amount)}",
                      f"{mv.currency} {ar_number(changes['amount'])}"))
        mv.amount = changes["amount"]
        money_changed = True
    if "currency" in changes and changes["currency"] != mv.currency:
        diffs.append(("💱", mv.currency, changes["currency"]))
        mv.currency = changes["currency"]
        money_changed = True
    if money_changed or date_changed or cashback_changed:
        old_usd = mv.amount_usd
        net = net_amount(Decimal(mv.amount), mv.cashback_kind, mv.cashback_value)
        # Regla: TC de la fecha de pago, capeada a hoy. `reprice_movement` respeta
        # las tasas lockeadas (manual / awaiting) y no pisa una tasa buena con un
        # fallback del proveedor.
        mv.amount_usd, mv.fx_rate, mv.fx_source = await reprice_movement(
            session, mv, net, fx_reference_date(mv.payment_date, today)
        )
        # El efecto en USD del cambio, visible en la card (salvo gasto ya en USD,
        # donde la línea de monto lo dice igual).
        if mv.currency != "USD" and old_usd is not None and mv.amount_usd != old_usd:
            diffs.append(("💵", f"USD {ar_number(old_usd)}", f"USD {ar_number(mv.amount_usd)}"))

    await session.commit()
    return diffs


async def _pick_buttons(session, candidates, action: str, payload: dict, owner: str, question: str) -> BotReply:
    token = await create_pending(session, owner=owner, payload=payload, kind=action)
    buttons = []
    for mv in candidates[:3]:
        label = f"{(mv.description or mv.type)[:16]} · {mv.currency} {mv.amount:.0f} · {fmt_date(mv.created_at.date())}"
        buttons.append((f"{action}:{token}|{mv.id}", label[:20]))
    return buttons_reply(question, buttons)


async def handle_edit(session, user: User, wa_id: str, parsed, today: date,
                      text: str | None = None) -> BotReply:
    if not parsed.changes:
        # Se descartó algo por inválido (categoría inventada, un pagador que no
        # es ninguno de los dos): decir QUÉ, en vez del genérico "no sé qué
        # cambiar", que dejaba al usuario reescribiendo lo mismo.
        if parsed.rejected:
            cats = ", ".join((await session.execute(
                select(Category.name).order_by(Category.sort_order)
            )).scalars().all())
            return text_reply(
                f"{copy.H_HUH} No pude usar {' ni '.join(parsed.rejected)}.\n"
                f"Categorías válidas: _{cats}_."
            )
        # Sin cambios pero con un gasto fresco a la vista: la misma guía
        # contextual del dispatcher, con el gasto concreto y ejemplos.
        recent = await recent_movement(
            session, ttl_minutes=get_settings().edit_recent_ttl_minutes, created_by=user.id,
        )
        if recent is not None:
            return text_reply(copy.correction_hint(
                recent.description, await describe_recent(session, recent),
            ))
        return text_reply(
            f"{copy.H_HUH} Entendí que querés *editar*, pero no qué cambiar. "
            "Ej: _la cena de ayer fue 25_."
        )
    candidates = await find_candidates(
        session, ref_last=parsed.ref_last, ref_text=parsed.ref_text, ref_date=parsed.ref_date
    )
    if not candidates:
        return text_reply(f"{copy.H_WARN} No encontré ningún movimiento que matchee esa referencia.")
    if len(candidates) > 1:
        # Editar el TOTAL de un batch: si todos los matches son hermanos del
        # mismo batch, no hay ambigüedad — cualquiera representa al conjunto.
        if (parsed.changes.get("amount_is_total")
                and len({m.batch_key for m in candidates}) == 1
                and candidates[0].batch_key):
            return await apply_edit_to(session, user, candidates[0], parsed.changes, today)
        payload = {"changes": _serialize_changes(parsed.changes)}
        return await _pick_buttons(session, candidates, "edit_pick", payload, user.username, "¿Cuál querés editar?")
    reply = await apply_edit_to(session, user, candidates[0], parsed.changes, today)
    # Red determinística: el parser dijo "el último" (sin ref_text) pero el
    # último ya estaba así. Si el TEXTO del mensaje nombra otro movimiento
    # ('el taxi era compartido' con el helado como último), editar ese.
    if (reply.text and reply.text.startswith("Nada que cambiar")
            and not parsed.ref_text and text):
        alt = [m for m in await find_candidates(
            session, ref_last=False, ref_text=text, ref_date=parsed.ref_date
        ) if m.id != candidates[0].id]
        if len(alt) == 1:
            return await apply_edit_to(session, user, alt[0], parsed.changes, today)
    return reply


async def apply_edit_to(session, user: User, mv: Movement, changes: dict, today: date) -> BotReply:
    # "El total era 480" sobre un gasto en partes/cuotas: redistribuir el batch
    # entero en proporción, no editar un renglón suelto.
    warning = ""
    if changes.get("amount_is_total") and mv.batch_key and "amount" in changes:
        reply, reason = await _apply_batch_total(session, mv, changes["amount"], today)
        if reply is not None:
            return reply
        # No se pudo repartir: se edita el renglón suelto, pero DICIÉNDOLO. En
        # silencio, "el total era 480" dejaba un batch cuyo total no era 480.
        if reason:
            warning = f"\n{copy.H_WARN} {reason}"
    changes = {k: v for k, v in changes.items() if k != "amount_is_total"}
    diffs = await apply_changes(session, mv, changes, today, user.username)
    if not diffs:
        return text_reply("Nada que cambiar: ya estaba así. 👌" + warning)
    return text_reply(edit_card(mv, diffs) + warning)


async def _apply_batch_total(session, mv: Movement, new_total: Decimal,
                             today: date) -> tuple[BotReply | None, str | None]:
    """Re-escala todos los hermanos del batch a un total nuevo, conservando las
    proporciones (misma regla que expand_installments: la última fila absorbe el
    redondeo).

    Devuelve (reply, motivo). Con reply=None el edit cae al camino puntual de
    siempre y el motivo se le muestra al usuario: un batch en dos monedas no
    tiene un total único contra el cual repartir, y callarlo dejaba el conjunto
    sumando otra cosa que la pedida."""
    from app.bot.render import batch_total_card

    siblings = (await session.execute(
        select(Movement).where(Movement.batch_key == mv.batch_key).order_by(Movement.id)
    )).scalars().all()
    if len(siblings) < 2:
        return None, None
    if len({m.currency for m in siblings}) != 1:
        monedas = ", ".join(sorted({m.currency for m in siblings}))
        return None, (
            f"Ese gasto entró en varias monedas ({monedas}), así que no puedo "
            "repartir un total único: cambié solo esta parte. Corregí la otra aparte."
        )
    old_total = sum((Decimal(m.amount) for m in siblings), Decimal(0))
    if old_total <= 0 or new_total <= 0:
        return None, None
    if new_total == old_total:
        return None, None

    cent = Decimal("0.01")
    amounts = [
        (Decimal(m.amount) / old_total * new_total).quantize(cent, rounding=ROUND_HALF_UP)
        for m in siblings[:-1]
    ]
    remainder = new_total - sum(amounts)
    if remainder <= 0 or any(a <= 0 for a in amounts):
        return None, (
            f"Con un total de {ar_number(new_total)} alguna parte quedaba en cero o "
            "en negativo, así que cambié solo esta. Decime los montos de cada parte."
        )
    amounts.append(remainder)

    for m, amt in zip(siblings, amounts):
        m.amount = amt
        # Invariante 10: amount_usd sale SIEMPRE del neto. Las cuotas heredan el
        # cashback pct del gasto original, así que un batch con cashback es un
        # caso real, no teórico: repartir el bruto acá lo dejaba de descontar.
        net = net_amount(amt, m.cashback_kind, m.cashback_value)
        m.amount_usd, m.fx_rate, m.fx_source = await reprice_movement(
            session, m, net, fx_reference_date(m.payment_date, today)
        )
    await session.commit()
    return text_reply(batch_total_card(siblings, old_total, new_total)), None


async def handle_delete(session, user: User, wa_id: str, parsed, today: date) -> BotReply:
    candidates = await find_candidates(
        session, ref_last=parsed.ref_last, ref_text=parsed.ref_text, ref_date=parsed.ref_date
    )
    if not candidates:
        return text_reply(f"{copy.H_WARN} No encontré ningún movimiento que matchee esa referencia.")
    if len(candidates) > 1:
        return await _pick_buttons(session, candidates, "del_pick", {}, user.username, "¿Cuál querés borrar?")
    mv = candidates[0]
    payer = await _payer_name(session, mv)
    cat = await _cat_name(session, mv)
    token = await create_pending(
        session, owner=user.username, payload={"ids": [mv.id]}, kind="del_confirm",
    )
    return buttons_reply(
        f"{copy.H_WARN} ¿Borrar este movimiento? Es irreversible.\n{movement_summary(mv, cat, payer)}",
        [(f"del_confirm:{token}", "Borrar 🗑️"), (f"del_cancel:{token}", "Cancelar")],
    )


# --- serialización de changes para pendings (edit multi-candidato) ---

def _serialize_changes(changes: dict) -> dict:
    out = {}
    for k, v in changes.items():
        out[k] = v.isoformat() if isinstance(v, date) else str(v)
    return out


def _deserialize_changes(raw: dict) -> dict:
    from decimal import Decimal
    out = dict(raw)
    if "amount" in out:
        out["amount"] = Decimal(out["amount"])
    if "date" in out:
        out["date"] = date.fromisoformat(out["date"])
    return out


async def apply_edit_pick(session, user: User, token: str, movement_id: int, today: date) -> BotReply:
    data = await load_pending(session, token, owner=user.username, kind="edit_pick")
    if data is None:
        return text_reply("⚠️ Expiró: ese pending ya no está disponible.")
    mv = (await session.execute(select(Movement).where(Movement.id == movement_id))).scalar_one_or_none()
    if mv is None:
        return text_reply("⚠️ No encontrado: ese movimiento ya no existe.")
    reply = await apply_edit_to(session, user, mv, _deserialize_changes(data["changes"]), today)
    await close_pending(session, token)
    return reply


async def apply_delete_pick(session, user: User, token: str, movement_id: int) -> BotReply:
    data = await load_pending(session, token, owner=user.username, kind="del_pick")
    if data is None:
        return text_reply("⚠️ Expiró: ese pending ya no está disponible.")
    mv = (await session.execute(select(Movement).where(Movement.id == movement_id))).scalar_one_or_none()
    await close_pending(session, token)
    if mv is None:
        return text_reply("⚠️ No encontrado: ese movimiento ya no existe.")
    payer = await _payer_name(session, mv)
    cat = await _cat_name(session, mv)
    confirm_token = await create_pending(
        session, owner=user.username, payload={"ids": [mv.id]}, kind="del_confirm",
    )
    return buttons_reply(
        f"{copy.H_WARN} ¿Borrar este movimiento? Es irreversible.\n{movement_summary(mv, cat, payer)}",
        [(f"del_confirm:{confirm_token}", "Borrar 🗑️"), (f"del_cancel:{confirm_token}", "Cancelar")],
    )
