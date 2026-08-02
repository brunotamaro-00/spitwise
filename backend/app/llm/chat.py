"""Clientes de chat con tool-use para el agente Q&A, provider-agnostic.

Las herramientas se definen una sola vez como ToolSpec (schema JSON neutral +
handler async) y cada cliente las traduce a su wire format. Misma firma
duck-typed `run()` en ambos, espejando el `.parse()` de client.py.

`run()` devuelve un ChatResult: además del texto, el OUTCOME del loop
(`ok`, `iteration_cap`, `budget_exceeded`, `empty_completion`, `provider_error`,
`tool_error`) y una traza segura (provider, canal, rondas, nombres de tools,
errores, latencia). Sin eso, una degradación —cap de rondas, timeout, refusal—
llegaba al usuario como el mismo texto genérico y era invisible en los logs.

Presupuestos SEPARADOS (rondas, tool calls, tiempo) con una **llamada final de
síntesis** reservada: al agotarse cualquiera de los tres, el modelo recibe una
última vuelta SIN herramientas para responder con la evidencia que ya juntó.
Antes esa evidencia se tiraba y el usuario recibía "me enredé" aunque las tools
hubieran devuelto exactamente lo que pedía.
"""
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from app import trace
from app.config import get_settings

logger = logging.getLogger(__name__)

FALLBACK = "😵 Me enredé buscando eso. Probá preguntarlo un poco más simple."

# Presupuesto TOTAL del loop de tool-use, como múltiplo del timeout por request:
# acota el peor caso (antes: max_iterations × timeout ≈ 150s de silencio). La
# síntesis final sale de ese mismo total (se le reserva un request), así que el
# peor caso NO empeoró al sumarla.
_LOOP_BUDGET_FACTOR = 2.0

# --- outcomes del loop (el que termina la corrida) ---
OK = "ok"
ITERATION_CAP = "iteration_cap"  # se agotaron las rondas de tool-use
BUDGET_EXCEEDED = "budget_exceeded"  # se agotó el presupuesto de tiempo o de tool calls
EMPTY_COMPLETION = "empty_completion"  # el modelo cerró sin texto
PROVIDER_ERROR = "provider_error"  # la API del proveedor falló
TOOL_ERROR = "tool_error"  # todas las tools del turno fallaron

_SYNTHESIS_NUDGE = (
    "SE ACABÓ EL PRESUPUESTO DE BÚSQUEDA de este turno. Respondé AHORA con lo que "
    "YA devolvieron las herramientas más arriba. No pidas más herramientas. Si lo "
    "que hay no alcanza para responder del todo, decí en una línea qué pudiste ver "
    "y qué te falta. Nunca inventes datos que no estén arriba."
)


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict  # JSON schema neutral
    handler: Callable[..., Awaitable[Any]]


@dataclass
class ChatResult:
    """Texto + qué pasó en el loop. `text` vacío = no hay respuesta usable y el
    canal tiene que degradar con su propia copy (nunca un genérico persistido)."""

    text: str = ""
    outcome: str = OK
    provider: str = ""
    channel: str = ""
    rounds: int = 0
    tool_calls: list[str] = field(default_factory=list)
    tool_errors: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    # Cuál de los tres presupuestos cortó el loop ('rounds' | 'time' | 'tool_calls').
    limit_hit: str = ""
    # El texto salió de la llamada final de síntesis (respuesta parcial grounded).
    synthesized: bool = False

    @property
    def ok(self) -> bool:
        return self.outcome == OK

    @property
    def has_evidence(self) -> bool:
        """¿Alguna tool devolvió datos en este turno? (grounding)"""
        return len(self.tool_calls) > len(self.tool_errors)

    @property
    def successful_tools(self) -> list[str]:
        """Las tools que DEVOLVIERON datos. `tool_calls` incluye las que
        explotaron, y una tool fallida no es evidencia de nada: sin esto, un
        `aggregate_expenses` con error habilitaba un "no hay gastos" falso.
        Resta de multiset — la misma tool puede llamarse varias veces y fallar
        solo en algunas."""
        from collections import Counter

        left = Counter(self.tool_errors)
        out = []
        for name in self.tool_calls:
            if left.get(name):
                left[name] -= 1
                continue
            out.append(name)
        return out


