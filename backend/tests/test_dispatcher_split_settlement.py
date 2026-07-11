from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.api.auth import hash_password
from app.balance import compute_balance
from app.bot.dispatcher import dispatch
from app.bot.interactive import handle_interactive
from app.db.models import Movement, User


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    async def parse(self, text, default_currency, category_names):
        return self.payload


async def _two_users(db_session):
    u1 = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    u2 = User(username="katia", password_hash=hash_password("pw"), whatsapp_wa_id="549222")
    db_session.add_all([u1, u2])
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    await db_session.commit()
    return u1, u2


async def test_capture_then_split_override_to_mine(db_session):
    u1, u2 = await _two_users(db_session)
    fake = FakeLLM({"amount": "100", "currency": "USD", "description": "hotel", "category": "Alojamiento",
                    "split": "shared", "is_settlement": False, "confidence": 0.95, "candidates": []})
    reply = await dispatch(db_session, "549111", "text", "hotel 100", None, date(2026, 8, 6), llm_client=fake)
    assert reply.buttons  # ofrece override de split
    mv = (await db_session.execute(select(Movement))).scalar_one()
    # Los botones apuntan al movimiento recién creado (no al "último global").
    assert reply.buttons[0][0] == f"split_shared:{mv.id}"
    # Simular tap en "Solo mío"
    await handle_interactive(db_session, u1, "549111", f"split_mine:{mv.id}", date(2026, 8, 6))
    await db_session.refresh(mv)
    assert mv.split == "payer_only"
    bal = compute_balance((await db_session.execute(select(Movement))).scalars().all(), u1.id, u2.id)
    assert bal.amount_usd == Decimal("0")  # solo mío => nadie debe


async def test_borrar_command_confirms_then_deletes(db_session):
    u1, u2 = await _two_users(db_session)
    db_session.add(Movement(type="expense", amount=Decimal("20"), currency="USD",
                            amount_usd=Decimal("20"), fx_rate=Decimal("1"), fx_source="frankfurter",
                            paid_by=u1.id, split="shared", movement_date=date(2026, 8, 6), created_by=u1.id))
    await db_session.commit()
    mv = (await db_session.execute(select(Movement))).scalar_one()
    # "borrar" pide confirmación con botones sobre el último movimiento del usuario.
    reply = await dispatch(db_session, "549111", "text", "borrar", None, date(2026, 8, 6))
    assert reply.buttons and reply.buttons[0][0] == f"del_confirm:{mv.id}"
    # Confirmar borra.
    await handle_interactive(db_session, u1, "549111", f"del_confirm:{mv.id}", date(2026, 8, 6))
    assert (await db_session.execute(select(Movement))).scalars().all() == []


async def test_settlement_capture(db_session):
    u1, u2 = await _two_users(db_session)
    # u2 le debe 50 a u1
    db_session.add(Movement(type="expense", amount=Decimal("100"), currency="USD",
                            amount_usd=Decimal("100"), fx_rate=Decimal("1"), fx_source="frankfurter",
                            paid_by=u1.id, split="shared", movement_date=date(2026, 8, 6), created_by=u1.id))
    await db_session.commit()
    fake = FakeLLM({"amount": "50", "currency": "USD", "description": "saldo", "category": "Otros",
                    "split": "shared", "is_settlement": True, "confidence": 0.9, "candidates": []})
    await dispatch(db_session, "549222", "text", "le pasé 50 usd", None, date(2026, 8, 7), llm_client=fake)
    bal = compute_balance((await db_session.execute(select(Movement))).scalars().all(), u1.id, u2.id)
    assert bal.amount_usd == Decimal("0")  # saldado
