"""Presupuestos del loop de chat y síntesis final (app/llm/chat.py).

La evidencia que juntaron las tools no se tira: al agotarse rondas, tool calls
o tiempo, el modelo recibe una última vuelta SIN herramientas para responder con
lo que ya tiene. Antes ese caso devolvía "me enredé" aunque las tools hubieran
traído justo lo que se pedía.
"""
from types import SimpleNamespace

from app.llm.chat import (
    BUDGET_EXCEEDED, ITERATION_CAP, TOOL_ERROR, AnthropicChat, OpenAIChat, ToolSpec,
)


def _tool(handler, name="sumar"):
    return ToolSpec(name=name, description="suma",
                    input_schema={"type": "object", "properties": {}}, handler=handler)


async def _noop(**kw):
    return {"total": "90.00"}


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


def _tool_use(name="sumar", n=1):
    return SimpleNamespace(stop_reason="tool_use", content=[
        SimpleNamespace(type="tool_use", id=f"tu{i}", name=name, input={})
        for i in range(n)
    ])


def _text(t):
    return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=t)])


async def test_round_cap_synthesizes_with_the_evidence_gathered():
    captured = []

    async def create(**kwargs):
        captured.append(kwargs)
        # La última llamada (síntesis) va sin tools: ahí sí responde.
        if "tools" not in kwargs:
            return _text("Van *USD 90* con lo que alcancé a mirar.")
        return _tool_use()

    res = await _anthropic(create).run(system="s", history=[], user_text="x",
                                       tools=[_tool(_noop)], max_iterations=2)
    assert res.outcome == ITERATION_CAP and res.limit_hit == "rounds"
    assert res.synthesized and "USD 90" in res.text
    # La síntesis lleva el nudge y NO ofrece herramientas.
    assert "tools" not in captured[-1]
    assert "PRESUPUESTO" in captured[-1]["messages"][-1]["content"]


async def test_tool_call_budget_is_separate_from_rounds():
    """Una sola ronda puede pedir 6 tools: el cap de rondas no lo frena."""
    async def create(**kwargs):
        if "tools" not in kwargs:
            return _text("parcial")
        return _tool_use(n=6)

    chat = _anthropic(create)
    chat._max_tool_calls = 4
    res = await chat.run(system="s", history=[], user_text="x", tools=[_tool(_noop)],
                         max_iterations=8)
    assert res.outcome == BUDGET_EXCEEDED and res.limit_hit == "tool_calls"
    assert len(res.tool_calls) == 6 and res.text == "parcial"


async def test_no_synthesis_without_evidence():
    """Sin tools útiles no hay nada que sintetizar: no se gasta un request."""
    calls = []

    async def boom(**kw):
        raise ValueError("nope")

    async def create(**kwargs):
        calls.append(kwargs)
        return _tool_use()

    res = await _anthropic(create).run(system="s", history=[], user_text="x",
                                       tools=[_tool(boom)], max_iterations=2)
    assert res.outcome == TOOL_ERROR and res.text == ""
    assert all("tools" in c for c in calls)  # nunca se llamó a sintetizar


async def test_synthesis_failure_degrades_without_text():
    async def create(**kwargs):
        if "tools" not in kwargs:
            raise RuntimeError("cortó justo ahí")
        return _tool_use()

    res = await _anthropic(create).run(system="s", history=[], user_text="x",
                                       tools=[_tool(_noop)], max_iterations=2)
    assert res.outcome == ITERATION_CAP and res.text == "" and not res.synthesized


async def test_openai_synthesizes_too():
    tool_msg = SimpleNamespace(content=None, tool_calls=[
        SimpleNamespace(id="c1", function=SimpleNamespace(name="sumar", arguments="{}")),
    ])

    async def create(**kwargs):
        if "tools" not in kwargs:
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content="parcial pero real", tool_calls=None))])
        return SimpleNamespace(choices=[SimpleNamespace(message=tool_msg)])

    res = await _openai(create).run(system="s", history=[], user_text="x",
                                    tools=[_tool(_noop)], max_iterations=2)
    assert res.outcome == ITERATION_CAP and res.text == "parcial pero real"


# --- paridad entre providers --------------------------------------------------

async def test_openai_marks_tool_errors_in_the_content():
    """OpenAI no tiene `is_error`: sin marcador el modelo leía el error como dato."""
    captured = []

    async def boom(**kw):
        raise ValueError("persona desconocida: 'juan'")

    tool_msg = SimpleNamespace(content=None, tool_calls=[
        SimpleNamespace(id="c1", function=SimpleNamespace(name="sumar", arguments="{}")),
    ])
    final = SimpleNamespace(content="No encontré a esa persona.", tool_calls=None)
    responses = [
        SimpleNamespace(choices=[SimpleNamespace(message=tool_msg)]),
        SimpleNamespace(choices=[SimpleNamespace(message=final)]),
    ]

    async def create(**kwargs):
        captured.append(kwargs)
        return responses.pop(0)

    res = await _openai(create).run(system="s", history=[], user_text="x",
                                    tools=[_tool(boom)], max_iterations=3)
    tool_reply = captured[1]["messages"][-1]
    assert tool_reply["role"] == "tool" and tool_reply["content"].startswith("ERROR: ")
    assert "persona desconocida" in tool_reply["content"]
    assert res.tool_errors == ["sumar"]


async def test_openai_invalid_json_arguments_are_a_tool_error():
    """Antes se caía a `{}` y la tool devolvía datos de otra cosa, que el modelo citaba."""
    ran = []

    async def handler(**kw):
        ran.append(kw)
        return {"total": "1"}

    tool_msg = SimpleNamespace(content=None, tool_calls=[
        SimpleNamespace(id="c1", function=SimpleNamespace(name="sumar", arguments="{no json")),
    ])
    final = SimpleNamespace(content="listo", tool_calls=None)
    responses = [
        SimpleNamespace(choices=[SimpleNamespace(message=tool_msg)]),
        SimpleNamespace(choices=[SimpleNamespace(message=final)]),
    ]
    captured = []

    async def create(**kwargs):
        captured.append(kwargs)
        return responses.pop(0)

    res = await _openai(create).run(system="s", history=[], user_text="x",
                                    tools=[_tool(handler)], max_iterations=3)
    assert ran == []  # la tool nunca corrió con argumentos inventados
    assert res.tool_errors == ["sumar"]
    assert "argumentos inválidos" in captured[1]["messages"][-1]["content"]


async def test_generic_exception_stays_generic_for_the_model():
    """Solo los ValueError (escritos por las tools) vuelven con su mensaje."""
    captured = []

    async def boom(**kw):
        raise KeyError("columna_interna")

    async def create(**kwargs):
        captured.append(kwargs)
        return _tool_use() if len(captured) == 1 else _text("bueno")

    await _anthropic(create).run(system="s", history=[], user_text="x",
                                 tools=[_tool(boom)], max_iterations=3)
    content = captured[1]["messages"][-1]["content"][0]
    assert content["is_error"] is True
    assert content["content"] == "la herramienta falló con esos parámetros"
    assert "columna_interna" not in content["content"]
