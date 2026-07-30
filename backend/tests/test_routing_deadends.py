"""Routing entre canales y dead-ends del parser.

Tres cosas se fijan acá:
- una falla TÉCNICA de parseo (refusal, proveedor caído) se reintenta una vez y
  se dice como lo que es, en vez de rutearse a un agente por historial fresco;
- un `unknown` con señales inequívocas de plata va a finanzas aunque el hilo
  fresco sea de guías (el agente de guías no tiene con qué responderlo);
- los dead-ends de edición dicen QUÉ falló en vez de "no entendí".
"""
from datetime import date, datetime, timezone
from decimal import Decimal

from app.api.auth import hash_password
from app.bot import quick
from app.bot.active_stop import update_state_payload
from app.bot.dispatcher import dispatch
from app.bot.editor import handle_edit
from app.db.models import Movement, User
from app.llm.client import PARSE_FAILURE_PAYLOAD
from app.llm.parser import ParsedMessage, parse_message

TODAY = date(2026, 8, 20)


class FakeLLM:
    def __init__(self, *payloads):
        self.payloads = list(payloads)
        self.calls = 0

    async def parse(self, text, **kwargs):
        self.calls += 1
        return self.payloads[min(self.calls - 1, len(self.payloads) - 1)]


class BoomLLM:
    def __init__(self):
        self.calls = 0

    async def parse(self, text, **kwargs):
        self.calls += 1
        raise RuntimeError("503")


class FakeChat:
    def __init__(self):
        self.calls = []

    async def run(self, **kw):
        self.calls.append(kw)
        return "respuesta"


def _payload(**over):
    base = {"intent": "unknown", "amount": None, "currency": None, "description": None,
            "category": None, "split": "shared", "paid_by": None, "date": None,
            "city": None, "confidence": 0.9, "candidates": [], "ref_last": False,
            "ref_text": None, "ref_date": None}
    base.update(over)
    return base


async def _setup(db_session):
    u1 = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    u2 = User(username="katia", password_hash=hash_password("pw"), whatsapp_wa_id="549222")
    db_session.add_all([u1, u2])
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    await db_session.commit()
    return u1, u2


# --- retry solo ante falla técnica -------------------------------------------

async def test_parse_failure_is_retried_once_and_recovers():
    llm = FakeLLM(dict(PARSE_FAILURE_PAYLOAD), _payload(intent="question"))
    got = await parse_message("x", today=TODAY, category_names=[], usernames=["bruno"],
                              sender="bruno", client=llm)
    assert llm.calls == 2 and got.intent == "question" and got.parse_failure is None


async def test_semantic_unknown_is_not_retried():
    """Reintentar un 'no entendí' solo duplica la latencia: el modelo ya leyó."""
    llm = FakeLLM(_payload(intent="unknown"))
    got = await parse_message("bla", today=TODAY, category_names=[], usernames=["bruno"],
                              sender="bruno", client=llm)
    assert llm.calls == 1 and got.parse_failure is None


async def test_provider_error_is_retried_and_then_reported():
    llm = BoomLLM()
    got = await parse_message("x", today=TODAY, category_names=[], usernames=["bruno"],
                              sender="bruno", client=llm)
    assert llm.calls == 2 and got.parse_failure == "provider_error"


async def test_dispatch_reports_parse_failure_instead_of_guessing_a_channel(db_session):
    u1, _ = await _setup(db_session)
    await update_state_payload(db_session, "549111", trip_qa_history=[
        {"role": "user", "content": "qué hacemos?",
         "ts": datetime.now(timezone.utc).isoformat()},
        {"role": "assistant", "content": "cosas",
         "ts": datetime.now(timezone.utc).isoformat()},
    ])
    chat = FakeChat()
    reply = await dispatch(db_session, "549111", "text", "algo", None, TODAY,
                           llm_client=BoomLLM(), chat_client=chat)
    assert chat.calls == []  # no se ruteó a ningún agente
    assert "se me trabó" in reply.text.casefold()


# --- routing de unknown -------------------------------------------------------

def test_ledger_signals_are_conservative():
    assert quick.ledger_signal("¿y cuánto llevamos gastado?")
    assert quick.ledger_signal("¿y el saldo?")
    assert quick.ledger_signal("quedó algo pendiente?")
    # Preguntas de guías que también empiezan con 'cuánto' no son de plata.
    assert not quick.ledger_signal("¿cuánto sale la entrada?")
    assert not quick.ledger_signal("¿y ahí qué hacemos?")
    assert not quick.ledger_signal("¿y en Florencia?")


