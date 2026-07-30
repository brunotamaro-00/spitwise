"""Infraestructura común de los runners de escenarios (finanzas y viaje).

Los runners dejaron de ser solo transcripts: cada escenario declara CHECKS
deterministas —estado de la DB, a qué canal se ruteó, qué tools se llamaron—
que no dependen del wording del LLM. Un check que falla imprime el motivo y el
runner termina con **exit code 1**: eso es lo único que puede mirar CI. El
texto de las respuestas se sigue evaluando a ojo con el markdown.

La traza viene de `app.trace` (contextvar): el runner la enciende por turno y
la apaga después, así que en producción no cuesta nada.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable

from app import trace


@dataclass
class TurnTrace:
    """Foto de `app.trace` al terminar un turno (sin contenido del mensaje)."""

    intent: str | None = None
    parse_failure: str | None = None
    channel: str | None = None
    outcome: str | None = None
    tools: list[str] = field(default_factory=list)
    tool_errors: list[str] = field(default_factory=list)
    rounds: int = 0

    @classmethod
    def capture(cls) -> "TurnTrace":
        t = trace.current() or {}
        return cls(
            intent=t.get("intent"), parse_failure=t.get("parse_failure"),
            channel=t.get("channel"), outcome=t.get("outcome"),
            tools=list(t.get("tools") or []), tool_errors=list(t.get("tool_errors") or []),
            rounds=int(t.get("rounds") or 0),
        )

    def summary(self) -> str:
        parts = [f"intent={self.intent or '-'}"]
        if self.parse_failure:
            parts.append(f"parse_failure={self.parse_failure}")
        if self.channel:
            parts.append(f"canal={self.channel}")
        if self.outcome:
            parts.append(f"outcome={self.outcome}")
        parts.append(f"tools={','.join(self.tools) or '-'}")
        if self.tool_errors:
            parts.append(f"tool_errors={','.join(self.tool_errors)}")
        return " · ".join(parts)


@dataclass
class CheckCtx:
    """Lo que ve un check: la DB al final del escenario y la traza de cada turno."""

    session: object
    traces: list[TurnTrace]
    replies: list[str]

    def tools_used(self) -> set[str]:
        return {name for t in self.traces for name in t.tools}

    def intents(self) -> list[str | None]:
        return [t.intent for t in self.traces]

    def channels(self) -> list[str | None]:
        return [t.channel for t in self.traces]


# Un check devuelve la lista de errores (vacía = pasó).
Check = Callable[[CheckCtx], Awaitable[list[str]]]


class Errors(list):
    """Acumulador con la forma `errs.want(cond, "mensaje")`."""

    def want(self, cond: bool, msg: str) -> bool:
        if not cond:
            self.append(msg)
        return bool(cond)


async def load_movements(session):
    """Movimientos de la DB, más viejo primero."""
    from sqlalchemy import select

    from app.db.models import Movement

    return (await session.execute(select(Movement).order_by(Movement.id))).scalars().all()


def by_desc(movements, needle: str):
    """Movimientos cuya descripción contiene `needle` (case/acento-insensible)."""
    from app.textnorm import fold

    want = fold(needle)
    return [m for m in movements if want in fold(m.description or "")]


def one_by_desc(movements, needle: str):
    hits = by_desc(movements, needle)
    return hits[0] if len(hits) == 1 else None
