from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
import secrets
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.andiamo import force_sync_soon, sync_stops
from app.api.auth import get_current_user
from app.api.schemas import (
    CitySpendPublicOut,
    SpendDetailCategoryOut,
    SpendDetailMovementOut,
    SpendDetailOut,
    TripSpendOut,
)
from app.config import get_settings
from app.db.engine import get_session
from app.db.models import Category, Movement, Stop, User
from app.trip_time import today_in_tz

router = APIRouter(tags=["integration"])

_EXPENSE = Movement.type == "expense"


def _money(v) -> str:
    return f"{Decimal(str(v)):.2f}"


async def require_api_key(x_api_key: str = Header(...)) -> None:
    if not secrets.compare_digest(x_api_key, get_settings().trip_shared_api_key):
        raise HTTPException(status_code=401, detail="API key inválida")


async def _local_slugs(session: AsyncSession) -> list[str]:
    """Slugs que solo existen en Spitwise. Andiamo no los conoce, así que nunca
    se le exponen como ciudad (su itinerario no tiene dónde renderizarlos)."""
    return list(
        (await session.execute(select(Stop.slug).where(Stop.is_local.is_(True)))).scalars().all()
    )


@router.get("/cities/spend", response_model=list[CitySpendPublicOut])
async def cities_spend(
    slug: str | None = Query(default=None),
    _: None = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> list[CitySpendPublicOut]:
    """Total del hogar (gross amount_usd de expenses), no share personal.
    Excluye stops locales: son ciudades que no existen en el itinerario de Andiamo."""
    stmt = (
        select(Movement.stop_slug, Movement.city_name,
               func.sum(Movement.amount_usd), func.count())
        .where(_EXPENSE)
        .group_by(Movement.stop_slug, Movement.city_name)
    )
    local = await _local_slugs(session)
    if local:
        stmt = stmt.where(
            func.coalesce(Movement.stop_slug, "").not_in(local)
        )
    if slug:
        stmt = stmt.where(Movement.stop_slug == slug)
    rows = (await session.execute(stmt)).all()
    return [
        CitySpendPublicOut(slug=s, name=c, total_usd=_money(t), movement_count=cnt)
        for s, c, t, cnt in rows
    ]


@router.get("/cities/spend-detail", response_model=SpendDetailOut)
async def cities_spend_detail(
    slug: str = Query(...),
    limit: int = Query(default=5, ge=1, le=10),
    _: None = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> SpendDetailOut:
    """Detalle de gasto de una ciudad para Andiamo. Totales gross del hogar.
    Siempre 200: slug desconocido => ceros y arrays vacíos (nunca 404).
    Un stop local se trata como desconocido: para Andiamo no existe."""
    is_local = slug in await _local_slugs(session)
    movements: list[Movement] = []
    if not is_local:
        base = select(Movement).where(_EXPENSE, Movement.stop_slug == slug)
        movements = list((await session.execute(base)).scalars().all())

    total = sum((m.amount_usd for m in movements), Decimal("0"))
    city_name = movements[0].city_name if movements else None

    stop = None if is_local else (
        await session.execute(select(Stop).where(Stop.slug == slug))
    ).scalar_one_or_none()
    days = 0
    if stop and stop.arrival_date and stop.departure_date:
        days = max((stop.departure_date - stop.arrival_date).days, 0)
    if stop and not city_name:
        city_name = stop.name
    avg = total / days if days else Decimal("0")

    cats = {c.id: c for c in (await session.execute(select(Category))).scalars().all()}
    agg: dict[int | None, Decimal] = {}
    for m in movements:
        agg[m.category_id] = agg.get(m.category_id, Decimal("0")) + m.amount_usd
    by_category = [
        SpendDetailCategoryOut(
            category_id=cid,
            name=cats[cid].name if cid in cats else "Otros",
            icon=cats[cid].icon if cid in cats else None,
            total_usd=_money(v),
        )
        for cid, v in sorted(agg.items(), key=lambda kv: kv[1], reverse=True)
        if v > 0
    ]

    users = {u.id: u.username for u in (await session.execute(select(User))).scalars().all()}
    recent = sorted(movements, key=lambda m: (m.movement_date, m.id), reverse=True)[:limit]
    last_movements = [
        SpendDetailMovementOut(
            description=m.description,
            amount=_money(m.amount),
            currency=m.currency,
            amount_usd=_money(m.amount_usd),
            date=m.movement_date,
            category_id=m.category_id,
            paid_by_name=users.get(m.paid_by),
        )
        for m in recent
    ]

    return SpendDetailOut(
        slug=slug,
        city_name=city_name,
        total_usd=_money(total),
        movement_count=len(movements),
        itinerary_days=days,
        avg_per_day_usd=_money(avg),
        by_category=by_category,
        last_movements=last_movements,
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/trip/spend", response_model=TripSpendOut)
async def trip_spend(
    _: None = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> TripSpendOut:
    """Totales gross del viaje para el strip de /hoy en Andiamo."""
    total, count = (
        await session.execute(
            select(func.coalesce(func.sum(Movement.amount_usd), 0), func.count()).where(_EXPENSE)
        )
    ).one()
    today = today_in_tz(None)
    today_total = (
        await session.execute(
            select(func.coalesce(func.sum(Movement.amount_usd), 0)).where(
                _EXPENSE, Movement.movement_date == today
            )
        )
    ).scalar_one()
    return TripSpendOut(
        total_usd=_money(total), today_usd=_money(today_total), movement_count=count
    )


@router.post("/andiamo/sync-hook", status_code=202)
async def sync_hook(_: None = Depends(require_api_key)) -> dict:
    """Webhook de Andiamo (stops.changed): agenda un re-pull inmediato del
    itinerario. Responde 202 al instante; el sync corre como task."""
    force_sync_soon()
    return {"status": "scheduled"}


@router.post("/andiamo/sync")
async def trigger_sync(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await sync_stops(session)
