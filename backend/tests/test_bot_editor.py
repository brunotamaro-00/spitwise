from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import select

from app.api.auth import hash_password
from app.bot.dispatcher import dispatch
from app.bot.interactive import handle_interactive
from app.db.models import Movement, Stop, User

TODAY = date(2026, 8, 6)


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    async def parse(self, text, **kwargs):
        return self.payload


def _payload(**over):
    base = {
        "intent": "edit", "amount": None, "currency": None, "description": None,
        "category": None, "split": "shared", "paid_by": None, "date": None, "city": None,
        "confidence": 0.9, "candidates": [], "ref_last": False, "ref_text": None, "ref_date": None,
        "new_amount": None, "new_currency": None, "new_date": None, "new_city": None,
        "new_category": None, "new_description": None, "new_split": None, "new_paid_by": None,
    }
    base.update(over)
    return base


def _mv(u, desc, amount, d, city=None, slug=None):
    # d = día de carga (created_at): la referencia "de ayer" filtra por este día.
    return Movement(type="expense", amount=Decimal(amount), currency="USD",
                    amount_usd=Decimal(amount), fx_rate=Decimal("1"), fx_source="frankfurter",
                    paid_by=u.id, split="shared", description=desc,
                    created_at=datetime.combine(d, time(12)),
                    city_name=city, stop_slug=slug, created_by=u.id)


async def _setup(db_session):
    u1 = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    u2 = User(username="katia", password_hash=hash_password("pw"), whatsapp_wa_id="549222")
    db_session.add_all([
        u1, u2,
        Stop(slug="londres", order=1, name="Londres", arrival_date=date(2026, 8, 1),
             departure_date=date(2026, 8, 10), currency_code="GBP", timezone="Europe/London"),
        Stop(slug="roma", order=2, name="Roma", arrival_date=date(2026, 9, 20),
             departure_date=date(2026, 9, 26), currency_code="EUR", timezone="Europe/Rome"),
    ])
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    await db_session.commit()
    return u1, u2


async def test_edit_amount_by_reference(db_session):
    u1, _ = await _setup(db_session)
    db_session.add_all([
        _mv(u1, "cena", "10", date(2026, 8, 5), "Londres", "londres"),
        _mv(u1, "taxi", "8", date(2026, 8, 6), "Londres", "londres"),
    ])
    await db_session.commit()
    fake = FakeLLM(_payload(ref_text="cena", new_amount="25"))
    reply = await dispatch(db_session, "549111", "text", "la cena fue 25", None, TODAY, llm_client=fake)
    assert "Editado" in (reply.text or "")
    cena = (await db_session.execute(select(Movement).where(Movement.description == "cena"))).scalar_one()
    assert cena.amount == Decimal("25")
    assert cena.amount_usd == Decimal("25.00")  # USD recalculado


async def test_edit_date_recalculates_city(db_session):
    # "era del 23/9": la fecha no se guarda; solo re-imputa la ciudad por itinerario.
    u1, _ = await _setup(db_session)
    db_session.add(_mv(u1, "cena", "10", date(2026, 8, 5), "Londres", "londres"))
    await db_session.commit()
    fake = FakeLLM(_payload(ref_last=True, new_date="2026-09-23"))
    reply = await dispatch(db_session, "549111", "text", "la fecha era el 23/9", None, TODAY, llm_client=fake)
    mv = (await db_session.execute(select(Movement))).scalar_one()
    assert mv.city_name == "Roma" and mv.stop_slug == "roma"
    assert "Londres → *Roma*" in (reply.text or "")


async def test_edit_defaults_to_last_movement(db_session):
    u1, _ = await _setup(db_session)
    db_session.add_all([
        _mv(u1, "cena", "10", date(2026, 8, 5)),
        _mv(u1, "taxi", "8", date(2026, 8, 6)),
    ])
    await db_session.commit()
    fake = FakeLLM(_payload(ref_last=True, new_category="Transporte"))
    await dispatch(db_session, "549111", "text", "el último era transporte", None, TODAY, llm_client=fake)
    taxi = (await db_session.execute(select(Movement).where(Movement.description == "taxi"))).scalar_one()
    cats = dict((await db_session.execute(
        select(Movement.description, Movement.category_id))).all())
    assert taxi.category_id is not None
    assert cats["cena"] is None  # el otro no se tocó


async def test_edit_ambiguous_reference_asks_buttons(db_session):
    u1, _ = await _setup(db_session)
    db_session.add_all([
        _mv(u1, "cena pizza", "30", date(2026, 8, 5)),
        _mv(u1, "cena pastas", "12", date(2026, 8, 5)),
    ])
    await db_session.commit()
    fake = FakeLLM(_payload(ref_text="cena", ref_date="2026-08-05", new_amount="25"))
    reply = await dispatch(db_session, "549111", "text", "la cena de ayer fue 25", None, TODAY, llm_client=fake)
    assert len(reply.buttons) == 2
    assert "¿Cuál" in (reply.text or "")
    # Elegir la primera opción aplica el cambio a ESE movimiento.
    u1_db = (await db_session.execute(select(User).where(User.username == "bruno"))).scalar_one()
    bid = reply.buttons[0][0]
    reply2 = await handle_interactive(db_session, u1_db, "549111", bid, TODAY)
    assert "Editado" in (reply2.text or "")
    amounts = {d: a for d, a in (await db_session.execute(
        select(Movement.description, Movement.amount))).all()}
    assert Decimal("25") in amounts.values()
    assert Decimal("12") in amounts.values() or Decimal("30") in amounts.values()