def as_result(value) -> ChatResult:
    """Normaliza lo que devuelve un cliente de chat. Los dobles de test
    devuelven `str` pelado: se toma como respuesta ok (o empty si viene vacía)."""
    if isinstance(value, ChatResult):
        return value
    text = (value or "").strip()
    return ChatResult(text=text, outcome=OK if text else EMPTY_COMPLETION)


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


async def _run_tool(tools_by_name: dict[str, ToolSpec], name: str, args: dict) -> tuple[str, bool]:
    """(resultado serializado, is_error). Nunca levanta: el error vuelve al modelo.

    Solo los ValueError vuelven con su mensaje: son los que las tools escriben a
    propósito para que el modelo se corrija ('guide_slug desconocido; válidas:
    [...]'). Cualquier otra excepción es un bug o una falla de infra y se
    devuelve genérica — filtrar internals al prompt no ayuda a nadie.

    El log NO lleva los argumentos: son texto libre derivado del mensaje del
    usuario (ciudades, descripciones) y no tienen por qué quedar en disco."""
    tool = tools_by_name.get(name)
    if tool is None:
        trace.add_tool(name, error=True)
        return f"herramienta desconocida: {name}", True
    try:
        out = _dumps(await tool.handler(**(args or {})))
    except ValueError as exc:
        trace.add_tool(name, error=True)
        return f"parámetros inválidos: {exc}", True
    except Exception as exc:
        logger.warning("qa_tool_error tool=%s err=%s", name, type(exc).__name__)
        trace.add_tool(name, error=True)
        return "la herramienta falló con esos parámetros", True
    trace.add_tool(name)
    return out, False


def _degrade(res: ChatResult, outcome: str) -> str:
    """Un cap/budget donde TODAS las tools fallaron se reporta como `tool_error`:
    el problema no fue el presupuesto sino que no hubo evidencia con qué responder."""
    if outcome in (ITERATION_CAP, BUDGET_EXCEEDED) and res.tool_calls and not res.has_evidence:
        return TOOL_ERROR
    return outcome


def _log(res: ChatResult) -> ChatResult:
    """Traza segura y única del turno: sin mensajes, snippets ni identificadores."""
    logger.info(
        "chat_done provider=%s channel=%s outcome=%s limit=%s synthesized=%s rounds=%d "
        "tools=%d tool_names=%s tool_errors=%d elapsed=%.2f",
        res.provider, res.channel or "-", res.outcome, res.limit_hit or "-",
        res.synthesized, res.rounds, len(res.tool_calls),
        ",".join(res.tool_calls) or "-", len(res.tool_errors), res.elapsed_s,
    )
    trace.set_fields(outcome=res.outcome, rounds=res.rounds)
    return res


def make_chat_llm():
    """Mismo criterio de proveedor que make_llm() (parser)."""
    s = get_settings()
    provider = s.llm_provider.lower() or (
        "openai" if (s.openai_api_key and not s.anthropic_api_key) else "anthropic"
    )
    if provider == "openai":
        return OpenAIChat()
    return AnthropicChat()


class _BaseChat:
    """Presupuestos y bookkeeping compartidos por los dos providers."""

    provider = ""
    _budget_s = 60.0  # default para instancias armadas a mano (tests)
    _synthesis_reserve_s = 30.0  # se descuenta del total: la síntesis no lo estira
    _max_tool_calls = 10

    def _budgets(self, s) -> None:
        self._budget_s = s.chat_timeout_seconds * _LOOP_BUDGET_FACTOR
        self._synthesis_reserve_s = s.chat_timeout_seconds
        self._max_tool_calls = s.qa_max_tool_calls

    def _new_run(self, channel: str) -> tuple[ChatResult, float, float]:
        res = ChatResult(provider=self.provider, channel=channel)
        started = time.monotonic()
        # El loop corta antes del total para dejar lugar a la síntesis final.
        loop_deadline = started + max(0.0, self._budget_s - self._synthesis_reserve_s)
        return res, started, loop_deadline


