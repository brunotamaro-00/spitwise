"""Seed del stop local Pititas: idempotente y apagado por default."""
from datetime import date

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.db.models import Stop, User
from app.stops_local import PITITAS_SLUG, seed_local_stops


@pytest.fixture
def owner(monkeypatch):
    monkeypatch.setenv("PITITAS_OWNER", "katia")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def no_owner(monkeypatch):
    """Sin owner configurado, de verdad.

    `Settings` lee `env_file=".env"`, así que limpiar la caché no alcanza: en la
    máquina de desarrollo el `.env` real trae `PITITAS_OWNER=katia` y el test
    veía un owner que no había pedido. Pasaba en CI (donde no hay `.env`) y
    fallaba local — el peor modo de fallo para una suite que se corre a mano.
    La env var explícita gana sobre el dotenv, así que esto lo fija en los dos.
    """
    monkeypatch.setenv("PITITAS_OWNER", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _seed_portugal(session):
    session.add(Stop(slug="portugal", order=7, name="Portugal", currency_code="EUR",
                     arrival_date=date(2026, 9, 4), departure_date=date(2026, 9, 12)))
    await session.commit()


async def test_sin_owner_no_siembra_nada(db_session, no_owner):
    await seed_local_stops(db_session)
    assert (await db_session.execute(select(func.count()).select_from(Stop))).scalar_one() == 0


async def test_siembra_pititas(db_session, owner):
    await _seed_portugal(db_session)
    await seed_local_stops(db_session)

    s = (await db_session.execute(select(Stop).where(Stop.slug == PITITAS_SLUG))).scalar_one()
    assert s.name == "Pititas"
    assert s.country_flag == "👭"
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


async def _seed_users(session):
    session.add_all([User(username="bruno"), User(username="katia")])
    await session.commit()


async def test_contraparte_imputa_a_bruno_las_paradas_contenidas(db_session, owner):
    """El reverso de Pititas: la parada común que cae entera en el tramo de
    Katia (Pititas) es solo de Bruno, para que ella no la vea en /ciudades."""
    await _seed_users(db_session)
    # Portugal: entero dentro de 4..12 sept (la ventana de Pititas) => de Bruno.
    session_add = Stop(slug="lisboa", order=7, name="Lisboa", currency_code="EUR",
                       arrival_date=date(2026, 9, 4), departure_date=date(2026, 9, 12))
    db_session.add(session_add)
    # Barcelona: solapa apenas una punta (termina el 5) => la vivieron los dos.
    db_session.add(Stop(slug="barcelona", order=6, name="Barcelona", currency_code="EUR",
                        arrival_date=date(2026, 9, 1), departure_date=date(2026, 9, 5)))
    await db_session.commit()

    await seed_local_stops(db_session)

    lisboa = (await db_session.execute(select(Stop).where(Stop.slug == "lisboa"))).scalar_one()
    barcelona = (await db_session.execute(select(Stop).where(Stop.slug == "barcelona"))).scalar_one()
    assert lisboa.owner_username == "bruno"
    assert barcelona.owner_username is None


async def test_contraparte_se_libera_si_deja_de_solapar(db_session, owner):
    """Si Andiamo mueve una parada fuera del tramo, deja de ser exclusiva."""
    await _seed_users(db_session)
    db_session.add(Stop(slug="lisboa", order=7, name="Lisboa", currency_code="EUR",
                        arrival_date=date(2026, 9, 4), departure_date=date(2026, 9, 12),
                        owner_username="bruno"))
    await db_session.commit()
    # Ahora Lisboa arranca en octubre: ya no solapa Pititas.
    lisboa = (await db_session.execute(select(Stop).where(Stop.slug == "lisboa"))).scalar_one()
    lisboa.arrival_date = date(2026, 10, 1)
    lisboa.departure_date = date(2026, 10, 6)
    await db_session.commit()

    await seed_local_stops(db_session)
    lisboa = (await db_session.execute(select(Stop).where(Stop.slug == "lisboa"))).scalar_one()
    assert lisboa.owner_username is None


async def test_sin_snapshot_usa_orden_de_fallback(db_session, owner):
    """Si Andiamo todavía no sincronizó, el seed no explota: usa el fallback y
    el próximo arranque lo corrige."""
    await seed_local_stops(db_session)
    s = (await db_session.execute(select(Stop).where(Stop.slug == PITITAS_SLUG))).scalar_one()
    assert s.order == 7
