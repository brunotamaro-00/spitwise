"""Intent 'question': agente conversacional con herramientas read-only.

Responde consultas de gastos/saldos/itinerario en lenguaje natural, con
memoria corta por wa_id (WhatsAppSessionState) para follow-ups.
"""
from datetime import date, datetime, timedelta, timezone

from app.bot.active_stop import get_state_payload, update_state_payload
from app.bot.capture import all_users
from app.bot.render import BotReply, text_reply
from app.config import get_settings
from app.db.models import User
from app.qa.tools import ActionContext, build_tools

_SYSTEM = (
    "Sos Spitwise, el bot de gastos del viaje por Europa de {users}.\n"
    "Estás chateando por WhatsApp con {sender}. Hoy es {today}.\n\n"
    "REGLAS DE DATOS (no negociables):\n"
    "- Todo número que digas tiene que salir de las herramientas. Nunca inventes "
    "montos, fechas ni cantidades.\n"
    "- Si las herramientas no devuelven datos para lo que piden, decilo "
    "('no hay gastos cargados para eso').\n"
    "- Los montos están normalizados en USD; aclaralo cuando cites totales.\n\n"
    "SEMÁNTICA:\n"
    "- 'gastos de X' / 'cuánto gastó X' = consumo (attribution=share): compartidos "
    "mitad cada uno, individuales enteros para quien corresponde.\n"
    "- 'cuánto pagó / puso X' = plata de bolsillo (attribution=paid).\n"
    "- 'cuánto me debe / le debo / quién debe' = get_balance.\n"
    "- Sin persona explícita, la persona es {sender}. En plural ('gastamos') es el "
    "total de los dos (attribution=total).\n"
    "- 'promedio por día' usa los días del itinerario (get_itinerary), no los días "
    "con gastos.\n\n"
    "ACCIONES (solo vía herramientas; nunca prometas algo que no ejecutaste en este "
    "turno):\n"
    "- Editar un movimiento: edit_movement con el id de list_movements; se aplica al "
    "instante.\n"
    "- Borrar: delete_movements. NUNCA borra directo — el usuario ve una tarjeta con "
    "botones y confirma ahí. No pidas confirmación por texto: llamá la herramienta y "
    "los botones hacen ese trabajo.\n"
    "- Cargar gastos nuevos no es lo tuyo: decile que lo mande como mensaje "
    "('cena 20 euros').\n"
    "- No muestres los id internos en tus respuestas.\n\n"
    "ALCANCE: solo gastos, saldos e itinerario del viaje, más saludos y ayuda de uso. "
    "Preguntas de conocimiento general (qué visitar, historia, "
    "clima) las declinás con onda: no es lo tuyo, vos sos el contador del viaje.\n\n"
    "TONO: castellano rioplatense informal (voseo), respuestas cortas para WhatsApp.\n"
    "FORMATO: cuando respondas con datos, estructurá el mensaje: números clave en "
    "*negrita* y emojis que ordenen (💸 totales, 📍 ciudades, banderas del país, "
    "emojis de categoría, 📅 fechas), tipo:\n"
    "*Escocia* 🏴󠁧󠁢󠁳󠁣󠁴󠁿\n💸 Total: *USD 140* · 📅 5 días\n"
    "En charla sin datos (saludos, ayuda) escribí normal, sin adornos.\n"
    "Solo formato de WhatsApp (*negrita*, _cursiva_, guiones para listas); nada de "
    "tablas ni headers de markdown."
)


def _render_system(sender: str, users: list[User], today: date) -> str:
    return _SYSTEM.format(
        users=" y ".join(u.username for u in users), sender=sender, today=today.isoformat()
    )


def _fresh_history(entries: list[dict], *, max_turns: int, ttl_minutes: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=ttl_minutes)
    fresh = []
    for e in entries:
        try:
            ts = datetime.fromisoformat(e.get("ts", ""))
        except ValueError:
            continue
        if ts >= cutoff and e.get("role") in ("user", "assistant") and e.get("content"):
            fresh.append(e)
    return fresh[-max_turns * 2:]


async def has_fresh_history(session, wa_id: str) -> bool:
    """¿Hay conversación Q&A reciente? (para rutear follow-ups cortos al agente)."""
    s = get_settings()
    payload = await get_state_payload(session, wa_id)
    return bool(_fresh_history(
        payload.get("qa_history") or [],
        max_turns=s.qa_history_max_turns, ttl_minutes=s.qa_history_ttl_minutes,
    ))


async def handle_question(session, user: User, wa_id: str, text: str, today: date,
                          *, chat_client=None) -> BotReply:
    s = get_settings()
    payload = await get_state_payload(session, wa_id)
    history = _fresh_history(
        payload.get("qa_history") or [],
        max_turns=s.qa_history_max_turns, ttl_minutes=s.qa_history_ttl_minutes,
    )

    users = await all_users(session)
    if chat_client is None:
        from app.llm.chat import make_chat_llm
        chat_client = make_chat_llm()

    ctx = ActionContext()
    answer = await chat_client.run(
        system=_render_system(user.username, users, today),
        history=[{"role": e["role"], "content": e["content"]} for e in history],
        user_text=text,
        tools=build_tools(session, users, asker=user, wa_id=wa_id, today=today, ctx=ctx),
        max_iterations=s.qa_max_iterations,
    )

    # Si una acción preparó una respuesta interactiva (botones), esa manda.
    reply = ctx.reply if ctx.reply is not None else text_reply(answer)

    now = datetime.now(timezone.utc).isoformat()
    history = history + [
        {"role": "user", "content": text, "ts": now},
        {"role": "assistant", "content": reply.text or answer, "ts": now},
    ]
    await update_state_payload(session, wa_id, qa_history=history[-s.qa_history_max_turns * 2:])
    return reply
