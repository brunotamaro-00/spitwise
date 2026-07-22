from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.balance import UNSETTLED
from app.bot import copy
from app.cashback import net_amount
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


def cashback_text(kind: str | None, value: Decimal | None, currency: str) -> str:
    """Etiqueta corta del cashback: '2%' | '5 CHF' | '—' (sin cashback)."""
    if kind not in ("pct", "amount") or value is None:
        return "—"
    return f"{ar_number(value)}%" if kind == "pct" else f"{ar_number(value)} {currency}"


def _cashback_line(mv) -> str | None:
    """Línea de cashback para la card, con el bruto (amount = bruto tipeado)."""
    kind = getattr(mv, "cashback_kind", None)
    value = getattr(mv, "cashback_value", None)
    if kind not in ("pct", "amount") or value is None:
        return None
    return (
        f"💸 Cashback {cashback_text(kind, value, mv.currency)} "
        f"· bruto {mv.currency} {ar_number(mv.amount)}"
    )


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
    # Un pending/awaiting todavía no entra al balance: no mostrar deuda por esto.
    if getattr(mv, "status", "confirmed") in UNSETTLED:
        return None
    factor = {"shared": Decimal("0.5"), "other_only": Decimal("1")}.get(mv.split)
    if factor is None:
        return None
    debe = Decimal(mv.amount_usd) * factor
    if debe <= 0:
        return None
    return f"⚖️ *{_cap(other_name)}* le debe *USD {ar_number(debe)}* por esto"


def movement_summary(mv, cat_name: str | None, payer_name: str) -> str:
    """Una línea que identifica un movimiento (para botones y confirmaciones).
    La fecha es la de carga: el único eje temporal que queda."""
    desc = _cap(mv.description or cat_name or mv.type)
    loc = f" · {mv.city_name}" if mv.city_name else ""
    return f"{desc} · {mv.currency} {ar_number(mv.amount)} · {fmt_date(mv.created_at.date())}{loc} · Pagó {_cap(payer_name)}"


def _payment_line(mv) -> str | None:
    """Línea de fecha de pago, solo cuando difiere del caso normal (hoy):
    pending => se paga en el futuro con TC provisorio; confirmed con fecha =>
    retroactivo pagado ese día. Sin countdowns."""
    if not getattr(mv, "payment_date", None):
        return None
    if getattr(mv, "status", "confirmed") == "pending":
        return f"📅 Se paga el {fmt_date(mv.payment_date)} · TC provisorio"
    return f"📅 Pagado el {fmt_date(mv.payment_date)}"


def expense_card(mv, cat_name: str | None, payer_name: str, other_name: str) -> str:
    city = mv.city_name or "Sin ciudad"
    # El monto mostrado es el NETO (bruto - cashback); amount guarda el bruto.
    net = net_amount(Decimal(mv.amount), getattr(mv, "cashback_kind", None),
                     getattr(mv, "cashback_value", None))
    lines = [
        copy.H_EXPENSE,
        "",
        f"{cat_label(cat_name)} — {mv.description or 'sin descripción'}",
        f"💰 {fmt_money(net, mv.currency, mv.amount_usd)}",
    ]
    cashback = _cashback_line(mv)
    if cashback:
        lines.append(cashback)
    lines += [
        f"📍 {city}",
        f"👤 Pagó {_cap(payer_name)} · {split_label(mv.split, _cap(payer_name), _cap(other_name))}",
    ]
    payment = _payment_line(mv)
    if payment:
        lines.append(payment)
    owes = _owes_line(mv, payer_name, other_name)
    if owes:
        lines.append(owes)
    return "\n".join(lines)


@dataclass
class BatchRow:
    """Un movimiento recién guardado de un mensaje multi-gasto, listo para render."""
    mv: object
    cat_name: str | None
    payer_name: str
    uncertain: bool = False  # categoría dudosa => ❓ (sin botones en batch)


