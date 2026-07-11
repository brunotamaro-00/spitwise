from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.andiamo import sync_stops
from app.api.auth import get_current_user
from app.api.schemas import CitySpendPublicOut
from app.config import get_settings
from app.db.engine import get_session
from app.db.models import Movement, User

router = APIRouter(tags=["integration"])


async def require_api_key(x_api_key: str = Header(...)) -> None:
    if x_api_key != get_settings().trip_shared_api_key:
        raise HTTPException(status_code=401, detail="API key inválida")


@router.get("/cities/spend", response_model=list[CitySpendPublicOut])
async def cities_spend(
    slug: str | None = Query(default=None),
    _: None = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> list[CitySpendPublicOut]:
    stmt = (
        select(Movement.stop_slug, Movement.city_name,
               func.sum(Movement.amount_usd), func.count())
        .where(Movement.type == "expense")
        .group_by(Movement.stop_slug, Movement.city_name)
    )
    if slug:
        stmt = stmt.where(Movement.stop_slug == slug)
    rows = (await session.execute(stmt)).all()
    return [
        CitySpendPublicOut(slug=s, name=c, total_usd=f"{Decimal(str(t)):.2f}", movement_count=cnt)
        for s, c, t, cnt in rows
    ]


@router.post("/andiamo/sync")
async def trigger_sync(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    n = await sync_stops(session)
    return {"synced": n}
