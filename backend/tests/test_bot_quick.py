"""Fast-paths del bot ('saldo', 'total'): responden sin pasar por el LLM."""
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


def _expense(payer_id: int, usd: str, split: str = "shared") -> Movement:
    return Movement(
        type="expense", amount=Decimal(usd), currency="USD", amount_usd=Decimal(usd),
        fx_rate=Decimal("1"), fx_source="direct", paid_by=payer_id, split=split,
        created_by=payer_id,
    )


def test_route_folds_accents_and_punctuation():
    assert route("¿Quién debe?") == "balance"
    assert route("Saldo") == "balance"
    assert route("total") == "total"
    assert route("Resumen") == "total"
    # 'hoy' ya no es fast-path: sin fecha imputada, va al agente Q&A.
    assert route("hoy") is None
    # No fast-path: preguntas en lenguaje natural van al agente Q&A.
    assert route("cuánto gastamos en Roma") is None
    assert route("¿cuánto gastamos?") is None
    assert route("cena 20 euros") is None


async def test_saldo_sin_llm(db_session):
    u1, _u2 = await _seed(db_session)
    db_session.add(_expense(u1.id, "100"))
    await db_session.commit()
    reply = await dispatch(db_session, "549110", "text", "saldo", None, TODAY, llm_client=BoomLLM())
    assert "Balance" in reply.text
    assert "*Katia*" in reply.text and "*Bruno*" in reply.text
    assert "USD 50,0" in reply.text


async def test_saldo_a_mano(db_session):
    await _seed(db_session)
    reply = await dispatch(db_session, "549110", "text", "balance", None, TODAY, llm_client=BoomLLM())
    assert "a mano" in reply.text


async def test_total_del_viaje(db_session):
    u1, _u2 = await _seed(db_session)
    # Itinerario: 10 días (arrival→departure).
    db_session.add(Stop(slug="roma", order=1, name="Roma", currency_code="EUR",
                        arrival_date=date(2026, 8, 1), departure_date=date(2026, 8, 11)))
    db_session.add(_expense(u1.id, "80"))
    db_session.add(_expense(u1.id, "20"))
    # Un settlement no es gasto: no suma al total del viaje.
    db_session.add(Movement(type="settlement", amount=Decimal("50"), currency="USD",
                            amount_usd=Decimal("50"), fx_rate=Decimal("1"), fx_source="direct",
                            paid_by=u1.id, split="shared", created_by=u1.id))
    await db_session.commit()
    reply = await dispatch(db_session, "549110", "text", "total", None, TODAY, llm_client=BoomLLM())
    assert "Total del viaje" in reply.text
    assert "USD 100,0" in reply.text
    assert "Tu parte: USD 50,0" in reply.text
    assert "10 días" in reply.text
    assert "USD 10,0* por día" in reply.text


async def test_total_counts_days_like_the_web(db_session):
    """'total' descartaba las paradas con dueño —incluidas las PROPIAS del
    remitente, como Portugal mientras Katia está en Pititas— porque llamaba a
    _itinerary_days sin username. Menos noches = $/día más alto que /ciudades."""
    from app.api.city_analytics import _itinerary_days
    from app.bot.quick import handle_total

    u1, _ = await _seed(db_session)
    db_session.add_all([
        Stop(slug="lisboa", name="Lisboa", order=1,
             arrival_date=date(2026, 8, 1), departure_date=date(2026, 8, 5)),
        # Tramo propio de Bruno (contraparte de Pititas): SÍ cuenta para él.
        Stop(slug="porto", name="Porto", order=2, owner_username="bruno",
             arrival_date=date(2026, 8, 5), departure_date=date(2026, 8, 9)),
        _expense(u1.id, "400"),
    ])
    await db_session.commit()

    reply = await handle_total(db_session, u1)
    days_web = await _itinerary_days(db_session, None, u1.username)
    days_all = await _itinerary_days(db_session, None)
    assert days_web != days_all, "el fixture debe distinguir ambos conteos"
    # 8 noches con username (Lisboa 4 + Porto 4) vs 4 sin él.
    assert (days_web, days_all) == (8, 4)
    # El promedio del bot usa los días de la web: 400/8 = 50, no 400/4 = 100.
    assert "50" in reply.text
