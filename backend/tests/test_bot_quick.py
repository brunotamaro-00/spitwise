"""Fast-paths del bot ('saldo', 'hoy', 'total'): responden sin pasar por el LLM."""
from datetime import date
from decimal import Decimal

from app.api.auth import hash_password
from app.bot.dispatcher import dispatch
from app.bot.quick import route
from app.db.models import Movement, Stop, User

TODAY = date(2026, 8, 6)


class BoomLLM:
    """Explota si el dispatcher intenta parsear: prueba que el fast-path no usa LLM."""

    async def parse(self, *a, **kw):
        raise AssertionError("el fast-path no debe llamar al LLM")


async def _seed(db_session):
    u1 = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549110")
    u2 = User(username="katia", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    db_session.add_all([u1, u2])
    await db_session.commit()
    return u1, u2


def _expense(payer_id: int, usd: str, day: date, split: str = "shared") -> Movement:
    return Movement(
        type="expense", amount=Decimal(usd), currency="USD", amount_usd=Decimal(usd),
        fx_rate=Decimal("1"), fx_source="direct", paid_by=payer_id, split=split,
        movement_date=day, created_by=payer_id,
    )


def test_route_folds_accents_and_punctuation():
    assert route("¿Quién debe?") == "balance"
    assert route("Saldo") == "balance"
    assert route("HOY") == "today"
    assert route("total") == "total"
    assert route("Resumen") == "total"
    # No fast-path: preguntas en lenguaje natural van al agente Q&A.
    assert route("cuánto gastamos en Roma") is None
    assert route("¿cuánto gastamos?") is None
    assert route("cena 20 euros") is None


async def test_saldo_sin_llm(db_session):
    u1, _u2 = await _seed(db_session)
    db_session.add(_expense(u1.id, "100", TODAY))
    await db_session.commit()
    reply = await dispatch(db_session, "549110", "text", "saldo", None, TODAY, llm_client=BoomLLM())
    assert "Balance" in reply.text
    assert "*Katia*" in reply.text and "*Bruno*" in reply.text
    assert "USD 50,0" in reply.text


async def test_saldo_a_mano(db_session):
    await _seed(db_session)
    reply = await dispatch(db_session, "549110", "text", "balance", None, TODAY, llm_client=BoomLLM())
    assert "a mano" in reply.text


async def test_hoy_solo_cuenta_el_dia(db_session):
    u1, u2 = await _seed(db_session)
    db_session.add(Stop(slug="roma", order=1, name="Roma", currency_code="EUR",
                        arrival_date=date(2026, 8, 1), departure_date=date(2026, 8, 10)))
    db_session.add(_expense(u1.id, "30", TODAY))
    db_session.add(_expense(u2.id, "10", TODAY, split="payer_only"))
    db_session.add(_expense(u1.id, "99", date(2026, 8, 5)))  # ayer: afuera
    await db_session.commit()
    reply = await dispatch(db_session, "549110", "text", "hoy", None, TODAY, llm_client=BoomLLM())
    assert "Hoy" in reply.text and "Roma" in reply.text
    assert "USD 40,0" in reply.text  # total del día
    assert "Tu parte: USD 15,0" in reply.text  # 30/2; el payer_only de katia no
    assert "2 gastos" in reply.text


async def test_hoy_sin_gastos(db_session):
    await _seed(db_session)
    reply = await dispatch(db_session, "549110", "text", "hoy", None, TODAY, llm_client=BoomLLM())
    assert "no hay gastos" in reply.text


async def test_total_del_viaje(db_session):
    u1, _u2 = await _seed(db_session)
    # Itinerario: 10 días (arrival→departure).
    db_session.add(Stop(slug="roma", order=1, name="Roma", currency_code="EUR",
                        arrival_date=date(2026, 8, 1), departure_date=date(2026, 8, 11)))
    db_session.add(_expense(u1.id, "80", date(2026, 8, 2)))
    db_session.add(_expense(u1.id, "20", TODAY))
    # Un settlement no es gasto: no suma al total del viaje.
    db_session.add(Movement(type="settlement", amount=Decimal("50"), currency="USD",
                            amount_usd=Decimal("50"), fx_rate=Decimal("1"), fx_source="direct",
                            paid_by=u1.id, split="shared", movement_date=TODAY, created_by=u1.id))
    await db_session.commit()
    reply = await dispatch(db_session, "549110", "text", "total", None, TODAY, llm_client=BoomLLM())
    assert "Total del viaje" in reply.text
    assert "USD 100,0" in reply.text
    assert "Tu parte: USD 50,0" in reply.text
    assert "10 días" in reply.text
    assert "USD 10,0* por día" in reply.text