async def test_edit_paid_by_and_split(db_session):
    u1, u2 = await _setup(db_session)
    db_session.add(_mv(u1, "museo", "20", date(2026, 8, 6)))
    await db_session.commit()
    fake = FakeLLM(_payload(ref_last=True, new_paid_by="katia", new_split="payer_only"))
    reply = await dispatch(db_session, "549111", "text", "el museo lo pagó katia y es solo de ella",
                           None, TODAY, llm_client=fake)
    mv = (await db_session.execute(select(Movement))).scalar_one()
    assert mv.paid_by == u2.id
    assert mv.split == "payer_only"
    assert "Editado" in (reply.text or "")


async def test_delete_by_reference_confirms_then_deletes(db_session):
    u1, _ = await _setup(db_session)
    db_session.add_all([
        _mv(u1, "museo", "20", date(2026, 8, 5)),
        _mv(u1, "cena", "30", date(2026, 8, 6)),
    ])
    await db_session.commit()
    fake = FakeLLM(_payload(intent="delete", ref_text="museo"))
    reply = await dispatch(db_session, "549111", "text", "borrá el museo", None, TODAY, llm_client=fake)
    assert reply.buttons and reply.buttons[0][0].startswith("del_confirm:")
    assert "Museo" in (reply.text or "")
    await handle_interactive(db_session, u1, "549111", reply.buttons[0][0], TODAY)
    left = (await db_session.execute(select(Movement.description))).scalars().all()
    assert left == ["cena"]


async def test_edit_no_match_reports(db_session):
    u1, _ = await _setup(db_session)
    db_session.add(_mv(u1, "cena", "10", date(2026, 8, 5)))
    await db_session.commit()
    fake = FakeLLM(_payload(ref_text="paracaidismo", new_amount="99"))
    reply = await dispatch(db_session, "549111", "text", "el paracaidismo fue 99", None, TODAY, llm_client=fake)
    assert "No encontré" in (reply.text or "")


async def test_edit_date_persists_payment_date_and_historic_fx(db_session):
    """'era de ayer' ahora también persiste la fecha de pago y recalcula el TC
    con la tasa de esa fecha (histórico), no la de hoy."""
    from app.db.models import FxRate
    u1, _ = await _setup(db_session)
    mv = _mv(u1, "cena", "20", TODAY)
    mv.currency = "EUR"
    db_session.add_all([
        mv,
        FxRate(currency="EUR", rate_date=date(2026, 8, 5), rate_to_usd=Decimal("1.05")),
        FxRate(currency="EUR", rate_date=TODAY, rate_to_usd=Decimal("1.10")),
    ])
    await db_session.commit()
    fake = FakeLLM(_payload(ref_last=True, new_date="2026-08-05"))
    await dispatch(db_session, "549111", "text", "era de ayer", None, TODAY, llm_client=fake)
    await db_session.refresh(mv)
    assert mv.payment_date == date(2026, 8, 5)
    assert mv.status == "confirmed"
    assert mv.fx_rate == Decimal("1.05")


async def test_edit_date_to_future_marks_pending(db_session):
    u1, _ = await _setup(db_session)
    mv = _mv(u1, "hostel", "100", TODAY)
    db_session.add(mv)
    await db_session.commit()
    fake = FakeLLM(_payload(ref_last=True, new_date="2026-09-22"))
    await dispatch(db_session, "549111", "se paga el 22-sep", "se paga el 22-sep", None,
                   TODAY, llm_client=fake)
    await db_session.refresh(mv)
    assert mv.payment_date == date(2026, 9, 22)
    assert mv.status == "pending"
    assert mv.city_name == "Roma"  # re-imputada por el itinerario de esa fecha


async def test_edit_amount_keeps_manual_fx(db_session):
    """Invariante 6 también en el editor: la tasa manual no se pisa."""
    u1, _ = await _setup(db_session)
    mv = _mv(u1, "cena", "20", TODAY)
    mv.currency = "GBP"
    mv.fx_source = "manual"
    mv.fx_rate = Decimal("1.30")
    mv.amount_usd = Decimal("26.00")
    db_session.add(mv)
    await db_session.commit()
    fake = FakeLLM(_payload(ref_last=True, new_amount="40"))
    await dispatch(db_session, "549111", "fueron 40", "fueron 40", None, TODAY, llm_client=fake)
    await db_session.refresh(mv)
    assert mv.fx_source == "manual"
    assert mv.fx_rate == Decimal("1.30")
    assert mv.amount_usd == Decimal("52.00")
