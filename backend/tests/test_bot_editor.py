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


async def test_edit_date_alone_keeps_city(db_session):
    # "se paga el 23/9": la fecha de pago cambia, la ciudad NO se arrastra a la
    # parada de esa fecha (el gasto sigue siendo de donde ocurrió).
    u1, _ = await _setup(db_session)
    db_session.add(_mv(u1, "cena", "10", date(2026, 8, 5), "Londres", "londres"))
    await db_session.commit()
    fake = FakeLLM(_payload(ref_last=True, new_date="2026-09-23"))
    reply = await dispatch(db_session, "549111", "text", "se paga el 23/9", None, TODAY, llm_client=fake)
    mv = (await db_session.execute(select(Movement))).scalar_one()
    assert mv.city_name == "Londres" and mv.stop_slug == "londres"
    assert mv.payment_date == date(2026, 9, 23)
    assert "Roma" not in (reply.text or "")


async def test_edit_city_explicit_still_resolves_stop(db_session):
    u1, _ = await _setup(db_session)
    db_session.add(_mv(u1, "cena", "10", date(2026, 8, 5), "Londres", "londres"))
    await db_session.commit()
    fake = FakeLLM(_payload(ref_last=True, new_city="Roma"))
    reply = await dispatch(db_session, "549111", "text", "era en roma", None, TODAY, llm_client=fake)
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
    assert mv.city_name is None  # la fecha sola no re-imputa la ciudad


async def test_edit_only_user_relative_to_new_payer(db_session):
    """'lo pagó katia y es solo de ella': el split se deriva server-side contra
    el pagador NUEVO (payer_only), sin depender de la aritmética del LLM."""
    u1, u2 = await _setup(db_session)
    db_session.add(_mv(u1, "paseo", "28", date(2026, 8, 6)))
    await db_session.commit()
    fake = FakeLLM(_payload(ref_last=True, new_paid_by="katia", new_only_user="katia"))
    await dispatch(db_session, "549111", "text", "lo pagó katia y es solo de ella",
                   None, TODAY, llm_client=fake)
    mv = (await db_session.execute(select(Movement))).scalar_one()
    assert mv.paid_by == u2.id
    assert mv.split == "payer_only"


async def test_edit_only_user_shared(db_session):
    u1, _ = await _setup(db_session)
    mv = _mv(u1, "super", "22", date(2026, 8, 6))
    mv.split = "other_only"
    db_session.add(mv)
    await db_session.commit()
    fake = FakeLLM(_payload(ref_last=True, new_only_user="shared"))
    await dispatch(db_session, "549111", "text", "en realidad era compartido",
                   None, TODAY, llm_client=fake)
    await db_session.refresh(mv)
    assert mv.split == "shared"


async def test_edit_paid_by_alone_preserves_owner(db_session):
    """Cambiar solo el pagador no cambia de quién es el gasto: el split relativo
    se da vuelta para conservar al dueño."""
    u1, u2 = await _setup(db_session)
    mv = _mv(u1, "paseo", "28", date(2026, 8, 6))
    mv.split = "other_only"  # pagó bruno, es de katia
    db_session.add(mv)
    await db_session.commit()
    fake = FakeLLM(_payload(ref_last=True, new_paid_by="katia"))
    await dispatch(db_session, "549111", "text", "lo pagó katia", None, TODAY, llm_client=fake)
    await db_session.refresh(mv)
    assert mv.paid_by == u2.id
    assert mv.split == "payer_only"  # sigue siendo de katia


async def test_ref_text_wins_over_ref_last(db_session):
    """'el taxi era compartido' con ref_last=true del parser: el match por texto
    manda y edita el taxi, no el último cargado."""
    u1, _ = await _setup(db_session)
    taxi = _mv(u1, "taxi", "12", date(2026, 8, 6))
    taxi.split = "payer_only"
    db_session.add_all([taxi, _mv(u1, "helado", "5", date(2026, 8, 6))])
    await db_session.commit()
    fake = FakeLLM(_payload(ref_last=True, ref_text="taxi", new_only_user="shared"))
    reply = await dispatch(db_session, "549111", "text", "el taxi era compartido",
                           None, TODAY, llm_client=fake)
    await db_session.refresh(taxi)
    assert taxi.split == "shared"
    assert "Editado" in (reply.text or "")


async def test_edit_batch_total_rescales_siblings(db_session):
    """'el total era 480' sobre cuotas: redistribuye el batch en proporción; la
    última fila absorbe el redondeo."""
    u1, _ = await _setup(db_session)
    a = _mv(u1, "hostel (1/2)", "129", date(2026, 8, 6))
    b = _mv(u1, "hostel (2/2)", "301", date(2026, 8, 6))
    for m in (a, b):
        m.batch_key = "abc123"
    b.payment_date = date(2026, 9, 3)
    b.status = "pending"
    db_session.add_all([a, b])
    await db_session.commit()
    fake = FakeLLM(_payload(ref_text="hostel", ref_last=True,
                            new_amount="480", new_amount_is_total=True))
    reply = await dispatch(db_session, "549111", "text", "no, el total era 480",
                           None, TODAY, llm_client=fake)
    await db_session.refresh(a)
    await db_session.refresh(b)
    assert a.amount == Decimal("144.00")
    assert b.amount == Decimal("336.00")
    assert a.amount + b.amount == Decimal("480.00")
    assert b.status == "pending"  # la cuota futura sigue pendiente
    assert "Total" in (reply.text or "")


