"""Alta de notas en Andiamo (POST /api/integration/notes).

Espejo de `andiamo_documents.py`: Andiamo es el dueño de las notas, Spitwise
solo dicta. Lo que se escribe acá vuelve al cache local por el sync
(`andiamo_content.sync_notes`), nunca por escritura directa a `trip_notes`.
"""
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class AndiamoNoteError(Exception):
    """Falla de alta (red o respuesta no-2xx). El mensaje es apto para logs,
    nunca para el usuario."""


async def create_note(*, title: str | None, body: str, stop_slug: str | None,
                      pinned: bool = False,
                      client: httpx.AsyncClient | None = None) -> dict:
    s = get_settings()
    if not s.andiamo_url:
        raise AndiamoNoteError("andiamo_url no configurada")
    url = f"{s.andiamo_url}/api/integration/notes"
    headers = {"X-Api-Key": s.trip_shared_api_key}
    payload = {"title": title or "", "body": body, "pinned": pinned}
    if stop_slug:
        payload["stopSlug"] = stop_slug

    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=10.0)
    try:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("andiamo_note_create_failed title=%r: %s", title, exc)
        raise AndiamoNoteError(str(exc)) from exc
    finally:
        if owns:
            await client.aclose()
