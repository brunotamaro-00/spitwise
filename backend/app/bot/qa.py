"""Intent 'question': agente conversacional con herramientas read-only.

Responde consultas de gastos/saldos/itinerario en lenguaje natural, con
memoria corta por wa_id (WhatsAppSessionState) para follow-ups.
"""
from datetime import date, datetime, timedelta, timezone

from app.bot.active_stop import get_state_payload, resolve_trip_timezone, update_state_payload
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
    "{app_link_rule}"
    "CONTEXTO: recordás el hilo reciente. Resolvé follow-ups elípticos usando el "
    "último turno: si venías del balance y te dicen '¿y ayer?', o de Roma y dicen "
    "'¿y en Florencia?', reusá la intención anterior cambiando solo lo que pidieron.\n\n"
    "AMBIGÜEDAD: si falta UN dato para responder, preguntá SOLO esa cosa puntual, en "
    "una línea. No listes todas las opciones ni pidas varios datos a la vez.\n"
    "ERRORES: si no entendés, nunca tires un error técnico; pedí que lo reformule con "
    "un ejemplo concreto ('No te seguí, ¿probás algo como \"gastos de Roma\"?').\n\n"
    "ALCANCE: sos el contador del viaje (gastos, saldos, itinerario) + saludos y ayuda. "
    "Preguntas de afuera (qué visitar, historia, clima) no son lo tuyo: respondé con "
    "onda y humor, y redirigí en una línea. No seas estricto: es un bot para dos.\n\n"
    "TONO: castellano rioplatense informal (voseo), respuestas cortas para WhatsApp.\n\n"
    "FORMATO (consistente siempre):\n"
    "- MONTOS: siempre 'USD 1.234,5' — punto de miles, coma decimal, UN decimal. "
    "Convertí lo que devuelven las tools (ej '306.45') a ese formato ('USD 306,5').\n"
    "- NEGRITA (*...*) para el dato clave de cada oración: el monto, el nombre, la "
    "ciudad o el total.\n"
    "- Emojis que ordenan: 💸 totales, 📍 ciudades, banderas del país, emoji de "
    "categoría, 📅 fechas. Al LISTAR, NO uses emojis: recargan y ocupan lugar.\n"
    "- LISTAR movimientos = una línea COMPACTA por gasto, pensada para mobile. "
    "Formato exacto por ítem, con ' · ' de separador: "
    "'dd/mm · Descripción · *USD 32,9* · quién · reparto'. Reglas de esa línea:\n"
    "  · fecha de carga corta dd/mm (sin año); descripción tal cual, sin emoji de categoría.\n"
    "  · ciudad/país SOLO si el usuario no la fijó ya en la consulta (si pidió 'gastos "
    "de Roma', no repitas Roma en cada línea); sin bandera ni 📍.\n"
    "  · pagador: solo el nombre (sin 'pagó').\n"
    "  · reparto abreviado: '50/50' si es compartido; 'solo <nombre>' si es de una sola "
    "persona. Omitilo si TODOS los ítems tienen el mismo reparto (aclaralo una vez arriba).\n"
    "  · encabezá con UNA línea breve ('Últimos N gastos (USD):') y nada de montos "
    "normalizados repetido por ítem.\n"
    "  Ejemplo:\n"
    "  Últimos 3 gastos (USD):\n"
    "  - 16/09 · Hostel Friburgo · *USD 32,9* · bruno · 50/50\n"
    "  - 12/09 · Vuelo Estrasburgo · *USD 90,0* · bruno · solo bruno\n"
    "  - 09/09 · Hostel Porto · *USD 34,3* · bruno · solo bruno\n"
    "- Si list_movements trae 'truncated'=true, cerrá con el 'app_link' que devuelve "
    "('…y N más — mirálos en la app: <link>') en vez de volcar todo.\n"
    "- Charla sin datos (saludos, ayuda): escribí normal, sin adornos.\n"
    "- Solo formato WhatsApp (*negrita*, _cursiva_, guiones); nada de tablas ni headers "
    "de markdown. Ejemplo con datos:\n"
    "*Escocia* 🏴󠁧󠁢󠁳󠁣󠁴󠁿\n💸 Total: *USD 140,0* · 📅 5 días"
)


def _render_system(sender: str, users: list[User], today: date) -> str:
    from app.bot import copy

    home = copy.link_home()
    if home:
        app_link_rule = (
            f"LINK DE LA APP: la app del viaje está en {home} — si te preguntan "
            "'cuál es el link', 'dónde lo veo', 'pasame la app' y similares, pasáselo "
            "tal cual. Para listados con filtros, usá el 'app_link' que devuelven las "
            "herramientas (link con los filtros ya aplicados).\n\n"
        )
    else:
        app_link_rule = (
            "LINK DE LA APP: no hay una URL configurada, así que NO tenés link para "
            "pasar. Si te lo piden, decí que la app existe pero no tenés el link a mano; "
            "no inventes una URL.\n\n"
        )
    return _SYSTEM.format(
        users=" y ".join(u.username for u in users), sender=sender,
        today=today.isoformat(), app_link_rule=app_link_rule,
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
    tz_name = await resolve_trip_timezone(session, user.username)
    answer = await chat_client.run(
        system=_render_system(user.username, users, today),
        history=[{"role": e["role"], "content": e["content"]} for e in history],
        user_text=text,
        tools=build_tools(session, users, asker=user, today=today, ctx=ctx, tz_name=tz_name),
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
