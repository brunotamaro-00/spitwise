"""Reconciliación del sync: archivar stops borrados en Andiamo con movimientos,
borrar los que no tienen, desarchivar los que reaparecen."""

from datetime import date
from decimal import Decimal

import httpx
from sqlalchemy import select

from app.andiamo import sync_stops
from app.db.models import Movement, Stop, User

_LONDRES = {
    "slug": "londres", "order": 1, "name": "Londres", "country": "Reino Unido",
    "countryFlag": "🇬🇧", "arrivalDate": "2026-08-05", "departureDate": "2026-08-13",
    "currencyCode": "GBP", "timezone": "Europe/London",
    "isTransit": False, "isCandidate": False, "isFlexMargin": False,
}
_PARIS = {
    "slug": "paris", "order": 6, "name": "París", "country": "Francia",
    "countryFlag": "🇫🇷", "arrivalDate": "2026-08-29", "departureDate": "2026-09-04",
    "currencyCode": "EUR", "timezone": "Europe/Paris",
    "isTransit": False, "isCandidate": False, "isFlexMargin": False,
}


def _client(payload, status=200):
    def handler(request):
        return httpx.Response(status, json=payload)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://andiamo")


async def _seed_movement(session, slug: str, city: str) -> None:
    user = (await session.execute(select(User))).scalars().first()
    if user is None:
        user = User(username="bruno")
        session.add(user)
        await session.flush()
    session.add(Movement(
        type="expense", amount=Decimal("10"), currency="USD", amount_usd=Decimal("10"),
        fx_rate=Decimal("1"), fx_source="manual", paid_by=user.id, split="shared",
        stop_slug=slug, city_name=city,  created_by=user.id,
    ))
    await session.commit()


async def _sync(session, payload, status=200):
    async with _client(payload, status=status) as c:
        return await sync_stops(session, client=c)


async def _stops_by_slug(session) -> dict[str, Stop]:
    return {s.slug: s for s in (await session.execute(select(Stop))).scalars().all()}


async def test_missing_stop_with_movements_is_archived(db_session, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("ANDIAMO_URL", "http://andiamo")
    get_settings.cache_clear()

    await _sync(db_session, [_LONDRES, _PARIS])
    await _seed_movement(db_session, "paris", "París")

    result = await _sync(db_session, [_LONDRES])  # paris desapareció
    assert result["status"] == "ok"
    assert result["archived"] == 1
    assert result["deleted"] == 0

    stops = await _stops_by_slug(db_session)
    assert stops["paris"].is_archived is True
    assert stops["londres"].is_archived is False
    # Los movimientos siguen intactos.
    movs = (await db_session.execute(select(Movement))).scalars().all()
    assert len(movs) == 1 and movs[0].stop_slug == "paris"
    get_settings.cache_clear()


async def test_missing_stop_without_movements_is_deleted(db_session, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("ANDIAMO_URL", "http://andiamo")
    get_settings.cache_clear()

    await _sync(db_session, [_LONDRES, _PARIS])
    result = await _sync(db_session, [_LONDRES])
    assert result["deleted"] == 1
    assert result["archived"] == 0
    assert set((await _stops_by_slug(db_session)).keys()) == {"londres"}
    get_settings.cache_clear()


async def test_empty_payload_never_touches_snapshot(db_session, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("ANDIAMO_URL", "http://andiamo")
    get_settings.cache_clear()

    await _sync(db_session, [_LONDRES, _PARIS])
    result = await _sync(db_session, [])
    assert result["archived"] == 0 and result["deleted"] == 0
    stops = await _stops_by_slug(db_session)
    assert set(stops.keys()) == {"londres", "paris"}
    assert not any(s.is_archived for s in stops.values())
    get_settings.cache_clear()


async def test_fetch_failure_never_touches_snapshot(db_session, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("ANDIAMO_URL", "http://andiamo")
    get_settings.cache_clear()

    await _sync(db_session, [_LONDRES, _PARIS])
    result = await _sync(db_session, {}, status=500)
    assert result["status"] == "fetch_failed"
    assert set((await _stops_by_slug(db_session)).keys()) == {"londres", "paris"}
    get_settings.cache_clear()


async def test_reappearing_slug_is_unarchived(db_session, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("ANDIAMO_URL", "http://andiamo")
    get_settings.cache_clear()

    await _sync(db_session, [_LONDRES, _PARIS])
    await _seed_movement(db_session, "paris", "París")
    await _sync(db_session, [_LONDRES])  # archiva paris
    result = await _sync(db_session, [_LONDRES, _PARIS])  # paris vuelve
    assert result["status"] == "ok"
    stops = await _stops_by_slug(db_session)
    assert stops["paris"].is_archived is False
    get_settings.cache_clear()
