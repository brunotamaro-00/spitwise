from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.api.auth import hash_password
from app.bot.capture import handle_capture
from app.db.models import Movement, User


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    async def parse(self, text, **kwargs):
        return self.payload


def _payload(**over):
    base = {
        "intent": "expense", "amount": None, "currency": None, "description": None,
        "category": None, "split": "shared", "paid_by": None, "date": None, "city": None,
        "confidence": 0.9, "candidates": [],
    }
    base.update(over)
    return base


async def _user(db_session):
    u = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549110")
    db_session.add(u)
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    await db_session.commit()
    return u


async def test_autoregister_high_confidence(db_session):
    u = await _user(db_session)
    fake = FakeLLM(_payload(amount="20", currency="USD", description="taxi",
                            category="Transporte", confidence=0.95))
    reply = await handle_capture(db_session, u, "549110", "taxi 20", date(2026, 8, 6), llm_client=fake)
    assert "Transporte" in (reply.text or "")
    assert "Gasto guardado" in (reply.text or "")
    movs = (await db_session.execute(select(Movement))).scalars().all()
    assert len(movs) == 1
    assert movs[0].amount_usd == Decimal("20.00")
    assert movs[0].paid_by == u.id
    assert reply.movement_id == movs[0].id
    assert not reply.buttons  # captura limpia: sin botones


async def test_ambiguous_category_asks_buttons(db_session):
    u = await _user(db_session)
    fake = FakeLLM(_payload(amount="20", currency="USD", description="cosa", category="Comida",
                            confidence=0.4, candidates=["Comida", "Compras"]))
    reply = await handle_capture(db_session, u, "549110", "cosa 20", date(2026, 8, 6), llm_client=fake)
    assert reply.buttons  # pide categoría
    assert (await db_session.execute(select(Movement))).scalars().all() == []
