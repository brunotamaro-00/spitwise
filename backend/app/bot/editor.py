import unicodedata
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import copy
from app.bot.capture import _category_id, _map_source, other_user, resolve_place, user_by_username
from app.bot.pending import close_pending, create_pending, load_pending
from app.bot.render import (
    BotReply, ar_number, buttons_reply, cat_label, edit_card, fmt_date, movement_summary,
    split_label, text_reply,
)
from app.db.models import Category, Movement, User
from app.fx import convert_to_usd

_SEARCH_LIMIT = 50  # movimientos recientes donde buscar referencias


async def recent_movement(session: AsyncSession, *, ttl_minutes: int) -> Movement | None:
    """El último gasto cargado, si es lo bastante fresco como para esperar una
    corrección. Sirve de contexto al parser: apenas guardado, un mensaje que ajusta
    monto/ciudad/categoría/división/pagador casi seguro lo corrige, no carga uno nuevo.

    Solo gastos (los settlements no tienen las 5 dimensiones corregibles). El corte
    es por created_at UTC-naive, igual criterio que find_candidates."""
    cutoff = datetime.utcnow() - timedelta(minutes=ttl_minutes)
    return (await session.execute(
        select(Movement).where(Movement.type == "expense", Movement.created_at >= cutoff)
        .order_by(Movement.id.desc()).limit(1)
    )).scalars().first()


async def describe_recent(session: AsyncSession, mv: Movement) -> str:
    """Resumen compacto del último gasto para el prompt del parser (una línea)."""
    payer = (await _payer_name(session, mv)).capitalize()
    other = await other_user(session, (await session.execute(
        select(User).where(User.id == mv.paid_by))).scalar_one())
    other_name = other.username.capitalize() if other else "el otro"
    parts = [
        mv.description or "gasto",
        f"{mv.currency} {ar_number(mv.amount)}",
        mv.city_name or "sin ciudad",
        f"pagó {payer}",
        split_label(mv.split, payer, other_name),
    ]
    cat = await _cat_name(session, mv)
    if cat:
        parts.append(f"categoría {cat}")
    return " · ".join(parts)


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s.casefold())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _score(mv: Movement, ref_tokens: set[str]) -> int:
    """La descripción pesa más que ciudad/raw: los hermanos de un batch comparten
    raw_message ('cena 40, taxi 12…') y empatarían solo por él."""
    desc = _fold(mv.description or "")
    rest = _fold(f"{mv.city_name or ''} {mv.raw_message or ''}")
    return sum(3 if t in desc else (1 if t in rest else 0) for t in ref_tokens)


async def find_candidates(session: AsyncSession, *, ref_last: bool, ref_text: str | None,
                          ref_date: date | None) -> list[Movement]:
    """Movimientos que matchean la referencia, mejor primero. Sin referencia => el último.

    'el museo de ayer' = cargado ayer: la referencia por fecha filtra por día de
    created_at (corte UTC — aceptable para un bot de dos personas en viaje)."""
    q = select(Movement).order_by(Movement.id.desc()).limit(_SEARCH_LIMIT)
    if ref_date is not None:
        q = (select(Movement).where(func.date(Movement.created_at) == ref_date.isoformat())
             .order_by(Movement.id.desc()).limit(_SEARCH_LIMIT))
    movements = (await session.execute(q)).scalars().all()
    if not movements:
        return []

    if ref_last or not ref_text:
        return movements[:1]

    ref_tokens = {t for t in _fold(ref_text).split() if len(t) > 2}
    if not ref_tokens:
        return movements[:1]
    scored = [(m, _score(m, ref_tokens)) for m in movements]
    best = max(s for _, s in scored)
    if best == 0:
        return []
    return [m for m, s in scored if s == best]


async def _payer_name(session, mv: Movement) -> str:
    u = (await session.execute(select(User).where(User.id == mv.paid_by))).scalar_one_or_none()
    return u.username if u else "?"


