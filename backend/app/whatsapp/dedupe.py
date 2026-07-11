from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WhatsAppDedupe


async def claim_wamid(session: AsyncSession, wamid: str) -> bool:
    exists = (
        await session.execute(select(WhatsAppDedupe).where(WhatsAppDedupe.wamid == wamid))
    ).scalar_one_or_none()
    if exists is not None:
        return False
    session.add(WhatsAppDedupe(wamid=wamid))
    await session.commit()
    return True


async def purge_old(session: AsyncSession, older_than_hours: int = 48) -> int:
    cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
    res = await session.execute(
        delete(WhatsAppDedupe).where(WhatsAppDedupe.created_at < cutoff)
    )
    await session.commit()
    return res.rowcount or 0
