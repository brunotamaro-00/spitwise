import json
from datetime import date
from types import SimpleNamespace

from sqlalchemy import select

from app.api.auth import hash_password
from app.bot.active_stop import get_state_payload, resolve_active_stop, set_active_stop_override
from app.bot.dispatcher import dispatch
from app.bot.qa import handle_question
from app.db.models import Movement, User
from app.llm.chat import AnthropicChat, OpenAIChat, ToolSpec

TODAY = date(2026, 8, 6)


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    async def parse(self, text, **kwargs):
        return self.payload


class FakeChat:
    def __init__(self, answer="respuesta"):
        self.answer = answer
        self.calls = []

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        return self.answer


def _question_payload():
    return {
        "intent": "question", "amount": None, "currency": None, "description": None,
        "category": None, "split": "shared", "paid_by": None, "date": None, "city": None,
        "confidence": 0.9, "candidates": [], "ref_last": False, "ref_text": None, "ref_date": None,
        "new_amount": None, "new_currency": None, "new_date": None, "new_city": None,
        "new_category": None, "new_description": None, "new_split": None, "new_paid_by": None,
    }


async def _setup(db_session):
    u1 = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    u2 = User(username="katia", password_hash=hash_password("pw"), whatsapp_wa_id="549222")
    db_session.add_all([u1, u2])
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    await db_session.commit()
    return u1, u2


async def test_dispatch_routes_question_to_chat(db_session):
    await _setup(db_session)
    chat = FakeChat("Van USD 90 en total 💸")
    reply = await dispatch(db_session, "549111", "text", "cuánto gastamos?", None, TODAY,
                           llm_client=FakeLLM(_question_payload()), chat_client=chat)
    assert reply.text == "Van USD 90 en total 💸"
    assert not reply.buttons
    assert (await db_session.execute(select(Movement))).scalars().all() == []
    # El agente recibe las 4 herramientas y el system con sender y semántica.
    call = chat.calls[0]
    assert {t.name for t in call["tools"]} == {
        "aggregate_expenses", "list_movements", "get_balance", "get_itinerary"}
    assert "bruno" in call["system"] and "share" in call["system"]


async def test_question_history_persists_and_feeds_followup(db_session):
    u1, _ = await _setup(db_session)
    chat = FakeChat()
    await handle_question(db_session, u1, "549111", "cuánto gastamos?", TODAY, chat_client=chat)
    await handle_question(db_session, u1, "549111", "y el detalle?", TODAY, chat_client=chat)
    # El segundo run recibe el turno anterior como historia.
    assert chat.calls[0]["history"] == []
    assert chat.calls[1]["history"] == [
        {"role": "user", "content": "cuánto gastamos?"},
        {"role": "assistant", "content": "respuesta"},
    ]
    payload = await get_state_payload(db_session, "549111")
    assert len(payload["qa_history"]) == 4


async def test_history_survives_active_stop_override_and_viceversa(db_session):
    u1, _ = await _setup(db_session)
    await handle_question(db_session, u1, "549111", "hola", TODAY, chat_client=FakeChat())
    await set_active_stop_override(db_session, "549111", "roma", "Roma", "EUR")
    payload = await get_state_payload(db_session, "549111")
    assert payload["qa_history"]  # no fue pisada
    assert payload["active_stop"]["stop_slug"] == "roma"
    assert (await resolve_active_stop(db_session, "549111", TODAY))[0] == "roma"
    # Y una nueva pregunta no pisa el override.
    await handle_question(db_session, u1, "549111", "otra", TODAY, chat_client=FakeChat())
    payload = await get_state_payload(db_session, "549111")
    assert payload["active_stop"]["stop_slug"] == "roma"


def _tool(handler):
    return ToolSpec(name="sumar", description="suma",
                    input_schema={"type": "object", "properties": {}}, handler=handler)


async def test_anthropic_loop_executes_tools():
    async def handler(**kw):
        return {"total": "90.00"}

    responses = [
        SimpleNamespace(stop_reason="tool_use", content=[
            SimpleNamespace(type="tool_use", id="tu1", name="sumar", input={}),
        ]),
        SimpleNamespace(stop_reason="end_turn", content=[
            SimpleNamespace(type="text", text="Son USD 90."),
        ]),
    ]
    captured = []

    async def create(**kwargs):
        captured.append(kwargs)
        return responses.pop(0)

    chat = AnthropicChat.__new__(AnthropicChat)
    chat._client = SimpleNamespace(messages=SimpleNamespace(create=create))
    chat._model = "claude-test"
    out = await chat.run(system="sys", history=[], user_text="cuánto?", tools=[_tool(handler)])
    assert out == "Son USD 90."
    # El segundo request lleva el tool_result con el JSON del handler.
    second = captured[1]["messages"]
    result_msg = second[-1]
    assert result_msg["role"] == "user"
    assert result_msg["content"][0]["tool_use_id"] == "tu1"
    assert json.loads(result_msg["content"][0]["content"]) == {"total": "90.00"}


async def test_openai_loop_executes_tools():
    async def handler(**kw):
        return {"total": "90.00"}

    msg_tool = SimpleNamespace(
        content=None,
        tool_calls=[SimpleNamespace(id="c1", function=SimpleNamespace(name="sumar", arguments="{}"))],
    )
    msg_final = SimpleNamespace(content="Son USD 90.", tool_calls=None)
    responses = [
        SimpleNamespace(choices=[SimpleNamespace(message=msg_tool)]),
        SimpleNamespace(choices=[SimpleNamespace(message=msg_final)]),
    ]
    captured = []

    async def create(**kwargs):
        captured.append(kwargs)
        return responses.pop(0)

    chat = OpenAIChat.__new__(OpenAIChat)
    chat._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    chat._model = "gpt-test"
    out = await chat.run(system="sys", history=[], user_text="cuánto?", tools=[_tool(handler)])
    assert out == "Son USD 90."
    second = captured[1]["messages"]
    assert second[-1]["role"] == "tool"
    assert json.loads(second[-1]["content"]) == {"total": "90.00"}


async def test_loop_tool_error_returns_is_error_to_model():
    async def handler(**kw):
        raise ValueError("persona desconocida")

    responses = [
        SimpleNamespace(stop_reason="tool_use", content=[
            SimpleNamespace(type="tool_use", id="tu1", name="sumar", input={}),
        ]),
        SimpleNamespace(stop_reason="end_turn", content=[
            SimpleNamespace(type="text", text="No encontré a esa persona."),
        ]),
    ]
    captured = []

    async def create(**kwargs):
        captured.append(kwargs)
        return responses.pop(0)

    chat = AnthropicChat.__new__(AnthropicChat)
    chat._client = SimpleNamespace(messages=SimpleNamespace(create=create))
    chat._model = "claude-test"
    out = await chat.run(system="sys", history=[], user_text="x", tools=[_tool(handler)])
    assert out == "No encontré a esa persona."
    assert captured[1]["messages"][-1]["content"][0]["is_error"] is True


async def test_loop_iteration_cap_falls_back():
    async def handler(**kw):
        return {}

    async def create(**kwargs):
        return SimpleNamespace(stop_reason="tool_use", content=[
            SimpleNamespace(type="tool_use", id="tu", name="sumar", input={}),
        ])

    chat = AnthropicChat.__new__(AnthropicChat)
    chat._client = SimpleNamespace(messages=SimpleNamespace(create=create))
    chat._model = "claude-test"
    out = await chat.run(system="s", history=[], user_text="x", tools=[_tool(handler)],
                         max_iterations=2)
    assert "enredé" in out
