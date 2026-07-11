from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

# Símbolos/nombres comunes → ISO.
_CURRENCY_ALIASES = {
    "£": "GBP", "libra": "GBP", "libras": "GBP", "pound": "GBP", "pounds": "GBP",
    "€": "EUR", "euro": "EUR", "euros": "EUR",
    "$": "USD", "usd": "USD", "dolar": "USD", "dólar": "USD", "dolares": "USD",
    "chf": "CHF", "franco": "CHF", "francos": "CHF",
    "czk": "CZK", "corona": "CZK", "coronas": "CZK",
    "pln": "PLN", "zloty": "PLN", "zlotys": "PLN",
    "huf": "HUF", "florin": "HUF", "forinto": "HUF", "forintos": "HUF",
    "ars": "ARS", "peso": "ARS", "pesos": "ARS",
}
_VALID_SPLIT = {"shared", "payer_only", "other_only"}


@dataclass
class ParsedMovement:
    amount: Decimal | None
    currency: str | None
    description: str | None
    category_name: str | None
    split: str = "shared"
    is_settlement: bool = False
    confidence: float = 1.0
    category_candidates: list[str] = field(default_factory=list)


def _norm_currency(v, default_currency: str) -> str:
    if v is None:
        return default_currency.upper()
    s = str(v).strip().lower()
    if s in _CURRENCY_ALIASES:
        return _CURRENCY_ALIASES[s]
    up = s.upper()
    return up if len(up) == 3 else default_currency.upper()


def _to_decimal(v):
    if v is None:
        return None
    try:
        return Decimal(str(v).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


async def parse_movement(text, *, default_currency, category_names, client=None):
    if client is None:
        from app.llm.client import make_llm
        client = make_llm()
    raw = await client.parse(text, default_currency, category_names)

    category = raw.get("category")
    if category not in category_names:
        category = "Otros"
    split = raw.get("split", "shared")
    if split not in _VALID_SPLIT:
        split = "shared"
    candidates = [c for c in (raw.get("candidates") or []) if c in category_names]

    return ParsedMovement(
        amount=_to_decimal(raw.get("amount")),
        currency=_norm_currency(raw.get("currency"), default_currency),
        description=(raw.get("description") or None),
        category_name=category,
        split=split,
        is_settlement=bool(raw.get("is_settlement")),
        confidence=float(raw.get("confidence", 1.0)),
        category_candidates=candidates,
    )
