"""Herramientas read-only del agente Q&A: funciones puras sobre la DB.

Los handlers levantan ValueError ante parámetros inválidos; el loop de chat
se lo devuelve al modelo como tool_result con error para que se corrija.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.balance import compute_balance
from app.db.models import Category, Movement, Stop, User
from app.llm.chat import ToolSpec
from app.spend import user_share

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


async def _load_context(session: AsyncSession):
    movements = (await session.execute(
        select(Movement).where(Movement.type == "expense").order_by(Movement.movement_date, Movement.id)
    )).scalars().all()
    stops = {s.slug: s for s in (await session.execute(select(Stop))).scalars().all()}
    cats = {c.id: c.name for c in (await session.execute(select(Category))).scalars().all()}
    return movements, stops, cats


def _filter(movements, stops, cats, *, date_from=None, date_to=None, cities=None,
            countries=None, categories=None, currency=None):
    d_from = _to_date(date_from, "date_from")
    d_to = _to_date(date_to, "date_to")
    city_set = {_fold(c) for c in (cities or [])}
    country_set = {_fold(c) for c in (countries or [])}
    cat_set = {_fold(c) for c in (categories or [])}
    curr = str(currency).strip().upper() if currency else None

    out = []
    for m in movements:
        if d_from and m.movement_date < d_from:
            continue
        if d_to and m.movement_date > d_to:
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
                             person=None, attribution="share", date_from=None, date_to=None,
                             cities=None, countries=None, categories=None, currency=None,
                             group_by="none") -> dict:
    movements, stops, cats = await _load_context(session)
    rows_src = _filter(movements, stops, cats, date_from=date_from, date_to=date_to,
                       cities=cities, countries=countries, categories=categories, currency=currency)
    who = _resolve_person(users, person, asker)

    def amount_for(m, uid: int) -> Decimal:
        if attribution == "paid":
            return m.amount_usd if m.paid_by == uid else Decimal("0")
        if attribution == "total":
            return m.amount_usd
        return user_share(m, uid)

    def key_for(m) -> str:
        if group_by == "day":
            return m.movement_date.isoformat()
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


async def list_movements(session: AsyncSession, users: list[User], *, date_from=None, date_to=None,
                         cities=None, countries=None, categories=None, currency=None,
                         limit=20) -> dict:
    movements, stops, cats = await _load_context(session)
    rows_src = _filter(movements, stops, cats, date_from=date_from, date_to=date_to,
                       cities=cities, countries=countries, categories=categories, currency=currency)
    usernames = {u.id: u.username for u in users}
    limit = max(1, min(int(limit or 20), 50))
    newest_first = list(reversed(rows_src))
    rows = []
    for m in newest_first[:limit]:
        stop = stops.get(m.stop_slug) if m.stop_slug else None
        rows.append({
            "date": m.movement_date.isoformat(),
            "description": m.description,
            "category": cats.get(m.category_id),
            "city": m.city_name,
            "country": stop.country if stop else None,
            "amount": _money(m.amount),
            "currency": m.currency,
            "amount_usd": _money(m.amount_usd),
            "paid_by": usernames.get(m.paid_by),
            "split": m.split,
        })
    return {"rows": rows, "truncated": len(rows_src) > limit, "total_matches": len(rows_src)}


async def get_balance(session: AsyncSession, users: list[User]) -> dict:
    if len(users) != 2:
        raise ValueError("el balance requiere exactamente 2 usuarios")
    movements = (await session.execute(select(Movement))).scalars().all()
    bal = compute_balance(movements, users[0].id, users[1].id)
    usernames = {u.id: u.username for u in users}
    return {
        "debtor": usernames.get(bal.debtor_id),
        "creditor": usernames.get(bal.creditor_id),
        "amount_usd": _money(bal.amount_usd),
        "note": "debtor le debe amount_usd a creditor; si ambos son null están a mano",
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


_FILTER_PROPS = {
    "date_from": {"type": "string", "description": "Fecha mínima inclusive, YYYY-MM-DD."},
    "date_to": {"type": "string", "description": "Fecha máxima inclusive, YYYY-MM-DD."},
    "cities": {"type": "array", "items": {"type": "string"},
               "description": "Ciudades (nombre o slug del itinerario)."},
    "countries": {"type": "array", "items": {"type": "string"},
                  "description": "Países tal como figuran en el itinerario (get_itinerary los lista)."},
    "categories": {"type": "array", "items": {"type": "string"},
                   "description": "Nombres exactos de categoría."},
    "currency": {"type": "string", "description": "Moneda ORIGINAL del gasto (ISO 4217, ej: EUR)."},
}


def build_tools(session: AsyncSession, users: list[User], asker: User) -> list[ToolSpec]:
    usernames = [u.username for u in users]

    async def _aggregate(**kw):
        return await aggregate_expenses(session, users, asker, **kw)

    async def _list(**kw):
        return await list_movements(session, users, **kw)

    async def _balance(**kw):
        return await get_balance(session, users)

    async def _itinerary(**kw):
        return await get_itinerary(session)

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
                         "que aggregate_expenses. Para 'dame el detalle', 'qué gastos hubo en...'."),
            input_schema={
                "type": "object",
                "properties": {
                    **_FILTER_PROPS,
                    "limit": {"type": "integer", "description": "Máximo de filas (default 20, tope 50)."},
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
    ]
