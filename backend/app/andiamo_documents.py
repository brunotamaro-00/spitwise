"""Subida de documentos a Andiamo (POST /api/integration/documents).

Espejo del patrón httpx + X-Api-Key de `andiamo.py`, pero de escritura: el bot
manda el binario en multipart y Andiamo es el único dueño del storage (R2).
"""
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class AndiamoUploadError(Exception):
    """Falla de subida (red o respuesta no-2xx). El mensaje es apto para logs,
    nunca para el usuario."""


async def upload_document(*, file_bytes: bytes, filename: str, mime_type: str,
                          label: str, note: str | None, kind: str,
                          stop_slug: str | None, doc_date: str | None,
                          client: httpx.AsyncClient | None = None) -> dict:
    s = get_settings()
    if not s.andiamo_url:
        raise AndiamoUploadError("andiamo_url no configurada")
    url = f"{s.andiamo_url}/api/integration/documents"
    headers = {"X-Api-Key": s.trip_shared_api_key}
    data = {"label": label, "kind": kind}
    if note:
        data["note"] = note
    if stop_slug:
        data["stopSlug"] = stop_slug
    if doc_date:
        data["docDate"] = doc_date
    files = {"file": (filename, file_bytes, mime_type)}

    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=30.0)
    try:
        resp = await client.post(url, data=data, files=files, headers=headers)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("andiamo_document_upload_failed label=%r: %s", label, exc)
        raise AndiamoUploadError(str(exc)) from exc
    finally:
        if owns:
            await client.aclose()
