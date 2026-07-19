"""Fecha de pago en la captura del bot: futura => pending con TC proxy de hoy;
pasada => confirmed con TC histórico de esa fecha; sin fecha => como siempre."""
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.api.auth import hash_password
from app.bot.capture import handle_capture
from app.db.models import FxRate, Movement, Stop, User

TODAY = date(2026, 8, 6)


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
        Stop(slug="york", order=1, name="York", arrival_date=date(2026, 7, 28),
             departure_date=date(2026, 8, 2), currency_code="GBP", timezone="Europe/London"),
        Stop(slug="interlaken", order=2, name="Interlaken", arrival_date=date(2026, 9, 1),
             departure_date=date(2026, 9, 6), currency_code="CHF", timezone="Europe/Zurich"),
    ])
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    await db_session.commit()
    return u1, u2


async def test_future_payment_date_is_pending_with_proxy_rate(db_session):
    u1, _ = await _setup(db_session)
    # TC proxy: el de HOY (fecha de carga), no existe tasa para la fecha futura.
    db_session.add(FxRate(currency="CHF", rate_date=TODAY, rate_to_usd=Decimal("1.20")))
    await db_session.commit()
    fake = FakeLLM(_payload(amount="430", currency="CHF", description="hostel interlaken",
                            category="Alojamiento", date="2026-09-03"))
    await handle_capture(db_session, u1, "549111", "430 chf hostel, se paga el 3-sep",
                         TODAY, llm_client=fake)
    mv = (await db_session.execute(select(Movement))).scalar_one()
    assert mv.status == "pending"
    assert mv.payment_date == date(2026, 9, 3)
    assert mv.amount_usd == Decimal("516.00")  # 430 * 1.20 proxy de hoy
    # La ciudad sale del itinerario de la fecha de pago, no de la de hoy.
    assert mv.stop_slug == "interlaken"


async def test_past_payment_date_is_confirmed_with_historic_rate(db_session):
    u1, _ = await _setup(db_session)
    # TC histórico cacheado para la fecha del gasto; el de hoy es otro.
    db_session.add_all([
        FxRate(currency="EUR", rate_date=date(2026, 7, 31), rate_to_usd=Decimal("1.05")),
        FxRate(currency="EUR", rate_date=TODAY, rate_to_usd=Decimal("1.10")),
    ])
    await db_session.commit()
    fake = FakeLLM(_payload(amount="130", currency="EUR", description="hospedaje york",
                            category="Alojamiento", date="2026-07-31", city="York"))
    await handle_capture(db_session, u1, "549111", "130 EUR hospedaje York 31 de julio",
                         TODAY, llm_client=fake)
    mv = (await db_session.execute(select(Movement))).scalar_one()
    assert mv.status == "confirmed"
    assert mv.payment_date == date(2026, 7, 31)
    assert mv.amount_usd == Decimal("136.50")  # 130 * 1.05 del 31-jul
    assert mv.city_name == "York"


async def test_no_date_keeps_old_semantics(db_session):
    u1, _ = await _setup(db_session)
    fake = FakeLLM(_payload(amount="10", currency="USD", description="cena", category="Comida"))
    await handle_capture(db_session, u1, "549111", "cena 10usd", TODAY, llm_client=fake)
    mv = (await db_session.execute(select(Movement))).scalar_one()
    assert mv.status == "confirmed"
    assert mv.payment_date is None


async def test_settlement_ignores_future_date(db_session):
    u1, _ = await _setup(db_session)
    fake = FakeLLM(_payload(intent="settlement", amount="50", currency="USD",
                            description="pago", date="2026-09-03"))
    await handle_capture(db_session, u1, "549111", "le paso 50 el 3-sep", TODAY, llm_client=fake)
    mv = (await db_session.execute(select(Movement))).scalar_one()
    assert mv.type == "settlement"
    assert mv.status == "confirmed"
    assert mv.payment_date is None
