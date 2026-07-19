from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics import build_trip_pace
from app.api.auth import get_current_user
from app.api.schemas import (
    CategorySpendOut,
    CityPaceOut,
    SummaryOut,
    TripBlockOut,
    TripPaceOut,
)
from app.bot.active_stop import resolve_trip_timezone
from app.db.engine import get_session
from app.db.models import Category, Movement, Stop, User
from app.due import ensure_due_settled
from app.spend import user_share
from app.trip_time import today_in_tz

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
_EXPENSE = Movement.type == "expense"


def _money(v) -> str:
    return f"{Decimal(str(v)):.2f}"


def _money_opt(v) -> str | None:
    return None if v is None else _money(v)


async def _expenses(session: AsyncSession) -> list[Movement]:
    return list((await session.execute(select(Movement).where(_EXPENSE))).scalars().all())


# Todos los endpoints del dashboard son personales: reflejan el consumo del
# usuario logueado (su parte de cada gasto), no el total del viaje.
@router.get("/summary", response_model=SummaryOut)
async def summary(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SummaryOut:
    await ensure_due_settled(session)
    rows = await _expenses(session)
    shares = [user_share(m, user.id) for m in rows]
    total = sum(shares, Decimal("0"))
    count = sum(1 for s in shares if s > 0)
    return SummaryOut(total_usd=_money(total), movement_count=count)


@router.get("/by-category", response_model=list[CategorySpendOut])
async def by_category(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CategorySpendOut]:
    cats = {c.id: c for c in (await session.execute(select(Category))).scalars().all()}
    agg: dict[int, Decimal] = {}
    for m in await _expenses(session):
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


@router.get("/pace", response_model=TripPaceOut)
async def pace(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TripPaceOut:
    """Ritmo del viaje: $/día global y por ciudad con alojamiento prorrateado
    por noches y generales prorrateados en todo el viaje. Ver app/analytics.py."""
    stops = list((await session.execute(select(Stop))).scalars().all())
    movements = await _expenses(session)
    lodging_id = (
        await session.execute(select(Category.id).where(Category.name == "Alojamiento"))
    ).scalar_one_or_none()
    today = today_in_tz(await resolve_trip_timezone(session, user.username))

    data = build_trip_pace(
        stops,
        movements,
        lodging_category_id=lodging_id,
        user_id=user.id,
        username=user.username,
        today=today,
    )
    t = data["trip"]
    return TripPaceOut(
        as_of=today,
        trip=TripBlockOut(
            status=t["status"],
            start=t["start"],
            end=t["end"],
            total_nights=t["total_nights"],
            elapsed_nights=t["elapsed_nights"],
            total_usd=_money(t["total_usd"]),
            general_usd=_money(t["general_usd"]),
            general_per_day_usd=_money_opt(t["general_per_day_usd"]),
            avg_per_day_usd=_money_opt(t["avg_per_day_usd"]),
            run_rate_usd=_money_opt(t["run_rate_usd"]),
            accrued_usd=_money(t["accrued_usd"]),
            projected_total_usd=_money_opt(t["projected_total_usd"]),
        ),
        cities=[
            CityPaceOut(
                stop_slug=c["stop_slug"],
                city_name=c["city_name"],
                country_flag=c["country_flag"],
                order=c["order"],
                status=c["status"],
                is_archived=c["is_archived"],
                is_transit=c["is_transit"],
                arrival_date=c["arrival_date"],
                departure_date=c["departure_date"],
                nights=c["nights"],
                elapsed_nights=c["elapsed_nights"],
                movement_count=c["movement_count"],
                total_usd=_money(c["total_usd"]),
                lodging_usd=_money(c["lodging_usd"]),
                other_usd=_money(c["other_usd"]),
                per_day_usd=_money_opt(c["per_day_usd"]),
                lodging_per_night_usd=_money_opt(c["lodging_per_night_usd"]),
                other_per_day_usd=_money_opt(c["other_per_day_usd"]),
                delta_vs_trip_pct=c["delta_vs_trip_pct"],
            )
            for c in data["cities"]
        ],
    )
