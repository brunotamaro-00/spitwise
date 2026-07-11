from datetime import date

from app.bot.active_stop import resolve_active_stop, set_active_stop_override


async def test_default_no_stop(db_session):
    slug, city, cur = await resolve_active_stop(db_session, "549110", date(2026, 8, 6))
    assert (slug, city, cur) == (None, None, "USD")


async def test_override_used(db_session):
    await set_active_stop_override(db_session, "549110", "paris", "París", "EUR")
    slug, city, cur = await resolve_active_stop(db_session, "549110", date(2026, 8, 6))
    assert (slug, city, cur) == ("paris", "París", "EUR")
