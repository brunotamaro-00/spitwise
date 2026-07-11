from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.schemas import CategorySpendOut, CitySpendOut, SummaryOut, TimePointOut
from app.db.engine import get_session
from app.db.models import Category, Movement, User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
_EXPENSE = Movement.type == "expense"


def _money(v) -> str:
    return f"{Decimal(str(v)):.2f}"


@router.get("/summary", response_model=SummaryOut)
async def summary(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SummaryOut:
    total = (await session.execute(
        select(func.coalesce(func.sum(Movement.amount_usd), 0)).where(_EXPENSE)
    )).scalar_one()
    count = (await session.execute(
        select(func.count()).select_from(Movement).where(_EXPENSE)
    )).scalar_one()
    return SummaryOut(total_usd=_money(total), movement_count=count)


@router.get("/by-city", response_model=list[CitySpendOut])
async def by_city(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CitySpendOut]:
    rows = (await session.execute(
        select(Movement.stop_slug, Movement.city_name, func.sum(Movement.amount_usd))
        .where(_EXPENSE)
        .group_by(Movement.stop_slug, Movement.city_name)
        .order_by(func.sum(Movement.amount_usd).desc())
    )).all()
    return [CitySpendOut(stop_slug=s, city_name=c, total_usd=_money(t)) for s, c, t in rows]


@router.get("/by-category", response_model=list[CategorySpendOut])
async def by_category(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CategorySpendOut]:
    rows = (await session.execute(
        select(Category.id, Category.name, Category.icon, func.sum(Movement.amount_usd))
        .join(Movement, Movement.category_id == Category.id)
        .where(_EXPENSE)
        .group_by(Category.id, Category.name, Category.icon)
        .order_by(func.sum(Movement.amount_usd).desc())
    )).all()
    return [
        CategorySpendOut(category_id=i, name=n, icon=ic, total_usd=_money(t))
        for i, n, ic, t in rows
    ]


@router.get("/timeseries", response_model=list[TimePointOut])
async def timeseries(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[TimePointOut]:
    rows = (await session.execute(
        select(Movement.movement_date, func.sum(Movement.amount_usd))
        .where(_EXPENSE)
        .group_by(Movement.movement_date)
        .order_by(Movement.movement_date)
    )).all()
    out: list[TimePointOut] = []
    cum = Decimal("0")
    for d, t in rows:
        cum += Decimal(str(t))
        out.append(TimePointOut(date=d, cumulative_usd=_money(cum)))
    return out
