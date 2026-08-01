"""Sync del contenido de viaje de Andiamo (guías markdown + notas + documentos).

Espejo de andiamo.py (stops) pero para la base de conocimiento del Q&A de
viaje del bot. Deliberadamente módulo aparte: el sync de stops corre en el
path caliente del webhook y no se toca; este solo se dispara desde el
lifespan, el sync-hook y el handler de trip_question (lazy, no bloqueante).
"""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import GuideDoc, StopGuide, SyncMeta, TripDocument, TripNote

logger = logging.getLogger(__name__)

_GUIDES_VERSION_KEY = "guides_version"


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_dt(v: str | None) -> datetime | None:
    if not v:
        return None
    try:
        parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed


def _parse_date(v: str | None) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        return None


async def fetch_guides_export(*, client: httpx.AsyncClient | None = None) -> dict:
    s = get_settings()
    url = f"{s.andiamo_url}/api/guides/export"
    headers = {"X-Api-Key": s.trip_shared_api_key}
    owns = client is None
    if owns:
        # ~3MB de markdown: timeout más generoso que el sync de stops.
        client = httpx.AsyncClient(timeout=30.0)
    try:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()
    finally:
        if owns:
            await client.aclose()


async def fetch_notes(*, client: httpx.AsyncClient | None = None) -> list[dict]:
    s = get_settings()
    url = f"{s.andiamo_url}/api/notes"
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


async def fetch_documents(*, client: httpx.AsyncClient | None = None) -> list[dict]:
    s = get_settings()
    url = f"{s.andiamo_url}/api/integration/documents"
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


async def sync_guides(session: AsyncSession, *, client: httpx.AsyncClient | None = None) -> dict:
    """Sync de guías. Retorna {synced, deleted, status}.

    status: ok | unchanged | fetch_failed

    No-op si la version del export coincide con la última sincronizada.
    Reconciliación total (los docs no tienen FKs): upsert por
    (guide_slug, doc_slug), borrado de ausentes y reemplazo completo de
    stop_guides. Un payload vacío o inválido jamás arrasa el snapshot.
    """
    try:
        data = await fetch_guides_export(client=client)
    except Exception:
        logger.warning("andiamo_guides_sync_failed; usando snapshot existente")
        return {"synced": 0, "deleted": 0, "status": "fetch_failed"}

    docs = data.get("docs") if isinstance(data, dict) else None
    version = data.get("version", "") if isinstance(data, dict) else ""
    if not isinstance(docs, list) or not docs:
        logger.warning("andiamo_guides_sync_bad_payload")
        return {"synced": 0, "deleted": 0, "status": "fetch_failed"}

    meta = await session.get(SyncMeta, _GUIDES_VERSION_KEY)
    if meta is not None and version and meta.value == version:
        return {"synced": 0, "deleted": 0, "status": "unchanged"}

    existing = {
        (d.guide_slug, d.doc_slug): d
        for d in (await session.execute(select(GuideDoc))).scalars().all()
    }
    payload_keys: set[tuple[str, str]] = set()
    n = 0
    for item in docs:
        key = (item.get("guideSlug", ""), item.get("docSlug", ""))
        if not key[0] or not key[1]:
            continue
        payload_keys.add(key)
        row = existing.get(key) or GuideDoc(guide_slug=key[0], doc_slug=key[1])
        row.guide_title = item.get("guideTitle", key[0])
        row.title = item.get("title", key[1])
        row.country = item.get("country")
        row.kind = item.get("kind", "city")
        row.file = item.get("file", "")
        row.content_md = item.get("content", "")
        row.synced_at = _utcnow_naive()
        if key not in existing:
            session.add(row)
        n += 1

    deleted = 0
    for key, row in existing.items():
        if key not in payload_keys:
            await session.delete(row)
            deleted += 1

    stop_to_guides = data.get("stopToGuides")
    if isinstance(stop_to_guides, dict):
        await session.execute(delete(StopGuide))
        for stop_slug, guide_slugs in stop_to_guides.items():
            for position, guide_slug in enumerate(guide_slugs):
                session.add(StopGuide(stop_slug=stop_slug, guide_slug=guide_slug, position=position))

    if version:
        if meta is None:
            session.add(SyncMeta(key=_GUIDES_VERSION_KEY, value=version))
        else:
            meta.value = version

    await session.commit()
    return {"synced": n, "deleted": deleted, "status": "ok"}


async def sync_notes(session: AsyncSession, *, client: httpx.AsyncClient | None = None) -> dict:
    """Sync de notas: upsert por id + borrado de ausentes. Mismas garantías
    que sync_guides: fetch fallido o payload inválido no toca el snapshot.
    Payload vacío acá SÍ vacía la tabla (borrar la última nota es legítimo)."""
    try:
        data = await fetch_notes(client=client)
    except Exception:
        logger.warning("andiamo_notes_sync_failed; usando snapshot existente")
        return {"synced": 0, "deleted": 0, "status": "fetch_failed"}

    if not isinstance(data, list):
        logger.warning("andiamo_notes_sync_bad_payload type=%s", type(data).__name__)
        return {"synced": 0, "deleted": 0, "status": "fetch_failed"}

    existing = {n.id: n for n in (await session.execute(select(TripNote))).scalars().all()}
    payload_ids: set[str] = set()
    n = 0
    for item in data:
        note_id = item.get("id")
        if not note_id:
            continue
        payload_ids.add(note_id)
        row = existing.get(note_id) or TripNote(id=note_id)
        row.stop_slug = item.get("stopSlug")
        row.title = item.get("title", "")
        row.body = item.get("body", "")
        row.pinned = bool(item.get("pinned"))
        row.updated_at = _parse_dt(item.get("updatedAt"))
        row.synced_at = _utcnow_naive()
        if note_id not in existing:
            session.add(row)
        n += 1

    deleted = 0
    for note_id, row in existing.items():
        if note_id not in payload_ids:
            await session.delete(row)
            deleted += 1

    await session.commit()
    return {"synced": n, "deleted": deleted, "status": "ok"}


