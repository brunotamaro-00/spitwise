from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.bot import copy
from app.categories.catalog import CATEGORIES

_CAT_EMOJI = {name: emoji for name, emoji, _ in CATEGORIES}


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
    """Fecha corta dd/mm, mismo estándar que la web (formatShortDate)."""
    return f"{d.day:02d}/{d.month:02d}"


def ar_number(amount: Decimal) -> str:
    """Número al estándar es-AR de la app: punto de miles, coma decimal, SIEMPRE 1
    decimal ("20,0", "1.234,5", "306,5"). Réplica de frontend/src/lib/format.ts."""
    q = Decimal(amount).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    signo = "-" if q < 0 else ""
    entero, dec = f"{abs(q):.1f}".split(".")
    entero = f"{int(entero):,}".replace(",", ".")
    return f"{signo}{entero},{dec}"


def fmt_money(amount: Decimal, currency: str, amount_usd: Decimal | None = None) -> str:
    """'USD 1.234,5', y para no-USD 'EUR 1.234,5 → USD 1.300,0'."""
    base = f"{currency} {ar_number(amount)}"
    if currency != "USD" and amount_usd is not None:
        return f"{base} → USD {ar_number(amount_usd)}"
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


def _owes_line(mv, payer_name: str, other_name: str) -> str | None:
    """Qué debe el otro por ESTE gasto según el split (determinista, 1 movimiento).
    shared → mitad; other_only → total; payer_only → nada (sin línea)."""
    if mv.type == "settlement" or mv.amount_usd is None:
        return None
    factor = {"shared": Decimal("0.5"), "other_only": Decimal("1")}.get(mv.split)
    if factor is None:
        return None
    debe = Decimal(mv.amount_usd) * factor
    if debe <= 0:
        return None
    return f"⚖️ *{_cap(other_name)}* le debe *USD {ar_number(debe)}* por esto"


def movement_summary(mv, cat_name: str | None, payer_name: str) -> str:
    """Una línea que identifica un movimiento (para botones y confirmaciones)."""
    desc = _cap(mv.description or cat_name or mv.type)
    loc = f" · {mv.city_name}" if mv.city_name else ""
    return f"{desc} · {mv.currency} {ar_number(mv.amount)} · {fmt_date(mv.movement_date)}{loc} · Pagó {_cap(payer_name)}"


def expense_card(mv, cat_name: str | None, payer_name: str, other_name: str) -> str:
    city = mv.city_name or "Sin ciudad"
    lines = [
        copy.H_EXPENSE,
        "",
        f"{cat_label(cat_name)} — {mv.description or 'sin descripción'}",
        f"💰 {fmt_money(mv.amount, mv.currency, mv.amount_usd)}",
        f"📅 {fmt_date(mv.movement_date)} · 📍 {city}",
        f"👤 Pagó {_cap(payer_name)} · {split_label(mv.split, _cap(payer_name), _cap(other_name))}",
    ]
    owes = _owes_line(mv, payer_name, other_name)
    if owes:
        lines.append(owes)
    return "\n".join(lines)


def settlement_card(mv, payer_name: str, other_name: str) -> str:
    return (
        f"{copy.H_SETTLEMENT}\n\n"
        f"*{_cap(payer_name)}* → *{_cap(other_name)}*\n"
        f"💰 {fmt_money(mv.amount, mv.currency, mv.amount_usd)}\n"
        f"📅 {fmt_date(mv.movement_date)}"
    )


def edit_card(mv, diffs: list[tuple[str, str, str]]) -> str:
    """diffs: [(etiqueta, antes, después)] solo de los campos que cambiaron."""
    desc = _cap(mv.description or mv.type)
    lines = "\n".join(f"{label}: {before} → *{after}*" for label, before, after in diffs)
    return f"{copy.H_EDIT} · _{desc}_\n\n{lines}"


def deleted_card(summary: str, *, plural: int | None = None) -> str:
    """Confirmación de borrado con desglose de lo que se borró."""
    if plural and plural > 1:
        return f"{copy.H_DELETE} · {plural} movimientos\n\n{summary}"
    return f"{copy.H_DELETE}\n\n{summary}"


def unknown_reply() -> BotReply:
    return text_reply(copy.NOT_UNDERSTOOD)
