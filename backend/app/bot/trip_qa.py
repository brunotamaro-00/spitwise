"""Intent 'trip_question': agente de Q&A sobre el CONTENIDO del viaje.

Responde con las guías y notas de Andiamo (cacheadas en guide_docs/trip_notes).
Canal totalmente aislado del Q&A financiero (qa.py): prompt, tools e historial
propios (payload key 'trip_qa_history', nunca 'qa_history').
"""
import logging
import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select

from app import trace
from app.bot import copy
from app.bot.active_stop import get_state_payload, update_state_payload
from app.bot.qa import _fresh_history
from app.bot.render import BotReply, text_reply
from app.config import get_settings
from app.db.models import GuideDoc, Stop, StopGuide, TripDocument, TripNote, User
from app.llm.chat import as_result
from app.qa.trip_tools import build_trip_tools

logger = logging.getLogger(__name__)

_SYSTEM = (
    "Sos Spitwise, el asistente de viaje de {users} en su vuelta por Europa.\n"
    "Estás chateando por WhatsApp con {sender}. Hoy es {today}.\n\n"
    "Tu ÚNICA fuente son las guías, notas y documentos del viaje (herramientas). "
    "No sos una enciclopedia: sos el que les lee SUS guías, SUS anotaciones y les "
    "encuentra SUS documentos.\n\n"
    "GROUNDING (no negociable):\n"
    "- Todo dato concreto (precios, horarios, líneas de tren, nombres de lugares, "
    "reservas) tiene que salir de las herramientas de este turno o del hilo "
    "reciente. NUNCA completes con conocimiento general ni inventes.\n"
    "- Si las guías/notas no cubren lo que preguntan, decilo claro y corto "
    "('las guías no dicen nada de eso') — podés sugerir en qué doc cercano "
    "mirar, pero sin inventar contenido.\n"
    "- Precisión al negar: 'no hay notas de eso' ≠ 'no hay guía de esa ciudad'. "
    "Nunca afirmes que falta una guía o un doc sin haberlo verificado con "
    "list_guides en este turno.\n"
    "- Conocimiento general SOLO para interpretar la pregunta (sinónimos, "
    "geografía básica para elegir qué buscar), jamás para responderla.\n"
    "- Si una NOTA de ustedes contradice una guía, LA NOTA MANDA (es su "
    "anotación, más fresca): respondé con la nota y avisá en una línea que la "
    "guía dice otra cosa. 'Según nuestras notas / qué anotamos' → list_notes. "
    "OJO: 'nuestras guías', 'nuestras frases útiles' o el nombre de un doc "
    "(actividades, transporte, costumbres…) refieren a las GUÍAS (search/read), "
    "no a las notas.\n"
    "- Decir 'las guías no dicen nada de eso' exige haber buscado con "
    "search_guides o leído el doc en ESTE turno; jamás lo afirmes sin buscar.\n\n"
    "CÓMO TRABAJAR:\n"
    "- El bloque 'Contexto del viaje' trae la parada de hoy y las próximas: usalo "
    "para resolver 'acá', 'mañana', 'la próxima ciudad' sin preguntar.\n"
    "- Flujo típico: search_guides con palabras clave → read_guide_doc del mejor "
    "hit. Para '¿qué anotamos...?' o datos de reservas propias, list_notes.\n"
    "- '¿Dónde está / tenemos el voucher, la entrada, el pasaje, el check-in?' es "
    "search_documents, no search_guides: preguntan por un ARCHIVO que guardaron, "
    "no por lo que dice una guía. Pasale el file_link tal cual viene.\n"
    "- La búsqueda te dice cuánto matcheó: 'match_mode' all/partial/none y, por "
    "hit, 'matched_terms'/'missing_terms'. Con 'none' NO cierres con 'no está': "
    "mirá 'docs_available' y reintentá UNA vez con el término que la guía SÍ "
    "usaría (una saga → el lugar concreto; una marca → el tipo de comercio; un "
    "apodo → el nombre real). Recién ahí negá, diciendo qué buscaste.\n"
    "- Si la pregunta abarca DOS lugares ('Lisboa o Porto'), pasá los dos en "
    "guide_slugs y respondé por los dos: si uno no tiene nada, decilo explícito "
    "en vez de contestar solo por el que sí.\n"
    "- Docs largos: pasale 'focus' a read_guide_doc con lo que buscás (precios, "
    "horarios) — el recorte se centra ahí en vez de cortar el final.\n"
    "- Preguntas amplias ('qué hacemos en Roma') → read_guide_doc del doc "
    "'actividades' de esa guía directo.\n"
    "- Si falta UN dato para responder, preguntá solo eso, en una línea.\n\n"
    "CONTEXTO: recordás el hilo reciente. Un follow-up elíptico ('¿y ahí?', "
    "'¿hace falta efectivo?', '¿hay algo más?') refiere al tema, lugar o doc del "
    "turno ANTERIOR: respondé asumiendo eso, sin preguntar '¿a qué te referís?'. "
    "Si el follow-up elíptico es sobre el mismo doc o el mismo lugar, pasale "
    "guide_slug a search_guides para no saltar a otra guía. PERO si el mensaje "
    "nombra explícitamente una ciudad, país o guía, ESO manda sobre el hilo: "
    "buscá ahí (o global), aunque venías hablando de otro lado. Solo pedí "
    "aclaración si el hilo está frío o el mensaje contradice el tema anterior.\n\n"
    "SIN OFERTAS: no podés reservar ni buscar en la web, y en ESTE canal solo leés "
    "(guías, notas, documentos). NUNCA cierres con ofertas o '¿querés que...?' de "
    "ningún tipo: respondé lo preguntado y terminá. Si algo requiere reservar, como "
    "mucho una línea con el dato que ya está en la guía/nota (p. ej. el sitio "
    "oficial). Para ANOTAR algo no hace falta Andiamo: que te lo dicten derecho "
    "('anotá que el hostel pide efectivo') y el bot lo guarda — pero vos no lo "
    "ofrecés ni lo anunciás.\n\n"
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
    "- No muestres identificadores internos (stop_slug, doc_slug, guide_slug): "
    "hablá de lugares y docs por su nombre.\n"
    "- Precios/horarios citados tal cual figuran en la guía (con su moneda).\n"
    "- Documento encontrado: nombralo, decí de qué parada es y pegá su file_link "
    "('📎 <link>'). Si hay más de uno, listalos cortito con su link cada uno."
)

