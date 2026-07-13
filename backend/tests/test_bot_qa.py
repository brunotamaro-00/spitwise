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
    # El agente recibe las herramientas y el system con sender y semántica.
    call = chat.calls[0]
    assert {t.name for t in call["tools"]} == {
        "aggregate_expenses", "list_movements", "get_balance", "get_itinerary",
        "edit_movement", "delete_movements"}
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


class ToolCallingFakeChat:
    """Simula un agente que llama una herramienta y devuelve un texto final."""

    def __init__(self, tool_name, args, answer="hecho"):
        self.tool_name, self.args, self.answer = tool_name, args, answer
        self.tool_result = None

    async def run(self, *, tools, **kwargs):
        tool = next(t for t in tools if t.name == self.tool_name)
        self.tool_result = await tool.handler(**self.args)
        return self.answer


async def _seed_movements(db_session, u1):
    from decimal import Decimal
    from app.db.models import Movement
    m1 = Movement(type="expense", amount=Decimal("100"), currency="CHF", amount_usd=Decimal("112"),
                  fx_rate=Decimal("1.12"), fx_source="fallback", paid_by=u1.id, split="payer_only",
                  description="teleferico", movement_date=date(2026, 9, 22), created_by=u1.id)
    m2 = Movement(type="expense", amount=Decimal("100"), currency="CHF", amount_usd=Decimal("112"),
                  fx_rate=Decimal("1.12"), fx_source="fallback", paid_by=u1.id, split="shared",
                  description="teleferico", movement_date=date(2026, 9, 22), created_by=u1.id)
    db_session.add_all([m1, m2])
    await db_session.commit()
    return m1, m2


async def test_agent_delete_prepares_buttons_then_button_deletes(db_session):
    u1, _ = await _setup(db_session)
    m1, m2 = await _seed_movements(db_session, u1)
    chat = ToolCallingFakeChat("delete_movements", {"movement_ids": [m1.id, m2.id]})
    reply = await handle_question(db_session, u1, "549111", "sí, borralos", TODAY, chat_client=chat)
    # La respuesta es la tarjeta con botones (no el texto del modelo) y nada se borró aún.
    assert reply.buttons and reply.buttons[0][0].startswith("qa_del:")
    assert "irreversible" in (reply.text or "")
    assert "Teleferico" in (reply.text or "")
    assert chat.tool_result["status"] == "confirmacion_pendiente"
    assert len((await db_session.execute(select(Movement))).scalars().all()) == 2
    # Confirmar con el botón borra los 2.
    from app.bot.interactive import handle_interactive
    out = await handle_interactive(db_session, u1, "549111", reply.buttons[0][0], TODAY)
    assert "2 movimientos" in (out.text or "")
    assert (await db_session.execute(select(Movement))).scalars().all() == []
    # El token queda consumido: reusarlo no borra de nuevo.
    out2 = await handle_interactive(db_session, u1, "549111", reply.buttons[0][0], TODAY)
    assert "Expiró" in (out2.text or "")


async def test_agent_edit_applies_changes(db_session):
    u1, u2 = await _setup(db_session)
    m1, _ = await _seed_movements(db_session, u1)
    chat = ToolCallingFakeChat("edit_movement",
                               {"movement_id": m1.id, "split": "shared", "category": "transporte"})
    reply = await handle_question(db_session, u1, "549111", "ese es 50/50 y transporte",
                                  TODAY, chat_client=chat)
    assert reply.text == "hecho"  # sin botones: la edición se aplica directa
    await db_session.refresh(m1)
    assert m1.split == "shared"
    assert m1.category_id is not None
    assert chat.tool_result["changes"]


async def test_unknown_with_fresh_history_goes_to_agent(db_session):
    await _setup(db_session)
    unknown = dict(_question_payload(), intent="unknown")
    # Sin conversación previa: enlatado.
    reply = await dispatch(db_session, "549111", "text", "Si", None, TODAY,
                           llm_client=FakeLLM(unknown), chat_client=FakeChat("con contexto"))
    assert "No te entendí" in (reply.text or "")
    # Con conversación fresca: va al agente.
    await dispatch(db_session, "549111", "text", "cuánto gastamos?", None, TODAY,
                   llm_client=FakeLLM(_question_payload()), chat_client=FakeChat("USD 90"))
    reply = await dispatch(db_session, "549111", "text", "Si", None, TODAY,
                           llm_client=FakeLLM(unknown), chat_client=FakeChat("con contexto"))
    assert reply.text == "con contexto"


async def test_list_movements_rows_include_id(db_session):
    u1, _ = await _setup(db_session)
    m1, m2 = await _seed_movements(db_session, u1)
    from app.qa.tools import list_movements
    got = await list_movements(db_session, [u1], limit=5)
    assert {r["id"] for r in got["rows"]} == {m1.id, m2.id}
