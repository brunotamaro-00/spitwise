from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.categories.catalog import CATEGORIES

_CAT_EMOJI = {name: emoji for name, emoji in CATEGORIES}
_MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


@dataclass
class BotReply:
    text: str | None = None
    buttons: list[tuple[str, str]] = field(default_factory=list)
    movement_id: int | None = None  # seteado por la captura al crear un movimiento


def text_reply(s: str) -> BotReply:
    return BotReply(text=s)


def buttons_reply(s: str, buttons: list[tuple[str, str]]) -> BotReply:
    return BotReply(text=s, buttons=buttons)


def fmt_date(d: date) -> str:
    return f"{d.day} {_MONTHS[d.month - 1]}"


def fmt_money(amount: Decimal, currency: str, amount_usd: Decimal | None = None) -> str:
    base = f"{currency} {Decimal(amount):.2f}"
    if currency != "USD" and amount_usd is not None:
        return f"{base} → USD {Decimal(amount_usd):.2f}"
    return base


def cat_label(name: str | None) -> str:
    name = name or "Otros"
    emoji = _CAT_EMOJI.get(name, "📦")
    return f"{emoji} {name}"


def split_label(split: str, payer_name: str, other_name: str) -> str:
    return {
        "shared": "÷ 50/50",
        "payer_only": f"Solo {payer_name}",
        "other_only": f"Solo {other_name}",
    }.get(split, "÷ 50/50")


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def movement_summary(mv, cat_name: str | None, payer_name: str) -> str:
    """Una línea que identifica un movimiento (para botones y confirmaciones)."""
    desc = _cap(mv.description or cat_name or mv.type)
    loc = f" · {mv.city_name}" if mv.city_name else ""
    return f"{desc} · {mv.currency} {Decimal(mv.amount):.2f} · {fmt_date(mv.movement_date)}{loc} · Pagó {_cap(payer_name)}"


def expense_card(mv, cat_name: str | None, payer_name: str, other_name: str) -> str:
    city = mv.city_name or "Sin ciudad"
    return (
        "✅ *Gasto guardado*\n\n"
        f"{cat_label(cat_name)} — {mv.description or 'sin descripción'}\n"
        f"💰 {fmt_money(mv.amount, mv.currency, mv.amount_usd)}\n"
        f"📅 {fmt_date(mv.movement_date)} · 📍 {city}\n"
        f"👤 Pagó {_cap(payer_name)} · {split_label(mv.split, _cap(payer_name), _cap(other_name))}"
    )


def settlement_card(mv, payer_name: str, other_name: str) -> str:
    return (
        "💸 *Pago de saldo*\n\n"
        f"{_cap(payer_name)} → {_cap(other_name)}\n"
        f"💰 {fmt_money(mv.amount, mv.currency, mv.amount_usd)}\n"
        f"📅 {fmt_date(mv.movement_date)}"
    )


def edit_card(mv, diffs: list[tuple[str, str, str]]) -> str:
    """diffs: [(etiqueta, antes, después)] solo de los campos que cambiaron."""
    desc = _cap(mv.description or mv.type)
    lines = "\n".join(f"{label}: {before} → {after}" for label, before, after in diffs)
    return f"✏️ *{desc} · editado*\n\n{lines}"


def unknown_reply() -> BotReply:
    return text_reply(
        "🤔 No te entendí. Ejemplos de lo que puedo hacer:\n"
        "· _cena 20 euros_\n"
        "· _pagó katia 15gbp el museo, solo de ella_\n"
        "· _la cena de ayer fue 25, no 20_\n"
        "· _borrá el último_"
    )
