from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.schemas import CategorySpendOut, CitySpendOut, SummaryOut, TimePointOut
from app.db.engine import get_session
from app.db.models import Category, Movement, User
from app.spend import user_share

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
_EXPENSE = Movement.type == "expense"


def _money(v) -> str:
    return f"{Decimal(str(v)):.2f}"


async def _expenses(session: AsyncSession) -> list[Movement]:
    return list((await session.execute(select(Movement).where(_EXPENSE))).scalars().all())


# Todos los endpoints del dashboard son personales: reflejan el consumo del
# usuario logueado (su parte de cada gasto), no el total del viaje.
@router.get("/summary", response_model=SummaryOut)
async def summary(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SummaryOut:
    rows = await _expenses(session)
    shares = [user_share(m, user.id) for m in rows]
    total = sum(shares, Decimal("0"))
    count = sum(1 for s in shares if s > 0)
    return SummaryOut(total_usd=_money(total), movement_count=count)


@router.get("/by-city", response_model=list[CitySpendOut])
async def by_city(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CitySpendOut]:
    agg: dict[tuple[str | None, str | None], Decimal] = {}
    for m in await _expenses(session):
        share = user_share(m, user.id)
        if share <= 0:
            continue
        key = (m.stop_slug, m.city_name)
        agg[key] = agg.get(key, Decimal("0")) + share
    items = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)
    return [CitySpendOut(stop_slug=s, city_name=c, total_usd=_money(v)) for (s, c), v in items]


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


@router.get("/timeseries", response_model=list[TimePointOut])
async def timeseries(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[TimePointOut]:
    by_date: dict = {}
    for m in await _expenses(session):
        share = user_share(m, user.id)
        if share <= 0:
            continue
        by_date[m.movement_date] = by_date.get(m.movement_date, Decimal("0")) + share
    out: list[TimePointOut] = []
    cum = Decimal("0")
    for d in sorted(by_date):
        cum += by_date[d]
        out.append(TimePointOut(date=d, cumulative_usd=_money(cum)))
    return out
