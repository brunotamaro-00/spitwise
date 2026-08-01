"""Canal notas: el usuario dicta una nota por chat y se guarda en Andiamo.

Contraparte de escritura del Q&A de viaje (que solo lee). Mismo patrón que el
canal documentos: preview + botones, un pending, y la escritura recién en el
confirm. Spitwise NUNCA escribe `trip_notes` directo — esa tabla es cache del
sync; la fuente de verdad es Andiamo.
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.andiamo_notes import AndiamoNoteError, create_note
from app.bot import copy
from app.bot.pending import cancel_pending, close_pending, create_pending, load_pending
from app.bot.render import BotReply, buttons_reply, note_preview_card, note_saved_card, text_reply
from app.config import get_settings
from app.db.models import Stop, User

logger = logging.getLogger(__name__)

PENDING_KIND = "note_create"


async def _stop_name(session: AsyncSession, slug: str | None) -> str | None:
    if not slug:
        return None
    row = (await session.execute(select(Stop).where(Stop.slug == slug))).scalar_one_or_none()
    return row.name if row else None


async def handle_note_capture(session: AsyncSession, user: User, parsed, today) -> BotReply:
    """Preview de la nota dictada + botones. No escribe nada todavía."""
    if not get_settings().andiamo_url:
        return text_reply(copy.NOTE_NO_ANDIAMO)

    body = (parsed.note_body or "").strip()
    if not body:
        # Nada entra a medias: sin contenido se pide la aclaración.
        return text_reply(copy.NOTE_EMPTY)

    # Misma resolución de parada que un gasto (invariante 5): ciudad explícita →
    # esa parada; sin ciudad → la de hoy; fuera de rango → General (slug None).
    from app.bot.capture import resolve_place
    stop_slug, _city_name, _currency = await resolve_place(
        session, today, parsed.city, user.username
    )

    title = (parsed.note_title or "").strip() or None
    payload = {"title": title, "body": body, "stop_slug": stop_slug}
    token = await create_pending(session, owner=user.username, payload=payload,
                                 kind=PENDING_KIND)
    stop_name = await _stop_name(session, stop_slug)
    return buttons_reply(note_preview_card(title, body, stop_name), [
        (f"note_save:{token}", "Guardar 📝"),
        (f"note_cancel:{token}", "Cancelar"),
    ])


async def confirm_note(session: AsyncSession, user: User, token: str, *,
                       http_client=None) -> BotReply:
    data = await load_pending(session, token, owner=user.username)
    if data is None:
        return text_reply("⚠️ Expiró: esa nota ya no está disponible. Dictámela de nuevo.")

    kwargs = dict(title=data.get("title"), body=data["body"],
                  stop_slug=data.get("stop_slug"), client=http_client)
    try:
        await create_note(**kwargs)
    except AndiamoNoteError:
        try:
            await create_note(**kwargs)  # 1 reintento inmediato (red/deploy)
        except AndiamoNoteError:
            # El pending queda abierto: re-tocar Guardar reintenta.
            return text_reply(copy.NOTE_SAVE_FAILED)

    await close_pending(session, token)
    # Andiamo pingea notes.changed, pero el cache local no tiene por qué esperar
    # el round-trip para que un "¿qué anotamos?" siguiente la vea.
    from app.andiamo_content import force_content_sync_soon
    force_content_sync_soon(notes_only=True)

    stop_name = await _stop_name(session, data.get("stop_slug"))
    return text_reply(note_saved_card(
        data.get("title"), data["body"], stop_name,
        copy.link_andiamo_stop(data.get("stop_slug")),
    ))


async def cancel_note(session: AsyncSession, user: User, token: str) -> BotReply:
    await cancel_pending(session, token)
    return text_reply(copy.NOTE_CANCELLED)
