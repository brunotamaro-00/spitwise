"""Analítica por ciudad para el tab "Ciudades".

Todos los endpoints son *personales*: reflejan la parte del usuario logueado
(`user_share`), igual que el resto del dashboard. Aceptan `slugs` (repetible)
para filtrar a 1+ ciudades; sin `slugs` = todas las ciudades.
"""

from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.bot.active_stop import visible_stops
from app.api.schemas import (
    CategorySpendOut,
    CityBreakdownOut,
    CityDailyOut,
    CitySummaryOut,
    MovementOut,
)
from app.db.engine import get_session
from app.db.models import Category, Movement, Stop, User
from app.spend import user_share

router = APIRouter(prefix="/dashboard/city", tags=["city-analytics"])
_EXPENSE = Movement.type == "expense"


def _money(v) -> str:
    return f"{Decimal(str(v)):.2f}"


async def _expenses_for(
    session: AsyncSession, slugs: list[str] | None, *, only_cities: bool = False
) -> list[Movement]:
    stmt = select(Movement).where(_EXPENSE)
    if slugs:
        stmt = stmt.where(Movement.stop_slug.in_(slugs))
    elif only_cities:
        # Sin filtro explícito, excluir los gastos generales (sin ciudad).
        stmt = stmt.where(Movement.stop_slug.is_not(None))
    return list((await session.execute(stmt)).scalars().all())


async def _itinerary_days(
    session: AsyncSession, slugs: list[str] | None, username: str | None = None
) -> int:
    """Días de estadía según el itinerario de Andiamo. Es la base del promedio
    por día: refleja los días del viaje, no los días con gastos.

    Cuenta días **distintos**, no la suma de duraciones: hay paradas que ocurren
    a la vez (Katia en Pititas mientras Bruno está en Portugal) y sumarlas
    contaría dos veces el mismo día del viaje.

    Sin filtro de ciudades, el itinerario es el del usuario: a Katia no le suma
    Portugal, porque en ese tramo ella está en Pititas.
    """
    if slugs:
        # Drill-down explícito: los días son los de las ciudades pedidas, aunque
        # sean del otro (Bruno puede ver Pititas si pagó algo de ese tramo).
        stops = (
            await session.execute(select(Stop).where(Stop.slug.in_(slugs)))
        ).scalars().all()
    else:
        stops = [
            s for s in await visible_stops(session, username)
            if not s.is_candidate and not s.is_archived
        ]

    days: set[date] = set()
    for s in stops:
        if not (s.arrival_date and s.departure_date):
            continue
        d = s.arrival_date
        while d < s.departure_date:  # departure exclusivo: noches, no fechas
            days.add(d)
            d += timedelta(days=1)
    return len(days)


@router.get("/summary", response_model=CitySummaryOut)
async def city_summary(
    slugs: list[str] | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CitySummaryOut:
    total = Decimal("0")
    count = 0
    for m in await _expenses_for(session, slugs):
        share = user_share(m, user.id)
        if share <= 0:
            continue
        total += share
        count += 1
    # Días del itinerario (Andiamo), no días con gastos cargados.
    n_days = await _itinerary_days(session, slugs, user.username)
    avg = total / n_days if n_days else Decimal("0")

    arrival = departure = None
    if slugs and len(slugs) == 1:
        stop = (
            await session.execute(select(Stop).where(Stop.slug == slugs[0]))
        ).scalar_one_or_none()
        if stop is not None:
            arrival, departure = stop.arrival_date, stop.departure_date

    return CitySummaryOut(
        total_usd=_money(total),
        movement_count=count,
        days=n_days,
        avg_per_day_usd=_money(avg),
        arrival_date=arrival,
        departure_date=departure,
    )


@router.get("/by-category", response_model=list[CategorySpendOut])
async def city_by_category(
    slugs: list[str] | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CategorySpendOut]:
    cats = {c.id: c for c in (await session.execute(select(Category))).scalars().all()}
    agg: dict[int, Decimal] = {}
    for m in await _expenses_for(session, slugs):
        if m.category_id is None:
            continue
        share = user_share(m, user.id)
        if share <= 0:
            continue
        agg[m.category_id] = agg.get(m.category_id, Decimal("0")) + share
    items = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)
    return [
        CategorySpendOut(
            category_id=cid,
            name=cats[cid].name if cid in cats else None,
            icon=cats[cid].icon if cid in cats else None,
            total_usd=_money(v),
        )
        for cid, v in items
    ]


@router.get("/daily", response_model=list[CityDailyOut])
async def city_daily(
    slugs: list[str] | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CityDailyOut]:
    """Gasto por día (no acumulado) para las ciudades filtradas.

    Excluye siempre los gastos generales (sin ciudad): suman al total del viaje
    pero no son gasto "diario en destino", que es lo que muestra este gráfico.
    """
    by_date: dict[date, Decimal] = {}
    for m in await _expenses_for(session, slugs, only_cities=True):
        share = user_share(m, user.id)
        if share <= 0:
            continue
        by_date[m.movement_date] = by_date.get(m.movement_date, Decimal("0")) + share
    return [CityDailyOut(date=d, total_usd=_money(by_date[d])) for d in sorted(by_date)]


@router.get("/breakdown", response_model=list[CityBreakdownOut])
async def city_breakdown(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CityBreakdownOut]:
    """Una fila por ciudad (todas), ordenada por el itinerario (Stop.order).
    Archivadas después de las activas; sin stop asociado ("Sin ciudad") al final."""
    stops = (await session.execute(select(Stop))).scalars().all()
    flags = {s.slug: s.country_flag for s in stops}
    order = {s.slug: s.order for s in stops}
    archived = {s.slug: s.is_archived for s in stops}
    agg: dict[tuple[str | None, str | None], dict] = {}
    for m in await _expenses_for(session, None):
        share = user_share(m, user.id)
        if share <= 0:
            continue
        key = (m.stop_slug, m.city_name)
        row = agg.setdefault(
            key, {"total": Decimal("0"), "count": 0, "days": set()}
        )
        row["total"] += share
        row["count"] += 1
        row["days"].add(m.movement_date)
    _LAST = 10**9

    def _sort_key(kv):
        slug = kv[0][0]
        if slug is None:
            return (2, _LAST)
        return (1 if archived.get(slug) else 0, order.get(slug, _LAST))

    items = sorted(agg.items(), key=_sort_key)
    return [
        CityBreakdownOut(
            stop_slug=slug,
            city_name=name,
            country_flag=flags.get(slug) if slug else None,
            total_usd=_money(row["total"]),
            movement_count=row["count"],
            days=len(row["days"]),
            is_archived=archived.get(slug) if slug else None,
        )
        for (slug, name), row in items
    ]


@router.get("/movements", response_model=list[MovementOut])
async def city_movements(
    slugs: list[str] | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Movement]:
    """Detalle de movimientos de las ciudades filtradas (más recientes primero)."""
    stmt = select(Movement).where(_EXPENSE)
    if slugs:
        stmt = stmt.where(Movement.stop_slug.in_(slugs))
    stmt = stmt.order_by(Movement.movement_date.desc(), Movement.id.desc())
    return list((await session.execute(stmt)).scalars().all())
