"""Degradación de los canales Q&A cuando el loop no deja respuesta usable.

Reglas que se verifican acá:
- la copy es del canal y de la causa, no un genérico único;
- una degradación NO se guarda en el historial (el follow-up siguiente tiene que
  seguir apoyado en el último turno que sí sirvió);
- si una acción ya se aplicó a la DB, se confirma el efecto real en vez de
  responder que el bot se enredó.
"""
from datetime import date
from decimal import Decimal

from app.api.auth import hash_password
from app.bot.active_stop import get_state_payload
from app.bot.qa import handle_question
from app.bot.trip_qa import handle_trip_question
from app.db.models import Movement, User
from app.llm.chat import BUDGET_EXCEEDED, PROVIDER_ERROR, TOOL_ERROR, ChatResult

TODAY = date(2026, 8, 6)


class DegradedChat:
    """Devuelve un ChatResult sin texto, como el loop tras agotar presupuesto."""

    def __init__(self, outcome=BUDGET_EXCEEDED, run_tool=None):
        self.outcome = outcome
        self.run_tool = run_tool  # (nombre, kwargs) a ejecutar antes de degradar

    async def run(self, *, tools, **kw):
        calls = []
        if self.run_tool:
            name, args = self.run_tool
            by_name = {t.name: t for t in tools}
            calls.append(name)
            await by_name[name].handler(**args)
        return ChatResult(text="", outcome=self.outcome, tool_calls=calls)


class OkChat:
    async def run(self, **kw):
        return ChatResult(text="Van *USD 90*", outcome="ok")


async def _setup(db_session):
    u1 = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    u2 = User(username="katia", password_hash=hash_password("pw"), whatsapp_wa_id="549222")
    db_session.add_all([u1, u2])
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    await db_session.commit()
    return u1, u2


async def test_degraded_reply_is_channel_and_cause_specific(db_session):
    u1, _ = await _setup(db_session)
    budget = await handle_question(db_session, u1, "549111", "cuánto gastamos?", TODAY,
                                   chat_client=DegradedChat(BUDGET_EXCEEDED))
    provider = await handle_question(db_session, u1, "549111", "cuánto gastamos?", TODAY,
                                     chat_client=DegradedChat(PROVIDER_ERROR))
    tools = await handle_question(db_session, u1, "549111", "cuánto gastamos?", TODAY,
                                  chat_client=DegradedChat(TOOL_ERROR))
    assert budget.text != provider.text != tools.text
    assert "acotala" in budget.text.casefold()
    assert "conexión" in provider.text.casefold()


async def test_trip_degradation_talks_about_guides(db_session):
    u1, _ = await _setup(db_session)
    reply = await handle_trip_question(db_session, u1, "549111", "qué hacemos?", TODAY,
                                       chat_client=DegradedChat(TOOL_ERROR))
    assert "guías" in reply.text.casefold()


async def test_degradation_is_not_persisted_in_history(db_session):
    u1, _ = await _setup(db_session)
    await handle_question(db_session, u1, "549111", "cuánto gastamos en Roma?", TODAY,
                          chat_client=OkChat())
    await handle_question(db_session, u1, "549111", "¿y en Paris?", TODAY,
                          chat_client=DegradedChat())
    payload = await get_state_payload(db_session, "549111")
    contents = [e["content"] for e in payload["qa_history"]]
    # El último turno útil sigue siendo el ancla del hilo.
    assert contents == ["cuánto gastamos en Roma?", "Van *USD 90*"]


async def test_trip_degradation_is_not_persisted_either(db_session):
    u1, _ = await _setup(db_session)
    await handle_trip_question(db_session, u1, "549111", "qué hacemos?", TODAY,
                               chat_client=DegradedChat())
    payload = await get_state_payload(db_session, "549111")
    assert not payload.get("trip_qa_history")


async def test_executed_edit_is_confirmed_even_if_the_model_gives_up(db_session):
    u1, u2 = await _setup(db_session)
    mv = Movement(type="expense", amount=Decimal("40"), currency="EUR",
                  amount_usd=Decimal("44"), fx_rate=Decimal("1.1"), fx_source="cache",
                  description="Cena", paid_by=u1.id, split="shared", created_by=u1.id,
                  status="confirmed")
    db_session.add(mv)
    await db_session.commit()

    reply = await handle_question(
        db_session, u1, "549111", "poné la cena en 45", TODAY,
        chat_client=DegradedChat(BUDGET_EXCEEDED,
                                 run_tool=("edit_movement", {"movement_id": mv.id,
                                                             "amount": "45"})),
    )
    await db_session.refresh(mv)
    assert mv.amount == Decimal("45")
    # La edición ya está commiteada: la respuesta la confirma, no dice "me enredé".
    assert "Cena" in reply.text and "45" in reply.text
    assert "enredé" not in reply.text
