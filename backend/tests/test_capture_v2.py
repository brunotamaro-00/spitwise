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
        Stop(slug="londres", order=1, name="Londres", arrival_date=date(2026, 8, 1),
             departure_date=date(2026, 8, 10), currency_code="GBP", timezone="Europe/London"),
        Stop(slug="roma", order=2, name="Roma", arrival_date=date(2026, 9, 20),
             departure_date=date(2026, 9, 26), currency_code="EUR", timezone="Europe/Rome"),
    ])
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    await db_session.commit()
    return u1, u2


async def test_explicit_date_resolves_city_from_itinerary(db_session):
    u1, _ = await _setup(db_session)
    fake = FakeLLM(_payload(amount="10", currency="USD", description="cena",
                            category="Comida", date="2026-09-23"))
    reply = await handle_capture(db_session, u1, "549111", "10usd en cena el 23 de septiembre",
                                 TODAY, llm_client=fake)
    mv = (await db_session.execute(select(Movement))).scalar_one()
    assert mv.movement_date == date(2026, 9, 23)
    assert mv.city_name == "Roma"
    assert mv.stop_slug == "roma"
    assert "23/09" in reply.text and "Roma" in reply.text


async def test_default_currency_follows_movement_date_city(db_session):
    u1, _ = await _setup(db_session)
    # Cachear FX para no ir a la red. El TC es el de la fecha de CARGA (hoy),
    # aunque el gasto sea de otra fecha.
    db_session.add(FxRate(currency="EUR", rate_date=TODAY, rate_to_usd=Decimal("1.10")))
    await db_session.commit()
    fake = FakeLLM(_payload(amount="10", description="cena", category="Comida", date="2026-09-23"))
    await handle_capture(db_session, u1, "549111", "cena 10 el 23 de septiembre", TODAY, llm_client=fake)
    mv = (await db_session.execute(select(Movement))).scalar_one()
    assert mv.currency == "EUR"  # moneda de Roma, no la de la parada de hoy
    assert mv.amount_usd == Decimal("11.00")


async def test_date_outside_itinerary_has_no_city(db_session):
    u1, _ = await _setup(db_session)
    fake = FakeLLM(_payload(amount="10", currency="USD", description="cena",
                            category="Comida", date="2026-12-25"))
    reply = await handle_capture(db_session, u1, "549111", "cena 10usd el 25 de diciembre",
                                 TODAY, llm_client=fake)
    mv = (await db_session.execute(select(Movement))).scalar_one()
    assert mv.city_name is None and mv.stop_slug is None
    assert "Sin ciudad" in reply.text


async def test_paid_by_name_sets_other_user_as_payer(db_session):
    u1, u2 = await _setup(db_session)
    fake = FakeLLM(_payload(amount="20", currency="USD", description="museo",
                            category="Actividades", paid_by="katia"))
    reply = await handle_capture(db_session, u1, "549111", "pagó katia 20usd el museo",
                                 TODAY, llm_client=fake)
    mv = (await db_session.execute(select(Movement))).scalar_one()
    assert mv.paid_by == u2.id
    assert mv.created_by == u1.id
    assert "Katia" in reply.text


async def test_explicit_city_matches_stop(db_session):
    u1, _ = await _setup(db_session)
    fake = FakeLLM(_payload(amount="10", currency="USD", description="cena",
                            category="Comida", city="roma"))
    await handle_capture(db_session, u1, "549111", "cena 10usd en roma", TODAY, llm_client=fake)
    mv = (await db_session.execute(select(Movement))).scalar_one()
    assert mv.stop_slug == "roma"
    assert mv.city_name == "Roma"


async def test_full_card_contents(db_session):
    u1, _ = await _setup(db_session)
    fake = FakeLLM(_payload(amount="10", currency="USD", description="cena", category="Comida"))
    reply = await handle_capture(db_session, u1, "549111", "cena 10usd", TODAY, llm_client=fake)
    text = reply.text or ""
    assert "✅ *Gasto guardado*" in text
    assert "🍽️ Comida — cena" in text
    assert "USD 10,0" in text
    assert "06/08" in text
    assert "Londres" in text  # parada activa de hoy
    assert "Pagó Bruno" in text
    assert "50/50" in text
