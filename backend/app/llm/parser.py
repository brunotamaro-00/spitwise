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
_VALID_INTENTS = {"expense", "settlement", "edit", "delete", "question", "trip_question", "unknown"}

# Campos editables que el LLM devuelve como new_<campo>.
EDIT_FIELDS = ("amount", "currency", "date", "city", "category", "description", "split", "paid_by")
_VALID_CASHBACK_KINDS = {"pct", "amount"}


def split_for(only_user: str | None, payer_username: str) -> str:
    """Split del movimiento a partir de DE QUIÉN es el gasto (`only_user`) y de
    quién lo pagó. La aritmética relativa al pagador (payer_only/other_only) es
    del server: el LLM solo dice de quién es el gasto, nunca calcula el reparto."""
    if not only_user or only_user == "shared":
        return "shared"
    return "payer_only" if only_user == payer_username else "other_only"


@dataclass
class Installment:
    """Una etapa de un gasto pagado en partes ('30% hoy y el resto el 3-sep').
    percent y amount vienen del mensaje; la etapa 'el resto' no trae ninguno.
    Los montos finales los calcula el server (capture.expand_installments),
    nunca la aritmética del LLM."""

    percent: Decimal | None = None  # 0..100
    amount: Decimal | None = None  # monto explícito de la etapa
    pay_date: date | None = None  # None = hoy
    currency: str | None = None  # ISO si la etapa tiene moneda propia (seña USD + resto GBP)


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
    # Fecha en que se paga/pagó el gasto ("ayer", "el 3 de septiembre"). Elige la
    # parada mirando el itinerario Y se persiste como Movement.payment_date
    # (futura => pending con TC proxy; pasada => TC histórico). None => hoy.
    payment_date: date | None = None
    # Fecha con la que se elige la PARADA, cuando difiere de payment_date. La
    # setea `expand_installments`: las cuotas de un mismo gasto comparten lugar
    # (el del gasto), aunque cada una se pague en su fecha. Sin esto, "30% hoy y
    # el resto el 3-sep" mandaba las dos mitades a ciudades distintas — y con
    # `owner_split` de por medio, a splits distintos. None => usar payment_date.
    place_date: date | None = None
    city: str | None = None  # None => itinerario estricto por fecha (fuera de rango => General)
    # Cashback de tarjeta. kind='pct' (value=%) | 'amount' (value=monto fijo en la
    # moneda del gasto). Ambos None => sin cashback. amount sigue siendo el bruto.
    cashback_kind: str | None = None
    cashback_value: Decimal | None = None
    confidence: float = 1.0
    category_candidates: list[str] = field(default_factory=list)
    # edit / delete
    ref_last: bool = False
    ref_text: str | None = None
    ref_date: date | None = None
    changes: dict = field(default_factory=dict)  # campo -> valor nuevo, ya normalizado
    # Mensaje multi-gasto: 2+ ítems normalizados (cada uno un ParsedMessage
    # expense/settlement autocontenido). Vacío => single, camino de siempre.
    batch: list["ParsedMessage"] = field(default_factory=list)
    # UN gasto pagado en etapas: amount lleva el total y acá van las partes.
    # Vacío => pago único.
    installments: list[Installment] = field(default_factory=list)

    @property
    def is_settlement(self) -> bool:
        return self.intent == "settlement"


def _norm_cashback(
    raw: dict, prefix: str = "", amount: Decimal | None = None
) -> tuple[str | None, Decimal | None]:
    """(kind, value) saneados desde `<prefix>cashback_kind`/`<prefix>cashback_value`.
    Degrada a (None, None) si algo no cierra (invariante: no romper la carga).

    `amount` (cuando se conoce acá) descarta un cashback fijo mayor al gasto. En
    el camino de edit el monto de referencia vive en el movimiento, no en el
    payload: ese techo lo aplica `editor.apply_changes`."""
    from app.cashback import normalize_cashback
    kind = str(raw.get(f"{prefix}cashback_kind") or "").strip().lower() or None
    if kind not in _VALID_CASHBACK_KINDS:
        kind = None
    return normalize_cashback(kind, _to_decimal(raw.get(f"{prefix}cashback_value")), amount)


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
    # only_user = de quién pasa a ser el gasto ('shared' | username). El split
    # concreto lo deriva el editor contra el pagador EFECTIVO (post new_paid_by).
    only = str(raw.get("new_only_user") or "").strip().lower()
    if only == "shared" or only in usernames:
        changes["only_user"] = only
    elif raw.get("new_split") in _VALID_SPLIT:  # compat payloads viejos / tests
        changes["split"] = raw["new_split"]
    if (v := str(raw.get("new_paid_by") or "").strip().lower()) in usernames:
        changes["paid_by"] = v
    # Cashback: 'new_cashback_kind'='none' lo saca; kind+value válidos lo setean.
    if str(raw.get("new_cashback_kind") or "").strip().lower() == "none":
        changes["cashback"] = (None, None)
    else:
        cb_kind, cb_value = _norm_cashback(raw, prefix="new_")
        if cb_kind is not None:
            changes["cashback"] = (cb_kind, cb_value)
    # Flag de alcance del monto: el nuevo monto es el TOTAL de un batch/cuotas.
    if "amount" in changes and raw.get("new_amount_is_total"):
        changes["amount_is_total"] = True
    return changes


