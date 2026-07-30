"""Intent 'question': agente conversacional con herramientas read-only.

Responde consultas de gastos/saldos/itinerario en lenguaje natural, con
memoria corta por wa_id (WhatsAppSessionState) para follow-ups.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app import trace
from app.balance import UNSETTLED
from app.bot import copy
from app.bot.active_stop import get_state_payload, resolve_trip_timezone, update_state_payload
from app.bot.capture import all_users
from app.bot.render import BotReply, text_reply
from app.config import get_settings
from app.db.models import User
from app.llm.chat import as_result
from app.qa.tools import ActionContext, build_tools

_SYSTEM = (
    "Sos Spitwise, el bot de gastos del viaje por Europa de {users}.\n"
    "Estás chateando por WhatsApp con {sender}. Hoy es {today}.\n\n"
    "REGLAS DE DATOS (no negociables):\n"
    "- Todo número que digas tiene que salir de las herramientas o del bloque "
    "'Datos actuales' que acompaña cada mensaje (ya verificado contra la DB). "
    "Nunca inventes montos, fechas ni cantidades.\n"
    "- Si el bloque 'Datos actuales' alcanza para responder (saldo, un gasto "
    "reciente, si algo entra o no al saldo), respondé DIRECTO sin llamar "
    "herramientas: es más rápido.\n"
    "- OJO: el bloque trae SOLO el saldo y los ÚLTIMOS movimientos, no el "
    "historial completo. Para totales o sumas con filtro ('cuánto gastamos en "
    "X', por ciudad/categoría/persona) usá aggregate_expenses SIEMPRE; nunca "
    "respondas 'no hay gastos' o 'USD 0' mirando solo el bloque.\n"
    "- Una PREGUNTA sobre un dato ('¿en qué ciudad quedó X?') se responde con "
    "el dato; no asumas que quieren editar salvo pedido explícito de cambio.\n"
    "- Un gasto 'pendiente' (fecha de pago futura) NO entra al saldo entre los "
    "dos hasta que llegue su fecha; sí cuenta en los totales del viaje.\n"
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


_SNAPSHOT_MOVES = 8  # últimos movimientos que viajan en el snapshot


async def _context_snapshot(session, users: list[User], today: date,
                            tz_name: str | None) -> str:
    """Bloque 'Datos actuales' que acompaña cada pregunta: saldo, pendientes y
    últimos movimientos, en UNA carga de DB. La mayoría de las consultas se
    contesta con esto en un solo round-trip, sin herramientas."""
    from sqlalchemy import select

    from app.balance import compute_balance
    from app.bot.active_stop import place_for_date
    from app.bot.render import ar_number, fmt_date
    from app.db.models import Movement
    from app.trip_time import day_in_tz

    movements = (await session.execute(
        select(Movement).order_by(Movement.id)
    )).scalars().all()
    names = {u.id: u.username for u in users}

    lines = ["Datos actuales (verificados contra la DB en este momento):"]
    stop = await place_for_date(session, today, None)
    if stop is not None:
        lines.append(f"- Parada activa hoy: {stop.name}")

    if len(users) == 2:
        bal = compute_balance(movements, users[0].id, users[1].id)
        if bal.debtor_id is None:
            lines.append("- Saldo: están a mano (solo cuenta lo confirmado)")
        else:
            lines.append(
                f"- Saldo: {names.get(bal.debtor_id)} le debe "
                f"USD {ar_number(bal.amount_usd)} a {names.get(bal.creditor_id)} "
                "(solo cuenta lo confirmado)"
            )
    # `awaiting` cuenta acá igual que `pending`: sigue afuera del saldo. Filtrar
    # solo `pending` hacía que un gasto desapareciera de esta línea justo al
    # vencer, y el LLM se quedaba sin con qué explicar el delta contra el saldo.
    pending = [m for m in movements if m.type == "expense" and m.status in UNSETTLED]
    if pending:
        total_p = sum((m.amount_usd for m in pending if m.amount_usd is not None), Decimal(0))
        lines.append(
            f"- Pendientes (fecha de pago no confirmada, EXCLUIDOS del saldo hasta confirmarse): "
            f"{len(pending)} por USD {ar_number(total_p)}"
        )

    if movements:
        lines.append(
            f"- Últimos movimientos, más nuevo primero (id interno para "
            f"edit_movement/delete_movements, no lo muestres):"
        )
        for m in reversed(movements[-_SNAPSHOT_MOVES:]):
            day = fmt_date(day_in_tz(m.created_at, tz_name))
            payer = names.get(m.paid_by, "?")
            if m.type == "settlement":
                other = next((n for n in names.values() if n != payer), "?")
                lines.append(
                    f"  · id={m.id} · {day} · pago de saldo {payer}→{other} · "
                    f"USD {ar_number(m.amount_usd)}"
                )
                continue
            if m.split == "shared":
                reparto = "50/50"
            elif m.split == "payer_only":
                reparto = f"solo {payer}"
            else:
                reparto = "solo " + next((n for n in names.values() if n != payer), "?")
            line = (
                f"  · id={m.id} · {day} · {m.description or 'gasto'} · "
                f"{m.currency} {ar_number(m.amount)} (USD {ar_number(m.amount_usd)}) · "
                f"{m.city_name or 'sin ciudad'} · pagó {payer} · {reparto}"
            )
            if m.payment_date and m.status == "pending":
                line += f" · PENDIENTE, se paga el {fmt_date(m.payment_date)}"
            elif m.payment_date and m.status == "awaiting":
                line += (
                    f" · VENCIÓ el {fmt_date(m.payment_date)}, falta confirmarlo en la web"
                )
            lines.append(line)
    else:
        lines.append("- Sin movimientos cargados todavía")
    return "\n".join(lines)


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
    trace.set_fields(channel="qa")
    # Snapshot de la DB junto al mensaje: lo simple se contesta sin herramientas
    # (menos round-trips = menos latencia). El historial guarda el texto pelado.
    snapshot = await _context_snapshot(session, users, today, tz_name)
    result = as_result(await chat_client.run(
        system=_render_system(user.username, users, today),
        history=[{"role": e["role"], "content": e["content"]} for e in history],
        user_text=f"{snapshot}\n\nMensaje de {user.username}: {text}",
        tools=build_tools(session, users, asker=user, today=today, ctx=ctx, tz_name=tz_name),
        max_iterations=s.qa_max_iterations,
        channel="qa",
    ))
    # Si una acción preparó una respuesta interactiva (botones), esa manda.
    if ctx.reply is not None:
        reply = ctx.reply
    elif result.text:
        reply = text_reply(result.text)
    elif ctx.performed:
        # El modelo se quedó sin presupuesto DESPUÉS de editar: el cambio ya está
        # commiteado, así que se confirma con lo que pasó de verdad.
        reply = text_reply(copy.action_done(ctx.performed))
    else:
        # Sin respuesta usable: copy por canal + causa, y NO se guarda en el
        # historial — así el próximo follow-up sigue apoyado en el último turno
        # que sí sirvió, en vez de en un "me enredé".
        return text_reply(copy.chat_degraded("qa", result.outcome))

    now = datetime.now(timezone.utc).isoformat()
    history = history + [
        {"role": "user", "content": text, "ts": now},
        {"role": "assistant", "content": reply.text or result.text, "ts": now},
    ]
    await update_state_payload(session, wa_id, qa_history=history[-s.qa_history_max_turns * 2:])
    return reply
