import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Movement, Stop
from app.trip_time import utcnow_naive

logger = logging.getLogger(__name__)


def _parse_date(v: str | None) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        return None


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


async def sync_stops(session: AsyncSession, *, client: httpx.AsyncClient | None = None) -> dict:
    """Sync itinerario. Retorna {synced, archived, deleted, status, errors}.

    status: ok | fetch_failed | partial

    Reconciliación: stops que ya no están en Andiamo se archivan si tienen
    movimientos (los gastos nunca se pierden) o se borran si no. Solo corre
    con status ok y payload no vacío: un payload vacío o parcial jamás debe
    arrasar el snapshot.

    Los stops locales (is_local) viven fuera de este contrato: no existen en
    Andiamo, así que el sync nunca los pisa ni los reconcilia.
    """
    try:
        data = await fetch_stops(client=client)
    except Exception:
        logger.warning("andiamo_sync_failed; usando snapshot existente")
        return {"synced": 0, "archived": 0, "deleted": 0, "status": "fetch_failed", "errors": ["fetch_failed"]}

    if not isinstance(data, list):
        logger.warning("andiamo_sync_bad_payload type=%s", type(data).__name__)
        return {"synced": 0, "archived": 0, "deleted": 0, "status": "fetch_failed", "errors": ["bad_payload"]}

    existing = {s.slug: s for s in (await session.execute(select(Stop))).scalars().all()}
    n = 0
    errors: list[str] = []
    payload_slugs: set[str] = set()
    for item in data:
        try:
            slug = item["slug"]
            payload_slugs.add(slug)
            row = existing.get(slug) or Stop(slug=slug)
            # Un slug local homónimo nunca se pisa con datos de Andiamo.
            if row.is_local:
                continue
            row.order = item.get("order", 0)
            row.name = item.get("name", slug)
            row.country = item.get("country")
            row.country_flag = item.get("countryFlag")
            row.arrival_date = _parse_date(item.get("arrivalDate"))
            row.departure_date = _parse_date(item.get("departureDate"))
            row.currency_code = item.get("currencyCode")
            row.timezone = item.get("timezone")
            # Andiamo ya no expone isTransit: tránsito es implícito (0 noches).
            # departure es exclusivo, así que noches = departure - arrival.
            row.is_transit = (
                row.arrival_date is not None
                and row.departure_date is not None
                and (row.departure_date - row.arrival_date).days == 0
            )
            row.is_candidate = bool(item.get("isCandidate"))
            row.is_flex_margin = bool(item.get("isFlexMargin"))
            # Si reaparece un slug archivado (recreado en Andiamo), se desarchiva.
            row.is_archived = False
            row.synced_at = utcnow_naive()
            if slug not in existing:
                session.add(row)
            n += 1
        except Exception as exc:
            errors.append(f"{item.get('slug', '?')}: {exc}")
            logger.warning("andiamo_sync_item_failed item=%s", item, exc_info=True)

    archived = deleted = 0
    if not errors and payload_slugs:
        missing = [
            s for slug, s in existing.items()
            if slug not in payload_slugs and not s.is_local
        ]
        for stop in missing:
            has_movements = (
                await session.execute(
                    select(func.count())
                    .select_from(Movement)
                    .where(Movement.stop_slug == stop.slug)
                )
            ).scalar_one() > 0
            if has_movements:
                if not stop.is_archived:
                    stop.is_archived = True
                    archived += 1
            else:
                await session.delete(stop)
                deleted += 1

    await session.commit()
    status = "partial" if errors else "ok"
    return {"synced": n, "archived": archived, "deleted": deleted, "status": status, "errors": errors}


_FRESH_TTL = timedelta(hours=6)
# Guardas in-process: válidas SOLO porque el deploy corre un único proceso
# uvicorn (ver DEPLOY.md — nunca --workers). _dirty coalesce webhooks que
# llegan mientras un sync está corriendo: se agenda exactamente un run más.
_refresh_running = False
_dirty = False


async def _background_refresh() -> None:
    global _refresh_running, _dirty
    from app.db.engine import get_sessionmaker
    try:
        maker = get_sessionmaker()
        while True:
            _dirty = False
            async with maker() as session:
                await sync_stops(session)
            if not _dirty:
                break
    except Exception:
        logger.warning("andiamo_lazy_refresh_failed", exc_info=True)
    finally:
        _refresh_running = False


async def ensure_stops_fresh(session: AsyncSession) -> None:
    """Refresh perezoso del snapshot (TTL 6h). Nunca bloquea: dispara un task y retorna."""
    global _refresh_running
    if _refresh_running or not get_settings().andiamo_url:
        return
    last = (await session.execute(select(func.max(Stop.synced_at)))).scalar_one_or_none()
    now = utcnow_naive()
    if last is not None:
        last_naive = last.replace(tzinfo=None) if last.tzinfo else last
        if now - last_naive < _FRESH_TTL:
            return
    _refresh_running = True
    asyncio.create_task(_background_refresh())


def force_sync_soon() -> None:
    """Sync inmediato en background (webhook de Andiamo). Ignora el TTL;
    nunca bloquea. Si ya hay un sync corriendo, marca _dirty para que ese
    mismo task corra una pasada más al terminar."""
    global _refresh_running, _dirty
    if not get_settings().andiamo_url:
        return
    if _refresh_running:
        _dirty = True
        return
    _refresh_running = True
    asyncio.create_task(_background_refresh())