def _batch_owes_line(rows: list[BatchRow], usernames: list[str]) -> str | None:
    """Neto entre los dos por ESTE batch, misma aritmética por ítem que _owes_line
    (shared → mitad, other_only → todo, payer_only → nada; settlement acredita
    el total al que paga)."""
    if len(usernames) != 2:
        return None
    owed = {u: Decimal(0) for u in usernames}  # cuánto le deben A ese usuario
    for r in rows:
        mv = r.mv
        if mv.amount_usd is None or r.payer_name not in owed:
            continue
        # Los pending/awaiting no entran al balance todavía.
        if getattr(mv, "status", "confirmed") in UNSETTLED:
            continue
        if mv.type == "settlement":
            owed[r.payer_name] += Decimal(mv.amount_usd)
            continue
        factor = {"shared": Decimal("0.5"), "other_only": Decimal("1")}.get(mv.split)
        if factor:
            owed[r.payer_name] += Decimal(mv.amount_usd) * factor
    a, b = usernames
    net = owed[a] - owed[b]
    if net == 0:
        return None
    debtor, amt = (b, net) if net > 0 else (a, -net)
    return f"⚖️ *{_cap(debtor)}* le debe *USD {ar_number(amt)}* por esto"


def batch_card(rows: list[BatchRow], usernames: list[str]) -> str:
    """Confirmación única de un mensaje multi-gasto: header con lo común a todos,
    una línea por ítem (con sufijos solo donde difiere), total y neto."""
    cities = [r.mv.city_name for r in rows if r.mv.type != "settlement"]
    payers = [r.payer_name for r in rows]
    common_city = cities[0] if cities and all(c == cities[0] for c in cities) else None
    common_payer = payers[0] if len(set(payers)) == 1 else None

    meta = []
    if common_city:
        meta.append(f"📍 {common_city}")
    if common_payer:
        meta.append(f"👤 Pagó {_cap(common_payer)}")
    head = copy.H_BATCH.format(n=len(rows))
    if meta:
        head += " · " + " · ".join(meta)

    lines = [head, ""]
    for r in rows:
        mv = r.mv
        if mv.type == "settlement":
            line = f"- 💸 Saldo · {fmt_money(mv.amount, mv.currency, mv.amount_usd)}"
        else:
            emoji = _CAT_EMOJI.get(r.cat_name or "Otros", "📦")
            desc = mv.description or (r.cat_name or "gasto").lower()
            flag = " ❓" if r.uncertain else ""
            net = net_amount(Decimal(mv.amount), getattr(mv, "cashback_kind", None),
                             getattr(mv, "cashback_value", None))
            line = f"- {emoji} {desc}{flag} · {fmt_money(net, mv.currency, mv.amount_usd)}"
            if getattr(mv, "cashback_kind", None):
                line += f" · 💸 {cashback_text(mv.cashback_kind, mv.cashback_value, mv.currency)}"
            if mv.split != "shared":
                other = next((u for u in usernames if u != r.payer_name), "el otro")
                line += f" · {split_label(mv.split, _cap(r.payer_name), _cap(other))}"
        if not common_city and mv.city_name:
            line += f" · {mv.city_name}"
        if not common_payer:
            line += f" · pagó {_cap(r.payer_name)}"
        if getattr(mv, "status", "confirmed") == "pending" and mv.payment_date:
            line += f" · 📅 {fmt_date(mv.payment_date)}"
        lines.append(line)

    total = sum((Decimal(r.mv.amount_usd) for r in rows
                 if r.mv.type != "settlement" and r.mv.amount_usd is not None), Decimal(0))
    if total > 0:
        lines.append("")
        lines.append(f"💰 Total: *USD {ar_number(total)}*")
    owes = _batch_owes_line(rows, usernames)
    if owes:
        lines.append(owes)
    if any(r.uncertain for r in rows):
        lines.append(copy.BATCH_CAT_HINT)
    return "\n".join(lines)


def settlement_card(mv, payer_name: str, other_name: str) -> str:
    return (
        f"{copy.H_SETTLEMENT}\n\n"
        f"*{_cap(payer_name)}* → *{_cap(other_name)}*\n"
        f"💰 {fmt_money(mv.amount, mv.currency, mv.amount_usd)}"
    )


