"""Canal documentos: adjunto de WhatsApp → interpretación vision → Andiamo.

Canal 100% lateral al financiero (patrón trip_qa): prompt, cliente LLM y flujo
propios. El adjunto se interpreta, se muestra un preview con botones
Guardar/Cancelar (pending `doc_upload`), acepta correcciones por texto mientras
el preview está fresco, y recién al confirmar se sube a Andiamo (que es el
dueño del storage). Los bytes nunca se persisten acá: se re-descargan de Meta
al confirmar (su media vive semanas; el pending, horas).
"""
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.andiamo_documents import AndiamoUploadError, upload_document
from app.bot import copy
from app.bot.documents.kinds import DOC_KINDS, normalize_kind
from app.bot.pending import cancel_pending, close_pending, create_pending, load_pending
from app.bot.render import BotReply, buttons_reply, document_preview_card, document_saved_card, text_reply
from app.config import get_settings
from app.db.models import BotPendingAction, Stop, User
from app.whatsapp.verify import MediaInfo

logger = logging.getLogger(__name__)

PENDING_KIND = "doc_upload"

# Espejo de la validación de Andiamo (src/lib/document-upload.ts).
MAX_BYTES = 20 * 1024 * 1024
ALLOWED_MIME = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
_MIME_EXT = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_iso(v: str | None) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        return None


def _safe_filename(media: MediaInfo | None, mime: str) -> str:
    """Andiamo valida la extensión del filename: si el adjunto no trae nombre
    (las fotos de WPP no traen) o la extensión no acompaña al MIME, se sintetiza."""
    ext = _MIME_EXT.get(mime, "pdf")
    name = (media.filename or "").strip() if media else ""
    if name and name.lower().endswith(f".{ext}"):
        return name
    if name and mime == "application/pdf" and name.lower().endswith(".pdf"):
        return name
    return f"documento.{ext}" if ext == "pdf" else f"foto.{ext}"


async def load_doc_stops(session: AsyncSession) -> list[dict]:
    """Catálogo dinámico de paradas para el prompt (nunca hardcodear stops)."""
    rows = (await session.execute(
        select(Stop).where(Stop.is_archived.is_(False), Stop.is_candidate.is_(False))
        .order_by(Stop.order)
    )).scalars().all()
    return [{
        "slug": s.slug, "name": s.name, "country": s.country,
        "arrival_date": s.arrival_date.isoformat() if s.arrival_date else None,
        "departure_date": s.departure_date.isoformat() if s.departure_date else None,
    } for s in rows]


async def _stop_name(session: AsyncSession, slug: str | None) -> str | None:
    if not slug:
        return None
    row = (await session.execute(select(Stop).where(Stop.slug == slug))).scalar_one_or_none()
    return row.name if row else None


def _make_meta_client():
    from app.whatsapp.meta_client import MetaClient
    s = get_settings()
    return MetaClient(s.whatsapp_access_token, s.whatsapp_phone_number_id, s.whatsapp_graph_version)


async def _preview_reply(session: AsyncSession, user: User, payload: dict) -> BotReply:
    stop_name = await _stop_name(session, payload.get("stop_slug"))
    token = await create_pending(session, owner=user.username, payload=payload, kind=PENDING_KIND)
    text = document_preview_card(
        payload.get("kind") or "other", payload.get("label") or "Documento",
        payload.get("note"), stop_name, _parse_iso(payload.get("doc_date")),
        not_travel=not payload.get("is_travel_doc", True),
    )
    return buttons_reply(text, [
        (f"doc_save:{token}", "Guardar 📎"),
        (f"doc_cancel:{token}", "Cancelar"),
    ])


async def handle_document_media(session: AsyncSession, user: User, wa_id: str,
                                media: MediaInfo | None, today: date, *,
                                vision_client=None, meta_client=None) -> BotReply:
    s = get_settings()
    if not s.andiamo_url:
        return text_reply(copy.DOC_NO_ANDIAMO)
    if media is None or not media.media_id:
        return text_reply(copy.DOC_READ_FAILED)
    mime = (media.mime_type or "").split(";")[0].strip()
    if mime not in ALLOWED_MIME:
        return text_reply(copy.DOC_UNSUPPORTED)

    meta = meta_client or _make_meta_client()
    owns_meta = meta_client is None
    try:
        file_bytes, dl_mime = await meta.download_media(media.media_id)
    except Exception:
        logger.exception("doc_media_download_failed media_id=%s", media.media_id)
        return text_reply(copy.DOC_READ_FAILED)
    finally:
        if owns_meta:
            await meta.aclose()
    if len(file_bytes) > MAX_BYTES:
        return text_reply(copy.DOC_TOO_BIG)
    mime = (dl_mime or mime).split(";")[0].strip()
    if mime not in ALLOWED_MIME:
        return text_reply(copy.DOC_UNSUPPORTED)

    stops = await load_doc_stops(session)
    vision = vision_client
    if vision is None:
        from app.llm.vision import make_vision_llm
        vision = make_vision_llm()
    extraction = await vision.extract(
        file_bytes, mime, today=today, stops=stops, kinds=DOC_KINDS,
        caption=media.caption, filename=media.filename,
    )
    if not extraction:
        return text_reply(copy.DOC_READ_FAILED)

    known_slugs = {st["slug"] for st in stops}
    slug = extraction.get("stop_slug")
    payload = {
        "media_id": media.media_id,
        "mime": mime,
        "filename": _safe_filename(media, mime),
        "caption": media.caption,
        "kind": normalize_kind(extraction.get("kind")),
        "doc_date": extraction.get("doc_date") if _parse_iso(extraction.get("doc_date")) else None,
        "stop_slug": slug if slug in known_slugs else None,
        "label": (extraction.get("label") or "").strip() or "Documento",
        "note": (extraction.get("note") or "").strip() or None,
        "is_travel_doc": bool(extraction.get("is_travel_doc", True)),
    }
    return await _preview_reply(session, user, payload)


