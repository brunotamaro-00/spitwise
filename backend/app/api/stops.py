from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.andiamo import ensure_stops_fresh
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
    """Paradas del itinerario para el selector de ciudad (orden del recorrido).
    Excluye candidatas y archivadas (borradas en Andiamo pero con gastos)."""
    # Fallback perezoso (TTL 6h) por si el webhook de Andiamo nunca llegó.
    await ensure_stops_fresh(session)
    rows = (
        await session.execute(
            select(Stop)
            .where(Stop.is_candidate.is_(False), Stop.is_archived.is_(False))
            .order_by(Stop.order)
        )
    ).scalars().all()
    return list(rows)
