from dataclasses import dataclass, field
from datetime import date
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
_VALID_INTENTS = {"expense", "settlement", "edit", "delete", "question", "unknown"}

# Campos editables que el LLM devuelve como new_<campo>.
EDIT_FIELDS = ("amount", "currency", "date", "city", "category", "description", "split", "paid_by")


@dataclass
class ParsedMessage:
    intent: str = "unknown"
    # expense / settlement
    amount: Decimal | None = None
    currency: str | None = None  # None => usar la de la ciudad resuelta
    description: str | None = None
    category_name: str | None = None
    split: str = "shared"
    paid_by: str | None = None  # username, None => quien escribe
    movement_date: date | None = None  # None => hoy
    city: str | None = None  # None => itinerario según fecha
    confidence: float = 1.0
    category_candidates: list[str] = field(default_factory=list)
    # edit / delete
    ref_last: bool = False
    ref_text: str | None = None
    ref_date: date | None = None
    changes: dict = field(default_factory=dict)  # campo -> valor nuevo, ya normalizado

    @property
    def is_settlement(self) -> bool:
        return self.intent == "settlement"


def _norm_currency(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in _CURRENCY_ALIASES:
        return _CURRENCY_ALIASES[s]
    up = s.upper()
    return up if len(up) == 3 and up.isalpha() else None


def _to_decimal(v):
    if v is None:
        return None
    try:
        return Decimal(str(v).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _to_date(v) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(str(v))
    except ValueError:
        return None


def normalize_changes(raw: dict, category_names, usernames) -> dict:
    """new_* → dict campo→valor normalizado (descarta inválidos).

    Lo usan el parser (intent edit) y la herramienta edit_movement del agente Q&A.
    """
    changes: dict = {}
    if (v := _to_decimal(raw.get("new_amount"))) is not None:
        changes["amount"] = v
    if (v := _norm_currency(raw.get("new_currency"))) is not None:
        changes["currency"] = v
    if (v := _to_date(raw.get("new_date"))) is not None:
        changes["date"] = v
    if raw.get("new_city"):
        changes["city"] = str(raw["new_city"]).strip()
    if raw.get("new_category") in category_names:
        changes["category"] = raw["new_category"]
    if raw.get("new_description"):
        changes["description"] = str(raw["new_description"]).strip()
    if raw.get("new_split") in _VALID_SPLIT:
        changes["split"] = raw["new_split"]
    if (v := str(raw.get("new_paid_by") or "").strip().lower()) in usernames:
        changes["paid_by"] = v
    return changes


async def parse_message(
    text, *, today: date, category_names: list[str] | None = None, usernames: list[str],
    sender: str, client=None, categories: list[tuple[str, str | None]] | None = None,
) -> ParsedMessage:
    """`categories` = [(nombre, descripción)] para enriquecer el prompt; si no viene,
    alcanza con `category_names` (API vieja, usada en tests)."""
    if categories is not None:
        category_names = [n for n, _ in categories]
    if category_names is None:
        category_names = []
    if client is None:
        from app.llm.client import make_llm
        client = make_llm()
    raw = await client.parse(
        text, today=today, category_names=category_names, usernames=usernames,
        sender=sender, categories=categories,
    )

    intent = raw.get("intent")
    if intent not in _VALID_INTENTS:
        # Compat: payloads viejos sin intent usaban is_settlement.
        intent = "settlement" if raw.get("is_settlement") else "expense"

    category = raw.get("category")
    if category not in category_names:
        category = "Otros"
    split = raw.get("split")
    if split not in _VALID_SPLIT:
        split = "shared"
    paid_by = str(raw.get("paid_by") or "").strip().lower()

    return ParsedMessage(
        intent=intent,
        amount=_to_decimal(raw.get("amount")),
        currency=_norm_currency(raw.get("currency")),
        description=(raw.get("description") or None),
        category_name=category,
        split=split,
        paid_by=paid_by if paid_by in usernames else None,
        movement_date=_to_date(raw.get("date")),
        city=(str(raw.get("city")).strip() if raw.get("city") else None),
        confidence=float(raw.get("confidence", 1.0)),
        category_candidates=[c for c in (raw.get("candidates") or []) if c in category_names],
        ref_last=bool(raw.get("ref_last")),
        ref_text=(raw.get("ref_text") or None),
        ref_date=_to_date(raw.get("ref_date")),
        changes=normalize_changes(raw, category_names, usernames),
    )