async def test_unknown_with_money_words_goes_to_finance_over_fresh_trip_thread(db_session):
    u1, _ = await _setup(db_session)
    now = datetime.now(timezone.utc).isoformat()
    await update_state_payload(db_session, "549111", trip_qa_history=[
        {"role": "user", "content": "qué hacemos en Viena?", "ts": now},
        {"role": "assistant", "content": "Schönbrunn", "ts": now},
    ])
    chat = FakeChat()
    await dispatch(db_session, "549111", "text", "¿y cuánto llevamos gastado?", None, TODAY,
                   llm_client=FakeLLM(_payload(intent="unknown")), chat_client=chat)
    tools = {t.name for t in chat.calls[0]["tools"]}
    assert "aggregate_expenses" in tools and "search_guides" not in tools


async def test_unknown_without_money_words_keeps_the_fresh_channel(db_session):
    u1, _ = await _setup(db_session)
    now = datetime.now(timezone.utc).isoformat()
    await update_state_payload(db_session, "549111", trip_qa_history=[
        {"role": "user", "content": "qué hacemos en Viena?", "ts": now},
        {"role": "assistant", "content": "Schönbrunn", "ts": now},
    ])
    chat = FakeChat()
    await dispatch(db_session, "549111", "text", "¿y ahí?", None, TODAY,
                   llm_client=FakeLLM(_payload(intent="unknown")), chat_client=chat)
    tools = {t.name for t in chat.calls[0]["tools"]}
    assert "search_guides" in tools


# --- dead-ends de edición -----------------------------------------------------

async def test_invalid_category_says_which_one(db_session):
    u1, _ = await _setup(db_session)
    parsed = await parse_message(
        "ponelo en bebidas", today=TODAY,
        category_names=["Comida", "Otros"], usernames=["bruno", "katia"], sender="bruno",
        client=FakeLLM(_payload(intent="edit", new_category="Bebidas", ref_last=True)),
    )
    assert parsed.rejected and "Bebidas" in parsed.rejected[0]
    reply = await handle_edit(db_session, u1, "549111", parsed, TODAY)
    assert "Bebidas" in reply.text and "Comida" in reply.text


async def test_invalid_payer_is_reported(db_session):
    u1, _ = await _setup(db_session)
    parsed = await parse_message(
        "pagó juan", today=TODAY, category_names=["Comida"],
        usernames=["bruno", "katia"], sender="bruno",
        client=FakeLLM(_payload(intent="edit", new_paid_by="juan", ref_last=True)),
    )
    reply = await handle_edit(db_session, u1, "549111", parsed, TODAY)
    assert "juan" in reply.text.casefold()


async def test_edit_without_changes_reuses_the_contextual_hint(db_session):
    u1, _ = await _setup(db_session)
    db_session.add(Movement(
        type="expense", amount=Decimal("39"), currency="USD", amount_usd=Decimal("39"),
        fx_rate=Decimal("1"), fx_source="cache", description="Tren", paid_by=u1.id,
        split="shared", created_by=u1.id, status="confirmed",
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    await db_session.commit()
    reply = await handle_edit(db_session, u1, "549111",
                              ParsedMessage(intent="edit", ref_last=True), TODAY)
    assert "Tren" in reply.text and "fueron 45" in reply.text


# --- corrección de un settlement reciente ------------------------------------

async def test_recent_settlement_is_offered_to_the_parser(db_session):
    u1, u2 = await _setup(db_session)
    db_session.add(Movement(
        type="settlement", amount=Decimal("80"), currency="USD", amount_usd=Decimal("80"),
        fx_rate=Decimal("1"), fx_source="manual", paid_by=u1.id, split="shared",
        created_by=u1.id, status="confirmed",
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    await db_session.commit()

    seen = {}

    class Spy(FakeLLM):
        async def parse(self, text, **kwargs):
            seen.update(kwargs)
            return await super().parse(text, **kwargs)

    await dispatch(db_session, "549111", "text", "no, eran 50", None, TODAY,
                   llm_client=Spy(_payload(intent="edit", ref_last=True, new_amount="50")),
                   chat_client=FakeChat())
    # El parser vio el pago de saldo: sin eso leía "no, eran 50" como gasto nuevo.
    assert "pago de saldo" in (seen["last_expense"] or "")
    mv = (await db_session.execute(
        __import__("sqlalchemy").select(Movement))).scalars().first()
    assert mv.amount == Decimal("50") and mv.type == "settlement"