def edit_card(mv, diffs: list[tuple[str, str, str]]) -> str:
    """diffs: [(etiqueta, antes, después)] solo de los campos que cambiaron."""
    desc = _cap(mv.description or mv.type)
    lines = "\n".join(f"{label}: {before} → *{after}*" for label, before, after in diffs)
    return f"{copy.H_EDIT} · _{desc}_\n\n{lines}"


def batch_total_card(siblings, old_total: Decimal, new_total: Decimal) -> str:
    """Card de un batch/cuotas re-escalado a un total nuevo: total viejo → nuevo
    y cómo quedó cada parte."""
    import re
    first = siblings[0]
    base_desc = re.sub(r"\s*\(\d+/\d+\)$", "", first.description or "gasto")
    lines = [
        f"{copy.H_EDIT} · _{_cap(base_desc)}_",
        "",
        f"💰 Total: {first.currency} {ar_number(old_total)} → *{first.currency} {ar_number(new_total)}*",
    ]
    for m in siblings:
        line = f"- {m.description or 'gasto'} · {fmt_money(m.amount, m.currency, m.amount_usd)}"
        if getattr(m, "status", "confirmed") == "pending" and m.payment_date:
            line += f" · 📅 {fmt_date(m.payment_date)}"
        lines.append(line)
    return "\n".join(lines)


def deleted_card(summary: str, *, plural: int | None = None) -> str:
    """Confirmación de borrado con desglose de lo que se borró."""
    if plural and plural > 1:
        return f"{copy.H_DELETE} · {plural} movimientos\n\n{summary}"
    return f"{copy.H_DELETE}\n\n{summary}"


def balance_card(debtor: str | None, creditor: str | None, amount: Decimal) -> str:
    """Tarjeta del fast-path 'saldo': quién le debe a quién, o a mano."""
    if not debtor or not creditor:
        return "⚖️ *Balance*\n\nEstán a mano 🤝"
    return f"⚖️ *Balance*\n\n*{_cap(debtor)}* le debe *USD {ar_number(amount)}* a *{_cap(creditor)}*"


def trip_card(total: Decimal, mine: Decimal, count: int, days: int, avg: Decimal,
              link: str | None) -> str:
    """Tarjeta del fast-path 'total': resumen de todo el viaje."""
    lines = [
        "🧳 *Total del viaje*",
        "",
        f"💸 Total: *USD {ar_number(total)}* · {count} gasto{'s' if count != 1 else ''}",
        f"👤 Tu parte: USD {ar_number(mine)}",
    ]
    if days > 0:
        lines.append(f"📅 {days} días · promedio *USD {ar_number(avg)}* por día")
    if link:
        lines.append(f"📲 {link}")
    return "\n".join(lines)


def unknown_reply() -> BotReply:
    return text_reply(copy.NOT_UNDERSTOOD)


def _document_lines(kind: str, label: str, note: str | None, stop_name: str | None,
                    doc_date: date | None) -> list[str]:
    from app.bot.documents.kinds import kind_label
    lines = [
        f"{kind_label(kind)} — *{label}*",
        f"📍 {stop_name or 'General'}",
        f"📅 {fmt_date(doc_date) if doc_date else 'Sin fecha'}",
    ]
    if note:
        lines.append(f"📝 {note}")
    return lines


def document_preview_card(kind: str, label: str, note: str | None, stop_name: str | None,
                          doc_date: date | None, *, not_travel: bool = False) -> str:
    lines = [copy.H_DOC, ""] + _document_lines(kind, label, note, stop_name, doc_date)
    if not_travel:
        lines.append(copy.DOC_NOT_TRAVEL_HINT)
    lines.append("")
    lines.append(copy.DOC_PREVIEW_HINT)
    return "\n".join(lines)


def document_saved_card(kind: str, label: str, note: str | None, stop_name: str | None,
                        doc_date: date | None, link: str | None) -> str:
    lines = [copy.H_DOC_SAVED, ""] + _document_lines(kind, label, note, stop_name, doc_date)
    if link:
        lines.append(f"📲 {link}")
    return "\n".join(lines)
