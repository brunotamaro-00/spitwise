"""Analítica por ciudad para el tab "Ciudades".

Todos los endpoints son *personales*: reflejan la parte del usuario logueado
(`user_share`), igual que el resto del dashboard. Aceptan `slugs` (repetible)
para filtrar a 1+ ciudades; sin `slugs` = todas las ciudades.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics import itinerary_dates
from app.api.auth import get_current_user
from app.bot.active_stop import visible_stops
from app.api.schemas import (
    CategorySpendOut,
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
    session: AsyncSession, slugs: list[str] | None
) -> list[Movement]:
    stmt = select(Movement).where(_EXPENSE)
    if slugs:
        stmt = stmt.where(Movement.stop_slug.in_(slugs))
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
    return len(itinerary_dates(stops))


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
    stmt = stmt.order_by(Movement.created_at.desc(), Movement.id.desc())
    return list((await session.execute(stmt)).scalars().all())
