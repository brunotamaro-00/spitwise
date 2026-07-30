"""Traza opcional de un turno del bot (canal, intent, tools, outcome).

Existe para que los runners de escenarios puedan afirmar cosas deterministas
—"esta pregunta se ruteó a finanzas y llamó aggregate_expenses"— sin parsear
el texto de la respuesta. En producción nadie la enciende: los eventos se
loguean igual desde `llm/chat.py`, y el costo de tenerla apagada es un
`ContextVar.get()` por evento.

No guarda contenido: solo nombres de tools, intent, canal y contadores. Nunca
mensajes, argumentos ni wa_id.
"""
from contextvars import ContextVar

_current: ContextVar[dict | None] = ContextVar("bot_trace", default=None)


def start() -> dict:
    """Arranca (y devuelve) una traza para el turno en curso."""
    t: dict = {
        "intent": None,
        "parse_failure": None,
        "channel": None,
        "outcome": None,
        "tools": [],  # nombres en orden de llamada
        "tool_errors": [],  # nombres de las que fallaron
        "rounds": 0,
    }
    _current.set(t)
    return t


def clear() -> None:
    _current.set(None)


def current() -> dict | None:
    return _current.get()


def set_fields(**kw) -> None:
    t = _current.get()
    if t is not None:
        t.update(kw)


def add_tool(name: str, *, error: bool = False) -> None:
    t = _current.get()
    if t is None:
        return
    t["tools"].append(name)
    if error:
        t["tool_errors"].append(name)


def bump_round() -> None:
    t = _current.get()
    if t is not None:
        t["rounds"] += 1
