from decimal import Decimal

from app.balance import Balance, MovementLike, compute_balance

A, B = 1, 2


def mv(type_, split, paid_by, amount):
    return MovementLike(type=type_, split=split, paid_by=paid_by, amount_usd=Decimal(amount))


def test_no_movements_is_settled():
    bal = compute_balance([], A, B)
    assert bal == Balance(debtor_id=None, creditor_id=None, amount_usd=Decimal("0"))


def test_shared_expense_paid_by_a():
    # A paga 100 compartido -> B le debe 50 a A.
    bal = compute_balance([mv("expense", "shared", A, "100")], A, B)
    assert bal.debtor_id == B
    assert bal.creditor_id == A
    assert bal.amount_usd == Decimal("50")


def test_other_only_paid_by_a():
    # A paga 80 pero es todo de B -> B le debe 80 a A.
    bal = compute_balance([mv("expense", "other_only", A, "80")], A, B)
    assert (bal.debtor_id, bal.creditor_id, bal.amount_usd) == (B, A, Decimal("80"))


def test_payer_only_moves_nothing():
    bal = compute_balance([mv("expense", "payer_only", A, "80")], A, B)
    assert bal.amount_usd == Decimal("0")


def test_settlement_reduces_debt():
    # B le debe 50 a A; luego B le paga 50 a A -> saldados.
    movements = [
        mv("expense", "shared", A, "100"),   # B debe 50 a A
        mv("settlement", "shared", B, "50"),  # B paga 50 a A
    ]
    bal = compute_balance(movements, A, B)
    assert bal.amount_usd == Decimal("0")


def test_mixed_nets_out():
    movements = [
        mv("expense", "shared", A, "100"),    # B debe 50 a A
        mv("expense", "shared", B, "40"),     # A debe 20 a B
        mv("expense", "other_only", A, "10"),  # B debe 10 a A
    ]
    # Neto: B debe 50 - 20 + 10 = 40 a A
    bal = compute_balance(movements, A, B)
    assert (bal.debtor_id, bal.creditor_id, bal.amount_usd) == (B, A, Decimal("40"))