def _extraction_summary(payload: dict, stop_name: str | None) -> str:
    return (
        f"tipo={DOC_KINDS.get(payload.get('kind') or 'other')} · "
        f"título='{payload.get('label')}' · "
        f"parada={stop_name or 'General'} · "
        f"fecha={payload.get('doc_date') or 'sin fecha'} · "
        f"nota='{payload.get('note') or ''}'"
    )


async def _fresh_doc_pending(session: AsyncSession, owner: str) -> BotPendingAction | None:
    """Último preview de documento sin resolver dentro de la ventana de
    corrección. Query indexada y sin LLM: es lo ÚNICO que el camino de texto
    financiero paga por este canal."""
    cutoff = _utcnow_naive() - timedelta(minutes=get_settings().doc_pending_fresh_minutes)
    return (await session.execute(
        select(BotPendingAction).where(
            BotPendingAction.owner == owner,
            BotPendingAction.action_type == PENDING_KIND,
            BotPendingAction.confirmed_at.is_(None),
            BotPendingAction.cancelled_at.is_(None),
            BotPendingAction.created_at >= cutoff,
        ).order_by(BotPendingAction.id.desc())
    )).scalars().first()


async def maybe_apply_correction(session: AsyncSession, user: User, wa_id: str, text: str,
                                 today: date, *, vision_client=None) -> BotReply | None:
    """Si hay un preview fresco y el texto lo corrige, re-arma el preview.
    Devuelve None cuando no aplica: el dispatcher sigue su flujo normal."""
    row = await _fresh_doc_pending(session, user.username)
    if row is None:
        return None
    import json
    payload = json.loads(row.payload_json)
    stops = await load_doc_stops(session)
    stop_name = await _stop_name(session, payload.get("stop_slug"))

    vision = vision_client
    if vision is None:
        from app.llm.vision import make_vision_llm
        vision = make_vision_llm()
    correction = await vision.classify_correction(
        text, _extraction_summary(payload, stop_name), today=today, stops=stops, kinds=DOC_KINDS,
    )
    if not correction.get("is_correction"):
        return None

    known_slugs = {st["slug"] for st in stops}
    if correction.get("stop_slug") in known_slugs:
        payload["stop_slug"] = correction["stop_slug"]
    if _parse_iso(correction.get("doc_date")):
        payload["doc_date"] = correction["doc_date"]
    if correction.get("kind") in DOC_KINDS:
        payload["kind"] = correction["kind"]
    if (correction.get("label") or "").strip():
        payload["label"] = correction["label"].strip()
    if (correction.get("note") or "").strip():
        payload["note"] = correction["note"].strip()

    await cancel_pending(session, row.token)
    return await _preview_reply(session, user, payload)


async def confirm_doc_upload(session: AsyncSession, user: User, token: str, *,
                             meta_client=None, http_client=None) -> BotReply:
    data = await load_pending(session, token, owner=user.username)
    if data is None:
        return text_reply("⚠️ Expiró: ese documento ya no está disponible. Reenviá el archivo.")

    meta = meta_client or _make_meta_client()
    owns_meta = meta_client is None
    try:
        file_bytes, _ = await meta.download_media(data["media_id"])
    except Exception:
        logger.exception("doc_confirm_download_failed media_id=%s", data.get("media_id"))
        return text_reply(copy.DOC_UPLOAD_FAILED)
    finally:
        if owns_meta:
            await meta.aclose()

    kwargs = dict(
        file_bytes=file_bytes, filename=data["filename"], mime_type=data["mime"],
        label=data["label"], note=data.get("note"), kind=data.get("kind") or "other",
        stop_slug=data.get("stop_slug"), doc_date=data.get("doc_date"),
        client=http_client,
    )
    try:
        await upload_document(**kwargs)
    except AndiamoUploadError:
        try:
            await upload_document(**kwargs)  # 1 reintento inmediato (red/deploy)
        except AndiamoUploadError:
            # El pending queda abierto: re-tocar Guardar reintenta.
            return text_reply(copy.DOC_UPLOAD_FAILED)

    await close_pending(session, token)
    stop_name = await _stop_name(session, data.get("stop_slug"))
    return text_reply(document_saved_card(
        data.get("kind") or "other", data["label"], data.get("note"), stop_name,
        _parse_iso(data.get("doc_date")), copy.link_andiamo_stop(data.get("stop_slug")),
    ))


async def cancel_doc_upload(session: AsyncSession, user: User, token: str) -> BotReply:
    await cancel_pending(session, token)
    return text_reply("Cancelado. Si querés, reenviá el archivo con más contexto en el mensaje.")
