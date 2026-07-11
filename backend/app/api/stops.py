from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.schemas import StopOut
from app.db.engine import get_session
from app.db.models import Stop, User

router = APIRouter(tags=["stops"])


@router.get("/stops", response_model=list[StopOut])
async def list_stops(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Stop]:
    """Paradas del itinerario para el selector de ciudad (orden del recorrido)."""
    rows = (
        await session.execute(
            select(Stop).where(Stop.is_candidate.is_(False)).order_by(Stop.order)
        )
    ).scalars().all()
    return list(rows)
