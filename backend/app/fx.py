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


def fx_reference_date(payment_date: date | None, today: date) -> date:
    """Fecha cuyo TC aplica a un movimiento: payment_date pasada → esa (histórico
    Frankfurter, ya cacheado por fecha en FxRate); futura o NULL → hoy (TC proxy
    de la fecha de carga, la regla de siempre). Limitación ARS: dolarapi solo
    publica MEP vivo, así que un movimiento en ARS siempre usa la tasa del día
    en que se procesa (get_rate_to_usd fuerza cache_date=today)."""
    return min(payment_date or today, today)


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


def map_fx_source(src: str, currency: str) -> str:
    """`src` crudo de get_rate_to_usd → el valor que se persiste en fx_source."""
    if src == "fallback":
        return "fallback"
    if src == "direct" or currency.upper() == "USD":
        return "direct"
    if currency.upper() == "ARS":
        return "dolarapi"
    return "frankfurter"


def is_rate_locked(mv) -> bool:
    """Un movimiento cuya tasa NO se re-consulta al recalcular el monto:

    - `fx_source == 'manual'`: invariante 6, una tasa tipeada a mano nunca se pisa.
    - `status == 'awaiting'`: `due.py` ya fijó el TC real al vencer, una sola vez.
      Recalcularlo lo rompe justo en ARS, donde `get_rate_to_usd` fuerza
      `cache_date=today` y devolvería el MEP de hoy en vez del del vencimiento.
    """
    return mv.fx_source == "manual" or mv.status == "awaiting"


async def reprice_movement(
    session: AsyncSession,
    mv,
    net: Decimal,
    on_date: date,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[Decimal, Decimal, str]:
    """(amount_usd, fx_rate, fx_source) para un movimiento existente cuyo neto cambió.

    Política única de re-precio, compartida por la API, el editor del bot y el
    recálculo de un batch. Sobre `convert_to_usd` agrega dos guardas:

    1. Tasa lockeada (`is_rate_locked`) → se recalcula el monto con la tasa guardada.
    2. Proveedor caído (`src == 'fallback'`) con una tasa buena ya guardada → se
       conserva la buena. Sin esto, corregir un typo de monto con Frankfurter/
       dolarapi abajo pisaba el histórico con la tasa de emergencia y no se
       reintentaba nunca. Es la misma guarda que `due.py` aplica al liquidar.
    """
    if is_rate_locked(mv):
        rate = Decimal(mv.fx_rate)
        return (net * rate).quantize(_TWO, rounding=ROUND_HALF_UP), rate, mv.fx_source

    amount_usd, rate, src = await convert_to_usd(session, net, mv.currency, on_date, client=client)
    if src == "fallback" and mv.fx_rate is not None and mv.fx_source != "fallback":
        rate = Decimal(mv.fx_rate)
        return (net * rate).quantize(_TWO, rounding=ROUND_HALF_UP), rate, mv.fx_source
    return amount_usd, rate, map_fx_source(src, mv.currency)
