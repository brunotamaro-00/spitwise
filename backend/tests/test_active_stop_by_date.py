from datetime import date

from app.bot.active_stop import resolve_active_stop, resolve_trip_timezone, set_active_stop_override
from app.db.models import Stop


async def _seed_stops(session):
    session.add_all([
        Stop(slug="londres", order=1, name="Londres", currency_code="GBP",
             arrival_date=date(2026, 8, 5), departure_date=date(2026, 8, 13)),
        Stop(slug="paris", order=6, name="París", currency_code="EUR",
             arrival_date=date(2026, 8, 29), departure_date=date(2026, 9, 4)),
    ])
    await session.commit()


async def test_active_by_date_inside_range(db_session):
    await _seed_stops(db_session)
    slug, city, cur = await resolve_active_stop(db_session, "549110", date(2026, 8, 6))
    assert (slug, city, cur) == ("londres", "Londres", "GBP")


async def test_between_stops_uses_last_arrived(db_session):
    await _seed_stops(db_session)
    # 20-ago: ya salió de Londres, no llegó a París -> última con arrival<=today
    slug, city, cur = await resolve_active_stop(db_session, "549110", date(2026, 8, 20))
    assert slug == "londres"


async def test_override_beats_date(db_session):
    await _seed_stops(db_session)
    await set_active_stop_override(db_session, "549110", "paris", "París", "EUR")
    slug, city, cur = await resolve_active_stop(db_session, "549110", date(2026, 8, 6))
    assert slug == "paris"


async def test_trip_timezone_none_without_stops(db_session):
    assert await resolve_trip_timezone(db_session) is None
