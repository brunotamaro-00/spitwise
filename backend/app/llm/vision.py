"""Lector de documentos de viaje (canal documentos, separado del parser financiero).

Recibe una imagen o PDF adjunto por WhatsApp y extrae los campos con los que se
archiva en Andiamo: kind, fecha en que se NECESITA el documento, parada del
itinerario, label y nota corta. Siempre por OpenAI (vision + PDF nativo);
ninguna regla es por-documento: el catálogo de paradas y de kinds llega por
contexto en cada llamada.
"""
import base64
from datetime import date

from pydantic import BaseModel

from app.config import get_settings

_SYSTEM = (
    "Sos el archivista de documentos de un viaje de una pareja. Te mandan por "
    "WhatsApp una imagen o PDF (reserva, entrada, ticket de tren/vuelo, auto de "
    "alquiler, seguro) y extraés los campos para archivarlo en la app del "
    "itinerario.\n\n"
    "Campos:\n"
    "- is_travel_doc: false solo si el archivo claramente NO es un documento de "
    "viaje archivable (una selfie, un meme, un recibo de supermercado).\n"
    "- kind: exactamente uno de la lista dada, por la FUNCIÓN del documento, no "
    "por cómo se llame a sí mismo: todo lo que da acceso a una actividad, museo, "
    "tour o atracción es 'ticket' (Entrada) aunque el documento diga 'voucher'; "
    "'voucher' queda para comprobantes canjeables que no son la entrada en sí. "
    "El alojamiento es 'checkin'; los traslados van por su medio (train/flight).\n"
    "- doc_date: ISO (YYYY-MM-DD). Es la fecha en que se NECESITA o USA el "
    "documento: el día de la entrada o visita, el check-in del alojamiento, el "
    "retiro del auto, la salida del tren o vuelo. NUNCA la fecha de compra, "
    "emisión o reserva (los documentos casi siempre se compran antes; esa fecha "
    "es una trampa). Si cubre un rango (auto del 18 al 25, estadía de 2 noches), "
    "SIEMPRE la primera fecha. Si no hay fecha de uso inferible, null.\n"
    "- stop_slug: el slug de la parada del itinerario a la que pertenece el "
    "documento, elegido de la lista dada. Para traslados (tren, vuelo, bus, "
    "ferry) la parada es SIEMPRE la de DESTINO, nunca la de origen. Para todo "
    "lo demás, la ciudad o zona donde se usa. Se elige por LUGAR: si el "
    "documento corresponde a la ciudad de una parada de la lista, devolvé esa "
    "parada AUNQUE las fechas del documento no caigan dentro de las fechas de "
    "la parada (el itinerario cambia; las fechas de la lista son orientativas, "
    "solo sirven para desambiguar entre paradas del mismo nombre o lugares "
    "repetidos). null SOLO si ningún lugar de la lista corresponde. NUNCA "
    "inventes un slug fuera de la lista.\n"
    "- label: título corto en español de qué es ('Tren York–Edimburgo', "
    "'Entrada Anne Frank House', 'Auto Hertz Edimburgo'); nombres propios "
    "capitalizados, sin punto final.\n"
    "- note: 1 o 2 frases cortas y accionables en español con lo práctico del "
    "documento: horario, asiento/coche, código o referencia de reserva, cantidad "
    "de personas, condiciones clave (a nombre de quién, hora límite). Sin "
    "markdown. Si el usuario mandó un comentario, integralo con lo que leíste "
    "del documento (redactá una nota nueva, nunca pegues su texto tal cual "
    "solo).\n"
    "- confidence: 0..1, qué tan seguro estás del conjunto fecha+parada+kind.\n\n"
    "Si el comentario del usuario trae ciudad o fecha, ESO manda por sobre lo "
    "que diga el documento. Hablan castellano rioplatense."
)

_CORRECTION_SYSTEM = (
    "El bot acaba de mostrar el preview de un documento de viaje por archivar y "
    "el usuario mandó un mensaje. Decidí si es una CORRECCIÓN de ese preview "
    "(cambia parada, fecha, tipo, título o nota: 'es en York', 'fecha 15-ago', "
    "'es un voucher', 'ponele que hay que llegar 30 min antes') o si es OTRA "
    "cosa (un gasto, una pregunta, charla) que no toca el documento.\n\n"
    "Si es corrección, devolvé SOLO los campos que cambian (el resto null):\n"
    "- stop_slug: de la lista de paradas dada, o null si no cambia. Si el "
    "usuario nombra un lugar que no matchea ninguna parada, no es corrección "
    "de parada válida: dejalo null.\n"
    "- doc_date: ISO, resolviendo fechas relativas con la fecha de hoy dada.\n"
    "- kind: de la lista dada.\n"
    "- label / note: solo si pide cambiarlos o agrega información para la nota.\n"
    "Si NO es corrección, is_correction=false y todo null. "
    "Hablan castellano rioplatense."
)


