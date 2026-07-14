from datetime import date
from decimal import Decimal, ROUND_HALF_UP

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import FxRate

_TWO = Decimal("0.01")
_SIX = Decimal("0.000001")


async def _cached_rate(session: AsyncSession, currency: str, on_date: date) -> Decimal | None:
    row = (
        await session.execute(
            select(FxRate).where(FxRate.currency == currency, FxRate.rate_date == on_date)
        )
    ).scalar_one_or_none()
    return row.rate_to_usd if row else None


async def _store_rate(session: AsyncSession, currency: str, on_date: date, rate: Decimal) -> None:
    """Inserta la tasa; si ya existe (race), no lanza — el caller re-lee cache."""
    dialect = session.bind.dialect.name if session.bind is not None else ""
    if dialect == "postgresql":
        stmt = (
            pg_insert(FxRate)
            .values(currency=currency, rate_date=on_date, rate_to_usd=rate)
            .on_conflict_do_nothing(index_elements=["currency", "rate_date"])
        )
        await session.execute(stmt)
        await session.flush()
        return
    # SQLite (tests) y demás: insert + tolerar unique.
    try:
        async with session.begin_nested():
            session.add(FxRate(currency=currency, rate_date=on_date, rate_to_usd=rate))
            await session.flush()
    except IntegrityError:
        pass


def _fallback_rate(currency: str) -> Decimal:
    rates = get_settings().fx_fallback_rates
    return Decimal(rates.get(currency, "1.0"))


async def get_rate_to_usd(
    session: AsyncSession,
    currency: str,
    on_date: date,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[Decimal, str]:
    currency = currency.upper()
    if currency == "USD":
        return Decimal("1"), "direct"

    # ARS: dolarapi solo publica MEP vivo (hoy). Nunca cachear bajo fechas arbitrarias
    # ni reutilizar caches de otros días como si fueran históricos.
    cache_date = date.today() if currency == "ARS" else on_date

    cached = await _cached_rate(session, currency, cache_date)
    if cached is not None:
        return cached, "cache"

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=10.0)
    try:
        if currency == "ARS":
            # Frankfurter (ECB) no publica ARS: usamos dólar MEP (dolarapi).
            resp = await client.get(f"{get_settings().dolarapi_url}/dolares/bolsa")
            resp.raise_for_status()
            venta = Decimal(str(resp.json()["venta"]))
            rate = (Decimal("1") / venta).quantize(_SIX, rounding=ROUND_HALF_UP)
            source = "dolarapi"
        else:
            url = f"{get_settings().frankfurter_url}/{on_date.isoformat()}"
            resp = await client.get(url, params={"base": currency, "symbols": "USD"})
            resp.raise_for_status()
            rate = Decimal(str(resp.json()["rates"]["USD"]))
            source = "frankfurter"
        await _store_rate(session, currency, cache_date, rate)
        # Si hubo race y otro proceso ganó el insert, devolver lo cacheado.
        cached_after = await _cached_rate(session, currency, cache_date)
        if cached_after is not None:
            return cached_after, source
        return rate, source
    except Exception:
        return _fallback_rate(currency), "fallback"
    finally:
        if owns_client:
            await client.aclose()


async def convert_to_usd(
    session: AsyncSession,
    amount: Decimal,
    currency: str,
    on_date: date,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[Decimal, Decimal, str]:
    rate, source = await get_rate_to_usd(session, currency, on_date, client=client)
    amount_usd = (amount * rate).quantize(_TWO, rounding=ROUND_HALF_UP)
    return amount_usd, rate, source
