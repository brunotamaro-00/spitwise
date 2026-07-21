"""Intent 'trip_question': agente de Q&A sobre el CONTENIDO del viaje.

Responde con las guías y notas de Andiamo (cacheadas en guide_docs/trip_notes).
Canal totalmente aislado del Q&A financiero (qa.py): prompt, tools e historial
propios (payload key 'trip_qa_history', nunca 'qa_history').
"""
from datetime import date, datetime, timezone

from sqlalchemy import func, select

from app.bot.active_stop import get_state_payload, update_state_payload
from app.bot.qa import _fresh_history
from app.bot.render import BotReply, text_reply
from app.config import get_settings
from app.db.models import GuideDoc, Stop, StopGuide, TripNote, User
from app.qa.trip_tools import build_trip_tools

_SYSTEM = (
    "Sos Spitwise, el asistente de viaje de {users} en su vuelta por Europa.\n"
    "Estás chateando por WhatsApp con {sender}. Hoy es {today}.\n\n"
    "Tu ÚNICA fuente son las guías y notas del viaje (herramientas). No sos una "
    "enciclopedia: sos el que les lee SUS guías y SUS anotaciones.\n\n"
    "GROUNDING (no negociable):\n"
    "- Todo dato concreto (precios, horarios, líneas de tren, nombres de lugares, "
    "reservas) tiene que salir de las herramientas de este turno o del hilo "
    "reciente. NUNCA completes con conocimiento general ni inventes.\n"
    "- Si las guías/notas no cubren lo que preguntan, decilo claro y corto "
    "('las guías no dicen nada de eso') — podés sugerir en qué doc cercano "
    "mirar, pero sin inventar contenido.\n"
    "- Conocimiento general SOLO para interpretar la pregunta (sinónimos, "
    "geografía básica para elegir qué buscar), jamás para responderla.\n\n"
    "CÓMO TRABAJAR:\n"
    "- El bloque 'Contexto del viaje' trae la parada de hoy y las próximas: usalo "
    "para resolver 'acá', 'mañana', 'la próxima ciudad' sin preguntar.\n"
    "- Flujo típico: search_guides con palabras clave → read_guide_doc del mejor "
    "hit. Para '¿qué anotamos...?' o datos de reservas propias, list_notes.\n"
    "- Preguntas amplias ('qué hacemos en Roma') → read_guide_doc del doc "
    "'actividades' de esa guía directo.\n"
    "- Si falta UN dato para responder, preguntá solo eso, en una línea.\n\n"
    "ALCANCE: preguntas de plata (cuánto gastamos, saldos, deudas) no son de este "
    "canal: respondé en una línea que eso lo conteste el contador ('preguntame "
    "\"¿cuánto gastamos en Roma?\" y te lo digo con números').\n\n"
    "TONO: castellano rioplatense informal (voseo), con onda; es un chat de a dos.\n\n"
    "FORMATO (WhatsApp, pantalla de teléfono):\n"
    "- CORTO: 3-8 líneas. Respondé LO QUE PREGUNTARON, no vuelques el doc entero.\n"
    "- *Negrita* para lo clave (lugar, precio, horario); guiones para listar; nada "
    "de tablas ni headers de markdown.\n"
    "- Si leíste un doc y hay más detalle útil, cerrá con su link: '📖 Más: <link>'. "
    "Si no hay link (tool sin URL), simplemente no lo pongas — nunca inventes URLs.\n"
    "- Precios/horarios citados tal cual figuran en la guía (con su moneda)."
)

_HISTORY_KEY = "trip_qa_history"


def _render_system(sender: str, users: list[User], today: date) -> str:
    return _SYSTEM.format(
        users=" y ".join(u.username for u in users), sender=sender,
        today=today.isoformat(),
    )


