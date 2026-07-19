"""Clientes de chat con tool-use para el agente Q&A, provider-agnostic.

Las herramientas se definen una sola vez como ToolSpec (schema JSON neutral +
handler async) y cada cliente las traduce a su wire format. Misma firma
duck-typed `run()` en ambos, espejando el `.parse()` de client.py.
"""
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.config import get_settings

logger = logging.getLogger(__name__)

_FALLBACK = "😵 Me enredé buscando eso. Probá preguntarlo un poco más simple."

# Presupuesto TOTAL del loop de tool-use, como múltiplo del timeout por request:
# acota el peor caso (antes: max_iterations × timeout ≈ 150s de silencio).
_LOOP_BUDGET_FACTOR = 2.0


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict  # JSON schema neutral
    handler: Callable[..., Awaitable[Any]]


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


async def _run_tool(tools_by_name: dict[str, ToolSpec], name: str, args: dict) -> tuple[str, bool]:
    """(resultado serializado, is_error). Nunca levanta: el error vuelve al modelo."""
    tool = tools_by_name.get(name)
    if tool is None:
        return f"herramienta desconocida: {name}", True
    try:
        return _dumps(await tool.handler(**(args or {}))), False
    except Exception:
        logger.exception("qa_tool_error tool=%s args=%s", name, args)
        return "la herramienta falló con esos parámetros", True


def make_chat_llm():
    """Mismo criterio de proveedor que make_llm() (parser)."""
    s = get_settings()
    provider = s.llm_provider.lower() or (
        "openai" if (s.openai_api_key and not s.anthropic_api_key) else "anthropic"
    )
    if provider == "openai":
        return OpenAIChat()
    return AnthropicChat()


class AnthropicChat:
    _budget_s = 60.0  # default para instancias armadas a mano (tests)

    def __init__(self) -> None:
        from anthropic import AsyncAnthropic

        s = get_settings()
        self._client = AsyncAnthropic(api_key=s.anthropic_api_key, timeout=s.chat_timeout_seconds)
        self._model = s.anthropic_chat_model
        self._budget_s = s.chat_timeout_seconds * _LOOP_BUDGET_FACTOR

    async def run(self, *, system: str, history: list[dict], user_text: str,
                  tools: list[ToolSpec], max_iterations: int = 8) -> str:
        by_name = {t.name: t for t in tools}
        api_tools = [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in tools
        ]
        messages = [*history, {"role": "user", "content": user_text}]
        # Bot de charla corta: effort bajo + thinking adaptivo para minimizar latencia.
        # El system se cachea (estable dentro del día por remitente).
        system_blocks = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        deadline = time.monotonic() + self._budget_s
        for i in range(max_iterations):
            if i and time.monotonic() > deadline:
                return _FALLBACK
            resp = await self._client.messages.create(
                model=self._model, max_tokens=2048, system=system_blocks,
                messages=messages, tools=api_tools,
                thinking={"type": "adaptive"},
                output_config={"effort": "low"},
            )
            if resp.stop_reason != "tool_use":
                text = "".join(b.text for b in resp.content if b.type == "text").strip()
                return text or _FALLBACK
            messages.append({"role": "assistant", "content": resp.content})
            # Todos los tool_result del turno van en UN solo mensaje user.
            results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                out, is_err = await _run_tool(by_name, block.name, dict(block.input or {}))
                result: dict = {"type": "tool_result", "tool_use_id": block.id, "content": out}
                if is_err:
                    result["is_error"] = True
                results.append(result)
            messages.append({"role": "user", "content": results})
        return _FALLBACK


class OpenAIChat:
    _budget_s = 60.0  # default para instancias armadas a mano (tests)

    def __init__(self) -> None:
        from openai import AsyncOpenAI

        s = get_settings()
        self._client = AsyncOpenAI(api_key=s.openai_api_key, timeout=s.chat_timeout_seconds)
        self._model = s.openai_chat_model
        self._budget_s = s.chat_timeout_seconds * _LOOP_BUDGET_FACTOR

    async def run(self, *, system: str, history: list[dict], user_text: str,
                  tools: list[ToolSpec], max_iterations: int = 8) -> str:
        by_name = {t.name: t for t in tools}
        api_tools = [
            {"type": "function",
             "function": {"name": t.name, "description": t.description, "parameters": t.input_schema}}
            for t in tools
        ]
        messages = [{"role": "system", "content": system}, *history,
                    {"role": "user", "content": user_text}]
        # Bot de charla corta: razonamiento al mínimo en los modelos que lo
        # traen (gpt-5*) — es el driver principal de latencia del agente.
        extra: dict = {}
        if self._model.startswith(("gpt-5", "o1", "o3", "o4")):
            extra["reasoning_effort"] = "low"
        deadline = time.monotonic() + self._budget_s
        for i in range(max_iterations):
            if i and time.monotonic() > deadline:
                return _FALLBACK
            resp = await self._client.chat.completions.create(
                model=self._model, messages=messages, tools=api_tools, **extra,
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                return (msg.content or "").strip() or _FALLBACK
            messages.append(msg)
            for call in msg.tool_calls:
                try:
                    args = json.loads(call.function.arguments or "{}")
                except ValueError:
                    args = {}
                out, _is_err = await _run_tool(by_name, call.function.name, args)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": out})
        return _FALLBACK
