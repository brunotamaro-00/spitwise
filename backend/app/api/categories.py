from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.schemas import CategoryOut
from app.db.engine import get_session
from app.db.models import Category, User

router = APIRouter(tags=["categories"])


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Category]:
    return list(
        (await session.execute(select(Category).order_by(Category.sort_order))).scalars().all()
    )
