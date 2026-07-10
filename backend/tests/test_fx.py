from datetime import date
from decimal import Decimal

import httpx

from app.fx import convert_to_usd, get_rate_to_usd


def _mock_client(rate: float | None):
    def handler(request: httpx.Request) -> httpx.Response:
        if rate is None:
            return httpx.Response(500)
        return httpx.Response(200, json={"rates": {"USD": rate}})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _mock_mep_client(venta: float | None):
    def handler(request: httpx.Request) -> httpx.Response:
        if venta is None:
            return httpx.Response(500)
        assert "dolares/bolsa" in str(request.url)
        return httpx.Response(200, json={
            "moneda": "USD", "casa": "bolsa", "compra": venta - 20, "venta": venta,
        })

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_usd_is_identity(db_session):
    rate, source = await get_rate_to_usd(db_session, "USD", date(2026, 8, 6))
    assert rate == Decimal("1")
    assert source == "direct"


async def test_frankfurter_hit_and_cache(db_session):
    async with _mock_client(1.27) as client:
        rate, source = await get_rate_to_usd(db_session, "GBP", date(2026, 8, 6), client=client)
    assert rate == Decimal("1.27")
    assert source == "frankfurter"
    # Segunda llamada: viene de cache (sin cliente => no red).
    rate2, source2 = await get_rate_to_usd(db_session, "GBP", date(2026, 8, 6))
    assert rate2 == Decimal("1.27")
    assert source2 == "cache"


async def test_fallback_on_api_error(db_session):
    async with _mock_client(None) as client:
        rate, source = await get_rate_to_usd(db_session, "EUR", date(2026, 8, 6), client=client)
    assert source == "fallback"
    assert rate == Decimal("1.08")


async def test_ars_uses_dolarapi_mep(db_session):
    # ARS no está en Frankfurter: va directo a dolarapi (MEP) -> 1/venta.
    async with _mock_mep_client(1600.0) as client:
        rate, source = await get_rate_to_usd(db_session, "ARS", date(2026, 8, 6), client=client)
    assert source == "dolarapi"
    assert rate == Decimal("0.000625")  # 1/1600
    # Segunda llamada: cache.
    rate2, source2 = await get_rate_to_usd(db_session, "ARS", date(2026, 8, 6))
    assert (rate2, source2) == (Decimal("0.000625"), "cache")


async def test_ars_fallback_on_dolarapi_error(db_session):
    async with _mock_mep_client(None) as client:
        rate, source = await get_rate_to_usd(db_session, "ARS", date(2026, 8, 6), client=client)
    assert source == "fallback"


async def test_convert_rounds_to_2dp(db_session):
    async with _mock_client(1.27) as client:
        amount_usd, rate, source = await convert_to_usd(
            db_session, Decimal("45.00"), "GBP", date(2026, 8, 6), client=client
        )
    assert amount_usd == Decimal("57.15")
    assert rate == Decimal("1.27")
