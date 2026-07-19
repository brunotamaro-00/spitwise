"""Liquidación lazy de pendientes y su exclusión del balance."""
from datetime import date
from decimal import Decimal

from sqlalchemy import select

import app.due as due
from app.api.auth import hash_password
from app.balance import MovementLike, compute_balance
from app.db.models import FxRate, Movement, User
from app.due import ensure_due_settled, settle_due_movements

TODAY = date(2026, 9, 5)


async def _users(db_session):
    u1 = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    u2 = User(username="katia", password_hash=hash_password("pw"), whatsapp_wa_id="549222")
    db_session.add_all([u1, u2])
    await db_session.commit()
    return u1, u2


def _pending(u, *, amount="430", currency="CHF", rate="1.20", pay=date(2026, 9, 3),
             fx_source="frankfurter"):
    amt = Decimal(amount)
    return Movement(
        type="expense", amount=amt, currency=currency,
        amount_usd=(amt * Decimal(rate)).quantize(Decimal("0.01")),
        fx_rate=Decimal(rate), fx_source=fx_source, paid_by=u.id, split="shared",
        description="hostel (2/2)", payment_date=pay, status="pending", created_by=u.id,
    )


async def test_settle_confirms_with_payment_date_rate(db_session):
    u1, _ = await _users(db_session)
    db_session.add_all([
        _pending(u1),
        # TC real del día de pago, distinto del proxy 1.20.
        FxRate(currency="CHF", rate_date=date(2026, 9, 3), rate_to_usd=Decimal("1.25")),
    ])
    await db_session.commit()
    n = await settle_due_movements(db_session, TODAY)
    assert n == 1
    mv = (await db_session.execute(select(Movement))).scalar_one()
    assert mv.status == "confirmed"
    assert mv.fx_rate == Decimal("1.25")
    assert mv.amount_usd == Decimal("537.50")
    assert mv.fx_source == "frankfurter"


async def test_settle_skips_future_and_is_idempotent(db_session):
    u1, _ = await _users(db_session)
    db_session.add_all([
        _pending(u1, pay=date(2026, 12, 1)),  # todavía no vence
        FxRate(currency="CHF", rate_date=date(2026, 9, 3), rate_to_usd=Decimal("1.25")),
        _pending(u1),
    ])
    await db_session.commit()
    assert await settle_due_movements(db_session, TODAY) == 1
    # Segunda pasada: nada pendiente vencido, nada que tocar.
    assert await settle_due_movements(db_session, TODAY) == 0
    future = (await db_session.execute(
        select(Movement).where(Movement.payment_date == date(2026, 12, 1))
    )).scalar_one()
    assert future.status == "pending"


async def test_settle_keeps_pending_on_fallback(db_session, monkeypatch):
    u1, _ = await _users(db_session)
    db_session.add(_pending(u1))
    await db_session.commit()

    async def _broken(session, currency, on_date, **kw):
        return Decimal("1.0"), "fallback"

    monkeypatch.setattr(due, "get_rate_to_usd", _broken)
    assert await settle_due_movements(db_session, TODAY) == 0
    mv = (await db_session.execute(select(Movement))).scalar_one()
    # Sigue pending con el proxy original: reintenta en el próximo touch.
    assert mv.status == "pending"
    assert mv.fx_rate == Decimal("1.20")


async def test_settle_manual_fx_flips_without_recompute(db_session):
    u1, _ = await _users(db_session)
    db_session.add_all([
        _pending(u1, fx_source="manual"),
        FxRate(currency="CHF", rate_date=date(2026, 9, 3), rate_to_usd=Decimal("1.25")),
    ])
    await db_session.commit()
    assert await settle_due_movements(db_session, TODAY) == 1
    mv = (await db_session.execute(select(Movement))).scalar_one()
    assert mv.status == "confirmed"
    assert mv.fx_rate == Decimal("1.20")  # la tasa manual no se pisa (invariante 6)
    assert mv.fx_source == "manual"


async def test_ensure_due_settled_throttles(db_session, monkeypatch):
    u1, _ = await _users(db_session)
    db_session.add_all([
        _pending(u1),
        FxRate(currency="CHF", rate_date=date(2026, 9, 3), rate_to_usd=Decimal("1.25")),
    ])
    await db_session.commit()
    monkeypatch.setattr(due, "_last_check", None)
    await ensure_due_settled(db_session, TODAY)
    mv = (await db_session.execute(select(Movement))).scalar_one()
    assert mv.status == "confirmed"
    # Dentro del TTL: no vuelve a mirar la DB aunque haya nuevos pendientes.
    db_session.add(_pending(u1))
    await db_session.commit()
    await ensure_due_settled(db_session, TODAY)
    still = (await db_session.execute(
        select(Movement).where(Movement.status == "pending")
    )).scalars().all()
    assert len(still) == 1


def test_compute_balance_excludes_pending():
    mvs = [
        MovementLike(type="expense", split="shared", paid_by=1, amount_usd=Decimal("100")),
        MovementLike(type="expense", split="shared", paid_by=1, amount_usd=Decimal("500"),
                     status="pending"),
    ]
    bal = compute_balance(mvs, 1, 2)
    # Solo el confirmado genera deuda: 50, no 300.
    assert bal.amount_usd == Decimal("50")
    assert bal.debtor_id == 2
