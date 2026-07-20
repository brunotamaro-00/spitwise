"""Stop local Pititas: Katia imputa a Pititas del 4 al 11 de sept, Bruno a Portugal.

Andiamo no sabe que Pititas existe: ni la reconciliación del sync ni el contrato
de /cities/spend deben verla.
"""
from datetime import date

import pytest
from sqlalchemy import select

from app.andiamo import sync_stops
from app.bot.active_stop import place_for_date, stop_for_date
from app.db.models import Movement, Stop, User

PORTUGAL = dict(
    slug="portugal", order=7, name="Portugal", country="Portugal", currency_code="EUR",
    timezone="Europe/Lisbon", arrival_date=date(2026, 9, 4), departure_date=date(2026, 9, 12),
)
ESTRASBURGO = dict(
    slug="estrasburgo", order=8, name="Estrasburgo", country="Francia", currency_code="EUR",
    timezone="Europe/Paris", arrival_date=date(2026, 9, 12), departure_date=date(2026, 9, 14),
)


async def _seed(session):
    session.add_all([
        Stop(**PORTUGAL),
        Stop(**ESTRASBURGO),
        Stop(slug="pititas", order=7, name="Pititas", country_flag="👭", currency_code="EUR",
             timezone="Europe/Paris", arrival_date=date(2026, 9, 4),
             departure_date=date(2026, 9, 12), is_local=True, owner_username="katia"),
    ])
    await session.commit()


# --- Imputación por remitente -------------------------------------------------

@pytest.mark.parametrize("d", [date(2026, 9, 4), date(2026, 9, 6), date(2026, 9, 11)])
async def test_katia_imputa_a_pititas_durante_el_tramo(db_session, d):
    await _seed(db_session)
    stop = await place_for_date(db_session, d, "katia")
    assert (stop.slug, stop.currency_code) == ("pititas", "EUR")


@pytest.mark.parametrize("d", [date(2026, 9, 4), date(2026, 9, 6), date(2026, 9, 11)])
async def test_bruno_imputa_a_portugal_en_el_mismo_tramo(db_session, d):
    await _seed(db_session)
    stop = await place_for_date(db_session, d, "bruno")
    assert stop.slug == "portugal"


async def test_el_12_es_estrasburgo_para_los_dos(db_session):
    await _seed(db_session)
    for who in ("katia", "bruno"):
        stop = await place_for_date(db_session, date(2026, 9, 12), who)
        assert stop.slug == "estrasburgo", who


async def test_antes_del_4_pititas_no_aplica(db_session):
    await _seed(db_session)
    session_stop = await place_for_date(db_session, date(2026, 9, 3), "katia")
    # 3-sept cae fuera de Portugal (arrival 4) y de Pititas: sin ciudad.
    assert session_stop is None


async def test_sin_username_nunca_cae_en_una_parada_ajena(db_session):
    await _seed(db_session)
    stop = await place_for_date(db_session, date(2026, 9, 6))
    assert stop.slug == "portugal"


async def test_gap_sin_itinerario_desempata_por_dueño(db_session):
    """Portugal y Pititas arrancan el mismo día: en un hueco del itinerario, la
    última arribada de Katia tiene que ser Pititas, no un empate arbitrario."""
    session_stops = [
        Stop(**PORTUGAL),
        Stop(slug="pititas", order=7, name="Pititas", currency_code="EUR",
             timezone="Europe/Paris", arrival_date=date(2026, 9, 4),
             departure_date=date(2026, 9, 12), is_local=True, owner_username="katia"),
    ]
    db_session.add_all(session_stops)
    await db_session.commit()
    from app.bot.active_stop import stop_for_date

    # 20-sept: ya salieron de todo, no hay stop siguiente => última arribada.
    assert (await stop_for_date(db_session, date(2026, 9, 20), "katia")).slug == "pititas"
    assert (await stop_for_date(db_session, date(2026, 9, 20), "bruno")).slug == "portugal"


async def test_active_stop_de_katia_es_pititas(db_session):
    await _seed(db_session)
    stop = await stop_for_date(db_session, date(2026, 9, 6), "katia")
    assert (stop.slug, stop.name, stop.currency_code) == ("pititas", "Pititas", "EUR")


async def test_timezone_por_usuario(db_session):
    """El 'hoy' de Katia lo define Paris, no Lisboa (una hora atrás)."""
    await _seed(db_session)
    # El probe usa la fecha real, así que solo verificamos el ruteo por owner
    # con una fecha dentro del tramo vía stop_for_date.
    from app.bot.active_stop import stop_for_date
    assert (await stop_for_date(db_session, date(2026, 9, 6), "katia")).timezone == "Europe/Paris"
    assert (await stop_for_date(db_session, date(2026, 9, 6), "bruno")).timezone == "Europe/Lisbon"


# --- El sync de Andiamo no toca los stops locales -----------------------------

class _FakeResp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


class _FakeClient:
    """Andiamo devuelve el itinerario real: Pititas nunca está en el payload."""

    def __init__(self, payload):
        self._p = payload

    async def get(self, *a, **k):
        return _FakeResp(self._p)


_ANDIAMO_PAYLOAD = [
    {"slug": "portugal", "order": 7, "name": "Portugal", "country": "Portugal",
     "currencyCode": "EUR", "timezone": "Europe/Lisbon",
     "arrivalDate": "2026-09-04", "departureDate": "2026-09-12"},
    {"slug": "estrasburgo", "order": 8, "name": "Estrasburgo", "country": "Francia",
     "currencyCode": "EUR", "timezone": "Europe/Paris",
     "arrivalDate": "2026-09-12", "departureDate": "2026-09-14"},
]


async def test_sync_no_borra_ni_archiva_el_stop_local(db_session):
    """La regresión más peligrosa: Andiamo pushea en cada edición del itinerario
    y la reconciliación borra todo lo que no venga en el payload."""
    await _seed(db_session)

    res = await sync_stops(db_session, client=_FakeClient(_ANDIAMO_PAYLOAD))

    assert res["status"] == "ok"
    assert res["deleted"] == 0 and res["archived"] == 0
    pititas = (
        await db_session.execute(select(Stop).where(Stop.slug == "pititas"))
    ).scalar_one()
    assert pititas.is_local is True
    assert pititas.is_archived is False
    assert pititas.owner_username == "katia"


async def test_sync_sigue_archivando_stops_de_andiamo(db_session):
    """No romper el contrato existente: un stop de Andiamo que desaparece y tiene
    gastos se archiva como siempre."""
    await _seed(db_session)
    db_session.add(User(id=1, username="bruno"))
    db_session.add(Movement(
        type="expense", amount=10, currency="EUR", amount_usd=11, fx_rate=1.1,
        paid_by=1, created_by=1, stop_slug="estrasburgo", city_name="Estrasburgo",
    ))
    await db_session.commit()

    # Andiamo borró Estrasburgo del itinerario.
    res = await sync_stops(db_session, client=_FakeClient(_ANDIAMO_PAYLOAD[:1]))

    assert res["archived"] == 1
    estras = (
        await db_session.execute(select(Stop).where(Stop.slug == "estrasburgo"))
    ).scalar_one()
    assert estras.is_archived is True
