import json
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BotPendingAction


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def create_pending(session: AsyncSession, owner: str, payload: dict, kind: str) -> str:
    token = secrets.token_urlsafe(18)
    session.add(BotPendingAction(
        token=token, channel="whatsapp", owner=owner, action_type=kind,
        payload_json=json.dumps(payload),
        expires_at=_utcnow_naive() + timedelta(hours=6),
    ))
    await session.commit()
    return token


async def load_pending(
    session: AsyncSession, token: str, *, owner: str | None = None,
) -> dict | None:
    row = (await session.execute(
        select(BotPendingAction).where(BotPendingAction.token == token)
    )).scalar_one_or_none()
    if row is None or row.confirmed_at is not None or row.cancelled_at is not None:
        return None
    if row.expires_at is not None and row.expires_at < _utcnow_naive():
        row.cancelled_at = _utcnow_naive()
        await session.commit()
        return None
    if owner is not None and row.owner != owner:
        return None
    data = json.loads(row.payload_json)
    data["_action_type"] = row.action_type
    return data


async def close_pending(session: AsyncSession, token: str) -> None:
    row = (await session.execute(
        select(BotPendingAction).where(BotPendingAction.token == token)
    )).scalar_one_or_none()
    if row is not None:
        row.confirmed_at = _utcnow_naive()
        await session.commit()


async def cancel_pending(session: AsyncSession, token: str) -> None:
    row = (await session.execute(
        select(BotPendingAction).where(BotPendingAction.token == token)
    )).scalar_one_or_none()
    if row is not None and row.cancelled_at is None:
        row.cancelled_at = _utcnow_naive()
        await session.commit()
