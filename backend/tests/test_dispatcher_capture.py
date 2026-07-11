from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.api.auth import hash_password
from app.bot.capture import handle_capture
from app.db.models import Movement, User


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    async def parse(self, text, default_currency, category_names):
        return self.payload


async def _user(db_session):
    u = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549110")
    db_session.add(u)
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    await db_session.commit()
    return u


async def test_autoregister_high_confidence(db_session):
    u = await _user(db_session)
    fake = FakeLLM({"amount": "20", "currency": "USD", "description": "taxi", "category": "Transporte",
                    "split": "shared", "is_settlement": False, "confidence": 0.95, "candidates": []})
    reply = await handle_capture(db_session, u, "549110", "taxi 20", date(2026, 8, 6), llm_client=fake)
    assert "Transporte" in (reply.text or "")
    movs = (await db_session.execute(select(Movement))).scalars().all()
    assert len(movs) == 1
    assert movs[0].amount_usd == Decimal("20.00")
    assert movs[0].paid_by == u.id
    assert reply.movement_id == movs[0].id


async def test_ambiguous_category_asks_buttons(db_session):
    u = await _user(db_session)
    fake = FakeLLM({"amount": "20", "currency": "USD", "description": "cosa", "category": "Comida",
                    "split": "shared", "is_settlement": False, "confidence": 0.4,
                    "candidates": ["Comida", "Compras"]})
    reply = await handle_capture(db_session, u, "549110", "cosa 20", date(2026, 8, 6), llm_client=fake)
    assert reply.buttons  # pide categoría
    assert (await db_session.execute(select(Movement))).scalars().all() == []
