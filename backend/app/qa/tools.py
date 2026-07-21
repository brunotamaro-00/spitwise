"""Herramientas del agente Q&A: consultas puras sobre la DB + acciones acotadas.

Los handlers levantan ValueError ante parámetros inválidos; el loop de chat
se lo devuelve al modelo como tool_result con error para que se corrija.

Acciones: edit_movement aplica el mismo flujo que el intent 'edit' (apply_changes,
con recálculo de ciudad/FX). delete_movements NUNCA borra: crea un pending y deja
lista una respuesta con botones de confirmación en el ActionContext — el borrado
real ocurre solo cuando el usuario toca el botón (interactive.py).
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.balance import UNSETTLED, compute_balance
from app.bot.render import BotReply
from app.db.models import Category, Movement, Stop, User
from app.llm.chat import ToolSpec
from app.spend import user_share
from app.trip_time import day_in_tz

_MAX_DELETE_IDS = 5


@dataclass
class ActionContext:
    """Canal lateral de las herramientas de acción hacia el handler: si una
    acción prepara una respuesta interactiva (botones), va acá y reemplaza
    al texto final del modelo."""

    reply: BotReply | None = None

_CENT = Decimal("0.01")


def _fold(s) -> str:
    return (s or "").strip().casefold()


def _money(d: Decimal) -> str:
    return str(Decimal(d).quantize(_CENT))


def _to_date(v, field: str) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(str(v))
    except ValueError:
        raise ValueError(f"{field} inválida: {v!r}, usar YYYY-MM-DD")


def _created_day(m: Movement, tz_name: str | None) -> date:
    """Día de carga del movimiento en la tz del viaje: el único eje temporal que queda."""
    return day_in_tz(m.created_at, tz_name)


async def _load_context(session: AsyncSession, cache: dict | None = None):
    """Movimientos + stops + categorías. `cache` (por turno del agente) evita
    recargar toda la DB en cada tool call del mismo turno."""
    if cache is not None and "ctx" in cache:
        return cache["ctx"]
    movements = (await session.execute(
        select(Movement).where(Movement.type == "expense").order_by(Movement.created_at, Movement.id)
    )).scalars().all()
    stops = {s.slug: s for s in (await session.execute(select(Stop))).scalars().all()}
    cats = {c.id: c.name for c in (await session.execute(select(Category))).scalars().all()}
    out = (movements, stops, cats)
    if cache is not None:
        cache["ctx"] = out
    return out


def _filter(movements, stops, cats, *, tz_name=None, date_from=None, date_to=None, cities=None,
            countries=None, categories=None, currency=None):
    d_from = _to_date(date_from, "date_from")
    d_to = _to_date(date_to, "date_to")
    city_set = {_fold(c) for c in (cities or [])}
    country_set = {_fold(c) for c in (countries or [])}
    cat_set = {_fold(c) for c in (categories or [])}
    curr = str(currency).strip().upper() if currency else None

    out = []
    for m in movements:
        day = _created_day(m, tz_name) if (d_from or d_to) else None
        if d_from and day < d_from:
            continue
        if d_to and day > d_to:
            continue
        if city_set and _fold(m.city_name) not in city_set and _fold(m.stop_slug) not in city_set:
            continue
        if country_set:
            stop = stops.get(m.stop_slug) if m.stop_slug else None
            if _fold(stop.country if stop else None) not in country_set:
                continue
        if cat_set and _fold(cats.get(m.category_id)) not in cat_set:
            continue
        if curr and (m.currency or "").upper() != curr:
            continue
        out.append(m)
    return out


def _resolve_person(users: list[User], name: str | None, asker: User) -> User:
    if not name:
        return asker
    wanted = _fold(name)
    for u in users:
        if _fold(u.username) == wanted:
            return u
    raise ValueError(f"persona desconocida: {name!r}; válidas: {[u.username for u in users]}")


async def aggregate_expenses(session: AsyncSession, users: list[User], asker: User, *,
                             tz_name=None, person=None, attribution="share", date_from=None,
                             date_to=None, cities=None, countries=None, categories=None,
                             currency=None, group_by="none", cache=None) -> dict:
    movements, stops, cats = await _load_context(session, cache)
    rows_src = _filter(movements, stops, cats, tz_name=tz_name, date_from=date_from,
                       date_to=date_to, cities=cities, countries=countries,
                       categories=categories, currency=currency)
    who = _resolve_person(users, person, asker)

    def amount_for(m, uid: int) -> Decimal:
        if attribution == "paid":
            return m.amount_usd if m.paid_by == uid else Decimal("0")
        if attribution == "total":
            return m.amount_usd
        return user_share(m, uid)

    def key_for(m) -> str:
        if group_by == "day":
            return _created_day(m, tz_name).isoformat()
        if group_by == "city":
            return m.city_name or "Sin ciudad"
        if group_by == "country":
            stop = stops.get(m.stop_slug) if m.stop_slug else None
            return (stop.country if stop else None) or "Sin país"
        if group_by == "category":
            return cats.get(m.category_id) or "Sin categoría"
        return "total"

    grouped: dict[str, dict] = {}
    if group_by == "person":
        for u in users:
            total = Decimal("0")
            count = 0
            for m in rows_src:
                # Por persona, "total" no aplica: se reparte como consumo.
                amt = amount_for(m, u.id) if attribution == "paid" else user_share(m, u.id)
                if amt:
                    total += amt
                    count += 1
            grouped[u.username] = {"total": total, "count": count}
    else:
        for m in rows_src:
            amt = amount_for(m, who.id)
            if attribution != "total" and not amt:
                continue
            g = grouped.setdefault(key_for(m), {"total": Decimal("0"), "count": 0})
            g["total"] += amt
            g["count"] += 1

    items = sorted(grouped.items(), key=lambda kv: kv[0]) if group_by == "day" \
        else sorted(grouped.items(), key=lambda kv: kv[1]["total"], reverse=True)
    return {
        "rows": [{"key": k, "total_usd": _money(v["total"]), "count": v["count"]} for k, v in items],
        "person": None if attribution == "total" or group_by == "person" else who.username,
        "attribution": attribution,
        "note": "montos en USD",
    }


def _app_link(cats: dict, *, date_from, date_to, cities, categories):
    """Deep-link best-effort a /movimientos desde los filtros de la consulta.
    Mapea 1 ciudad / 1 categoría (nombre→id) + rango de fechas; el resto se omite."""
    from app.bot import copy
    cat_id = None
    if categories and len(categories) == 1:
        inv = {(name or "").casefold(): cid for cid, name in cats.items()}
        cat_id = inv.get(str(categories[0]).strip().casefold())
    one_city = cities[0] if cities and len(cities) == 1 else None
    return copy.link_movements(city=one_city, category_id=cat_id,
                               date_from=date_from, date_to=date_to)


async def list_movements(session: AsyncSession, users: list[User], *, tz_name=None,
                         date_from=None, date_to=None, cities=None, countries=None,
                         categories=None, currency=None, limit=10, cache=None) -> dict:
    movements, stops, cats = await _load_context(session, cache)
    rows_src = _filter(movements, stops, cats, tz_name=tz_name, date_from=date_from,
                       date_to=date_to, cities=cities, countries=countries,
                       categories=categories, currency=currency)
    usernames = {u.id: u.username for u in users}
    limit = max(1, min(int(limit or 10), 50))
    newest_first = list(reversed(rows_src))
    rows = []
    for m in newest_first[:limit]:
        stop = stops.get(m.stop_slug) if m.stop_slug else None
        rows.append({
            "id": m.id,
            "date": _created_day(m, tz_name).isoformat(),
            "description": m.description,
            "category": cats.get(m.category_id),
            "city": m.city_name,
            "country": stop.country if stop else None,
            "amount": _money(m.amount),
            "currency": m.currency,
            "amount_usd": _money(m.amount_usd),
            "paid_by": usernames.get(m.paid_by),
            "split": m.split,
            "status": m.status,
            "payment_date": m.payment_date.isoformat() if m.payment_date else None,
        })
    truncated = len(rows_src) > limit
    out = {"rows": rows, "truncated": truncated, "total_matches": len(rows_src)}
    # Si hay más de las que mostramos, ofrecé el link a la app en vez de volcar todo.
    if truncated:
        link = _app_link(cats, date_from=date_from, date_to=date_to,
                         cities=cities, categories=categories)
        if link:
            out["app_link"] = link
    return out


async def get_balance(session: AsyncSession, users: list[User]) -> dict:
    if len(users) != 2:
        raise ValueError("el balance requiere exactamente 2 usuarios")
    movements = (await session.execute(select(Movement))).scalars().all()
    bal = compute_balance(movements, users[0].id, users[1].id)
    usernames = {u.id: u.username for u in users}
    pending = [m for m in movements if m.type == "expense" and m.status in UNSETTLED]
    return {
        "debtor": usernames.get(bal.debtor_id),
        "creditor": usernames.get(bal.creditor_id),
        "amount_usd": _money(bal.amount_usd),
        "pending_excluded_count": len(pending),
        "pending_excluded_usd": _money(sum(
            (m.amount_usd for m in pending if m.amount_usd is not None), Decimal(0)
        )),
        "note": ("debtor le debe amount_usd a creditor; si ambos son null están a mano. "
                 "Los gastos pending (fecha de pago futura) y los que esperan "
                 "confirmación NO cuentan en este saldo hasta que se confirmen."),
    }


async def get_itinerary(session: AsyncSession) -> dict:
    stops = (await session.execute(
        select(Stop).where(Stop.is_candidate.is_(False)).order_by(Stop.order)
    )).scalars().all()
    rows = []
    for s in stops:
        days = None
        if s.arrival_date and s.departure_date:
            days = (s.departure_date - s.arrival_date).days
        rows.append({
            "name": s.name, "slug": s.slug, "country": s.country,
            "arrival_date": s.arrival_date.isoformat() if s.arrival_date else None,
            "departure_date": s.departure_date.isoformat() if s.departure_date else None,
            "days": days, "currency_code": s.currency_code, "is_transit": s.is_transit,
        })
    return {"stops": rows, "note": "days = noches en la parada (departure - arrival)"}


async def edit_movement(session: AsyncSession, users: list[User], today: date,
                        asker: User | None = None, *, movement_id, **new_fields) -> dict:
    """Aplica cambios a un movimiento reutilizando el flujo del intent 'edit'
    (normalización + apply_changes, con recálculo de ciudad/FX)."""
    from app.bot.editor import apply_changes
    from app.llm.parser import normalize_changes

    mv = (await session.execute(
        select(Movement).where(Movement.id == int(movement_id))
    )).scalar_one_or_none()
    if mv is None:
        raise ValueError(f"no existe un movimiento con id {movement_id}")

    cat_names = list((await session.execute(
        select(Category.name).order_by(Category.sort_order)
    )).scalars().all())
    raw = {f"new_{k}": v for k, v in new_fields.items() if v is not None}
    if raw.get("new_category"):
        wanted = str(raw["new_category"]).strip().casefold()
        match = next((c for c in cat_names if c.casefold() == wanted), None)
        if match is None:
            raise ValueError(f"categoría inválida: {raw['new_category']!r}; válidas: {cat_names}")
        raw["new_category"] = match
    changes = normalize_changes(raw, cat_names, [u.username for u in users])
    if not changes:
        raise ValueError(
            "ningún cambio válido; campos: amount, currency (ISO), date (YYYY-MM-DD), "
            "city, category, description, only_user ('shared' o un username), paid_by"
        )
    diffs = await apply_changes(session, mv, changes, today,
                                asker.username if asker else None)
    return {
        "edited_id": mv.id,
        "changes": [{"campo": label, "antes": before, "despues": after}
                    for label, before, after in diffs],
        "note": "cambios aplicados y guardados",
    }


async def delete_movements(session: AsyncSession, users: list[User], asker: User,
                           ctx: ActionContext, *, movement_ids) -> dict:
    """Prepara (no ejecuta) el borrado: pending + tarjeta con botones de
    confirmación. El borrado real pasa en interactive.py al tocar el botón."""
    from app.bot.pending import create_pending
    from app.bot.render import buttons_reply, movement_summary

    ids = [int(i) for i in (movement_ids or [])]
    if not ids or len(ids) > _MAX_DELETE_IDS:
        raise ValueError(f"pasá entre 1 y {_MAX_DELETE_IDS} ids de movimientos")
    movements = (await session.execute(
        select(Movement).where(Movement.id.in_(ids))
    )).scalars().all()
    missing = [i for i in ids if i not in {m.id for m in movements}]
    if missing:
        raise ValueError(f"no existen movimientos con id {missing}")

    usernames = {u.id: u.username for u in users}
    cats = {c.id: c.name for c in (await session.execute(select(Category))).scalars().all()}
    lines = "\n".join(
        f"· {movement_summary(m, cats.get(m.category_id), usernames.get(m.paid_by, '?'))}"
        for m in movements
    )
    token = await create_pending(session, owner=asker.username, payload={"ids": ids}, kind="qa_del")
    n = len(ids)
    head = ("⚠️ ¿Borrar este movimiento? Es irreversible." if n == 1
            else f"⚠️ ¿Borrar estos {n} movimientos? Es irreversible.")
    label = "Borrar 🗑️" if n == 1 else f"Borrar los {n} 🗑️"
    ctx.reply = buttons_reply(f"{head}\n{lines}",
                              [(f"qa_del:{token}", label), ("del_cancel:0", "Cancelar")])
    return {
        "status": "confirmacion_pendiente",
        "note": ("El usuario ya ve la tarjeta con los botones de confirmación; "
                 "tu texto final NO se le envía."),
    }


_FILTER_PROPS = {
    "date_from": {"type": "string",
                  "description": "Fecha de carga mínima inclusive, YYYY-MM-DD (cuándo se registró el gasto)."},
    "date_to": {"type": "string",
                "description": "Fecha de carga máxima inclusive, YYYY-MM-DD (cuándo se registró el gasto)."},
    "cities": {"type": "array", "items": {"type": "string"},
               "description": "Ciudades (nombre o slug del itinerario)."},
    "countries": {"type": "array", "items": {"type": "string"},
                  "description": "Países tal como figuran en el itinerario (get_itinerary los lista)."},
    "categories": {"type": "array", "items": {"type": "string"},
                   "description": "Nombres exactos de categoría."},
    "currency": {"type": "string", "description": "Moneda ORIGINAL del gasto (ISO 4217, ej: EUR)."},
}


def build_tools(session: AsyncSession, users: list[User], asker: User, *,
                today: date, ctx: ActionContext, tz_name: str | None = None) -> list[ToolSpec]:
    usernames = [u.username for u in users]
    cache: dict = {}  # contexto de DB compartido entre tool calls del turno

    async def _aggregate(**kw):
        return await aggregate_expenses(session, users, asker, tz_name=tz_name,
                                        cache=cache, **kw)

    async def _list(**kw):
        return await list_movements(session, users, tz_name=tz_name, cache=cache, **kw)

    async def _balance(**kw):
        return await get_balance(session, users)

    async def _itinerary(**kw):
        return await get_itinerary(session)

    async def _edit(**kw):
        return await edit_movement(session, users, today, asker, **kw)

    async def _delete(**kw):
        return await delete_movements(session, users, asker, ctx, **kw)

    return [
        ToolSpec(
            name="aggregate_expenses",
            description=(
                "Suma gastos del viaje (en USD) con filtros y agrupación. Es la herramienta "
                "principal para '¿cuánto gastamos/gastó/pagó...?'. Devuelve filas {key, total_usd, count}."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "enum": usernames,
                               "description": "Persona. Si se omite, es quien pregunta."},
                    "attribution": {
                        "type": "string", "enum": ["share", "paid", "total"],
                        "description": ("share (default) = consumo de la persona: compartidos mitad y mitad, "
                                        "individuales enteros — es lo que significa 'cuánto gastó'; "
                                        "paid = plata que puso de bolsillo ('cuánto pagó'); "
                                        "total = gasto total del viaje entre los dos (ignora person)."),
                    },
                    **_FILTER_PROPS,
                    "group_by": {"type": "string",
                                 "enum": ["none", "day", "city", "country", "category", "person"],
                                 "description": "Cómo agrupar las filas del resultado. Default: none (un total)."},
                },
                "additionalProperties": False,
            },
            handler=_aggregate,
        ),
        ToolSpec(
            name="list_movements",
            description=("Lista el detalle de gastos (más recientes primero) con los mismos filtros "
                         "que aggregate_expenses. Para 'dame el detalle', 'qué gastos hubo en...'. "
                         "Mostrá como máximo 10; si 'truncated' es true, cerrá con el 'app_link' que "
                         "devuelve (link a la app) en vez de listar todo."),
            input_schema={
                "type": "object",
                "properties": {
                    **_FILTER_PROPS,
                    "limit": {"type": "integer", "description": "Máximo de filas (default 10, tope 50)."},
                },
                "additionalProperties": False,
            },
            handler=_list,
        ),
        ToolSpec(
            name="get_balance",
            description="Saldo entre las dos personas: quién le debe cuánto a quién (USD), ya neteado con pagos de saldo.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            handler=_balance,
        ),
        ToolSpec(
            name="get_itinerary",
            description=("Itinerario del viaje: paradas con ciudad, país, fechas y días. Usalo para "
                         "resolver países/fechas y para promedios por día (días del itinerario, no días con gastos)."),
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            handler=_itinerary,
        ),
        ToolSpec(
            name="edit_movement",
            description=("Edita un movimiento YA guardado (los cambios se aplican al instante). "
                         "Usá el id que devuelve list_movements (o el del snapshot de datos). "
                         "'date' cambia la fecha de pago (futura => queda pendiente) sin tocar "
                         "la ciudad; para mover de ciudad usá 'city'."),
            input_schema={
                "type": "object",
                "properties": {
                    "movement_id": {"type": "integer", "description": "id del movimiento (de list_movements)."},
                    "amount": {"type": "string", "description": "Nuevo monto (decimal como string)."},
                    "currency": {"type": "string", "description": "Nueva moneda ISO 4217."},
                    "date": {"type": "string",
                             "description": "Nueva fecha de pago YYYY-MM-DD (futura => pendiente)."},
                    "city": {"type": "string", "description": "Nueva ciudad."},
                    "category": {"type": "string", "description": "Nueva categoría (nombre de la lista)."},
                    "description": {"type": "string", "description": "Nueva descripción corta."},
                    "only_user": {"type": "string", "enum": ["shared", *usernames],
                                  "description": ("De quién es el gasto: 'shared' = compartido 50/50; "
                                                  "un username = solo de esa persona (el sistema calcula "
                                                  "el reparto contra quien pagó).")},
                    "paid_by": {"type": "string", "enum": usernames, "description": "Nuevo pagador."},
                },
                "required": ["movement_id"],
                "additionalProperties": False,
            },
            handler=_edit,
        ),
        ToolSpec(
            name="delete_movements",
            description=("Prepara el borrado de 1 a 5 movimientos. NO borra directo: le muestra al "
                         "usuario una tarjeta de confirmación con botones y el borrado ocurre solo si "
                         "confirma. Usala siempre que pidan borrar/eliminar; nunca digas que vas a "
                         "borrar sin llamarla."),
            input_schema={
                "type": "object",
                "properties": {
                    "movement_ids": {"type": "array", "items": {"type": "integer"},
                                     "description": "ids de los movimientos a borrar (de list_movements)."},
                },
                "required": ["movement_ids"],
                "additionalProperties": False,
            },
            handler=_delete,
        ),
    ]
