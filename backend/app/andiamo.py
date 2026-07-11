import asyncio
import logging
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Stop

logger = logging.getLogger(__name__)


def _parse_date(v: str | None) -> date | None:
    return date.fromisoformat(v) if v else None


async def fetch_stops(*, client: httpx.AsyncClient | None = None) -> list[dict]:
    s = get_settings()
    url = f"{s.andiamo_url}/api/stops"
    headers = {"X-Api-Key": s.trip_shared_api_key}
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=10.0)
    try:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()
    finally:
        if owns:
            await client.aclose()


async def sync_stops(session: AsyncSession, *, client: httpx.AsyncClient | None = None) -> int:
    try:
        data = await fetch_stops(client=client)
    except Exception:
        logger.warning("andiamo_sync_failed; usando snapshot existente")
        return 0

    existing = {s.slug: s for s in (await session.execute(select(Stop))).scalars().all()}
    n = 0
    for item in data:
        slug = item["slug"]
        row = existing.get(slug) or Stop(slug=slug)
        row.order = item.get("order", 0)
        row.name = item.get("name", slug)
        row.country = item.get("country")
        row.country_flag = item.get("countryFlag")
        row.arrival_date = _parse_date(item.get("arrivalDate"))
        row.departure_date = _parse_date(item.get("departureDate"))
        row.currency_code = item.get("currencyCode")
        row.timezone = item.get("timezone")
        row.is_transit = bool(item.get("isTransit"))
        row.is_candidate = bool(item.get("isCandidate"))
        row.is_flex_margin = bool(item.get("isFlexMargin"))
        row.synced_at = datetime.utcnow()
        if slug not in existing:
            session.add(row)
        n += 1
    await session.commit()
    return n


_FRESH_TTL = timedelta(hours=6)
_refresh_running = False


async def _background_refresh() -> None:
    global _refresh_running
    from app.db.engine import get_sessionmaker
    try:
        maker = get_sessionmaker()
        async with maker() as session:
            await sync_stops(session)
    except Exception:
        logger.warning("andiamo_lazy_refresh_failed", exc_info=True)
    finally:
        _refresh_running = False


async def ensure_stops_fresh(session: AsyncSession) -> None:
    """Refresh perezoso del snapshot (TTL 6h). Nunca bloquea: dispara un task y retorna."""
    global _refresh_running
    if _refresh_running:
        return
    last = (await session.execute(select(func.max(Stop.synced_at)))).scalar_one_or_none()
    if last is not None and datetime.utcnow() - last < _FRESH_TTL:
        return
    _refresh_running = True
    asyncio.create_task(_background_refresh())
