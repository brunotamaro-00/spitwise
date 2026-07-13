from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.active_stop import resolve_active_stop, stop_for_date
from app.bot.pending import close_pending, create_pending, load_pending
from app.bot.render import (
    BotReply, buttons_reply, cat_label, expense_card, settlement_card, text_reply,
)
from app.categories.catalog import CATEGORIES
from app.db.models import Category, Movement, User
from app.fx import convert_to_usd

_CONF_THRESHOLD = 0.6


def _cat_names() -> list[str]:
    return [c[0] for c in CATEGORIES]


async def load_categories(session: AsyncSession) -> list[tuple[str, str | None]]:
    """(name, description) desde la DB, en orden estable — para el prompt del parser."""
    rows = (await session.execute(
        select(Category.name, Category.description).order_by(Category.sort_order)
    )).all()
    # Sin seed todavía (tests con FakeLLM): caer al catálogo.
    return [(n, d) for n, d in rows] or [(n, d) for n, _, d in CATEGORIES]


async def _category_id(session: AsyncSession, name: str | None) -> int | None:
    if not name:
        return None
    return (await session.execute(select(Category.id).where(Category.name == name))).scalar_one_or_none()


def _map_source(src: str, currency: str) -> str:
    # Igual que app/api/movements.py (Plan 2).
    if src == "fallback":
        return "fallback"
    if currency.upper() == "ARS":
        return "dolarapi"
    return "frankfurter"


async def all_users(session: AsyncSession) -> list[User]:
    return (await session.execute(select(User).order_by(User.id))).scalars().all()


async def other_user(session: AsyncSession, user: User) -> User | None:
    return (await session.execute(
        select(User).where(User.id != user.id).order_by(User.id)
    )).scalars().first()


async def user_by_username(session: AsyncSession, username: str) -> User | None:
    return (await session.execute(
        select(User).where(User.username == username)
    )).scalar_one_or_none()


async def resolve_place(session, wa_id: str, movement_date: date, today: date, explicit_city: str | None):
    """(stop_slug, city_name, currency_code) para la fecha del movimiento.

    - Ciudad explícita en el mensaje: si matchea una parada, esa; si no, texto libre.
    - Fecha = hoy: parada activa (respeta el override de sesión para day-trips).
    - Otra fecha: parada del itinerario para esa fecha; fuera de rango => sin ciudad.
    """
    if explicit_city:
        from app.db.models import Stop
        stops = (await session.execute(select(Stop))).scalars().all()
        wanted = explicit_city.strip().casefold()
        for s in stops:
            if (s.name or "").casefold() == wanted:
                return s.slug, s.name, (s.currency_code or "USD")
        return None, explicit_city.strip(), "USD"

    if movement_date == today:
        return await resolve_active_stop(session, wa_id, today)

    stop = await stop_for_date(session, movement_date)
    if stop is None or not (stop.arrival_date and stop.arrival_date <= movement_date):
        return None, None, "USD"
    if stop.departure_date and movement_date >= stop.departure_date:
        return None, None, "USD"
    return stop.slug, stop.name, (stop.currency_code or "USD")


async def _persist(session, *, payer, parsed, amount_usd, rate, src, stop_slug, city_name,
                   cat_id, movement_date, created_by, raw):
    mv = Movement(
        type="settlement" if parsed.is_settlement else "expense",
        amount=parsed.amount, currency=parsed.currency, amount_usd=amount_usd,
        fx_rate=rate, fx_source=_map_source(src, parsed.currency), paid_by=payer.id, split=parsed.split,
        description=parsed.description, category_id=cat_id, stop_slug=stop_slug, city_name=city_name,
        movement_date=movement_date, created_by=created_by.id, raw_message=raw,
    )
    session.add(mv)
    await session.commit()
    return mv


