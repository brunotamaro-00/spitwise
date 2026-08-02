import json
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BotPendingAction


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_token() -> str:
    return secrets.token_urlsafe(18)


async def create_pending(session: AsyncSession, owner: str, payload: dict, kind: str,
                         token: str | None = None) -> str:
    """`token` pre-generado sirve para pendings HERMANOS que tienen que
    referenciarse entre sí (borrar el batch entero vs. solo el último): cada
    payload puede llevar el token del otro antes de que existan las filas."""
    token = token or new_token()
    session.add(BotPendingAction(
        token=token, channel="whatsapp", owner=owner, action_type=kind,
        payload_json=json.dumps(payload),
        expires_at=_utcnow_naive() + timedelta(hours=6),
    ))
    await session.commit()
    return token


async def load_pending(
    session: AsyncSession, token: str, *, owner: str | None = None,
    kind: str | None = None,
) -> dict | None:
    """`kind` es el tipo que el handler ESPERA: un token de otra clase de pending
    (un `doc_upload` llegando al handler de borrado) devuelve None en vez de que
    el handler interprete un payload que no es suyo."""
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
    if kind is not None and row.action_type != kind:
        return None
    return json.loads(row.payload_json)


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
