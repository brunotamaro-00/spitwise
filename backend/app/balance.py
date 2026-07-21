from dataclasses import dataclass
from decimal import Decimal

# Estados que todavía NO liquidaron: no generan deuda entre los dos ni aparecen
# en las líneas "le debe". `pending` = fecha de pago futura (TC proxy);
# `awaiting` = fecha alcanzada y TC lockeado, esperando confirmación manual.
UNSETTLED = frozenset({"pending", "awaiting"})


@dataclass
class MovementLike:
    type: str
    split: str
    paid_by: int
    amount_usd: Decimal
    status: str = "confirmed"


@dataclass
class Balance:
    debtor_id: int | None
    creditor_id: int | None
    amount_usd: Decimal


def compute_balance(movements, user_a: int, user_b: int) -> Balance:
    """Neto en USD entre dos usuarios.

    `net` positivo => user_a le debe a user_b; negativo => user_b le debe a user_a.
    """
    net = Decimal("0")
    for m in movements:
        # Un pending/awaiting aún no se confirmó: cuenta en totales/analytics
        # pero no genera deuda entre los dos hasta que se confirme el pagador.
        if getattr(m, "status", "confirmed") in UNSETTLED:
            continue
        payer = m.paid_by
        amt = m.amount_usd
        if m.type == "settlement":
            # payer le paga al otro => reduce lo que payer debe.
            if payer == user_a:
                net -= amt
            else:
                net += amt
            continue
        if m.split == "payer_only":
            continue
        if m.split == "other_only":
            share = amt
        elif m.split == "shared":
            share = amt / Decimal("2")
        else:
            # Split inválido: no silently tratar como shared.
            continue
        # El que NO pagó le debe `share` al que pagó.
        if payer == user_a:
            # user_b le debe a user_a => net (a debe a b) baja.
            net -= share
        else:
            net += share

    if net > 0:
        return Balance(debtor_id=user_a, creditor_id=user_b, amount_usd=net)
    if net < 0:
        return Balance(debtor_id=user_b, creditor_id=user_a, amount_usd=-net)
    return Balance(debtor_id=None, creditor_id=None, amount_usd=Decimal("0"))