async def test_edit_amount_without_total_flag_edits_single(db_session):
    u1, _ = await _setup(db_session)
    a = _mv(u1, "hostel (1/2)", "129", date(2026, 8, 6))
    b = _mv(u1, "hostel (2/2)", "301", date(2026, 8, 6))
    for m in (a, b):
        m.batch_key = "abc123"
    db_session.add_all([a, b])
    await db_session.commit()
    fake = FakeLLM(_payload(ref_last=True, new_amount="310"))
    await dispatch(db_session, "549111", "text", "la segunda cuota fue 310",
                   None, TODAY, llm_client=fake)
    await db_session.refresh(a)
    await db_session.refresh(b)
    assert a.amount == Decimal("129")
    assert b.amount == Decimal("310")


async def test_noop_edit_on_last_retries_with_message_text(db_session):
    """Parser flaky: 'el taxi era compartido' llega como ref_last sin ref_text y
    el último (helado) ya es shared. La red usa el texto del mensaje para
    encontrar el taxi y editarlo."""
    u1, _ = await _setup(db_session)
    taxi = _mv(u1, "taxi", "12", date(2026, 8, 6))
    taxi.split = "payer_only"
    db_session.add_all([taxi, _mv(u1, "helado", "5", date(2026, 8, 6))])
    await db_session.commit()
    fake = FakeLLM(_payload(ref_last=True, ref_text=None, new_only_user="shared"))
    reply = await dispatch(db_session, "549111", "text", "el taxi en realidad era compartido",
                           None, TODAY, llm_client=fake)
    await db_session.refresh(taxi)
    assert taxi.split == "shared"
    assert "Editado" in (reply.text or "")


async def test_noop_edit_without_named_movement_stays_noop(db_session):
    """'contalo solo para katia' sobre un último que ya estaba así: el texto no
    nombra otro movimiento → 'Nada que cambiar' legítimo."""
    u1, u2 = await _setup(db_session)
    tren = _mv(u2, "tren", "39", date(2026, 8, 6))
    tren.paid_by = u2.id
    tren.split = "payer_only"
    db_session.add(tren)
    await db_session.commit()
    fake = FakeLLM(_payload(ref_last=True, new_only_user="katia"))
    reply = await dispatch(db_session, "549222", "text", "no, contalo solo para katia",
                           None, TODAY, llm_client=fake)
    assert "Nada que cambiar" in (reply.text or "")


async def test_ref_date_is_hint_not_hard_filter(db_session):
    """'borrá el museo' con una ref_date mal adivinada por el parser: la fecha
    es una pista — si ese día no hay match, se busca sin fecha."""
    u1, _ = await _setup(db_session)
    db_session.add(_mv(u1, "museo", "20", date(2026, 8, 5)))
    await db_session.commit()
    fake = FakeLLM(_payload(intent="delete", ref_text="museo", ref_date="2026-08-20"))
    reply = await dispatch(db_session, "549111", "text", "borrá el museo", None, TODAY, llm_client=fake)
    assert reply.buttons and reply.buttons[0][0].startswith("del_confirm:")
    assert "Museo" in (reply.text or "")


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


async def test_edit_batch_total_keeps_cashback_net(db_session):
    """El recálculo del batch parte del NETO (invariante 10). Las cuotas heredan
    el cashback pct del gasto, así que esta combinación es real: repartir el
    bruto acá dejaba de descontarlo y el saldo quedaba inflado para siempre."""
    u1, _ = await _setup(db_session)
    a = _mv(u1, "hostel (1/2)", "100", date(2026, 8, 6))
    b = _mv(u1, "hostel (2/2)", "300", date(2026, 8, 6))
    for m in (a, b):
        m.batch_key = "abc123"
        m.cashback_kind, m.cashback_value = "pct", Decimal("10")
        m.fx_source = "manual"  # tasa 1 fija: aísla el efecto del cashback
        m.amount_usd = m.amount * Decimal("0.9")
    db_session.add_all([a, b])
    await db_session.commit()
    fake = FakeLLM(_payload(ref_text="hostel", ref_last=True,
                            new_amount="480", new_amount_is_total=True))
    await dispatch(db_session, "549111", "text", "el total era 480",
                   None, TODAY, llm_client=fake)
    await db_session.refresh(a)
    await db_session.refresh(b)
    # Los brutos se reparten como siempre…
    assert a.amount + b.amount == Decimal("480.00")
    # …pero el USD sigue siendo el neto (10% menos), no el bruto.
    assert a.amount_usd == Decimal("108.00")
    assert b.amount_usd == Decimal("324.00")
    assert a.amount_usd + b.amount_usd == Decimal("432.00")
