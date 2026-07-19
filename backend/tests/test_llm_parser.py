from datetime import date
from decimal import Decimal

from app.llm.parser import parse_message

CATS = [
    "Alojamiento", "Comida", "Supermercado", "Transporte", "Actividades",
    "Compras", "Salidas", "Regalos", "Salud", "Otros",
]
USERS = ["bruno", "katia"]
TODAY = date(2026, 8, 6)


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    async def parse(self, text, **kwargs):
        return self.payload


def _payload(**over):
    base = {
        "intent": "expense", "amount": None, "currency": None, "description": None,
        "category": None, "split": "shared", "paid_by": None, "date": None, "city": None,
        "confidence": 0.9, "candidates": [], "ref_last": False, "ref_text": None, "ref_date": None,
        "new_amount": None, "new_currency": None, "new_date": None, "new_city": None,
        "new_category": None, "new_description": None, "new_split": None, "new_paid_by": None,
    }
    base.update(over)
    return base


async def _parse(payload, text="x"):
    return await parse_message(text, today=TODAY, category_names=CATS,
                               usernames=USERS, sender="bruno", client=FakeLLM(payload))


async def test_parses_amount_currency_category():
    got = await _parse(_payload(amount="45", currency="GBP", description="cena",
                                category="Comida", confidence=0.95))
    assert got.intent == "expense"
    assert got.amount == Decimal("45")
    assert got.currency == "GBP"
    assert got.category_name == "Comida"
    assert got.split == "shared"
    assert got.is_settlement is False


async def test_currency_absent_stays_none_for_place_resolution():
    got = await _parse(_payload(amount="12", description="helado", category="Comida"))
    assert got.currency is None  # la resuelve la captura según la ciudad de la fecha


async def test_invalid_category_falls_to_otros():
    got = await _parse(_payload(amount="5", category="Museos"))
    assert got.category_name == "Otros"


async def test_low_confidence_keeps_candidates():
    got = await _parse(_payload(amount="5", category="Comida", confidence=0.4,
                                candidates=["Comida", "Compras"]))
    assert got.confidence == 0.4
    assert got.category_candidates == ["Comida", "Compras"]


async def test_explicit_date_and_paid_by():
    got = await _parse(_payload(amount="10", currency="USD", description="cena",
                                category="Comida", date="2026-09-23", paid_by="katia"))
    assert got.payment_date == date(2026, 9, 23)
    assert got.paid_by == "katia"


async def test_unknown_paid_by_is_dropped():
    got = await _parse(_payload(amount="10", paid_by="fulano"))
    assert got.paid_by is None


async def test_edit_intent_normalizes_changes():
    got = await _parse(_payload(intent="edit", ref_text="cena", ref_date="2026-08-05",
                                new_amount="25", new_category="Transporte", new_date="2026-09-23"))
    assert got.intent == "edit"
    assert got.ref_text == "cena"
    assert got.ref_date == date(2026, 8, 5)
    assert got.changes == {
        "amount": Decimal("25"), "category": "Transporte", "date": date(2026, 9, 23),
    }


async def test_invalid_changes_are_dropped():
    got = await _parse(_payload(intent="edit", ref_last=True,
                                new_category="Museos", new_split="mitad", new_paid_by="fulano"))
    assert got.changes == {}


async def test_legacy_payload_without_intent_maps_settlement():
    got = await _parse({"amount": "50", "is_settlement": True, "confidence": 0.9})
    assert got.intent == "settlement"
    assert got.is_settlement is True


def test_render_user_includes_category_descriptions():
    from app.llm.client import _render_user
    cats = [("Transporte", "tren, bus, ferry, teleférico"), ("Otros", "lo que no encaja")]
    out = _render_user("x", TODAY, ["Transporte", "Otros"], USERS, "bruno", categories=cats)
    assert "- Transporte: tren, bus, ferry, teleférico" in out
    assert "NATURALEZA" in out
    assert "SOLO si el gasto de verdad no encaja" in out


def test_render_user_without_descriptions_falls_back_to_flat_list():
    from app.llm.client import _render_user
    out = _render_user("x", TODAY, CATS, USERS, "bruno")
    assert "Categorías válidas: Alojamiento, Comida" in out


async def test_question_intent_is_valid():
    got = await _parse(_payload(intent="question"))
    assert got.intent == "question"


async def test_invalid_intent_defaults_to_unknown():
    got = await _parse(_payload(intent="gibberish", amount="10"))
    assert got.intent == "unknown"


async def test_legacy_payload_without_intent_defaults_to_unknown():
    got = await _parse({"amount": "10", "confidence": 0.9})
    assert got.intent == "unknown"


