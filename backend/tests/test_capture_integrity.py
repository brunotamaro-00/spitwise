"""Integridad de escritura del bot: nada entra a medias y en silencio.

Los casos de acá son degradaciones silenciosas reales del camino de captura y
edición: cuotas declaradas que no cierran y se guardaban como un gasto entero,
montos <= 0 que la API rechaza pero el bot aceptaba, descartes (tope de batch,
cashback fijo en cuotas, batch multi-moneda) que no se avisaban, y el contexto
de "último gasto" cruzándose entre los dos teléfonos.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.api.auth import hash_password
from app.bot.capture import handle_capture
from app.bot.dispatcher import dispatch
from app.bot.editor import apply_edit_to, recent_movement
from app.db.models import Category, FxRate, Movement, Stop, User
from app.llm.parser import Installment, ParsedMessage

TODAY = date(2026, 8, 20)


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    async def parse(self, text, **kwargs):
        self.last_kwargs = kwargs
        return self.payload


async def _setup(db_session):
    u1 = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    u2 = User(username="katia", password_hash=hash_password("pw"), whatsapp_wa_id="549222")
    db_session.add_all([u1, u2])
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    db_session.add_all([
        Stop(slug="lisboa", order=1, name="Lisboa", country="Portugal",
             arrival_date=date(2026, 8, 12), departure_date=date(2026, 8, 22),
             currency_code="EUR", owner_username="bruno"),
        Stop(slug="pititas", order=2, name="Pititas", arrival_date=date(2026, 9, 1),
             departure_date=date(2026, 9, 10), currency_code="EUR",
             is_local=True, owner_username="katia"),
    ])
    for cur in ("EUR", "CHF", "GBP"):
        db_session.add(FxRate(currency=cur, rate_date=TODAY, rate_to_usd=Decimal("1.10")))
    await db_session.commit()
    return u1, u2


def _expense(**over) -> ParsedMessage:
    base = dict(intent="expense", amount=Decimal("20"), currency="EUR",
                description="Cena", category_name="Comida")
    base.update(over)
    return ParsedMessage(**base)


async def _movements(db_session):
    return (await db_session.execute(select(Movement).order_by(Movement.id))).scalars().all()


# --- cuotas declaradas que no cierran ----------------------------------------

async def test_invalid_installments_do_not_persist_a_single_expense(db_session):
    u1, _ = await _setup(db_session)
    # Dos etapas 'resto' (sin percent ni amount): expand_installments no puede
    # repartir. Antes esto guardaba UN gasto por el total, con la fecha mal.
    parsed = _expense(amount=Decimal("430"), currency="CHF", description="Hostel",
                      installments=[Installment(), Installment()])
    reply = await handle_capture(db_session, u1, "549111", "hostel 430 chf en partes",
                                 TODAY, parsed=parsed)
    assert await _movements(db_session) == []
    assert "no lo guardé" in reply.text
    assert "430" in reply.text or "partes" in reply.text


async def test_valid_installments_still_expand(db_session):
    u1, _ = await _setup(db_session)
    parsed = _expense(amount=Decimal("400"), currency="CHF", description="Hostel",
                      installments=[Installment(percent=Decimal("25")),
                                    Installment(pay_date=date(2026, 9, 3))])
    await handle_capture(db_session, u1, "549111", "x", TODAY, parsed=parsed)
    movs = await _movements(db_session)
    assert [m.amount for m in movs] == [Decimal("100.00"), Decimal("300.00")]


async def test_fixed_cashback_dropped_in_installments_is_announced(db_session):
    u1, _ = await _setup(db_session)
    parsed = _expense(amount=Decimal("400"), currency="CHF", description="Hostel",
                      cashback_kind="amount", cashback_value=Decimal("20"),
                      installments=[Installment(percent=Decimal("25")),
                                    Installment(pay_date=date(2026, 9, 3))])
    reply = await handle_capture(db_session, u1, "549111", "x", TODAY, parsed=parsed)
    movs = await _movements(db_session)
    assert all(m.cashback_kind is None for m in movs)  # limitación conocida…
    assert "cashback" in reply.text.casefold()  # …pero dicha


# --- montos no positivos ------------------------------------------------------

async def test_zero_amount_is_rejected_like_the_api(db_session):
    u1, _ = await _setup(db_session)
    reply = await handle_capture(db_session, u1, "549111", "cena 0", TODAY,
                                 parsed=_expense(amount=Decimal("0")))
    assert await _movements(db_session) == []
    assert "mayor a cero" in reply.text


async def test_negative_amount_is_rejected(db_session):
    u1, _ = await _setup(db_session)
    await handle_capture(db_session, u1, "549111", "x", TODAY,
                         parsed=_expense(amount=Decimal("-5")))
    assert await _movements(db_session) == []


async def test_batch_drops_invalid_items_and_says_so(db_session):
    u1, _ = await _setup(db_session)
    parsed = _expense(batch=[
        _expense(amount=Decimal("10"), description="Metro"),
        _expense(amount=Decimal("0"), description="Agua"),
    ])
    reply = await handle_capture(db_session, u1, "549111", "x", TODAY, parsed=parsed)
    movs = await _movements(db_session)
    assert [m.description for m in movs] == ["Metro"]
    assert "Agua" in reply.text and "no era válido" in reply.text


# --- tope de batch ------------------------------------------------------------

async def test_batch_over_cap_keeps_ten_and_warns(db_session):
    u1, _ = await _setup(db_session)
    parsed = _expense(batch=[
        _expense(amount=Decimal(str(i + 1)), description=f"Gasto {i}") for i in range(13)
    ])
    reply = await handle_capture(db_session, u1, "549111", "x", TODAY, parsed=parsed)
    assert len(await _movements(db_session)) == 10
    assert "13 gastos" in reply.text and "otro mensaje" in reply.text


# --- contexto reciente por remitente -----------------------------------------

async def test_recent_movement_is_scoped_to_the_sender(db_session):
    u1, u2 = await _setup(db_session)
    db_session.add(Movement(
        type="expense", amount=Decimal("39"), currency="USD", amount_usd=Decimal("39"),
        fx_rate=Decimal("1"), fx_source="cache", description="Tren de Katia",
        paid_by=u2.id, split="shared", created_by=u2.id, status="confirmed",
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    await db_session.commit()
    # Katia lo ve como corregible; Bruno no (es de otro chat).
    assert (await recent_movement(db_session, ttl_minutes=15, created_by=u2.id)) is not None
    assert (await recent_movement(db_session, ttl_minutes=15, created_by=u1.id)) is None


async def test_dispatcher_passes_only_the_senders_last_expense(db_session):
    u1, u2 = await _setup(db_session)
    db_session.add(Movement(
        type="expense", amount=Decimal("39"), currency="USD", amount_usd=Decimal("39"),
        fx_rate=Decimal("1"), fx_source="cache", description="Tren de Katia",
        paid_by=u2.id, split="shared", created_by=u2.id, status="confirmed",
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    await db_session.commit()
    llm = FakeLLM({"intent": "expense", "amount": "12", "currency": "EUR",
                   "description": "Taxi", "category": "Transporte", "confidence": 0.9,
                   "candidates": []})
    await dispatch(db_session, "549111", "text", "taxi 12", None, TODAY, llm_client=llm)
    assert llm.last_kwargs["last_expense"] is None  # el gasto de Katia no viaja al prompt


# --- paridad captura / edición en owner split --------------------------------

async def test_moving_a_shared_expense_to_an_owner_stop_applies_owner_split(db_session):
    u1, _ = await _setup(db_session)
    mv = Movement(type="expense", amount=Decimal("20"), currency="EUR",
                  amount_usd=Decimal("22"), fx_rate=Decimal("1.1"), fx_source="cache",
                  description="Super", paid_by=u1.id, split="shared", created_by=u1.id,
                  stop_slug="lisboa", city_name="Lisboa", status="confirmed")
    db_session.add(mv)
    await db_session.commit()
    await apply_edit_to(db_session, u1, mv, {"city": "Pititas"}, TODAY)
    # Pititas es de Katia y paga Bruno: el gasto queda de ella (other_only).
    assert (mv.stop_slug, mv.split) == ("pititas", "other_only")


async def test_explicit_split_in_the_same_edit_wins_over_owner(db_session):
    u1, _ = await _setup(db_session)
    mv = Movement(type="expense", amount=Decimal("20"), currency="EUR",
                  amount_usd=Decimal("22"), fx_rate=Decimal("1.1"), fx_source="cache",
                  description="Super", paid_by=u1.id, split="shared", created_by=u1.id,
                  stop_slug="lisboa", city_name="Lisboa", status="confirmed")
    db_session.add(mv)
    await db_session.commit()
    await apply_edit_to(db_session, u1, mv,
                        {"city": "Pititas", "only_user": "shared"}, TODAY)
    assert mv.split == "shared"


# --- estados ------------------------------------------------------------------

async def test_editing_an_awaiting_movement_keeps_it_awaiting(db_session):
    """Regresión del camino bot: un edit de fecha no puede confirmar de prepo."""
    u1, _ = await _setup(db_session)
    mv = Movement(type="expense", amount=Decimal("100"), currency="EUR",
                  amount_usd=Decimal("110"), fx_rate=Decimal("1.1"), fx_source="cache",
                  description="Hostel", paid_by=u1.id, split="shared", created_by=u1.id,
                  payment_date=TODAY - timedelta(days=2), status="awaiting")
    db_session.add(mv)
    await db_session.commit()
    await apply_edit_to(db_session, u1, mv, {"date": TODAY - timedelta(days=1)}, TODAY)
    assert mv.status == "awaiting"


# --- batch multi-moneda: el descarte se dice ---------------------------------

async def test_multi_currency_batch_total_edit_warns(db_session):
    u1, _ = await _setup(db_session)
    for cur, amt in (("USD", "34"), ("GBP", "134")):
        db_session.add(Movement(
            type="expense", amount=Decimal(amt), currency=cur,
            amount_usd=Decimal(amt), fx_rate=Decimal("1"), fx_source="cache",
            description=f"Hostel ({cur})", paid_by=u1.id, split="shared",
            created_by=u1.id, status="confirmed", batch_key="b1",
        ))
    await db_session.commit()
    mv = (await _movements(db_session))[0]
    reply = await apply_edit_to(db_session, u1, mv,
                                {"amount": Decimal("50"), "amount_is_total": True}, TODAY)
    assert "varias monedas" in reply.text
    assert mv.amount == Decimal("50")  # se editó solo esta parte, y se dijo


# --- cat_pick recotiza --------------------------------------------------------

async def test_category_pick_reprices_with_the_confirmation_date(db_session):
    from app.bot.capture import apply_category_pick
    from app.bot.pending import create_pending

    from sqlalchemy import update

    u1, _ = await _setup(db_session)
    # El pending guardó la tasa de cuando se preguntó la categoría; al confirmar
    # (horas después, quizá cruzando la medianoche del viaje) vale otra.
    await db_session.execute(update(FxRate).where(FxRate.currency == "EUR")
                             .values(rate_to_usd=Decimal("2.00")))
    await db_session.commit()
    token = await create_pending(db_session, owner="bruno", kind="cat_pick", payload={
        "amount": "10", "currency": "EUR", "amount_usd": "11", "fx_rate": "1.10",
        "fx_source": "cache", "split": "shared", "description": "Aquello",
        "stop_slug": "lisboa", "city_name": "Lisboa", "payment_date": None,
        "status": "confirmed", "cashback_kind": None, "cashback_value": None,
        "paid_by": u1.id, "raw_message": "x",
    })
    cat_id = (await db_session.execute(
        select(Category.id).where(Category.name == "Comida"))).scalar_one()
    await apply_category_pick(db_session, u1, token, cat_id, TODAY)
    mv = (await _movements(db_session))[0]
    assert mv.fx_rate == Decimal("2.00") and mv.amount_usd == Decimal("20.00")


async def test_category_pick_double_tap_saves_one_movement(db_session):
    """El commit del movimiento iba ANTES del cierre del pending: un doble tap
    del botón encontraba el pending abierto y guardaba el gasto dos veces."""
    from app.bot.capture import apply_category_pick
    from app.bot.pending import create_pending

    u1, _ = await _setup(db_session)
    token = await create_pending(db_session, owner="bruno", kind="cat_pick", payload={
        "amount": "10", "currency": "EUR", "amount_usd": "11", "fx_rate": "1.10",
        "fx_source": "cache", "split": "shared", "description": "Aquello",
        "stop_slug": "lisboa", "city_name": "Lisboa", "payment_date": None,
        "status": "confirmed", "cashback_kind": None, "cashback_value": None,
        "paid_by": u1.id, "raw_message": "x",
    })
    cat_id = (await db_session.execute(
        select(Category.id).where(Category.name == "Comida"))).scalar_one()

    first = await apply_category_pick(db_session, u1, token, cat_id, TODAY)
    second = await apply_category_pick(db_session, u1, token, cat_id, TODAY)

    assert "Aquello" in first.text
    assert "Expiró" in second.text
    assert len(await _movements(db_session)) == 1