async def _cat_name(session, mv: Movement) -> str | None:
    if mv.category_id is None:
        return None
    return (await session.execute(
        select(Category.name).where(Category.id == mv.category_id)
    )).scalar_one_or_none()


async def apply_changes(session, mv: Movement, changes: dict, today: date,
                        username: str | None = None) -> list[tuple[str, str, str]]:
    """Aplica cambios a un movimiento con recálculo en cascada. Devuelve diffs (label, antes, después)."""
    diffs: list[tuple[str, str, str]] = []

    if "description" in changes and changes["description"] != mv.description:
        diffs.append(("📝", mv.description or "—", changes["description"]))
        mv.description = changes["description"]

    if "category" in changes:
        old = await _cat_name(session, mv)
        if changes["category"] != old:
            diffs.append(("🏷️", cat_label(old) if old else "—", cat_label(changes["category"])))
            mv.category_id = await _category_id(session, changes["category"])

    if "paid_by" in changes:
        old_name = await _payer_name(session, mv)
        if changes["paid_by"] != old_name:
            new_payer = await user_by_username(session, changes["paid_by"])
            if new_payer is not None:
                diffs.append(("👤", f"Pagó {old_name.capitalize()}", f"Pagó {new_payer.username.capitalize()}"))
                mv.paid_by = new_payer.id

    if "split" in changes and changes["split"] != mv.split:
        payer = await _payer_name(session, mv)
        other = await other_user(session, (await session.execute(
            select(User).where(User.id == mv.paid_by))).scalar_one())
        other_name = other.username.capitalize() if other else "el otro"
        diffs.append(("÷", split_label(mv.split, payer.capitalize(), other_name),
                      split_label(changes["split"], payer.capitalize(), other_name)))
        mv.split = changes["split"]

    # Fecha ("era de ayer"): no se guarda — solo re-imputa la ciudad mirando el
    # itinerario de esa fecha. Con ciudad explícita, un único resolve con ambas.
    new_date = changes.get("date")
    if (new_date is not None or "city" in changes) and mv.type != "settlement":
        slug, city, _cur = await resolve_place(
            session, new_date or today, changes.get("city"), username
        )
        if (slug, city) != (mv.stop_slug, mv.city_name):
            diffs.append(("📍", mv.city_name or "Sin ciudad", city or "Sin ciudad"))
            mv.stop_slug, mv.city_name = slug, city

    # Monto/moneda → recalcular USD.
    money_changed = False
    if "amount" in changes and changes["amount"] != mv.amount:
        diffs.append(("💰", f"{mv.currency} {ar_number(mv.amount)}",
                      f"{mv.currency} {ar_number(changes['amount'])}"))
        mv.amount = changes["amount"]
        money_changed = True
    if "currency" in changes and changes["currency"] != mv.currency:
        diffs.append(("💱", mv.currency, changes["currency"]))
        mv.currency = changes["currency"]
        money_changed = True
    if money_changed:
        # Regla: el TC es siempre el de la fecha de CARGA/edición, no la del gasto.
        amount_usd, rate, src = await convert_to_usd(session, mv.amount, mv.currency, today)
        mv.amount_usd, mv.fx_rate, mv.fx_source = amount_usd, rate, _map_source(src, mv.currency)

    await session.commit()
    return diffs


async def _pick_buttons(session, candidates, action: str, payload: dict, owner: str, question: str) -> BotReply:
    token = await create_pending(session, owner=owner, payload=payload, kind=action)
    buttons = []
    for mv in candidates[:3]:
        label = f"{(mv.description or mv.type)[:16]} · {mv.currency} {mv.amount:.0f} · {fmt_date(mv.created_at.date())}"
        buttons.append((f"{action}:{token}|{mv.id}", label[:20]))
    return buttons_reply(question, buttons)