# --- only_user: el reparto lo calcula el server, no el LLM ---

async def test_only_user_sender_is_payer_only():
    # bruno escribe, nadie más pagó ⇒ paga bruno; 'solo mío' ⇒ payer_only.
    got = await _parse(_payload(amount="10", only_user="bruno"))
    assert got.split == "payer_only"


async def test_only_user_other_person_is_other_only():
    got = await _parse(_payload(amount="10", only_user="katia"))
    assert got.split == "other_only"


async def test_only_user_with_same_paid_by_is_payer_only():
    # 'solo de katia, pagó katia' ⇒ es de quien pagó ⇒ payer_only.
    got = await _parse(_payload(amount="25", only_user="katia", paid_by="katia"))
    assert got.split == "payer_only"


async def test_only_user_null_stays_shared_even_with_paid_by():
    # 'cena 45 pagó katia' no es individual: shared.
    got = await _parse(_payload(amount="45", paid_by="katia"))
    assert got.split == "shared"


async def test_only_user_invalid_falls_back_to_shared():
    got = await _parse(_payload(amount="10", only_user="fulano"))
    assert got.split == "shared"


async def test_new_only_user_goes_to_changes():
    got = await _parse(_payload(intent="edit", ref_last=True, new_only_user="katia"))
    assert got.changes == {"only_user": "katia"}
    got = await _parse(_payload(intent="edit", ref_last=True, new_only_user="shared"))
    assert got.changes == {"only_user": "shared"}


async def test_new_amount_is_total_flag():
    got = await _parse(_payload(intent="edit", ref_last=True, new_amount="480",
                                new_amount_is_total=True))
    assert got.changes == {"amount": Decimal("480"), "amount_is_total": True}
    # Sin monto, el flag solo no genera cambio.
    got = await _parse(_payload(intent="edit", ref_last=True, new_amount_is_total=True))
    assert got.changes == {}


# --- multi-gasto: lista `expenses` → ParsedMessage.batch ---

def _item(**over):
    base = {
        "kind": "expense", "amount": None, "currency": None, "description": None,
        "category": None, "split": "shared", "paid_by": None, "date": None, "city": None,
        "confidence": 0.9, "candidates": [],
    }
    base.update(over)
    return base


async def test_batch_of_three_normalized():
    got = await _parse(_payload(amount="40", category="Comida", description="cena", expenses=[
        _item(amount="40", category="Comida", description="cena"),
        _item(amount="12", category="Transporte", description="taxi"),
        _item(amount="5", category="Museos", description="helado"),  # inválida → Otros
    ]))
    assert len(got.batch) == 3
    assert [p.amount for p in got.batch] == [Decimal("40"), Decimal("12"), Decimal("5")]
    assert got.batch[2].category_name == "Otros"
    assert all(p.intent == "expense" for p in got.batch)
    # El flat sigue siendo el primer ítem (fallback para código single).
    assert got.amount == Decimal("40")


async def test_batch_settlement_item_keeps_kind():
    got = await _parse(_payload(amount="40", expenses=[
        _item(amount="40", category="Comida", description="cena"),
        _item(kind="settlement", amount="50"),
    ]))
    assert len(got.batch) == 2
    assert got.batch[1].is_settlement is True


async def test_batch_items_without_amount_are_dropped():
    got = await _parse(_payload(amount="40", expenses=[
        _item(amount="40", description="cena", category="Comida"),
        _item(amount=None, description="propina"),
    ]))
    assert got.batch == []  # quedó 1 válido → single por el flat


async def test_single_item_list_stays_single():
    got = await _parse(_payload(amount="40", expenses=[_item(amount="40")]))
    assert got.batch == []


async def test_expenses_ignored_for_non_expense_intent():
    got = await _parse(_payload(intent="question", expenses=[
        _item(amount="1"), _item(amount="2"),
    ]))
    assert got.batch == []


async def test_batch_item_fields_normalized_like_flat():
    got = await _parse(_payload(amount="10", expenses=[
        _item(amount="10", currency="euros", paid_by="KATIA", date="2026-08-05",
              city="Roma", split="other_only"),
        _item(amount="3,5", currency="£", paid_by="fulano", split="mitad"),
    ]))
    a, b = got.batch
    assert a.currency == "EUR" and a.paid_by == "katia" and a.split == "other_only"
    assert a.payment_date == date(2026, 8, 5) and a.city == "Roma"
    assert b.amount == Decimal("3.5") and b.currency == "GBP"
    assert b.paid_by is None and b.split == "shared"