class AnthropicChat(_BaseChat):
    provider = "anthropic"

    def __init__(self) -> None:
        from anthropic import AsyncAnthropic

        s = get_settings()
        self._client = AsyncAnthropic(api_key=s.anthropic_api_key, timeout=s.chat_timeout_seconds)
        self._model = s.anthropic_chat_model
        self._budgets(s)

    async def _create(self, system_blocks, messages, api_tools):
        kw: dict = {}
        if api_tools:
            kw["tools"] = api_tools
        return await self._client.messages.create(
            model=self._model, max_tokens=2048, system=system_blocks,
            messages=messages, thinking={"type": "adaptive"},
            output_config={"effort": "low"}, **kw,
        )

    @staticmethod
    def _text_of(resp) -> str:
        return "".join(b.text for b in resp.content if b.type == "text").strip()

    async def run(self, *, system: str, history: list[dict], user_text: str,
                  tools: list[ToolSpec], max_iterations: int = 8,
                  channel: str = "") -> ChatResult:
        by_name = {t.name: t for t in tools}
        api_tools = [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in tools
        ]
        messages = [*history, {"role": "user", "content": user_text}]
        # Bot de charla corta: effort bajo + thinking adaptivo para minimizar latencia.
        # El system se cachea (estable dentro del día por remitente).
        system_blocks = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        res, started, loop_deadline = self._new_run(channel)

        def finish(outcome: str, text: str = "") -> ChatResult:
            res.outcome, res.text = _degrade(res, outcome), text
            res.elapsed_s = time.monotonic() - started
            return _log(res)

        async def synthesize(outcome: str) -> ChatResult:
            """Última vuelta SIN tools con la evidencia ya juntada."""
            if not res.has_evidence:
                return finish(outcome)
            try:
                resp = await self._create(
                    system_blocks,
                    [*messages, {"role": "user", "content": _SYNTHESIS_NUDGE}],
                    None,
                )
            except Exception as exc:
                logger.warning("chat_synthesis_failed provider=%s err=%s",
                               self.provider, type(exc).__name__)
                return finish(outcome)
            res.rounds += 1
            text = self._text_of(resp)
            res.synthesized = bool(text)
            return finish(outcome, text)

        for i in range(max_iterations):
            if i and time.monotonic() > loop_deadline:
                res.limit_hit = "time"
                return await synthesize(BUDGET_EXCEEDED)
            if len(res.tool_calls) >= self._max_tool_calls:
                res.limit_hit = "tool_calls"
                return await synthesize(BUDGET_EXCEEDED)
            try:
                resp = await self._create(system_blocks, messages, api_tools)
            except Exception as exc:
                logger.warning("chat_provider_error provider=%s err=%s",
                               self.provider, type(exc).__name__)
                return finish(PROVIDER_ERROR)
            res.rounds = i + 1
            if resp.stop_reason != "tool_use":
                text = self._text_of(resp)
                return finish(OK, text) if text else finish(EMPTY_COMPLETION)
            messages.append({"role": "assistant", "content": resp.content})
            # Todos los tool_result del turno van en UN solo mensaje user.
            results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                out, is_err = await _run_tool(by_name, block.name, dict(block.input or {}))
                res.tool_calls.append(block.name)
                if is_err:
                    res.tool_errors.append(block.name)
                result: dict = {"type": "tool_result", "tool_use_id": block.id, "content": out}
                if is_err:
                    result["is_error"] = True
                results.append(result)
            messages.append({"role": "user", "content": results})
        res.limit_hit = "rounds"
        return await synthesize(ITERATION_CAP)