async def _trip_context_snapshot(session, today: date) -> str:
    """Bloque 'Contexto del viaje': parada de hoy + próximas, sus guías y cuántas
    notas hay. Resuelve deícticos ('acá', 'mañana') sin round-trips extra."""
    from app.bot.active_stop import place_for_date

    docs_count = (await session.execute(
        select(func.count()).select_from(GuideDoc)
    )).scalar_one()
    lines = ["Contexto del viaje:"]
    if not docs_count:
        lines.append(
            "- ATENCIÓN: el cache de guías está VACÍO (sync pendiente). No hay "
            "contenido para leer: avisá que todavía no tenés las guías cargadas y "
            "que pruebe en un rato. No inventes nada."
        )

    stop = await place_for_date(session, today, None)
    if stop is not None:
        lines.append(f"- Parada de hoy: {stop.name} (slug {stop.slug})")
        upcoming = (await session.execute(
            select(Stop).where(
                Stop.is_candidate.is_(False), Stop.is_archived.is_(False),
                Stop.arrival_date > today,
            ).order_by(Stop.arrival_date).limit(3)
        )).scalars().all()
        for s in upcoming:
            lines.append(
                f"- Próxima: {s.name} (slug {s.slug}), llegan el "
                f"{s.arrival_date.isoformat()}"
            )
        slugs = [stop.slug] + [s.slug for s in upcoming[:1]]
        mappings = (await session.execute(
            select(StopGuide).where(StopGuide.stop_slug.in_(slugs))
            .order_by(StopGuide.position)
        )).scalars().all()
        if mappings:
            per_stop: dict[str, list[str]] = {}
            for m in mappings:
                per_stop.setdefault(m.stop_slug, []).append(m.guide_slug)
            for slug, guides in per_stop.items():
                lines.append(f"- Guías de {slug}: {', '.join(guides)}")
    else:
        lines.append("- Hoy no cae dentro de ninguna parada del itinerario")

    notes_count = (await session.execute(
        select(func.count()).select_from(TripNote)
    )).scalar_one()
    lines.append(f"- Notas cargadas en Andiamo: {notes_count}")
    return "\n".join(lines)


def latest_fresh_channel(payload: dict, *, max_turns: int, ttl_minutes: int) -> str | None:
    """A qué agente rutear un follow-up sin intent claro: el canal ('qa' |
    'trip') con actividad fresca más reciente, o None si ambos vencieron."""
    def last_ts(key: str) -> str:
        entries = _fresh_history(payload.get(key) or [],
                                 max_turns=max_turns, ttl_minutes=ttl_minutes)
        return max((e.get("ts", "") for e in entries), default="")

    qa_ts, trip_ts = last_ts("qa_history"), last_ts(_HISTORY_KEY)
    if not qa_ts and not trip_ts:
        return None
    return "trip" if trip_ts > qa_ts else "qa"


async def handle_trip_question(session, user: User, wa_id: str, text: str, today: date,
                               *, chat_client=None) -> BotReply:
    from app.andiamo_content import ensure_content_fresh
    from app.bot.capture import all_users

    # Lazy refresh del contenido: dispara un task y sigue; este turno usa el
    # snapshot actual. Nunca suma latencia al mensaje.
    await ensure_content_fresh(session)

    s = get_settings()
    payload = await get_state_payload(session, wa_id)
    history = _fresh_history(
        payload.get(_HISTORY_KEY) or [],
        max_turns=s.qa_history_max_turns, ttl_minutes=s.qa_history_ttl_minutes,
    )

    users = await all_users(session)
    if chat_client is None:
        from app.llm.chat import make_chat_llm
        chat_client = make_chat_llm()

    snapshot = await _trip_context_snapshot(session, today)
    answer = await chat_client.run(
        system=_render_system(user.username, users, today),
        history=[{"role": e["role"], "content": e["content"]} for e in history],
        user_text=f"{snapshot}\n\nMensaje de {user.username}: {text}",
        tools=build_trip_tools(session),
        max_iterations=s.qa_max_iterations,
    )
    reply = text_reply(answer)

    now = datetime.now(timezone.utc).isoformat()
    history = history + [
        {"role": "user", "content": text, "ts": now},
        {"role": "assistant", "content": answer, "ts": now},
    ]
    await update_state_payload(
        session, wa_id, **{_HISTORY_KEY: history[-s.qa_history_max_turns * 2:]}
    )
    return reply
