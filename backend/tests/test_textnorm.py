"""Estandarización de descripciones: primera mayúscula + nombres propios."""
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.api.auth import hash_password
from app.bot.capture import handle_capture
from app.db.models import Movement, Stop, User
from app.textnorm import normalize_description

NOUNS = ["Interlaken", "York", "San Sebastián", "Pititas"]


def test_first_letter_capitalized():
    assert normalize_description("cena con vino", NOUNS) == "Cena con vino"


def test_proper_nouns_take_canonical_case():
    assert normalize_description("hostel interlaken", NOUNS) == "Hostel Interlaken"
    assert normalize_description("tren a york", NOUNS) == "Tren a York"


def test_never_lowercases_existing_caps():
    assert normalize_description("Cena MUY cara", NOUNS) == "Cena MUY cara"


def test_collapses_whitespace_and_none():
    assert normalize_description("  cena   con vino  ", NOUNS) == "Cena con vino"
    assert normalize_description(None, NOUNS) is None
    assert normalize_description("   ", NOUNS) is None


def test_idempotent():
    once = normalize_description("hostel interlaken (2/2)", NOUNS)
    assert normalize_description(once, NOUNS) == once == "Hostel Interlaken (2/2)"


def test_short_noun_tokens_ignored_mid_sentence():
    # "San Sebastián" capitaliza sus tokens largos; un "de" suelto no se toca.
    assert normalize_description("pinchos en san sebastián", NOUNS) == "Pinchos en San Sebastián"


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    async def parse(self, text, **kwargs):
        return self.payload


async def test_capture_persists_normalized_description(db_session):
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
    fake = FakeLLM({
        "intent": "expense", "amount": "10", "currency": "USD",
        "description": "hostel interlaken", "category": "Alojamiento", "split": "shared",
        "paid_by": None, "date": None, "city": None, "confidence": 0.9, "candidates": [],
    })
    await handle_capture(db_session, u1, "549111", "10 usd hostel interlaken",
                         date(2026, 9, 2), llm_client=fake)
    mv = (await db_session.execute(select(Movement))).scalar_one()
    assert mv.description == "Hostel Interlaken"
