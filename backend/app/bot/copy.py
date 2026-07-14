"""Estándar visual único del bot: encabezados, viñetas y deep-links a la app.

Centraliza textos y formato para que las tarjetas (`render.py`) y los literales
sueltos de los handlers hablen el mismo idioma: voseo rioplatense, emojis y
negritas (`*...*`) consistentes. No importa de `render.py` para evitar ciclos.
"""
from urllib.parse import urlencode

from app.config import get_settings

# --- Encabezados estándar por tipo de respuesta (una sola fuente de verdad) ---
H_EXPENSE = "✅ *Gasto guardado*"
H_SETTLEMENT = "💸 *Pago de saldo*"
H_EDIT = "✏️ *Editado*"
H_DELETE = "🗑️ *Borrado*"
H_WARN = "⚠️"
H_HUH = "🤔"

# --- Errores y avisos conversacionales (nunca error técnico) ---
NOT_UNDERSTOOD = (
    f"{H_HUH} No te seguí. Probá algo como:\n"
    "- _cena 20 euros_\n"
    "- _pagó katia 15gbp el museo, solo de ella_\n"
    "- _la cena de ayer fue 25, no 20_\n"
    "- _borrá el último_\n"
    "- _¿cuánto gastamos en Roma?_"
)
SOMETHING_FAILED = (
    f"{H_WARN} Se me trabó procesando eso. Probá de nuevo, "
    "y si sigue, reformulalo un poco (ej: _cena 20 euros_)."
)
SAVED_BUT_UNCONFIRMED = (
    f"{H_WARN} Lo procesé, pero no pude confirmarte por WhatsApp. "
    "Revisá la app por las dudas."
)
EMPTY_MESSAGE = "Mandame un gasto, ej: _cena 20 euros_."


def bullets(items) -> str:
    """Lista estándar de WhatsApp con guiones."""
    return "\n".join(f"- {it}" for it in items)


def _base_url() -> str:
    return (get_settings().spitwise_url or "").rstrip("/")


def link_movements(*, mine: bool = False, city: str | None = None, category_id: int | None = None,
                   date_from: str | None = None, date_to: str | None = None,
                   q: str | None = None, sort: str | None = None) -> str | None:
    """Deep-link a /movimientos con filtros por URL. None si no hay dominio configurado."""
    base = _base_url()
    if not base:
        return None
    params: dict[str, str] = {}
    if mine:
        params["mine"] = "1"
    if city:
        params["city"] = city
    if category_id is not None:
        params["cat"] = str(category_id)
    if date_from:
        params["from"] = date_from
    if date_to:
        params["to"] = date_to
    if q:
        params["q"] = q
    if sort:
        params["sort"] = sort
    qs = urlencode(params)
    return f"{base}/movimientos" + (f"?{qs}" if qs else "")


def link_city(slug: str | None) -> str | None:
    base = _base_url()
    if not base or not slug:
        return None
    return f"{base}/ciudades?{urlencode({'c': slug})}"


def link_home() -> str | None:
    base = _base_url()
    return f"{base}/" if base else None
