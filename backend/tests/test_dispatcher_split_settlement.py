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


async def _two_users(db_session):
    u1 = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    u2 = User(username="katia", password_hash=hash_password("pw"), whatsapp_wa_id="549222")
    db_session.add_all([u1, u2])
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    await db_session.commit()
    return u1, u2


async def test_clean_capture_has_no_buttons(db_session):
    u1, u2 = await _two_users(db_session)
    fake = FakeLLM(_payload(amount="100", currency="USD", description="hotel",
                            category="Alojamiento", confidence=0.95))
    reply = await dispatch(db_session, "549111", "text", "hotel 100", None, date(2026, 8, 6), llm_client=fake)
    assert not reply.buttons  # sin botones si no hubo ambigüedad
    mv = (await db_session.execute(select(Movement))).scalar_one()
    assert mv.split == "shared"


async def test_split_edit_via_natural_language(db_session):
    u1, u2 = await _two_users(db_session)
    fake = FakeLLM(_payload(amount="100", currency="USD", description="hotel",
                            category="Alojamiento", confidence=0.95))
    await dispatch(db_session, "549111", "text", "hotel 100", None, date(2026, 8, 6), llm_client=fake)
    # "el último fue solo mío" → intent edit
    fake_edit = FakeLLM(_payload(intent="edit", ref_last=True, new_split="payer_only"))
    reply = await dispatch(db_session, "549111", "text", "el hotel fue solo mío", None,
                           date(2026, 8, 6), llm_client=fake_edit)
    assert "editado" in (reply.text or "")
    mv = (await db_session.execute(select(Movement))).scalar_one()
    assert mv.split == "payer_only"
    bal = compute_balance((await db_session.execute(select(Movement))).scalars().all(), u1.id, u2.id)
    assert bal.amount_usd == Decimal("0")  # solo mío => nadie debe


async def test_legacy_split_button_still_works(db_session):
    u1, u2 = await _two_users(db_session)
    db_session.add(Movement(type="expense", amount=Decimal("100"), currency="USD",
                            amount_usd=Decimal("100"), fx_rate=Decimal("1"), fx_source="frankfurter",
                            paid_by=u1.id, split="shared", movement_date=date(2026, 8, 6), created_by=u1.id))
    await db_session.commit()
    mv = (await db_session.execute(select(Movement))).scalar_one()
    await handle_interactive(db_session, u1, "549111", f"split_mine:{mv.id}", date(2026, 8, 6))
    await db_session.refresh(mv)
    assert mv.split == "payer_only"


async def test_borrar_command_confirms_then_deletes(db_session):
    u1, u2 = await _two_users(db_session)
    db_session.add(Movement(type="expense", amount=Decimal("20"), currency="USD",
                            amount_usd=Decimal("20"), fx_rate=Decimal("1"), fx_source="frankfurter",
                            paid_by=u1.id, split="shared", movement_date=date(2026, 8, 6), created_by=u1.id))
    await db_session.commit()
    mv = (await db_session.execute(select(Movement))).scalar_one()
    # "borrar" pide confirmación con botones sobre el último movimiento.
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
    fake = FakeLLM(_payload(intent="settlement", amount="50", currency="USD", description="saldo"))
    reply = await dispatch(db_session, "549222", "text", "le pasé 50 usd", None, date(2026, 8, 7), llm_client=fake)
    assert "Pago de saldo" in (reply.text or "")
    bal = compute_balance((await db_session.execute(select(Movement))).scalars().all(), u1.id, u2.id)
    assert bal.amount_usd == Decimal("0")  # saldado


async def test_unknown_intent_gives_examples(db_session):
    await _two_users(db_session)
    fake = FakeLLM(_payload(intent="unknown"))
    reply = await dispatch(db_session, "549111", "text", "hola como va", None, date(2026, 8, 6), llm_client=fake)
    assert "No te entendí" in (reply.text or "")
    assert not (await db_session.execute(select(Movement))).scalars().all()
