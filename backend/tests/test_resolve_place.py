"""Resolución de ciudad con nombre explícito (`resolve_place`).

La ciudad de un movimiento SIEMPRE sale de un Stop real o es None: cuando el
match por nombre falla, el gasto cae en silencio a la parada de la fecha. Estos
tests cubren los dos casos donde fallaba sin que se notara.
"""
from datetime import date

from app.bot.capture import resolve_place
from app.db.models import Stop

TODAY = date(2026, 8, 20)


async def _stops(db_session, **over):
    base = dict(slug="zurich", name="Zúrich", order=1, currency_code="CHF",
                arrival_date=date(2026, 8, 1), departure_date=date(2026, 8, 5))
    base.update(over)
    db_session.add_all([
        Stop(**base),
        Stop(slug="lisboa", name="Lisboa", order=2, currency_code="EUR",
             arrival_date=date(2026, 8, 18), departure_date=date(2026, 8, 25)),
    ])
    await db_session.commit()


async def test_explicit_city_matches_without_accent(db_session):
    """El teclado del celular no siempre pone la tilde: 'Zurich' es 'Zúrich'.
    Sin folding, el match fallaba y el gasto iba a la parada de la fecha."""
    await _stops(db_session)
    slug, name, cur = await resolve_place(db_session, TODAY, "Zurich", "bruno")
    assert (slug, name, cur) == ("zurich", "Zúrich", "CHF")


async def test_explicit_city_matches_case_insensitive(db_session):
    await _stops(db_session)
    slug, _, _ = await resolve_place(db_session, TODAY, "  ZÚRICH ", "bruno")
    assert slug == "zurich"


async def test_explicit_city_ignores_archived_stop(db_session):
    """Una parada archivada no la ofrece el prompt ni la acepta la API web:
    matchearla acá resucitaba de atrás una ciudad que ya no existe."""
    await _stops(db_session, is_archived=True)
    slug, name, _ = await resolve_place(db_session, TODAY, "Zúrich", "bruno")
    # No matchea la archivada: cae a la parada de la fecha (Lisboa).
    assert (slug, name) == ("lisboa", "Lisboa")


async def test_unknown_city_falls_back_to_date_stop(db_session):
    """Day-trip: 'Sintra' no es parada, el gasto va a donde se duerme ese día."""
    await _stops(db_session)
    slug, name, _ = await resolve_place(db_session, TODAY, "Sintra", "bruno")
    assert (slug, name) == ("lisboa", "Lisboa")


async def test_no_city_out_of_range_is_general(db_session):
    await _stops(db_session)
    slug, name, cur = await resolve_place(db_session, date(2026, 12, 25), None, "bruno")
    assert (slug, name, cur) == (None, None, "USD")