class OpenAIChat(_BaseChat):
    provider = "openai"

    def __init__(self) -> None:
        from openai import AsyncOpenAI

        s = get_settings()
        self._client = AsyncOpenAI(api_key=s.openai_api_key, timeout=s.chat_timeout_seconds)
        self._model = s.openai_chat_model
        self._budgets(s)
        # Bot de charla corta: razonamiento al mínimo en los modelos que lo
        # traen (gpt-5*) — es el driver principal de latencia del agente.
        self._extra: dict = {}
        if self._model.startswith(("gpt-5", "o1", "o3", "o4")):
            self._extra["reasoning_effort"] = "low"

    async def _create(self, messages, api_tools):
        kw: dict = {}
        if api_tools:
            kw["tools"] = api_tools
        return await self._client.chat.completions.create(
            model=self._model, messages=messages, **kw, **getattr(self, "_extra", {}),
        )

    async def run(self, *, system: str, history: list[dict], user_text: str,
                  tools: list[ToolSpec], max_iterations: int = 8,
                  channel: str = "") -> ChatResult:
        by_name = {t.name: t for t in tools}
        api_tools = [
            {"type": "function",
             "function": {"name": t.name, "description": t.description, "parameters": t.input_schema}}
            for t in tools
        ]
        messages = [{"role": "system", "content": system}, *history,
                    {"role": "user", "content": user_text}]
        res, started, loop_deadline = self._new_run(channel)

        def finish(outcome: str, text: str = "") -> ChatResult:
            res.outcome, res.text = _degrade(res, outcome), text
            res.elapsed_s = time.monotonic() - started
            return _log(res)

        async def synthesize(outcome: str) -> ChatResult:
            if not res.has_evidence:
                return finish(outcome)
            try:
                resp = await self._create(
                    [*messages, {"role": "user", "content": _SYNTHESIS_NUDGE}], None,
                )
            except Exception as exc:
                logger.warning("chat_synthesis_failed provider=%s err=%s",
                               self.provider, type(exc).__name__)
                return finish(outcome)
            res.rounds += 1
            text = (resp.choices[0].message.content or "").strip()
            res.synthesized = bool(text)
            return finish(outcome, text)

        for i in range(max_iterations):
            if i and time.monotonic() > loop_deadline:
                res.limit_hit = "time"
                return await synthesize(BUDGET_EXCEEDED)
            if len(res.tool_calls) >= self._max_tool_calls:
                res.limit_hit = "tool_calls"
                return await synthesize(BUDGET_EXCEEDED)
            try:
                resp = await self._create(messages, api_tools)
            except Exception as exc:
                logger.warning("chat_provider_error provider=%s err=%s",
                               self.provider, type(exc).__name__)
                return finish(PROVIDER_ERROR)
            res.rounds = i + 1
            msg = resp.choices[0].message
            if not msg.tool_calls:
                text = (msg.content or "").strip()
                return finish(OK, text) if text else finish(EMPTY_COMPLETION)
            messages.append(msg)
            for call in msg.tool_calls:
                name = call.function.name
                try:
                    args = json.loads(call.function.arguments or "{}")
                except ValueError:
                    # Paridad con Anthropic: argumentos corruptos son un ERROR de
                    # tool que vuelve al modelo, no una llamada con args vacíos
                    # (que devolvía datos de otra cosa y el modelo los citaba).
                    out, is_err = ("argumentos inválidos: no son JSON; "
                                   "reintentá con JSON bien formado"), True
                    trace.add_tool(name, error=True)
                else:
                    out, is_err = await _run_tool(by_name, name, args)
                res.tool_calls.append(name)
                if is_err:
                    res.tool_errors.append(name)
                # OpenAI no tiene `is_error`: el marcador va en el contenido, si
                # no el modelo lee el texto del error como si fuera un resultado.
                content = f"ERROR: {out}" if is_err else out
                messages.append({"role": "tool", "tool_call_id": call.id, "content": content})
        res.limit_hit = "rounds"
        return await synthesize(ITERATION_CAP)
