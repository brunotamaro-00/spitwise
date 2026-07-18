from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.api.auth import hash_password
from app.bot.dispatcher import dispatch
from app.db.models import Movement, Stop, User

TODAY = date(2026, 8, 6)


class FakeLLM:
    """Devuelve un payload fijo y recuerda los kwargs del último parse."""

    def __init__(self, payload):
        self.payload = payload
        self.last_kwargs = None

    async def parse(self, text, **kwargs):
        self.last_kwargs = kwargs
        return self.payload


def _edit_payload(**over):
    base = {
        "intent": "edit", "amount": None, "currency": None, "description": None,
        "category": None, "split": "shared", "paid_by": None, "date": None, "city": None,
        "confidence": 0.9, "candidates": [], "ref_last": True, "ref_text": None, "ref_date": None,
        "new_amount": None, "new_currency": None, "new_date": None, "new_city": None,
        "new_category": None, "new_description": None, "new_split": None, "new_paid_by": None,
        "expenses": [],
    }
    base.update(over)
    return base


def _expense_payload(**over):
    base = {
        "intent": "expense", "amount": None, "currency": None, "description": None,
        "category": None, "split": "shared", "paid_by": None, "date": None, "city": None,
        "confidence": 0.9, "candidates": [], "ref_last": False, "ref_text": None, "ref_date": None,
        "new_amount": None, "new_currency": None, "new_date": None, "new_city": None,
        "new_category": None, "new_description": None, "new_split": None, "new_paid_by": None,
        "expenses": [],
    }
    base.update(over)
    return base


async def _setup(db_session):
    u1 = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    u2 = User(username="katia", password_hash=hash_password("pw"), whatsapp_wa_id="549222")
    db_session.add_all([
        u1, u2,
        Stop(slug="londres", order=1, name="Londres", arrival_date=date(2026, 8, 1),
             departure_date=date(2026, 8, 10), currency_code="GBP", timezone="Europe/London"),
    ])
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    await db_session.commit()
    return u1, u2


def _fresh_expense(u, desc, amount, *, split="shared", created_at=None):
    return Movement(
        type="expense", amount=Decimal(amount), currency="USD", amount_usd=Decimal(amount),
        fx_rate=Decimal("1"), fx_source="frankfurter", paid_by=u.id, split=split,
        description=desc, created_by=u.id,
        created_at=created_at or datetime.utcnow(),
    )


async def test_fresh_expense_flows_into_parser_context(db_session):
    _, katia = await _setup(db_session)
    db_session.add(_fresh_expense(katia, "tren", "39", split="shared"))
    await db_session.commit()

    # La corrección se resuelve como edit del último (ref_last) → cambia el split.
    fake = FakeLLM(_edit_payload(new_split="payer_only"))
    reply = await dispatch(db_session, "549222", "text", "contalo solo para katia",
                           None, TODAY, llm_client=fake)

    assert fake.last_kwargs["last_expense"] is not None
    assert "tren" in fake.last_kwargs["last_expense"]
    assert "Editado" in (reply.text or "")
    mv = (await db_session.execute(select(Movement))).scalar_one()
    assert mv.split == "payer_only"


async def test_stale_expense_not_offered_as_context(db_session):
    _, katia = await _setup(db_session)
    old = datetime.utcnow() - timedelta(hours=2)
    db_session.add(_fresh_expense(katia, "tren", "39", created_at=old))
    await db_session.commit()

    fake = FakeLLM(_expense_payload(amount="20", currency="USD", description="cena",
                                    category="Comida"))
    await dispatch(db_session, "549222", "text", "cena 20 euros", None, TODAY, llm_client=fake)
    assert fake.last_kwargs["last_expense"] is None


async def test_amountless_expense_after_capture_guides_to_edit(db_session):
    _, katia = await _setup(db_session)
    db_session.add(_fresh_expense(katia, "tren", "39"))
    await db_session.commit()

    # El parser no pescó la corrección: la devuelve como expense sin monto.
    fake = FakeLLM(_expense_payload(amount=None, description="gasto"))
    reply = await dispatch(db_session, "549222", "text", "que sea solo de katia",
                           None, TODAY, llm_client=fake)

    assert "tren" in (reply.text or "")
    assert "cambiar" in (reply.text or "").lower()
    # No se creó ningún gasto nuevo.
    assert len((await db_session.execute(select(Movement))).scalars().all()) == 1
