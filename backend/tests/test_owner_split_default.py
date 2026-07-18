"""Default de split en paradas con dueño: Pititas → Solo Katia, Portugal → Solo
Bruno, sin necesidad de aclararlo en el mensaje. El resto del viaje sigue 50/50.
"""
from datetime import date

from sqlalchemy import select

from app.api.auth import hash_password
from app.bot.capture import handle_capture
from app.categories.seed import seed_categories
from app.db.models import Movement, Stop, User

TODAY = date(2026, 9, 6)  # dentro del tramo Pititas/Portugal (4-11 sept)


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    async def parse(self, text, **kwargs):
        return self.payload


def _payload(**over):
    base = {
        "intent": "expense", "amount": "30", "currency": "EUR", "description": "cena",
        "category": "Comida", "split": "shared", "paid_by": None, "date": None, "city": None,
        "confidence": 0.9, "candidates": [],
    }
    base.update(over)
    return base


async def _setup(db_session):
    bruno = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    katia = User(username="katia", password_hash=hash_password("pw"), whatsapp_wa_id="549222")
    db_session.add_all([
        bruno, katia,
        # Portugal es solo de Bruno (Katia se fue a Pititas): owner=bruno, como
        # lo deja el sync de la contraparte en prod.
        Stop(slug="portugal", order=7, name="Portugal", arrival_date=date(2026, 9, 4),
             departure_date=date(2026, 9, 12), currency_code="EUR", timezone="Europe/Lisbon",
             owner_username="bruno"),
        Stop(slug="pititas", order=7, name="Pititas", country_flag="😊",
             arrival_date=date(2026, 9, 4), departure_date=date(2026, 9, 12),
             currency_code="EUR", timezone="Europe/Paris",
             is_local=True, owner_username="katia"),
        # Una parada común (sin dueño) para el contraste 50/50.
        Stop(slug="paris", order=3, name="París", arrival_date=date(2026, 8, 1),
             departure_date=date(2026, 8, 6), currency_code="EUR", timezone="Europe/Paris"),
    ])
    await seed_categories(db_session)
    await db_session.commit()
    return bruno, katia


async def _last(db_session):
    return (await db_session.execute(select(Movement).order_by(Movement.id.desc()))).scalars().first()


async def test_pititas_katia_paga_es_solo_katia(db_session):
    _, katia = await _setup(db_session)
    fake = FakeLLM(_payload())
    await handle_capture(db_session, katia, "549222", "cena 30 euros", TODAY, llm_client=fake)
    mv = await _last(db_session)
    assert mv.stop_slug == "pititas"
    assert mv.split == "payer_only"  # la paga la dueña => Solo Katia


async def test_pititas_paga_bruno_sigue_siendo_solo_katia(db_session):
    """Katia carga un gasto de Pititas que pagó Bruno: el gasto es de ella igual,
    así que el otro (Bruno) no comparte => other_only ("Solo Katia")."""
    _, katia = await _setup(db_session)
    fake = FakeLLM(_payload(paid_by="bruno"))
    await handle_capture(db_session, katia, "549222", "pagó bruno 30", TODAY, llm_client=fake)
    mv = await _last(db_session)
    assert mv.stop_slug == "pititas"
    assert mv.split == "other_only"


async def test_bruno_nombrando_pititas_tambien_es_de_katia(db_session):
    """Bruno puede imputar a Pititas nombrándola; sigue siendo gasto de Katia."""
    bruno, _ = await _setup(db_session)
    fake = FakeLLM(_payload(city="Pititas"))
    await handle_capture(db_session, bruno, "549111", "cena 30 en pititas", TODAY, llm_client=fake)
    mv = await _last(db_session)
    assert mv.stop_slug == "pititas"
    assert mv.split == "other_only"  # paga Bruno, el gasto es de Katia


async def test_portugal_bruno_paga_es_solo_bruno(db_session):
    bruno, _ = await _setup(db_session)
    fake = FakeLLM(_payload())
    await handle_capture(db_session, bruno, "549111", "cena 30 euros", TODAY, llm_client=fake)
    mv = await _last(db_session)
    assert mv.stop_slug == "portugal"
    assert mv.split == "payer_only"  # la paga el dueño => Solo Bruno


async def test_portugal_paga_katia_sigue_siendo_solo_bruno(db_session):
    bruno, _ = await _setup(db_session)
    fake = FakeLLM(_payload(city="Portugal", paid_by="katia"))
    await handle_capture(db_session, bruno, "549111", "pagó katia 30 en portugal", TODAY, llm_client=fake)
    mv = await _last(db_session)
    assert mv.stop_slug == "portugal"
    assert mv.split == "other_only"


async def test_split_explicito_se_respeta(db_session):
    """Si el mensaje pide split individual explícito, no lo pisa el default."""
    _, katia = await _setup(db_session)
    # Katia en Pititas dice "compartido" via other_only explícito no aplica; el
    # caso real es payer_only explícito: se mantiene tal cual.
    fake = FakeLLM(_payload(split="payer_only", paid_by="bruno"))
    await handle_capture(db_session, katia, "549222", "cena 30 solo bruno", TODAY, llm_client=fake)
    mv = await _last(db_session)
    assert mv.split == "payer_only"


async def test_parada_comun_sigue_5050(db_session):
    """Sin dueño, el default no cambia: 50/50 como en todo el viaje."""
    _, katia = await _setup(db_session)
    fake = FakeLLM(_payload(city="París"))
    await handle_capture(db_session, katia, "549222", "cena 30 en paris", TODAY, llm_client=fake)
    mv = await _last(db_session)
    assert mv.stop_slug == "paris"
    assert mv.split == "shared"


async def test_batch_aplica_el_default_por_parada(db_session):
    """El multi-gasto también respeta el dueño de la parada por ítem."""
    _, katia = await _setup(db_session)
    payload = _payload(expenses=[
        _payload(amount="30", description="cena"),
        _payload(amount="12", description="taxi", category="Transporte"),
    ])
    await handle_capture(db_session, katia, "549222", "cena 30, taxi 12", TODAY, llm_client=FakeLLM(payload))
    movs = (await db_session.execute(select(Movement).order_by(Movement.id))).scalars().all()
    assert len(movs) == 2
    assert all(m.stop_slug == "pititas" for m in movs)
    assert all(m.split == "payer_only" for m in movs)
