from datetime import date

import httpx
from sqlalchemy import select

from app.andiamo import sync_stops
from app.db.models import Stop

_STOPS = [
    {"slug": "londres", "order": 1, "name": "Londres", "country": "Reino Unido",
     "countryFlag": "🇬🇧", "arrivalDate": "2026-08-05", "departureDate": "2026-08-13",
     "currencyCode": "GBP", "timezone": "Europe/London",
     "isTransit": False, "isCandidate": False, "isFlexMargin": False},
    {"slug": "paris", "order": 6, "name": "París", "country": "Francia",
     "countryFlag": "🇫🇷", "arrivalDate": "2026-08-29", "departureDate": "2026-09-04",
     "currencyCode": "EUR", "timezone": "Europe/Paris",
     "isTransit": False, "isCandidate": False, "isFlexMargin": False},
]


def _client(payload, status=200):
    def handler(request):
        return httpx.Response(status, json=payload)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://andiamo")


async def test_sync_upserts(db_session, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("ANDIAMO_URL", "http://andiamo")
    get_settings.cache_clear()
    async with _client(_STOPS) as c:
        n = await sync_stops(db_session, client=c)
    assert n == 2
    rows = (await db_session.execute(select(Stop).order_by(Stop.order))).scalars().all()
    assert rows[0].slug == "londres"
    assert rows[0].currency_code == "GBP"
    assert rows[0].timezone == "Europe/London"
    assert rows[0].arrival_date == date(2026, 8, 5)
    # Idempotente
    async with _client(_STOPS) as c:
        await sync_stops(db_session, client=c)
    assert len((await db_session.execute(select(Stop))).scalars().all()) == 2
    get_settings.cache_clear()


async def test_sync_returns_zero_on_error(db_session, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("ANDIAMO_URL", "http://andiamo")
    get_settings.cache_clear()
    async with _client({}, status=500) as c:
        n = await sync_stops(db_session, client=c)
    assert n == 0
    get_settings.cache_clear()