class DocExtraction(BaseModel):
    is_travel_doc: bool
    kind: str
    doc_date: str | None
    stop_slug: str | None
    label: str
    note: str | None
    confidence: float


class DocCorrection(BaseModel):
    is_correction: bool
    stop_slug: str | None
    doc_date: str | None
    kind: str | None
    label: str | None
    note: str | None


def _render_stops(stops: list[dict]) -> str:
    """Catálogo dinámico de paradas (slug, nombre, país, fechas). Sin esto el
    modelo solo conoce ciudades por cultura general y no puede devolver slugs."""
    lines = []
    for s in stops:
        rng = ""
        if s.get("arrival_date") or s.get("departure_date"):
            rng = f" ({s.get('arrival_date') or '?'} → {s.get('departure_date') or '?'})"
        country = f", {s['country']}" if s.get("country") else ""
        lines.append(f"- {s['slug']}: {s['name']}{country}{rng}")
    return "Paradas del itinerario (slug: nombre, país, llegada → salida):\n" + "\n".join(lines)


def _render_kinds(kinds: dict[str, str]) -> str:
    return "Kinds válidos: " + " · ".join(f"{k} ({v})" for k, v in kinds.items())


def _user_context(today: date, stops: list[dict], kinds: dict[str, str], caption: str | None,
                  filename: str | None) -> str:
    parts = [f"Hoy es {today.isoformat()}.", _render_kinds(kinds), _render_stops(stops)]
    if filename:
        parts.append(f"Nombre del archivo: {filename}")
    if caption:
        parts.append(f"Comentario del usuario junto al archivo: {caption}")
    else:
        parts.append("El usuario no mandó comentario.")
    return "\n".join(parts)


def _file_content_part(file_bytes: bytes, mime_type: str, filename: str | None) -> dict:
    b64 = base64.b64encode(file_bytes).decode()
    if mime_type == "application/pdf":
        return {"type": "file", "file": {
            "filename": filename or "documento.pdf",
            "file_data": f"data:application/pdf;base64,{b64}",
        }}
    return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}


def make_vision_llm():
    return OpenAIVision()


class OpenAIVision:
    def __init__(self) -> None:
        from openai import AsyncOpenAI

        s = get_settings()
        self._client = AsyncOpenAI(api_key=s.openai_api_key, timeout=s.vision_timeout_seconds)
        self._model = s.openai_vision_model

    async def extract(self, file_bytes: bytes, mime_type: str, *, today: date,
                      stops: list[dict], kinds: dict[str, str], caption: str | None = None,
                      filename: str | None = None) -> dict:
        resp = await self._client.chat.completions.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": [
                    {"type": "text", "text": _user_context(today, stops, kinds, caption, filename)},
                    _file_content_part(file_bytes, mime_type, filename),
                ]},
            ],
            response_format=DocExtraction,
        )
        parsed = resp.choices[0].message.parsed
        return parsed.model_dump() if parsed is not None else {}

    async def classify_correction(self, text: str, extraction_summary: str, *, today: date,
                                  stops: list[dict], kinds: dict[str, str]) -> dict:
        # Clasificación liviana sin el archivo: alcanza con el resumen del
        # preview. Timeout propio y corto — el de `extract` (90s) es para subir
        # un PDF, y acá está atravesado el camino financiero de cualquier texto
        # con un preview fresco a la vista.
        extra: dict = {}
        if self._model.startswith(("gpt-5", "o1", "o3", "o4")):
            extra["reasoning_effort"] = "minimal"
        resp = await self._client.with_options(timeout=15.0).chat.completions.parse(
            model=self._model,
            **extra,
            messages=[
                {"role": "system", "content": _CORRECTION_SYSTEM},
                {"role": "user", "content": (
                    f"Hoy es {today.isoformat()}.\n{_render_kinds(kinds)}\n{_render_stops(stops)}\n"
                    f"Preview actual del documento: {extraction_summary}\n"
                    f"Mensaje del usuario: {text}"
                )},
            ],
            response_format=DocCorrection,
        )
        parsed = resp.choices[0].message.parsed
        return parsed.model_dump() if parsed is not None else {"is_correction": False}
