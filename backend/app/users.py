import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import User

logger = logging.getLogger(__name__)


async def get_trip_users(session: AsyncSession) -> tuple[User, User]:
    users = (await session.execute(select(User).order_by(User.id))).scalars().all()
    if len(users) != 2:
        raise HTTPException(status_code=500, detail="El libro requiere exactamente 2 usuarios")
    return users[0], users[1]


async def username_for_wa_id(session: AsyncSession, wa_id: str) -> str | None:
    """Username del remitente de WhatsApp. None si el número no está registrado."""
    return (
        await session.execute(select(User.username).where(User.whatsapp_wa_id == wa_id))
    ).scalar_one_or_none()


async def seed_users_from_env(session: AsyncSession) -> None:
    from app.api.auth import hash_password

    raw = get_settings().auth_users
    if not raw:
        return
    for entry in raw.split(","):
        entry = entry.strip()
        if ":" not in entry:
            continue
        parts = entry.split(":", 2)
        username, password = parts[0].strip().lower(), parts[1].strip()
        wa_id = parts[2].strip() if len(parts) == 3 else None
        user = (
            await session.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if user is None:
            user = User(username=username, password_hash=hash_password(password))
            session.add(user)
        if wa_id and user.whatsapp_wa_id != wa_id:
            user.whatsapp_wa_id = wa_id
    await session.commit()
