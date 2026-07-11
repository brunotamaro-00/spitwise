from decimal import Decimal

from app.db.models import Movement

_HALF = Decimal("2")


def user_share(m: Movement, user_id: int) -> Decimal:
    """Porción de un gasto atribuible a `user_id` (consumo, independiente de
    quién lo pagó).

    - shared      -> mitad para cada uno
    - payer_only  -> entero para el pagador
    - other_only  -> entero para el que NO pagó
    - settlement  -> no es consumo, 0
    """
    if m.type != "expense":
        return Decimal("0")
    if m.split == "payer_only":
        return m.amount_usd if m.paid_by == user_id else Decimal("0")
    if m.split == "other_only":
        return m.amount_usd if m.paid_by != user_id else Decimal("0")
    return m.amount_usd / _HALF
