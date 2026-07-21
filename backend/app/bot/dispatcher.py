import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import copy, resolve_user_by_wa_id
from app.bot.capture import all_users, handle_capture, load_categories, load_city_names
from app.bot.editor import handle_delete, handle_edit
from app.bot.interactive import handle_interactive
from app.bot.render import BotReply, buttons_reply, fmt_money, text_reply, unknown_reply
from app.config import get_settings
from app.db.models import Movement, User

logger = logging.getLogger(__name__)


_DELETE_COMMANDS = {"borrar", "borrar último", "borrar ultimo", "eliminar"}
_HELP_COMMANDS = {
    "ayuda", "help", "qué podés hacer", "que podes hacer", "qué haces", "que haces",
    "cómo te uso", "como te uso", "cómo funciona", "como funciona",
}


def _help_reply() -> BotReply:
    home = copy.link_home()
    lines = [
        "👋 Soy *Spitwise*, el contador del viaje. Puedo:",
        copy.bullets([
            "*Cargar gastos*: _cena 20 euros_",
            "*Marcar de una persona*: _pagó katia 15gbp el museo, solo de ella_",
            "*Editar*: _la cena de ayer fue 25, no 20_",
            "*Borrar*: _borrá el último_",
            "*Consultar*: _¿cuánto gastamos en Roma?_ · _¿quién debe plata?_",
            "*Preguntar del viaje*: _¿qué hacemos mañana?_ · _¿cómo llegamos a Sintra?_",
            "*Archivar documentos*: mandame el PDF o foto de una reserva/entrada y lo guardo en Andiamo",
        ]),
        "⚡ Atajos al instante: *saldo* · *total*",
    ]
    if home:
        lines.append(f"📲 O abrí la app: {home}")
    return text_reply("\n".join(lines))


async def _handle_delete_command(session, user: User) -> BotReply:
    last = (await session.execute(
        select(Movement).order_by(Movement.id.desc())
    )).scalars().first()
    if last is None:
        return text_reply(f"{copy.H_WARN} Nada que borrar: no hay movimientos cargados.")

    # "borrar" justo después de un mensaje multi-gasto casi siempre significa
    # "me equivoqué con ese mensaje" → ofrecer el batch entero (con confirmación).
    if last.batch_key:
        siblings = (await session.execute(
            select(Movement).where(Movement.batch_key == last.batch_key).order_by(Movement.id)
        )).scalars().all()
        if len(siblings) > 1:
            from app.bot.interactive import _summary_lines
            from app.bot.pending import create_pending
            summary = await _summary_lines(session, siblings)
            token_all = await create_pending(
                session, owner=user.username,
                payload={"ids": [m.id for m in siblings]}, kind="del_confirm",
            )
            token_last = await create_pending(
                session, owner=user.username, payload={"ids": [last.id]}, kind="del_confirm",
            )
            return buttons_reply(
                f"{copy.H_WARN} Eso entró como *{len(siblings)} gastos juntos*. "
                f"¿Borrar? Es irreversible.\n{summary}",
                [
                    (f"del_confirm:{token_all}", f"Borrar los {len(siblings)} 🗑️"),
                    (f"del_confirm:{token_last}", "Solo el último"),
                    ("del_cancel:0", "Cancelar"),
                ],
            )

    desc = last.description or last.type
    return buttons_reply(
        f"{copy.H_WARN} ¿Borrar *{desc}* ({fmt_money(last.amount, last.currency, last.amount_usd)})?\n"
        "Es irreversible.",
        [(f"del_confirm:{last.id}", "Borrar 🗑️"), ("del_cancel:0", "Cancelar")],
    )


