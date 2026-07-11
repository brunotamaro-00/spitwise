from decimal import Decimal

from app.llm.parser import ParsedMovement, parse_movement

CATS = ["Alojamiento", "Comida", "Transporte", "Actividades", "Compras", "Bebidas/Salidas", "Otros"]


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    async def parse(self, text, default_currency, category_names):
        return self.payload


async def test_parses_amount_currency_category():
    fake = FakeLLM({
        "amount": "45", "currency": "GBP", "description": "cena", "category": "Comida",
        "split": "shared", "is_settlement": False, "confidence": 0.95, "candidates": [],
    })
    got = await parse_movement("cena 45 libras", default_currency="GBP", category_names=CATS, client=fake)
    assert got.amount == Decimal("45")
    assert got.currency == "GBP"
    assert got.category_name == "Comida"
    assert got.split == "shared"
    assert got.is_settlement is False


async def test_default_currency_when_absent():
    fake = FakeLLM({"amount": "12", "currency": None, "description": "helado",
                    "category": "Comida", "split": "shared", "is_settlement": False,
                    "confidence": 0.9, "candidates": []})
    got = await parse_movement("helado 12", default_currency="EUR", category_names=CATS, client=fake)
    assert got.currency == "EUR"


async def test_invalid_category_falls_to_otros():
    fake = FakeLLM({"amount": "5", "currency": "USD", "description": "x",
                    "category": "Museos", "split": "shared", "is_settlement": False,
                    "confidence": 0.9, "candidates": []})
    got = await parse_movement("x 5", default_currency="USD", category_names=CATS, client=fake)
    assert got.category_name == "Otros"


async def test_low_confidence_keeps_candidates():
    fake = FakeLLM({"amount": "5", "currency": "USD", "description": "x", "category": "Comida",
                    "split": "shared", "is_settlement": False, "confidence": 0.4,
                    "candidates": ["Comida", "Compras"]})
    got = await parse_movement("x 5", default_currency="USD", category_names=CATS, client=fake)
    assert got.confidence == 0.4
    assert got.category_candidates == ["Comida", "Compras"]
