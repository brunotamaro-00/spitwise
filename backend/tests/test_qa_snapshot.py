"""Snapshot que el agente Q&A financiero le pasa al LLM.

El snapshot tiene que explicar por sí solo por qué el saldo no es la suma de los
movimientos listados. Si un gasto excluido del balance no aparece marcado, el
LLM ve un delta sin causa y lo inventa.
"""
from datetime import date, datetime
from decimal import Decimal

from app.api.auth import hash_password
from app.bot.qa import _context_snapshot
from app.db.models import Movement, User

TODAY = date(2026, 9, 5)


async def _users(db_session):
    u1 = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    u2 = User(username="katia", password_hash=hash_password("pw"), whatsapp_wa_id="549222")
    db_session.add_all([u1, u2])
    await db_session.commit()
    return [u1, u2]


def _mv(u, *, status, pay, usd="200"):
    return Movement(
        type="expense", amount=Decimal(usd), currency="USD", amount_usd=Decimal(usd),
        fx_rate=Decimal("1"), fx_source="direct", paid_by=u.id, split="shared",
        description="hostel viena", payment_date=pay, status=status,
        created_at=datetime(2026, 9, 1, 12), created_by=u.id,
    )


async def test_snapshot_counts_awaiting_as_excluded(db_session):
    """`awaiting` sigue afuera del balance, pero el snapshot solo miraba
    `pending`: el gasto desaparecía de la línea de excluidos justo al vencer."""
    users = await _users(db_session)
    db_session.add_all([
        _mv(users[0], status="awaiting", pay=date(2026, 9, 3)),
        _mv(users[0], status="pending", pay=date(2026, 12, 1)),
    ])
    await db_session.commit()

    snap = await _context_snapshot(db_session, users, TODAY, "Europe/Vienna")
    # Los dos cuentan como excluidos: 2 por USD 400.
    assert "2 por USD 400" in snap
    assert "EXCLUIDOS del saldo" in snap


async def test_snapshot_marks_awaiting_line(db_session):
    users = await _users(db_session)
    db_session.add(_mv(users[0], status="awaiting", pay=date(2026, 9, 3)))
    await db_session.commit()

    snap = await _context_snapshot(db_session, users, TODAY, "Europe/Vienna")
    assert "VENCIÓ el 03/09" in snap
    assert "falta confirmarlo" in snap


async def test_snapshot_marks_pending_line(db_session):
    users = await _users(db_session)
    db_session.add(_mv(users[0], status="pending", pay=date(2026, 12, 1)))
    await db_session.commit()

    snap = await _context_snapshot(db_session, users, TODAY, "Europe/Vienna")
    assert "PENDIENTE, se paga el 01/12" in snap


async def test_snapshot_omits_note_without_unsettled(db_session):
    users = await _users(db_session)
    db_session.add(_mv(users[0], status="confirmed", pay=None))
    await db_session.commit()

    snap = await _context_snapshot(db_session, users, TODAY, "Europe/Vienna")
    assert "EXCLUIDOS del saldo" not in snap
