"""Fast-paths de consulta sin LLM: respuestas instantáneas para lo que más se
pregunta en viaje ('saldo', 'total'). Mismos números que la app y el
agente Q&A porque reusan compute_balance / user_share / días de itinerario.
"""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.city_analytics import _itinerary_days
from app.balance import compute_balance
from app.bot import copy
from app.bot.capture import all_users
from app.bot.editor import _fold
from app.bot.render import BotReply, balance_card, text_reply, trip_card
from app.db.models import Movement, User
from app.spend import user_share

# Comparación sobre texto foldeado (sin tildes, casefold): "¿Quién debe?" matchea.
# Solo comandos secos e inequívocos: las preguntas en lenguaje natural
# ("¿cuánto gastamos en Roma?") siguen yendo al agente Q&A, que mantiene el hilo.
_BALANCE = {"saldo", "balance", "quien debe", "quien debe plata", "deuda"}
_TOTAL = {"total", "resumen", "total del viaje"}

_PUNCT = "¿?¡!."


def route(text: str) -> str | None:
    """'balance' | 'total' si el mensaje es un comando rápido."""
    t = _fold(text).strip().strip(_PUNCT).strip()
    if t in _BALANCE:
        return "balance"
    if t in _TOTAL:
        return "total"
    return None


async def handle_balance(session: AsyncSession, user: User) -> BotReply:
    users = await all_users(session)
    if len(users) != 2:
        return text_reply(f"{copy.H_WARN} Necesito exactamente 2 usuarios para calcular el balance.")
    movements = (await session.execute(select(Movement))).scalars().all()
    bal = compute_balance(movements, users[0].id, users[1].id)
    names = {u.id: u.username for u in users}
    return text_reply(balance_card(names.get(bal.debtor_id), names.get(bal.creditor_id), bal.amount_usd))


async def handle_total(session: AsyncSession, user: User) -> BotReply:
    movements = (await session.execute(
        select(Movement).where(Movement.type == "expense")
    )).scalars().all()
    total = sum((m.amount_usd for m in movements), Decimal("0"))
    mine = sum((user_share(m, user.id) for m in movements), Decimal("0"))
    # Con username: `visible_stops` descarta las paradas de otro dueño (Pititas),
    # igual que /ciudades. Sin él contaba noches de más y el $/día del bot no
    # coincidía con el de la web para los mismos datos.
    days = await _itinerary_days(session, None, user.username)
    avg = total / days if days else Decimal("0")
    return text_reply(trip_card(total, mine, len(movements), days, avg, copy.link_home()))