def _norm_installments(raw_list) -> list[Installment]:
    """Etapas crudas → Installment. La validación y los montos finales son del
    server (capture.expand_installments), nunca de la aritmética del LLM."""
    return [
        Installment(
            percent=_to_decimal(it.get("percent")),
            amount=_to_decimal(it.get("amount")),
            pay_date=_to_date(it.get("date")),
            currency=_norm_currency(it.get("currency")),
        )
        for it in (raw_list or [])
        if isinstance(it, dict)
    ]


def _normalize_expense(raw: dict, category_names, usernames, sender: str | None = None) -> ParsedMessage:
    """Normaliza un gasto/settlement (flat o ítem de `expenses`) a ParsedMessage."""
    intent = "settlement" if raw.get("kind") == "settlement" else "expense"
    category = raw.get("category")
    if category not in category_names:
        category = "Otros"
    paid_by = str(raw.get("paid_by") or "").strip().lower()
    payer = paid_by if paid_by in usernames else sender
    # only_user (de quién es el gasto) manda; `split` directo queda como compat
    # de payloads viejos / tests con FakeLLM.
    only = str(raw.get("only_user") or "").strip().lower()
    if only in usernames or only == "shared":
        split = split_for(None if only == "shared" else only, payer or "")
    else:
        split = raw.get("split")
        if split not in _VALID_SPLIT:
            split = "shared"
    insts = _norm_installments(raw.get("installments")) if intent == "expense" else []
    amount = _to_decimal(raw.get("amount"))
    cb_kind, cb_value = _norm_cashback(raw, amount=amount) if intent == "expense" else (None, None)
    return ParsedMessage(
        intent=intent,
        amount=amount,
        currency=_norm_currency(raw.get("currency")),
        description=(raw.get("description") or None),
        category_name=category,
        split=split,
        paid_by=paid_by if paid_by in usernames else None,
        payment_date=_to_date(raw.get("date")),
        city=(str(raw.get("city")).strip() if raw.get("city") else None),
        cashback_kind=cb_kind,
        cashback_value=cb_value,
        confidence=float(raw.get("confidence", 1.0)),
        category_candidates=[c for c in (raw.get("candidates") or []) if c in category_names],
        installments=insts if len(insts) >= 2 else [],
    )


async def parse_message(
    text, *, today: date, category_names: list[str] | None = None, usernames: list[str],
    sender: str, client=None, categories: list[tuple[str, str | None]] | None = None,
    city_names: list[str] | None = None, last_expense: str | None = None,
) -> ParsedMessage:
    """`categories` = [(nombre, descripción)] para enriquecer el prompt; si no viene,
    alcanza con `category_names` (API vieja, usada en tests).

    `city_names` = paradas del itinerario: sin ellas el LLM solo reconoce ciudades
    por cultura general y se pierde las de nombre propio (Pititas, Highlands…).

    `last_expense` = resumen del gasto recién cargado (si sigue fresco): permite
    pescar correcciones naturales ('contalo solo para katia') como intent='edit'.
    """
    if categories is not None:
        category_names = [n for n, _ in categories]
    if category_names is None:
        category_names = []
    if client is None:
        from app.llm.client import make_llm
        client = make_llm()
    raw = await client.parse(
        text, today=today, category_names=category_names, usernames=usernames,
        sender=sender, categories=categories, city_names=city_names, last_expense=last_expense,
    )

    intent = raw.get("intent")
    if intent not in _VALID_INTENTS:
        # Compat: payloads viejos sin intent usaban is_settlement; resto => unknown.
        intent = "settlement" if raw.get("is_settlement") else "unknown"

    parsed = _normalize_expense(raw, category_names, usernames, sender)
    parsed.intent = intent
    parsed.ref_last = bool(raw.get("ref_last"))
    parsed.ref_text = raw.get("ref_text") or None
    parsed.ref_date = _to_date(raw.get("ref_date"))
    parsed.changes = normalize_changes(raw, category_names, usernames)

    # Multi-gasto: 2+ ítems válidos (con monto) => batch; con 1 alcanza el flat
    # (el prompt pide flat = primer ítem), y otros intents lo ignoran.
    if intent == "expense":
        items = [
            p for it in (raw.get("expenses") or [])
            if (p := _normalize_expense(it, category_names, usernames, sender)).amount is not None
        ]
        if len(items) >= 2:
            # Cada ítem lleva sus propias etapas (installments); el flat espeja
            # al primero, así que sus etapas sueltas se descartan.
            parsed.batch = items
            parsed.installments = []
    return parsed
