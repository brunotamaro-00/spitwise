from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.active_stop import resolve_active_stop
from app.bot.pending import close_pending, create_pending, load_pending
from app.bot.render import BotReply, buttons_reply, text_reply
from app.categories.catalog import CATEGORIES
from app.db.models import Category, Movement, User
from app.fx import convert_to_usd

_CONF_THRESHOLD = 0.6


def _cat_names() -> list[str]:
    return [c[0] for c in CATEGORIES]


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


async def _persist(session, *, user, parsed, amount_usd, rate, src, stop_slug, city_name, cat_id, today, raw):
    mv = Movement(
        type="settlement" if parsed.is_settlement else "expense",
        amount=parsed.amount, currency=parsed.currency, amount_usd=amount_usd,
        fx_rate=rate, fx_source=_map_source(src, parsed.currency), paid_by=user.id, split=parsed.split,
        description=parsed.description, category_id=cat_id, stop_slug=stop_slug, city_name=city_name,
        movement_date=today, created_by=user.id, raw_message=raw,
    )
    session.add(mv)
    await session.commit()
    return mv


async def handle_capture(session, user: User, wa_id: str, text: str, today: date, *, llm_client=None) -> BotReply:
    from app.llm.parser import parse_movement

    stop_slug, city_name, currency_code = await resolve_active_stop(session, wa_id, today)
    parsed = await parse_movement(text, default_currency=currency_code, category_names=_cat_names(), client=llm_client)
    if parsed.amount is None:
        return text_reply("⚠️ Monto: no pude leer el monto. Probá 'cena 20 euros'.")

    # Un saldo nunca lleva ciudad: siempre queda como gasto general.
    if parsed.is_settlement:
        stop_slug, city_name = None, None

    amount_usd, rate, src = await convert_to_usd(session, parsed.amount, parsed.currency, today)

    # Categoría ambigua → pending con botones (solo gastos, no settlement).
    if not parsed.is_settlement and parsed.confidence < _CONF_THRESHOLD and len(parsed.category_candidates) >= 2:
        payload = {
            "amount": str(parsed.amount), "currency": parsed.currency, "amount_usd": str(amount_usd),
            "fx_rate": str(rate), "fx_source": _map_source(src, parsed.currency), "split": parsed.split,
            "description": parsed.description, "stop_slug": stop_slug, "city_name": city_name,
            "movement_date": today.isoformat(),
        }
        token = await create_pending(session, owner=user.username, payload=payload, kind="cat_pick")
        buttons = []
        for name in parsed.category_candidates[:3]:
            cid = await _category_id(session, name)
            buttons.append((f"cat_pick:{token}|{cid}", name))
        return buttons_reply(f"¿Qué categoría? ({parsed.description or 'gasto'} · {parsed.currency} {parsed.amount})", buttons)

    cat_id = await _category_id(session, parsed.category_name)
    mv = await _persist(session, user=user, parsed=parsed, amount_usd=amount_usd, rate=rate, src=src,
                        stop_slug=stop_slug, city_name=city_name, cat_id=cat_id, today=today, raw=text)
    kind = "Pago (saldo)" if parsed.is_settlement else (parsed.category_name or "Otros")
    loc = f" · {city_name}" if city_name else ""
    reply = text_reply(f"✅ {kind}: {parsed.currency} {parsed.amount} (USD {amount_usd}){loc}")
    if not parsed.is_settlement:
        reply.movement_id = mv.id  # el dispatcher cuelga acá los botones de split
    return reply


async def apply_category_pick(session, user: User, token: str, category_id: int) -> BotReply:
    data = await load_pending(session, token)
    if data is None:
        return text_reply("⚠️ Expiró: ese pending ya no está disponible.")
    mv = Movement(
        type="expense", amount=Decimal(data["amount"]), currency=data["currency"],
        amount_usd=Decimal(data["amount_usd"]), fx_rate=Decimal(data["fx_rate"]),
        fx_source=data["fx_source"], paid_by=user.id, split=data["split"],
        description=data.get("description"), category_id=category_id,
        stop_slug=data.get("stop_slug"), city_name=data.get("city_name"),
        movement_date=date.fromisoformat(data["movement_date"]), created_by=user.id,
    )
    session.add(mv)
    await session.commit()
    await close_pending(session, token)
    cat = (await session.execute(select(Category).where(Category.id == category_id))).scalar_one_or_none()
    reply = text_reply(f"✅ {cat.name if cat else 'Otros'}: {mv.currency} {mv.amount} (USD {mv.amount_usd})")
    reply.movement_id = mv.id
    return reply
