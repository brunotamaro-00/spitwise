from datetime import date, datetime, timedelta, timezone

from app.api.auth import hash_password
from app.bot.active_stop import get_state_payload, update_state_payload
from app.bot.dispatcher import dispatch
from app.bot.trip_qa import handle_trip_question, latest_fresh_channel
from app.db.models import GuideDoc, Stop, StopGuide, User

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


class ToolCallingFakeChat:
    """Ejecuta una secuencia de (tool, args) y devuelve el último resultado como str."""

    def __init__(self, plan):
        self.plan = plan
        self.results = []

    async def run(self, *, tools, **kwargs):
        by_name = {t.name: t for t in tools}
        for name, args in self.plan:
            self.results.append(await by_name[name].handler(**args))
        return "ok"


def _payload(intent):
    return {
        "intent": intent, "amount": None, "currency": None, "description": None,
        "category": None, "split": "shared", "paid_by": None, "date": None, "city": None,
        "confidence": 0.9, "candidates": [], "ref_last": False, "ref_text": None, "ref_date": None,
    }


async def _setup(db_session):
    u1 = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    u2 = User(username="katia", password_hash=hash_password("pw"), whatsapp_wa_id="549222")
    db_session.add_all([u1, u2])
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    db_session.add(Stop(slug="roma", order=1, name="Roma", country="Italia",
                        arrival_date=date(2026, 8, 1), departure_date=date(2026, 8, 10)))
    db_session.add(Stop(slug="florencia", order=2, name="Florencia", country="Italia",
                        arrival_date=date(2026, 8, 10), departure_date=date(2026, 8, 14)))
    db_session.add(GuideDoc(guide_slug="roma", doc_slug="actividades", guide_title="Roma",
                            title="Actividades", country="Italia", kind="city",
                            file="italia/roma/actividades.md",
                            content_md="# Actividades\n\n- Coliseo €18 reservar antes"))
    db_session.add(StopGuide(stop_slug="roma", guide_slug="roma", position=0))
    await db_session.commit()
    return u1, u2


async def test_trip_agent_isolated_from_finance(db_session):
    u1, _ = await _setup(db_session)
    chat = FakeChat("El Coliseo se reserva antes 📖")
    reply = await handle_trip_question(db_session, u1, "549111", "hay que reservar el coliseo?",
                                       TODAY, chat_client=chat)
    assert reply.text == "El Coliseo se reserva antes 📖"
    call = chat.calls[0]
    # Solo tools de guías/notas — ninguna financiera.
    assert {t.name for t in call["tools"]} == {
        "search_guides", "list_guides", "read_guide_doc", "list_notes",
        "search_documents"}
    # Prompt propio: grounding sí, semántica financiera no.
    assert "guías" in call["system"] and "NUNCA completes" in call["system"]
    for financial in ("aggregate_expenses", "get_balance", "edit_movement", "attribution"):
        assert financial not in call["system"]
    # Snapshot con la parada de hoy y sus guías.
    assert "Parada de hoy: Roma" in call["user_text"]
    assert "Guías de roma: roma" in call["user_text"]


async def test_failed_tool_does_not_ground_a_trip_answer(db_session):
    """Una tool que explotó no trajo evidencia: la guarda estructural tiene que
    seguir bloqueando datos concretos aunque `tool_calls` no esté vacío."""
    from app.bot import copy
    from app.llm.chat import ChatResult

    u1, _ = await _setup(db_session)

    class Chat:
        def __init__(self, result):
            self.result = result

        async def run(self, **kw):
            return self.result

    answer = "El Coliseo sale 18 euros y abre 8:30."
    blocked = await handle_trip_question(
        db_session, u1, "549111", "cuánto sale el coliseo?", TODAY,
        chat_client=Chat(ChatResult(text=answer, outcome="ok",
                                    tool_calls=["search_guides"],
                                    tool_errors=["search_guides"])),
    )
    assert blocked.text == copy.TRIP_NO_EVIDENCE

    # La misma tool, esta vez sin error: la respuesta pasa.
    ok = await handle_trip_question(
        db_session, u1, "549222", "cuánto sale el coliseo?", TODAY,
        chat_client=Chat(ChatResult(text=answer, outcome="ok",
                                    tool_calls=["search_guides"])),
    )
    assert ok.text == answer


