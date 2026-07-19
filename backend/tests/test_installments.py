"""Pago en etapas: el server calcula los montos y el redondeo cierra exacto con
el total; las cuotas nacen como batch (batch_key compartido) con sufijo (i/n)."""
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.api.auth import hash_password
from app.bot.capture import expand_installments, handle_capture
from app.db.models import FxRate, Movement, Stop, User
from app.llm.parser import Installment, ParsedMessage

TODAY = date(2026, 7, 18)


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


async def _setup(db_session):
    u1 = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    u2 = User(username="katia", password_hash=hash_password("pw"), whatsapp_wa_id="549222")
    db_session.add_all([
        u1, u2,
        Stop(slug="interlaken", order=1, name="Interlaken", arrival_date=date(2026, 9, 1),
             departure_date=date(2026, 9, 6), currency_code="CHF", timezone="Europe/Zurich"),
    ])
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    await db_session.commit()
    return u1, u2


def _parsed(**over):
    base = dict(intent="expense", amount=Decimal("430"), currency="CHF",
                description="hostel interlaken", category_name="Alojamiento")
    base.update(over)
    return ParsedMessage(**base)


def test_expand_percent_and_rest_closes_exact():
    parsed = _parsed(installments=[
        Installment(percent=Decimal("30")),
        Installment(pay_date=date(2026, 9, 3)),  # "el resto"
    ])
    parts = expand_installments(parsed, TODAY)
    assert [p.amount for p in parts] == [Decimal("129.00"), Decimal("301.00")]
    assert parts[0].description == "hostel interlaken (1/2)"
    assert parts[1].description == "hostel interlaken (2/2)"
    assert parts[0].payment_date is None  # hoy
    assert parts[1].payment_date == date(2026, 9, 3)


def test_expand_ugly_rounding_closes_exact():
    parsed = _parsed(amount=Decimal("100"), installments=[
        Installment(percent=Decimal("33")),
        Installment(pay_date=date(2026, 9, 3)),
    ])
    parts = expand_installments(parsed, TODAY)
    assert [p.amount for p in parts] == [Decimal("33.00"), Decimal("67.00")]
    assert sum(p.amount for p in parts) == Decimal("100")


def test_expand_explicit_amount_stage():
    parsed = _parsed(installments=[
        Installment(amount=Decimal("100")),
        Installment(pay_date=date(2026, 9, 3)),
    ])
    parts = expand_installments(parsed, TODAY)
    assert [p.amount for p in parts] == [Decimal("100"), Decimal("330")]


def test_expand_orders_by_date():
    parsed = _parsed(installments=[
        Installment(percent=Decimal("70"), pay_date=date(2026, 9, 3)),
        Installment(percent=Decimal("30")),  # hoy => primero
    ])
    parts = expand_installments(parsed, TODAY)
    assert parts[0].payment_date is None and parts[0].amount == Decimal("129.00")
    assert parts[1].payment_date == date(2026, 9, 3) and parts[1].amount == Decimal("301.00")


def test_expand_invalid_returns_none():
    # Sin total.
    assert expand_installments(_parsed(amount=None, installments=[
        Installment(percent=Decimal("30")), Installment()]), TODAY) is None
    # Dos "resto".
    assert expand_installments(_parsed(installments=[
        Installment(), Installment()]), TODAY) is None
    # Remanente <= 0 (las etapas se comen el total).
    assert expand_installments(_parsed(installments=[
        Installment(percent=Decimal("100")), Installment()]), TODAY) is None
    # Una sola etapa.
    assert expand_installments(_parsed(installments=[
        Installment(percent=Decimal("30"))]), TODAY) is None


async def test_capture_installments_end_to_end(db_session):
    u1, _ = await _setup(db_session)
    db_session.add(FxRate(currency="CHF", rate_date=TODAY, rate_to_usd=Decimal("1.20")))
    await db_session.commit()
    fake = FakeLLM(_payload(
        amount="430", currency="CHF", description="hostel interlaken",
        category="Alojamiento",
        installments=[
            {"percent": "30", "amount": None, "date": None},
            {"percent": None, "amount": None, "date": "2026-09-03"},
        ],
    ))
    reply = await handle_capture(
        db_session, u1, "549111",
        "430 CHF en Hostel Interlaken. 30% hoy y el resto al ingresar el 3 de septiembre",
        TODAY, llm_client=fake,
    )
    mvs = (await db_session.execute(select(Movement).order_by(Movement.id))).scalars().all()
    assert len(mvs) == 2
    first, second = mvs
    assert first.amount == Decimal("129.00") and first.status == "confirmed"
    assert second.amount == Decimal("301.00") and second.status == "pending"
    assert second.payment_date == date(2026, 9, 3)
    assert first.batch_key == second.batch_key and first.batch_key
    assert "(1/2)" in first.description and "(2/2)" in second.description
    assert "(1/2)" in reply.text and "(2/2)" in reply.text
