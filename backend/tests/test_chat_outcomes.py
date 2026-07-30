"""Cobertura de los outcomes del loop de chat (app/llm/chat.py).

Un outcome mal clasificado es una degradación invisible: el usuario recibía el
mismo texto genérico ante un cap de rondas, un timeout, un refusal y una caída
del proveedor. Cada uno tiene que ser distinguible desde el resultado.
"""
from types import SimpleNamespace

import pytest

from app import trace
from app.llm import chat as chatmod
from app.llm.chat import (
    BUDGET_EXCEEDED, EMPTY_COMPLETION, ITERATION_CAP, OK, PROVIDER_ERROR, TOOL_ERROR,
    AnthropicChat, ChatResult, OpenAIChat, ToolSpec, as_result,
)


def _tool(handler, name="sumar"):
    return ToolSpec(name=name, description="suma",
                    input_schema={"type": "object", "properties": {}}, handler=handler)


def _anthropic(create):
    chat = AnthropicChat.__new__(AnthropicChat)
    chat._client = SimpleNamespace(messages=SimpleNamespace(create=create))
    chat._model = "claude-test"
    return chat


def _openai(create):
    chat = OpenAIChat.__new__(OpenAIChat)
    chat._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    chat._model = "gpt-test"
    return chat


def _tool_use_resp(name="sumar"):
    return SimpleNamespace(stop_reason="tool_use", content=[
        SimpleNamespace(type="tool_use", id="tu", name=name, input={}),
    ])


async def _noop(**kw):
    return {}


async def test_ok_outcome_carries_trace():
    async def create(**kwargs):
        return SimpleNamespace(stop_reason="end_turn",
                               content=[SimpleNamespace(type="text", text="listo")])

    res = await _anthropic(create).run(system="s", history=[], user_text="x", tools=[],
                                       channel="qa")
    assert (res.outcome, res.text, res.channel, res.rounds) == (OK, "listo", "qa", 1)
    assert res.ok and not res.tool_calls


async def test_empty_completion_is_not_ok():
    async def create(**kwargs):
        return SimpleNamespace(stop_reason="end_turn",
                               content=[SimpleNamespace(type="text", text="   ")])

    res = await _anthropic(create).run(system="s", history=[], user_text="x", tools=[])
    assert res.outcome == EMPTY_COMPLETION and res.text == ""


async def test_provider_error_does_not_raise():
    async def create(**kwargs):
        raise RuntimeError("503 upstream")

    res = await _anthropic(create).run(system="s", history=[], user_text="x", tools=[])
    assert res.outcome == PROVIDER_ERROR and res.text == ""


async def test_openai_provider_error_does_not_raise():
    async def create(**kwargs):
        raise RuntimeError("timeout")

    res = await _openai(create).run(system="s", history=[], user_text="x", tools=[])
    assert res.outcome == PROVIDER_ERROR and res.text == ""


async def test_iteration_cap_keeps_evidence_in_trace():
    async def create(**kwargs):
        return _tool_use_resp()

    res = await _anthropic(create).run(system="s", history=[], user_text="x",
                                       tools=[_tool(_noop)], max_iterations=2)
    assert res.outcome == ITERATION_CAP
    assert res.tool_calls == ["sumar", "sumar"] and res.has_evidence


async def test_all_tools_failing_reports_tool_error():
    async def boom(**kw):
        raise ValueError("nope")

    async def create(**kwargs):
        return _tool_use_resp()

    res = await _anthropic(create).run(system="s", history=[], user_text="x",
                                       tools=[_tool(boom)], max_iterations=2)
    # Sin evidencia útil: el cap no es el problema real, las tools lo son.
    assert res.outcome == TOOL_ERROR and not res.has_evidence


async def test_unknown_tool_is_an_error_not_a_crash():
    async def create(**kwargs):
        return _tool_use_resp(name="inexistente")

    res = await _anthropic(create).run(system="s", history=[], user_text="x",
                                       tools=[_tool(_noop)], max_iterations=2)
    assert res.tool_errors == ["inexistente", "inexistente"]


async def test_budget_exceeded_when_deadline_passes(monkeypatch):
    async def create(**kwargs):
        return _tool_use_resp()

    chat = _anthropic(create)
    chat._budget_s = -1.0  # ya vencido: la 2ª vuelta corta por presupuesto
    res = await chat.run(system="s", history=[], user_text="x", tools=[_tool(_noop)],
                         max_iterations=5)
    assert (res.outcome, res.limit_hit) == (BUDGET_EXCEEDED, "time")


async def test_openai_budget_exceeded():
    msg = SimpleNamespace(content=None, tool_calls=[
        SimpleNamespace(id="c1", function=SimpleNamespace(name="sumar", arguments="{}")),
    ])

    async def create(**kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    chat = _openai(create)
    chat._budget_s = -1.0
    res = await chat.run(system="s", history=[], user_text="x", tools=[_tool(_noop)],
                         max_iterations=5)
    assert res.outcome == BUDGET_EXCEEDED


def test_as_result_normalizes_plain_strings():
    assert as_result("hola") == ChatResult(text="hola", outcome=OK)
    assert as_result("").outcome == EMPTY_COMPLETION
    assert as_result(None).outcome == EMPTY_COMPLETION
    r = ChatResult(text="x", outcome=OK)
    assert as_result(r) is r


async def test_tool_log_never_carries_arguments(caplog):
    """Los args son texto libre del usuario: no van al log."""
    async def boom(**kw):
        raise RuntimeError("detalle interno")

    with caplog.at_level("WARNING"):
        out, is_err = await chatmod._run_tool(
            {"sumar": _tool(boom)}, "sumar", {"city": "Lisboa secreta"},
        )
    assert is_err and out == "la herramienta falló con esos parámetros"
    assert "Lisboa secreta" not in caplog.text and "detalle interno" not in caplog.text
    assert "tool=sumar" in caplog.text and "RuntimeError" in caplog.text


async def test_value_error_message_goes_back_to_the_model(caplog):
    """Los ValueError los escriben las tools para que el modelo se corrija."""
    async def bad_arg(**kw):
        raise ValueError("guide_slug desconocido: 'lisbon'; válidas: ['lisboa']")

    with caplog.at_level("WARNING"):
        out, is_err = await chatmod._run_tool({"sumar": _tool(bad_arg)}, "sumar", {})
    assert is_err and "válidas: ['lisboa']" in out
    assert caplog.text == ""  # un parámetro mal puesto no es un incidente


@pytest.fixture(autouse=True)
def _trace_ctx():
    trace.start()
    yield
    trace.clear()


async def test_trace_records_tools_and_outcome():
    async def create(**kwargs):
        return _tool_use_resp()

    await _anthropic(create).run(system="s", history=[], user_text="x",
                                 tools=[_tool(_noop)], max_iterations=2, channel="trip")
    t = trace.current()
    assert t["tools"] == ["sumar", "sumar"] and t["outcome"] == ITERATION_CAP