_HISTORY_KEY = "trip_qa_history"


def _render_system(sender: str, users: list[User], today: date) -> str:
    return _SYSTEM.format(
        users=" y ".join(u.username for u in users), sender=sender,
        today=today.isoformat(),
    )


_STALE_AFTER = timedelta(hours=24)


async def _freshness(session, model) -> tuple[int, bool]:
    """(cuántas filas hay, si el cache está viejo). Guías y notas se sincronizan
    por caminos distintos: una puede estar fresca y la otra no."""
    count = (await session.execute(select(func.count()).select_from(model))).scalar_one()
    if not count:
        return 0, False
    last = (await session.execute(select(func.max(model.synced_at)))).scalar_one_or_none()
    if last is None:
        return count, True
    last_naive = last.replace(tzinfo=None) if last.tzinfo else last
    return count, (datetime.utcnow() - last_naive) > _STALE_AFTER


async def _trip_context_snapshot(session, today: date) -> str:
    """Bloque 'Contexto del viaje': parada de hoy + próximas, sus guías y cuántas
    notas hay. Resuelve deícticos ('acá', 'mañana') sin round-trips extra."""
    from app.bot.active_stop import place_for_date

    docs_count, docs_stale = await _freshness(session, GuideDoc)
    lines = ["Contexto del viaje:"]
    if not docs_count:
        lines.append(
            "- ATENCIÓN: el cache de guías está VACÍO (sync pendiente). No hay "
            "contenido para leer: avisá que todavía no tenés las guías cargadas y "
            "que pruebe en un rato. No inventes nada."
        )
    elif docs_stale:
        # Stale no bloquea (el sync es lazy y en background), pero el agente
        # tiene que poder aclararlo si algo no cuadra.
        lines.append(
            "- OJO: las guías cacheadas están desactualizadas (hace más de un día "
            "que no sincronizan). Respondé igual con lo que hay, pero si te "
            "preguntan por algo recién cargado, aclaralo."
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

    notes_count, notes_stale = await _freshness(session, TripNote)
    lines.append(
        f"- Notas cargadas en Andiamo: {notes_count}"
        + (" (cache desactualizado)" if notes_stale else "")
    )
    # El conteo va en el snapshot para que _unverified_claims no lea "hay 3
    # documentos" como un número inventado.
    tdocs_count, tdocs_stale = await _freshness(session, TripDocument)
    lines.append(
        f"- Documentos guardados en Andiamo: {tdocs_count}"
        + (" (cache desactualizado)" if tdocs_stale else "")
    )
    return "\n".join(lines)


# Datos concretos que exigen evidencia: números (precios, horarios, líneas) y
# símbolos de moneda. Una respuesta con eso y CERO tools en el turno solo puede
# venir del conocimiento general del modelo — justo lo que este canal prohíbe.
_CONCRETE = re.compile(r"\d+(?:[.,]\d+)?")


def _unverified_claims(answer: str, snapshot: str) -> bool:
    """¿La respuesta afirma números que no salen del snapshot del turno?

    Conservador a propósito: si el número aparece en el snapshot (fechas del
    itinerario, cantidad de notas) no cuenta como afirmación nueva."""
    return any(n not in snapshot for n in _CONCRETE.findall(answer))


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

    trace.set_fields(channel="trip")
    snapshot = await _trip_context_snapshot(session, today)
    result = as_result(await chat_client.run(
        system=_render_system(user.username, users, today),
        history=[{"role": e["role"], "content": e["content"]} for e in history],
        user_text=f"{snapshot}\n\nMensaje de {user.username}: {text}",
        tools=build_trip_tools(session),
        max_iterations=s.qa_max_iterations,
        channel="trip",
    ))
    if not result.text:
        # Sin respuesta usable: copy del canal viaje según la causa, sin
        # persistirla — el próximo follow-up sigue colgado del último turno útil.
        return text_reply(copy.chat_degraded("trip", result.outcome))

    # Guarda ESTRUCTURAL de grounding: el prompt ya prohíbe contestar de cultura
    # general, pero prohibir no es garantizar. Si el turno no llamó ninguna
    # herramienta (ni hubo hilo previo del que colgarse) y aun así larga datos
    # concretos que no están en el snapshot, la respuesta no se manda: se
    # devuelve una negativa grounded. Preferimos un "no lo tengo" a un precio
    # inventado con cara de guía.
    # `successful_tools` y no `tool_calls`: una tool que explotó no trajo nada
    # con qué fundamentar la respuesta.
    if (not result.successful_tools and not history
            and _unverified_claims(result.text, snapshot)):
        logger.info("trip_grounding_blocked channel=trip outcome=%s", result.outcome)
        return text_reply(copy.TRIP_NO_EVIDENCE)

    answer = result.text
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
