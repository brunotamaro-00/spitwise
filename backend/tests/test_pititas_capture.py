"""El flujo real del bot: el mismo mensaje, en la misma fecha, cae en ciudades
distintas según quién lo mande."""
from datetime import date

from sqlalchemy import select

from app.api.auth import hash_password
from app.bot.capture import handle_capture
from app.categories.seed import seed_categories
from app.db.models import Movement, Stop, User

# Dentro del tramo Pititas (4-11 sept).
TODAY = date(2026, 9, 6)


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
    bruno = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    katia = User(username="katia", password_hash=hash_password("pw"), whatsapp_wa_id="549222")
    db_session.add_all([
        bruno, katia,
        Stop(slug="portugal", order=7, name="Portugal", arrival_date=date(2026, 9, 4),
             departure_date=date(2026, 9, 12), currency_code="EUR", timezone="Europe/Lisbon"),
        Stop(slug="pititas", order=7, name="Pititas", country_flag="😊",
             arrival_date=date(2026, 9, 4), departure_date=date(2026, 9, 12),
             currency_code="EUR", timezone="Europe/Paris",
             is_local=True, owner_username="katia"),
    ])
    await seed_categories(db_session)
    await db_session.commit()
    return bruno, katia


async def _last_movement(db_session):
    return (
        await db_session.execute(select(Movement).order_by(Movement.id.desc()))
    ).scalars().first()


async def test_gasto_de_katia_cae_en_pititas(db_session):
    _, katia = await _setup(db_session)
    fake = FakeLLM(_payload(amount="30", currency="EUR", description="cena", category="Comida"))

    await handle_capture(db_session, katia, "549222", "cena 30 euros", TODAY, llm_client=fake)

    mv = await _last_movement(db_session)
    assert (mv.stop_slug, mv.city_name) == ("pititas", "Pititas")


async def test_mismo_gasto_de_bruno_cae_en_portugal(db_session):
    bruno, _ = await _setup(db_session)
    fake = FakeLLM(_payload(amount="30", currency="EUR", description="cena", category="Comida"))

    await handle_capture(db_session, bruno, "549111", "cena 30 euros", TODAY, llm_client=fake)

    mv = await _last_movement(db_session)
    assert (mv.stop_slug, mv.city_name) == ("portugal", "Portugal")


async def test_katia_cargando_un_gasto_que_pago_bruno_sigue_en_pititas(db_session):
    """La ciudad la define el remitente: Katia está en Pititas aunque pague él."""
    _, katia = await _setup(db_session)
    fake = FakeLLM(_payload(amount="30", currency="EUR", description="cena",
                            category="Comida", paid_by="bruno"))

    await handle_capture(db_session, katia, "549222", "pagó bruno 30 euros", TODAY, llm_client=fake)

    mv = await _last_movement(db_session)
    assert mv.stop_slug == "pititas"


async def test_bruno_no_puede_imputar_a_pititas_por_nombre(db_session):
    """Una parada ajena nunca matchea, ni nombrándola: cae a texto libre."""
    bruno, _ = await _setup(db_session)
    fake = FakeLLM(_payload(amount="30", currency="EUR", description="cena",
                            category="Comida", city="Pititas"))

    await handle_capture(db_session, bruno, "549111", "cena 30 en pititas", TODAY, llm_client=fake)

    mv = await _last_movement(db_session)
    assert mv.stop_slug is None
    assert mv.city_name == "Pititas"  # texto libre, no la parada de Katia


async def test_settlement_de_katia_no_lleva_ciudad(db_session):
    """Invariante existente: un saldo nunca lleva ciudad, tampoco en Pititas."""
    _, katia = await _setup(db_session)
    fake = FakeLLM(_payload(intent="settlement", amount="20", currency="USD"))

    await handle_capture(db_session, katia, "549222", "le pasé 20 usd", TODAY, llm_client=fake)

    mv = await _last_movement(db_session)
    assert mv.type == "settlement"
    assert (mv.stop_slug, mv.city_name) == (None, None)