async def handle_edit(session, user: User, wa_id: str, parsed, today: date) -> BotReply:
    if not parsed.changes:
        return text_reply(
            f"{copy.H_HUH} Entendí que querés *editar*, pero no qué cambiar. "
            "Ej: _la cena de ayer fue 25_."
        )
    candidates = await find_candidates(
        session, ref_last=parsed.ref_last, ref_text=parsed.ref_text, ref_date=parsed.ref_date
    )
    if not candidates:
        return text_reply(f"{copy.H_WARN} No encontré ningún movimiento que matchee esa referencia.")
    if len(candidates) > 1:
        payload = {"changes": _serialize_changes(parsed.changes)}
        return await _pick_buttons(session, candidates, "edit_pick", payload, user.username, "¿Cuál querés editar?")
    return await apply_edit_to(session, user, candidates[0], parsed.changes, today)


async def apply_edit_to(session, user: User, mv: Movement, changes: dict, today: date) -> BotReply:
    diffs = await apply_changes(session, mv, changes, today, user.username)
    if not diffs:
        return text_reply("Nada que cambiar: ya estaba así. 👌")
    return text_reply(edit_card(mv, diffs))


async def handle_delete(session, user: User, wa_id: str, parsed, today: date) -> BotReply:
    candidates = await find_candidates(
        session, ref_last=parsed.ref_last, ref_text=parsed.ref_text, ref_date=parsed.ref_date
    )
    if not candidates:
        return text_reply(f"{copy.H_WARN} No encontré ningún movimiento que matchee esa referencia.")
    if len(candidates) > 1:
        return await _pick_buttons(session, candidates, "del_pick", {}, user.username, "¿Cuál querés borrar?")
    mv = candidates[0]
    payer = await _payer_name(session, mv)
    cat = await _cat_name(session, mv)
    token = await create_pending(
        session, owner=user.username, payload={"ids": [mv.id]}, kind="del_confirm",
    )
    return buttons_reply(
        f"{copy.H_WARN} ¿Borrar este movimiento? Es irreversible.\n{movement_summary(mv, cat, payer)}",
        [(f"del_confirm:{token}", "Borrar 🗑️"), ("del_cancel:0", "Cancelar")],
    )


# --- serialización de changes para pendings (edit multi-candidato) ---

def _serialize_changes(changes: dict) -> dict:
    out = {}
    for k, v in changes.items():
        out[k] = v.isoformat() if isinstance(v, date) else str(v)
    return out


def _deserialize_changes(raw: dict) -> dict:
    from decimal import Decimal
    out = dict(raw)
    if "amount" in out:
        out["amount"] = Decimal(out["amount"])
    if "date" in out:
        out["date"] = date.fromisoformat(out["date"])
    return out


async def apply_edit_pick(session, user: User, token: str, movement_id: int, today: date) -> BotReply:
    data = await load_pending(session, token, owner=user.username)
    if data is None:
        return text_reply("⚠️ Expiró: ese pending ya no está disponible.")
    mv = (await session.execute(select(Movement).where(Movement.id == movement_id))).scalar_one_or_none()
    if mv is None:
        return text_reply("⚠️ No encontrado: ese movimiento ya no existe.")
    reply = await apply_edit_to(session, user, mv, _deserialize_changes(data["changes"]), today)
    await close_pending(session, token)
    return reply


async def apply_delete_pick(session, user: User, token: str, movement_id: int) -> BotReply:
    data = await load_pending(session, token, owner=user.username)
    if data is None:
        return text_reply("⚠️ Expiró: ese pending ya no está disponible.")
    mv = (await session.execute(select(Movement).where(Movement.id == movement_id))).scalar_one_or_none()
    await close_pending(session, token)
    if mv is None:
        return text_reply("⚠️ No encontrado: ese movimiento ya no existe.")
    payer = await _payer_name(session, mv)
    cat = await _cat_name(session, mv)
    confirm_token = await create_pending(
        session, owner=user.username, payload={"ids": [mv.id]}, kind="del_confirm",
    )
    return buttons_reply(
        f"{copy.H_WARN} ¿Borrar este movimiento? Es irreversible.\n{movement_summary(mv, cat, payer)}",
        [(f"del_confirm:{confirm_token}", "Borrar 🗑️"), ("del_cancel:0", "Cancelar")],
    )