async def sync_documents(session: AsyncSession, *, client: httpx.AsyncClient | None = None) -> dict:
    """Sync de documentos (solo metadata): upsert por id + borrado de ausentes.
    Mismas garantías y misma asimetría que sync_notes: fetch fallido o payload
    inválido no toca el snapshot, pero una lista vacía SÍ vacía la tabla
    (borrar el último documento es legítimo)."""
    try:
        data = await fetch_documents(client=client)
    except Exception:
        logger.warning("andiamo_documents_sync_failed; usando snapshot existente")
        return {"synced": 0, "deleted": 0, "status": "fetch_failed"}

    if not isinstance(data, list):
        logger.warning("andiamo_documents_sync_bad_payload type=%s", type(data).__name__)
        return {"synced": 0, "deleted": 0, "status": "fetch_failed"}

    existing = {d.id: d for d in (await session.execute(select(TripDocument))).scalars().all()}
    payload_ids: set[str] = set()
    n = 0
    for item in data:
        doc_id = item.get("id")
        if not doc_id:
            continue
        payload_ids.add(doc_id)
        row = existing.get(doc_id) or TripDocument(id=doc_id)
        row.stop_slug = item.get("stopSlug")
        row.label = item.get("label", "")
        row.note = item.get("note")
        row.kind = item.get("kind") or "other"
        row.source = item.get("source") or "upload"
        row.doc_date = _parse_date(item.get("docDate"))
        row.file_name = item.get("fileName")
        row.mime_type = item.get("mimeType")
        row.created_at = _parse_dt(item.get("createdAt"))
        row.synced_at = _utcnow_naive()
        if doc_id not in existing:
            session.add(row)
        n += 1

    deleted = 0
    for doc_id, row in existing.items():
        if doc_id not in payload_ids:
            await session.delete(row)
            deleted += 1

    await session.commit()
    return {"synced": n, "deleted": deleted, "status": "ok"}


_CONTENT_FRESH_TTL = timedelta(hours=6)
# Guardas in-process: válidas SOLO por el proceso único de uvicorn (ver
# DEPLOY.md). Mismo patrón _dirty/coalescing que andiamo.py.
_refresh_running = False
_dirty = False
# Alcance de la pasada encolada: True = saltear guías (lo caro). Solo tiene
# sentido con `_dirty` en True; se acumula con AND sobre los pedidos que llegan.
_dirty_notes_only = False


async def _background_refresh(notes_only: bool = False) -> None:
    """notes_only=True saltea las guías (3MB de markdown) y sincroniza notas +
    documentos: los dos son metadata chica, cambian seguido y comparten evento
    de origen, así que no justifican un tercer flag de dirty."""
    global _refresh_running, _dirty, _dirty_notes_only
    from app.db.engine import get_sessionmaker
    try:
        maker = get_sessionmaker()
        while True:
            _dirty = False
            async with maker() as session:
                if not notes_only:
                    await sync_guides(session)
                await sync_notes(session)
                await sync_documents(session)
            if not _dirty:
                break
            # Alcance de la vuelta siguiente, según lo que se encoló mientras tanto.
            notes_only = _dirty_notes_only
    except Exception:
        logger.warning("andiamo_content_refresh_failed", exc_info=True)
    finally:
        _refresh_running = False


async def ensure_content_fresh(session: AsyncSession) -> None:
    """Refresh perezoso del contenido (TTL 6h). Nunca bloquea: dispara un task
    y retorna — el turno en curso usa el snapshot actual."""
    global _refresh_running
    if _refresh_running or not get_settings().andiamo_url:
        return
    last = (await session.execute(select(func.max(GuideDoc.synced_at)))).scalar_one_or_none()
    now = _utcnow_naive()
    if last is not None:
        last_naive = last.replace(tzinfo=None) if last.tzinfo else last
        if now - last_naive < _CONTENT_FRESH_TTL:
            return
    _refresh_running = True
    asyncio.create_task(_background_refresh())


def force_content_sync_soon(*, notes_only: bool = False) -> None:
    """Sync inmediato en background (sync-hook de Andiamo). Ignora el TTL;
    nunca bloquea. Con notes_only=True (eventos notes.changed / documents.changed)
    evita re-bajar los 3MB de guías y sincroniza solo notas + documentos."""
    global _refresh_running, _dirty, _dirty_notes_only
    if not get_settings().andiamo_url:
        return
    if _refresh_running:
        # La pasada extra baja guías salvo que TODOS los pedidos encolados sean
        # de notas. El AND arranca del primero: antes se acumulaba sobre un flag
        # que el propio loop ya había puesto en False, así que daba False
        # siempre y cada ping se bajaba las guías enteras.
        _dirty_notes_only = notes_only if not _dirty else (_dirty_notes_only and notes_only)
        _dirty = True
        return
    _refresh_running = True
    asyncio.create_task(_background_refresh(notes_only))
