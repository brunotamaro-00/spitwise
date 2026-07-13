from decimal import Decimal

from app.bot.render import ar_number


def format_settlement_confirm(currency: str, amount, amount_usd) -> str:
    monto = f"{currency} {ar_number(Decimal(str(amount)))}"
    usd = ar_number(Decimal(str(amount_usd)))
    return f"🤝 *Pago registrado*: {monto} (USD {usd}). Neto actualizado."
