"""Cards del bot con fecha de pago: sin countdowns, solo la fecha."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.bot.render import BatchRow, batch_card, expense_card


def _mv(**over):
    base = dict(type="expense", amount=Decimal("301"), currency="CHF",
                amount_usd=Decimal("361.20"), split="shared", description="hostel (2/2)",
                city_name="Interlaken", payment_date=None, status="confirmed")
    base.update(over)
    return SimpleNamespace(**base)


def test_pending_card_shows_payment_date_and_no_debt():
    mv = _mv(status="pending", payment_date=date(2026, 9, 3))
    card = expense_card(mv, "Alojamiento", "bruno", "katia")
    assert "Se paga el 03/09" in card
    assert "TC provisorio" in card
    assert "le debe" not in card  # pending no genera deuda todavía
    assert "días" not in card  # nunca countdown


def test_retroactive_card_shows_paid_date():
    mv = _mv(payment_date=date(2026, 7, 31))
    card = expense_card(mv, "Alojamiento", "bruno", "katia")
    assert "Pagado el 31/07" in card
    assert "le debe" in card  # confirmado sí entra al balance


def test_normal_card_has_no_payment_line():
    card = expense_card(_mv(), "Alojamiento", "bruno", "katia")
    assert "📅" not in card


def test_batch_card_marks_pending_rows():
    rows = [
        BatchRow(mv=_mv(description="hostel (1/2)", amount=Decimal("129"),
                        amount_usd=Decimal("154.80")), cat_name="Alojamiento",
                 payer_name="bruno"),
        BatchRow(mv=_mv(status="pending", payment_date=date(2026, 9, 3)),
                 cat_name="Alojamiento", payer_name="bruno"),
    ]
    card = batch_card(rows, ["bruno", "katia"])
    assert "📅 03/09" in card
    # El neto solo cuenta la cuota confirmada: 129 * 1.2 / 2 = 77.4.
    assert "USD 77,4" in card


def test_awaiting_card_does_not_say_paid():
    """Un awaiting venció pero todavía no entró al balance: la card lo daba por
    'Pagado' (solo distinguía pending) justo cuando falta confirmarlo."""
    mv = _mv(status="awaiting", payment_date=date(2026, 9, 3))
    card = expense_card(mv, "Alojamiento", "bruno", "katia")
    assert "Venció el 03/09" in card
    assert "Pagado el" not in card
    assert "confirmarlo en la web" in card
    assert "le debe" not in card  # sigue fuera del balance
    assert "días" not in card  # nunca countdown
