"""Estándar visual único del bot: encabezados, viñetas y deep-links a la app.

Centraliza textos y formato para que las tarjetas (`render.py`) y los literales
sueltos de los handlers hablen el mismo idioma: voseo rioplatense, emojis y
negritas (`*...*`) consistentes. No importa de `render.py` para evitar ciclos.
"""
from urllib.parse import urlencode

from app.config import get_settings

# --- Encabezados estándar por tipo de respuesta (una sola fuente de verdad) ---
H_EXPENSE = "✅ *Gasto guardado*"
H_BATCH = "✅ *{n} gastos guardados*"
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
# Etapas declaradas que no cierran: no se guarda nada. Guardar el total como un
# gasto único dejaba mal la fecha de pago y el status, y nadie se enteraba.
INSTALLMENTS_UNCLEAR = (
    f"{H_HUH} Entendí que eso se paga *en partes*, pero no me cerraron los montos, "
    "así que no lo guardé. Decímelo con el total y las etapas: "
    "_hostel 430 chf, 30% hoy y el resto el 3 de septiembre_."
)
NON_POSITIVE_AMOUNT = (
    f"{H_WARN} Un gasto tiene que tener un monto mayor a cero. "
    "Probá: _cena 20 euros_."
)

# --- Degradación de los agentes Q&A, por canal y por causa --------------------
# Un solo "me enredé" para todo escondía cosas distintas: el proveedor caído, la
# consulta demasiado ancha o las herramientas fallando. Cada una se dice como es
# y sugiere lo que de verdad ayuda; ninguna se guarda en el historial.
_DEGRADED = {
    "qa": {
        "provider_error": (
            f"{H_WARN} Se me cortó la conexión justo ahí. Mandámelo de nuevo en un toque."
        ),
        "tool_error": (
            f"{H_WARN} No pude leer los datos para responder eso. Probá otra vez, "
            "y si sigue, pedímelo más simple (ej: _gastos de Roma_)."
        ),
        "budget": (
            f"{H_HUH} Esa consulta me quedó muy ancha y no llegué a cerrarla. "
            "Acotala un poco: _gastos de Roma en comida_ · _cuánto puse yo en septiembre_."
        ),
    },
    "trip": {
        "provider_error": (
            f"{H_WARN} Se me cortó la conexión justo ahí. Repetímelo en un toque."
        ),
        "tool_error": (
            f"{H_WARN} No pude abrir las guías recién. Probá de nuevo en un rato."
        ),
        "budget": (
            f"{H_HUH} Me perdí buscando en las guías. Preguntámelo más puntual "
            "(ej: _entradas del Coliseo_ · _cómo llegar a Sintra_)."
        ),
    },
}


def chat_degraded(channel: str, outcome: str) -> str:
    """Copy de degradación según canal y outcome del loop (`llm/chat.py`)."""
    table = _DEGRADED.get(channel) or _DEGRADED["qa"]
    if outcome == "provider_error":
        return table["provider_error"]
    if outcome == "tool_error":
        return table["tool_error"]
    return table["budget"]


# El canal viaje no puede contestar de memoria: si el turno no consultó nada,
# esto reemplaza a la respuesta (ver trip_qa._unverified_claims).
TRIP_NO_EVIDENCE = (
    f"{H_HUH} No lo encontré en las guías ni en las notas, y de memoria no te lo "
    "invento. Preguntámelo con el lugar o el doc (ej: _actividades de Viena_ · "
    "_transporte en Praga_) y busco de nuevo."
)


# Falso cero: el agente negó gastos sin haberlos sumado. No se le manda el cero
# (sería un dato falso) ni se inventa un total: se pide la consulta concreta.
QA_UNVERIFIED_ZERO = (
    f"{H_HUH} No quiero contestarte de memoria y me faltó chequearlo. "
    "Pedímelo con el filtro concreto: _gastos de Roma_ · _cuánto gastamos en comida_ · "
    "_cuánto puse yo en septiembre_."
)


def correction_hint(description: str | None, summary: str) -> str:
    """Guía única para corregir el último gasto cargado. La usan el dispatcher
    (gasto sin monto justo después de cargar) y el editor (edit sin cambios):
    dos dead-ends distintos que llevaban al mismo lugar, con textos distintos."""
    return (
        f"{H_HUH} ¿Querías corregir *{description or 'el último gasto'}* ({summary})?\n"
        "Decime qué cambiar: _solo katia_ · _fueron 45_ · _en Paris_ · "
        "_pagó bruno_ · _es transporte_."
    )


def action_done(performed: list[str]) -> str:
    """Confirmación determinística de acciones YA aplicadas cuando el modelo no
    llegó a redactar: el cambio está en la DB, no se puede responder 'me enredé'."""
    detalle = "\n".join(f"· {p}" for p in performed)
    return f"{H_EDIT}\n{detalle}\n_(no llegué a redactarte el resto, pero el cambio quedó)_"


# --- Canal documentos (adjuntos → Andiamo) ---
H_DOC = "📎 *Documento*"
H_DOC_SAVED = "📎 *Documento guardado en Andiamo*"
DOC_UNSUPPORTED = (
    f"{H_WARN} Ese tipo de archivo no lo puedo archivar. "
    "Mandame un PDF, JPG, PNG o WebP."
)
DOC_TOO_BIG = f"{H_WARN} El archivo es muy pesado (máximo 20 MB)."
DOC_NO_ANDIAMO = (
    f"{H_WARN} No tengo conectado Andiamo, así que no puedo archivar documentos por ahora."
)
DOC_READ_FAILED = (
    f"{H_WARN} No pude leer el archivo. Probá mandarlo de nuevo en un rato."
)
DOC_UPLOAD_FAILED = (
    f"{H_WARN} No pude subirlo a Andiamo. Tocá *Guardar* de nuevo para reintentar."
)
DOC_NOT_TRAVEL_HINT = "_No parece un documento de viaje; fijate antes de guardar._"
DOC_PREVIEW_HINT = "_¿Algo mal? Corregime por texto: 'es en York' · 'fecha 15-ago' · 'es un voucher'._"
MEDIA_NOT_SUPPORTED = (
    f"{H_WARN} Audio, video o stickers no puedo procesar. "
    "Mandame texto, o un PDF/imagen si es un documento del viaje."
)
BATCH_CAT_HINT = '_Los ❓ son categorías dudosas: corregime como siempre ("el helado es Comida")._'


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


def link_budget() -> str | None:
    """Deep-link a /presupuesto. Es donde se cargan y editan los targets: el
    bot los lee pero no los escribe."""
    base = _base_url()
    return f"{base}/presupuesto" if base else None


def link_home() -> str | None:
    base = _base_url()
    return f"{base}/" if base else None


def link_andiamo_stop(slug: str | None) -> str | None:
    """Deep-link a los documentos del stop en Andiamo (o a los generales)."""
    base = (get_settings().andiamo_url or "").rstrip("/")
    if not base:
        return None
    return f"{base}/stops/{slug}" if slug else f"{base}/general"
