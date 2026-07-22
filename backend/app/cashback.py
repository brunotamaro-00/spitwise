"""Cashback de tarjeta declarado en un gasto.

`Movement.amount` guarda el BRUTO (lo que se tipeó / lo que dice el ticket). El
cashback baja el costo real del gasto: el NETO es derivado (nunca se persiste
aparte) y se hornea en `amount_usd`, que es de donde salen balance, spend
personal, analytics e integración. Regla única en todo el borde de escritura:

    amount_usd = net_amount(amount, kind, value) * fx_rate

`fx_rate` queda como la tasa de mercado pura (net_local × fx_rate = amount_usd).
"""

from decimal import Decimal, ROUND_HALF_UP

_TWO = Decimal("0.01")
_HUNDRED = Decimal("100")

# Modos válidos: pct = porcentaje; amount = monto fijo en la moneda del gasto.
VALID_KINDS = frozenset({"pct", "amount"})


def net_amount(amount: Decimal, kind: str | None, value: Decimal | None) -> Decimal:
    """Monto neto (bruto menos cashback), cuantizado a 0.01 y clampeado a >= 0.

    Sin cashback (kind None o value None) => devuelve el bruto tal cual, así las
    filas históricas y los gastos sin cashback se comportan idénticamente.
    """
    if kind not in VALID_KINDS or value is None:
        return amount
    reduction = (amount * value / _HUNDRED) if kind == "pct" else value
    net = amount - reduction
    if net < 0:
        net = Decimal("0")
    return net.quantize(_TWO, rounding=ROUND_HALF_UP)


def normalize_cashback(kind: str | None, value: Decimal | None) -> tuple[str | None, Decimal | None]:
    """(kind, value) saneados: si algo no cierra, devuelve (None, None) — sin
    cashback. Tolerante: la red de seguridad de los bordes de escritura del bot,
    donde un LLM puede mandar basura y no queremos romper la carga del gasto."""
    if kind not in VALID_KINDS or value is None:
        return None, None
    if value <= 0:
        return None, None
    if kind == "pct" and value > _HUNDRED:
        return None, None
    return kind, value.quantize(_TWO, rounding=ROUND_HALF_UP)


def validate_cashback(kind: str | None, value: Decimal | None, amount: Decimal) -> str | None:
    """Valida el par para la API (estricto): devuelve un mensaje de error si es
    inválido, o None si está OK. A diferencia de `normalize_cashback`, no degrada
    en silencio — el cliente web debe mandar algo coherente.

    Se considera 'sin cashback' solo si AMBOS son None; uno solo seteado es error.
    """
    if kind is None and value is None:
        return None
    if kind is None or value is None:
        return "cashback_kind y cashback_value se setean juntos o ninguno"
    if kind not in VALID_KINDS:
        return "cashback_kind debe ser 'pct' o 'amount'"
    if value <= 0:
        return "cashback_value debe ser mayor a 0"
    if kind == "pct" and value > _HUNDRED:
        return "cashback_value (pct) no puede superar 100"
    if kind == "amount" and value > amount:
        return "el cashback fijo no puede superar el monto del gasto"
    return None
