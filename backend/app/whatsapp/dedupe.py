from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WhatsAppDedupe


async def claim_wamid(session: AsyncSession, wamid: str) -> bool:
    """True si este proceso se queda con el mensaje (primera vez que lo ve).

    El chequeo previo evita el caso común; el INSERT puede fallar igual si Meta
    entrega el mismo `wamid` dos veces en paralelo (reintento por timeout). Sin
    capturar el IntegrityError eso era un 500 → Meta reintenta → bucle. Con la
    captura, el segundo simplemente pierde la carrera y no procesa.
    """
    exists = (
        await session.execute(select(WhatsAppDedupe).where(WhatsAppDedupe.wamid == wamid))
    ).scalar_one_or_none()
    if exists is not None:
        return False
    try:
        session.add(WhatsAppDedupe(wamid=wamid))
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return False
    return True


async def purge_old(session: AsyncSession, older_than_hours: int = 48) -> int:
    cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
    res = await session.execute(
        delete(WhatsAppDedupe).where(WhatsAppDedupe.created_at < cutoff)
    )
    await session.commit()
    return res.rowcount or 0
