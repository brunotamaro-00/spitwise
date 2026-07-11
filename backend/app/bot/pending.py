import json
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BotPendingAction


async def create_pending(session: AsyncSession, owner: str, payload: dict, kind: str) -> str:
    token = secrets.token_urlsafe(18)
    session.add(BotPendingAction(
        token=token, channel="whatsapp", owner=owner, action_type=kind,
        payload_json=json.dumps(payload),
        expires_at=datetime.utcnow() + timedelta(hours=6),
    ))
    await session.commit()
    return token


async def load_pending(session: AsyncSession, token: str) -> dict | None:
    row = (await session.execute(
        select(BotPendingAction).where(BotPendingAction.token == token)
    )).scalar_one_or_none()
    if row is None or row.confirmed_at is not None or row.cancelled_at is not None:
        return None
    data = json.loads(row.payload_json)
    data["_action_type"] = row.action_type
    return data


async def close_pending(session: AsyncSession, token: str) -> None:
    row = (await session.execute(
        select(BotPendingAction).where(BotPendingAction.token == token)
    )).scalar_one_or_none()
    if row is not None:
        row.confirmed_at = datetime.utcnow()
        await session.commit()
