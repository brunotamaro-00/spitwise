from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def resolve_user_by_wa_id(session: AsyncSession, wa_id: str) -> User | None:
    return (
        await session.execute(select(User).where(User.whatsapp_wa_id == wa_id))
    ).scalar_one_or_none()
