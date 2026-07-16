"""Seed del stop local Pititas: idempotente y apagado por default."""
from datetime import date

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.db.models import Stop
from app.stops_local import PITITAS_SLUG, seed_local_stops


@pytest.fixture
def owner(monkeypatch):
    monkeypatch.setenv("PITITAS_OWNER", "katia")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _seed_portugal(session):
    session.add(Stop(slug="portugal", order=7, name="Portugal", currency_code="EUR",
                     arrival_date=date(2026, 9, 4), departure_date=date(2026, 9, 12)))
    await session.commit()


async def test_sin_owner_no_siembra_nada(db_session):
    get_settings.cache_clear()
    await seed_local_stops(db_session)
    assert (await db_session.execute(select(func.count()).select_from(Stop))).scalar_one() == 0


async def test_siembra_pititas(db_session, owner):
    await _seed_portugal(db_session)
    await seed_local_stops(db_session)

    s = (await db_session.execute(select(Stop).where(Stop.slug == PITITAS_SLUG))).scalar_one()
    assert s.name == "Pititas"
    assert s.country_flag == "😊"
    assert s.currency_code == "EUR"
    assert s.timezone == "Europe/Paris"
    assert s.is_local is True
    assert s.owner_username == "katia"
    # departure exclusivo => cubre 4..11 sept.
    assert (s.arrival_date, s.departure_date) == (date(2026, 9, 4), date(2026, 9, 12))
    # Queda pegada a Portugal en el recorrido.
    assert s.order == 7


async def test_seed_es_idempotente(db_session, owner):
    await _seed_portugal(db_session)
    await seed_local_stops(db_session)
    await seed_local_stops(db_session)

    n = (
        await db_session.execute(
            select(func.count()).select_from(Stop).where(Stop.slug == PITITAS_SLUG)
        )
    ).scalar_one()
    assert n == 1


async def test_sin_snapshot_usa_orden_de_fallback(db_session, owner):
    """Si Andiamo todavía no sincronizó, el seed no explota: usa el fallback y
    el próximo arranque lo corrige."""
    await seed_local_stops(db_session)
    s = (await db_session.execute(select(Stop).where(Stop.slug == PITITAS_SLUG))).scalar_one()
    assert s.order == 7