async def _dispatch_inner(session, wa_id, message_type, text, interactive_id, today,
                          *, llm_client, chat_client, media=None, vision_client=None) -> BotReply:
    user = await resolve_user_by_wa_id(session, wa_id)
    if user is None:
        if not get_settings().whatsapp_auto_register:
            return text_reply("⚠️ No autorizado: este número no está vinculado.")
        user = User(username=f"wa_{wa_id[-8:]}", whatsapp_wa_id=wa_id)
        session.add(user)
        await session.commit()

    if message_type == "interactive":
        return await handle_interactive(session, user, wa_id, interactive_id or "", today)

    # Canal documentos: un adjunto va a Andiamo, nunca al parser financiero.
    if message_type in ("image", "document"):
        from app.bot.documents.pipeline import handle_document_media
        return await handle_document_media(session, user, wa_id, media, today,
                                           vision_client=vision_client)
    if message_type in ("audio", "video", "sticker"):
        return text_reply(copy.MEDIA_NOT_SUPPORTED)

    stripped = (text or "").strip()
    if not stripped:
        return text_reply(copy.EMPTY_MESSAGE)

    low = stripped.lower()
    # Ruteo rápido: comandos evidentes que no necesitan el parser LLM.
    if low in _DELETE_COMMANDS:
        return await _handle_delete_command(session, user)
    if low in _HELP_COMMANDS:
        return _help_reply()
    # Consultas frecuentes ('saldo', 'total'): respuesta instantánea sin LLM.
    from app.bot import quick
    quick_intent = quick.route(stripped)
    if quick_intent == "balance":
        return await quick.handle_balance(session, user)
    if quick_intent == "total":
        return await quick.handle_total(session, user)

    # Preview de documento fresco sin confirmar: un texto puede corregirlo
    # ('es en York'). El costo sin preview pendiente es UNA query indexada;
    # si el texto no es corrección, sigue el flujo financiero intacto.
    from app.bot.documents.pipeline import maybe_apply_correction
    doc_reply = await maybe_apply_correction(session, user, wa_id, stripped, today,
                                             vision_client=vision_client)
    if doc_reply is not None:
        return doc_reply

    from app.llm.parser import parse_message
    from app.bot.editor import describe_recent, recent_movement
    users = await all_users(session)
    # Gasto recién cargado como contexto: el bot espera una posible corrección.
    recent = await recent_movement(session, ttl_minutes=get_settings().edit_recent_ttl_minutes)
    parsed = await parse_message(
        stripped, today=today, categories=await load_categories(session),
        usernames=[u.username for u in users], sender=user.username, client=llm_client,
        city_names=await load_city_names(session),
        last_expense=await describe_recent(session, recent) if recent else None,
    )

    if parsed.intent == "edit":
        return await handle_edit(session, user, wa_id, parsed, today, text=stripped)
    if parsed.intent == "delete":
        return await handle_delete(session, user, wa_id, parsed, today)
    if parsed.intent == "question":
        from app.bot.qa import handle_question
        return await handle_question(session, user, wa_id, stripped, today, chat_client=chat_client)
    if parsed.intent == "trip_question":
        from app.bot.trip_qa import handle_trip_question
        return await handle_trip_question(session, user, wa_id, stripped, today, chat_client=chat_client)
    if parsed.intent == "unknown":
        # Follow-up corto de una conversación en curso ('sí', 'el segundo') → el
        # agente que la tenía sigue; el enlatado queda para mensajes sueltos.
        # Con dos canales (finanzas/viaje) gana el de actividad más reciente.
        from app.bot.active_stop import get_state_payload
        from app.bot.qa import handle_question
        from app.bot.trip_qa import handle_trip_question, latest_fresh_channel
        s = get_settings()
        channel = latest_fresh_channel(
            await get_state_payload(session, wa_id),
            max_turns=s.qa_history_max_turns, ttl_minutes=s.qa_history_ttl_minutes,
        )
        if channel == "trip":
            return await handle_trip_question(session, user, wa_id, stripped, today, chat_client=chat_client)
        if channel == "qa":
            return await handle_question(session, user, wa_id, stripped, today, chat_client=chat_client)
        return unknown_reply()
    # Red de seguridad: un "gasto" sin monto justo después de cargar uno casi
    # nunca es un gasto nuevo — es una corrección que el parser no pescó. En vez
    # del dead-end "no le pesqué el monto", guiá hacia editar el último.
    if parsed.intent == "expense" and parsed.amount is None and not parsed.batch and recent is not None:
        return text_reply(
            f"{copy.H_HUH} ¿Querías corregir *{recent.description or 'el último gasto'}* "
            f"({await describe_recent(session, recent)})?\n"
            "Decime qué cambiar: _solo katia_ · _fueron 45_ · _en Paris_ · "
            "_pagó bruno_ · _es transporte_."
        )
    return await handle_capture(session, user, wa_id, text, today, parsed=parsed)


async def dispatch(session: AsyncSession, wa_id, message_type, text, interactive_id, today: date,
                   *, llm_client=None, chat_client=None, media=None, vision_client=None) -> BotReply:
    try:
        return await _dispatch_inner(session, wa_id, message_type, text, interactive_id, today,
                                     llm_client=llm_client, chat_client=chat_client,
                                     media=media, vision_client=vision_client)
    except Exception:  # borde único de errores
        logger.exception("dispatch_error wa_id=%s", wa_id)
        return text_reply(copy.SOMETHING_FAILED)
