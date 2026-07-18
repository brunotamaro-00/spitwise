from datetime import date

from app.bot.active_stop import resolve_trip_timezone, stop_for_date
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
    stop = await stop_for_date(db_session, date(2026, 8, 6))
    assert (stop.slug, stop.name, stop.currency_code) == ("londres", "Londres", "GBP")


async def test_between_stops_uses_last_arrived(db_session):
    await _seed_stops(db_session)
    # 20-ago: ya salió de Londres, no llegó a París -> última con arrival<=today
    stop = await stop_for_date(db_session, date(2026, 8, 20))
    assert stop.slug == "londres"


async def test_trip_timezone_none_without_stops(db_session):
    assert await resolve_trip_timezone(db_session) is None