async def test_trip_history_key_isolated(db_session):
    u1, _ = await _setup(db_session)
    await update_state_payload(db_session, "549111", qa_history=[
        {"role": "user", "content": "saldo?", "ts": datetime.now(timezone.utc).isoformat()},
    ])
    await handle_trip_question(db_session, u1, "549111", "qué hacemos hoy?", TODAY,
                               chat_client=FakeChat())
    payload = await get_state_payload(db_session, "549111")
    # El canal de viaje escribe SU key y no toca la financiera.
    assert len(payload["trip_qa_history"]) == 2
    assert payload["qa_history"][0]["content"] == "saldo?"
    # Y el historial financiero no viajó al agente de guías.
    chat = FakeChat()
    await handle_trip_question(db_session, u1, "549111", "y mañana?", TODAY, chat_client=chat)
    assert chat.calls[0]["history"] == [
        {"role": "user", "content": "qué hacemos hoy?"},
        {"role": "assistant", "content": "respuesta"},
    ]


async def test_trip_tools_execute_via_agent(db_session, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("ANDIAMO_URL", "http://andiamo.test")
    get_settings.cache_clear()
    u1, _ = await _setup(db_session)
    chat = ToolCallingFakeChat([
        ("search_guides", {"query": "coliseo"}),
        ("read_guide_doc", {"guide_slug": "roma", "doc_slug": "actividades"}),
    ])
    await handle_trip_question(db_session, u1, "549111", "coliseo?", TODAY, chat_client=chat)
    assert chat.results[0]["hits"][0]["doc_slug"] == "actividades"
    assert chat.results[1]["link"] == "http://andiamo.test/guias/roma/actividades"
    get_settings.cache_clear()


async def test_empty_cache_flagged_in_snapshot(db_session):
    u1 = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    u2 = User(username="katia", password_hash=hash_password("pw"), whatsapp_wa_id="549222")
    db_session.add_all([u1, u2])
    await db_session.commit()
    chat = FakeChat()
    await handle_trip_question(db_session, u1, "549111", "qué hacemos?", TODAY, chat_client=chat)
    assert "VACÍO" in chat.calls[0]["user_text"]


def _ts(minutes_ago):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


def test_latest_fresh_channel():
    kw = {"max_turns": 8, "ttl_minutes": 60}
    assert latest_fresh_channel({}, **kw) is None
    qa = [{"role": "user", "content": "saldo", "ts": _ts(10)}]
    trip = [{"role": "user", "content": "coliseo", "ts": _ts(5)}]
    assert latest_fresh_channel({"qa_history": qa}, **kw) == "qa"
    assert latest_fresh_channel({"trip_qa_history": trip}, **kw) == "trip"
    assert latest_fresh_channel({"qa_history": qa, "trip_qa_history": trip}, **kw) == "trip"
    # Vencidos (fuera del TTL) no cuentan.
    stale = [{"role": "user", "content": "x", "ts": _ts(120)}]
    assert latest_fresh_channel({"qa_history": stale}, **kw) is None
    assert latest_fresh_channel({"qa_history": stale, "trip_qa_history": trip}, **kw) == "trip"


async def test_dispatch_routes_trip_question(db_session):
    await _setup(db_session)
    chat = FakeChat("respuesta de guía")
    reply = await dispatch(db_session, "549111", "text", "qué hacemos mañana?", None, TODAY,
                           llm_client=FakeLLM(_payload("trip_question")), chat_client=chat)
    assert reply.text == "respuesta de guía"
    assert {t.name for t in chat.calls[0]["tools"]} == {
        "search_guides", "list_guides", "read_guide_doc", "list_notes",
        "search_documents"}


async def test_dispatch_unknown_follows_latest_channel(db_session):
    await _setup(db_session)
    # Solo historial de viaje fresco → unknown va al agente de guías.
    await update_state_payload(db_session, "549111", trip_qa_history=[
        {"role": "user", "content": "coliseo?", "ts": _ts(3)},
        {"role": "assistant", "content": "sí, reservá", "ts": _ts(3)},
    ])
    chat = FakeChat()
    await dispatch(db_session, "549111", "text", "y cuánto sale?", None, TODAY,
                   llm_client=FakeLLM(_payload("unknown")), chat_client=chat)
    tools = {t.name for t in chat.calls[0]["tools"]}
    assert "search_guides" in tools and "get_balance" not in tools
    # Si el canal financiero es el más reciente, va al financiero.
    # (el dispatch anterior dejó trip_qa_history con ts de recién: lo envejecemos)
    await update_state_payload(db_session, "549111", trip_qa_history=[
        {"role": "user", "content": "coliseo?", "ts": _ts(30)},
        {"role": "assistant", "content": "sí, reservá", "ts": _ts(30)},
    ], qa_history=[
        {"role": "user", "content": "saldo?", "ts": _ts(1)},
        {"role": "assistant", "content": "a mano", "ts": _ts(1)},
    ])
    chat2 = FakeChat()
    await dispatch(db_session, "549111", "text", "y ayer?", None, TODAY,
                   llm_client=FakeLLM(_payload("unknown")), chat_client=chat2)
    assert "get_balance" in {t.name for t in chat2.calls[0]["tools"]}