async def handle_capture(session, user: User, wa_id: str, text: str, today: date,
                         *, parsed=None, llm_client=None) -> BotReply:
    if parsed is None:
        from app.llm.parser import parse_message
        users = await all_users(session)
        parsed = await parse_message(
            text, today=today, category_names=_cat_names(),
            usernames=[u.username for u in users], sender=user.username, client=llm_client,
        )

    if parsed.amount is None:
        return text_reply("⚠️ No pude leer el monto. Probá: _cena 20 euros_.")

    movement_date = parsed.movement_date or today
    stop_slug, city_name, place_currency = await resolve_place(
        session, wa_id, movement_date, today, parsed.city
    )
    if parsed.currency is None:
        parsed.currency = place_currency

    # Un saldo nunca lleva ciudad: siempre queda como gasto general.
    if parsed.is_settlement:
        stop_slug, city_name = None, None

    payer = user
    if parsed.paid_by and parsed.paid_by != user.username:
        payer = (await user_by_username(session, parsed.paid_by)) or user
    other = await other_user(session, payer)

    amount_usd, rate, src = await convert_to_usd(session, parsed.amount, parsed.currency, movement_date)

    # Categoría ambigua → pending con botones (solo gastos, no settlement).
    if not parsed.is_settlement and parsed.confidence < _CONF_THRESHOLD and len(parsed.category_candidates) >= 2:
        payload = {
            "amount": str(parsed.amount), "currency": parsed.currency, "amount_usd": str(amount_usd),
            "fx_rate": str(rate), "fx_source": _map_source(src, parsed.currency), "split": parsed.split,
            "description": parsed.description, "stop_slug": stop_slug, "city_name": city_name,
            "movement_date": movement_date.isoformat(), "paid_by": payer.id, "raw_message": text,
        }
        token = await create_pending(session, owner=user.username, payload=payload, kind="cat_pick")
        buttons = []
        for name in parsed.category_candidates[:3]:
            cid = await _category_id(session, name)
            buttons.append((f"cat_pick:{token}|{cid}", cat_label(name)))
        return buttons_reply(
            f"¿Qué categoría? ({parsed.description or 'gasto'} · {parsed.currency} {parsed.amount})", buttons
        )

    cat_id = await _category_id(session, parsed.category_name)
    mv = await _persist(session, payer=payer, parsed=parsed, amount_usd=amount_usd, rate=rate, src=src,
                        stop_slug=stop_slug, city_name=city_name, cat_id=cat_id,
                        movement_date=movement_date, created_by=user, raw=text)
    other_name = other.username if other else "el otro"
    if parsed.is_settlement:
        reply = text_reply(settlement_card(mv, payer.username, other_name))
    else:
        reply = text_reply(expense_card(mv, parsed.category_name, payer.username, other_name))
    reply.movement_id = mv.id
    return reply


async def apply_category_pick(session, user: User, token: str, category_id: int) -> BotReply:
    data = await load_pending(session, token)
    if data is None:
        return text_reply("⚠️ Expiró: ese pending ya no está disponible.")
    payer_id = int(data.get("paid_by") or user.id)
    mv = Movement(
        type="expense", amount=Decimal(data["amount"]), currency=data["currency"],
        amount_usd=Decimal(data["amount_usd"]), fx_rate=Decimal(data["fx_rate"]),
        fx_source=data["fx_source"], paid_by=payer_id, split=data["split"],
        description=data.get("description"), category_id=category_id,
        stop_slug=data.get("stop_slug"), city_name=data.get("city_name"),
        movement_date=date.fromisoformat(data["movement_date"]), created_by=user.id,
        raw_message=data.get("raw_message"),
    )
    session.add(mv)
    await session.commit()
    await close_pending(session, token)
    cat = (await session.execute(select(Category).where(Category.id == category_id))).scalar_one_or_none()
    payer = (await session.execute(select(User).where(User.id == payer_id))).scalar_one_or_none() or user
    other = await other_user(session, payer)
    reply = text_reply(expense_card(mv, cat.name if cat else "Otros", payer.username,
                                    other.username if other else "el otro"))
    reply.movement_id = mv.id
    return reply
