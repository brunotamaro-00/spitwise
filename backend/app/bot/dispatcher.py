import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import resolve_user_by_wa_id
from app.bot.capture import handle_capture
from app.bot.interactive import handle_interactive
from app.bot.render import BotReply, buttons_reply, text_reply
from app.config import get_settings
from app.db.models import Movement, User

logger = logging.getLogger(__name__)


_DELETE_COMMANDS = {"borrar", "borrar último", "borrar ultimo", "eliminar"}


async def _handle_delete_command(session, user: User) -> BotReply:
    last = (await session.execute(
        select(Movement).where(Movement.created_by == user.id).order_by(Movement.id.desc())
    )).scalars().first()
    if last is None:
        return text_reply("⚠️ Nada que borrar: no tenés movimientos cargados.")
    desc = last.description or last.type
    return buttons_reply(
        f"¿Borrar '{desc}' ({last.currency} {last.amount})? Es irreversible.",
        [(f"del_confirm:{last.id}", "Borrar 🗑️"), ("del_cancel:0", "Cancelar")],
    )


async def _dispatch_inner(session, wa_id, message_type, text, interactive_id, today, *, llm_client) -> BotReply:
    user = await resolve_user_by_wa_id(session, wa_id)
    if user is None:
        if not get_settings().whatsapp_auto_register:
            return text_reply("⚠️ No autorizado: este número no está vinculado.")
        user = User(username=f"wa_{wa_id[-8:]}", whatsapp_wa_id=wa_id)
        session.add(user)
        await session.commit()

    if message_type == "interactive":
        return await handle_interactive(session, user, wa_id, interactive_id or "", today)

    stripped = (text or "").strip()
    if not stripped:
        return text_reply("Mandame un gasto, ej: 'cena 20 euros'.")

    if stripped.lower() in _DELETE_COMMANDS:
        return await _handle_delete_command(session, user)

    reply = await handle_capture(session, user, wa_id, text, today, llm_client=llm_client)
    # Si se auto-registró un gasto, ofrecer override de split sobre ESE movimiento.
    if reply.movement_id is not None and not reply.buttons:
        return buttons_reply(reply.text or "", [
            (f"split_shared:{reply.movement_id}", "Compartido ✓"),
            (f"split_mine:{reply.movement_id}", "Solo mío"),
            (f"split_theirs:{reply.movement_id}", "Solo de ella"),
        ])
    return reply


async def dispatch(session: AsyncSession, wa_id, message_type, text, interactive_id, today: date, *, llm_client=None) -> BotReply:
    try:
        return await _dispatch_inner(session, wa_id, message_type, text, interactive_id, today, llm_client=llm_client)
    except Exception as exc:  # borde único de errores
        logger.exception("dispatch_error wa_id=%s", wa_id)
        return text_reply(f"⚠️ {type(exc).__name__}: {exc}")
