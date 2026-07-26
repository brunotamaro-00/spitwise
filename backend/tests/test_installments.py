"""Pago en etapas: el server calcula los montos y el redondeo cierra exacto con
el total; las cuotas nacen como batch (batch_key compartido) con sufijo (i/n)."""
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.api.auth import hash_password
from app.bot.capture import expand_installments, handle_capture
from app.db.models import FxRate, Movement, Stop, User
from app.llm.parser import Installment, ParsedMessage

TODAY = date(2026, 7, 18)


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    async def parse(self, text, **kwargs):
        return self.payload


def _payload(**over):
    base = {
        "intent": "expense", "amount": None, "currency": None, "description": None,
        "category": None, "split": "shared", "paid_by": None, "date": None, "city": None,
        "confidence": 0.9, "candidates": [],
    }
    base.update(over)
    return base


async def _setup(db_session):
    u1 = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    u2 = User(username="katia", password_hash=hash_password("pw"), whatsapp_wa_id="549222")
    db_session.add_all([
        u1, u2,
        Stop(slug="interlaken", order=1, name="Interlaken", arrival_date=date(2026, 9, 1),
             departure_date=date(2026, 9, 6), currency_code="CHF", timezone="Europe/Zurich"),
    ])
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    await db_session.commit()
    return u1, u2


def _parsed(**over):
    base = dict(intent="expense", amount=Decimal("430"), currency="CHF",
                description="hostel interlaken", category_name="Alojamiento")
    base.update(over)
    return ParsedMessage(**base)


def test_expand_percent_and_rest_closes_exact():
    parsed = _parsed(installments=[
        Installment(percent=Decimal("30")),
        Installment(pay_date=date(2026, 9, 3)),  # "el resto"
    ])
    parts = expand_installments(parsed, TODAY)
    assert [p.amount for p in parts] == [Decimal("129.00"), Decimal("301.00")]
    assert parts[0].description == "hostel interlaken (1/2)"
    assert parts[1].description == "hostel interlaken (2/2)"
    assert parts[0].payment_date is None  # hoy
    assert parts[1].payment_date == date(2026, 9, 3)


def test_expand_ugly_rounding_closes_exact():
    parsed = _parsed(amount=Decimal("100"), installments=[
        Installment(percent=Decimal("33")),
        Installment(pay_date=date(2026, 9, 3)),
    ])
    parts = expand_installments(parsed, TODAY)
    assert [p.amount for p in parts] == [Decimal("33.00"), Decimal("67.00")]
    assert sum(p.amount for p in parts) == Decimal("100")


def test_expand_explicit_amount_stage():
    parsed = _parsed(installments=[
        Installment(amount=Decimal("100")),
        Installment(pay_date=date(2026, 9, 3)),
    ])
    parts = expand_installments(parsed, TODAY)
    assert [p.amount for p in parts] == [Decimal("100"), Decimal("330")]


def test_expand_orders_by_date():
    parsed = _parsed(installments=[
        Installment(percent=Decimal("70"), pay_date=date(2026, 9, 3)),
        Installment(percent=Decimal("30")),  # hoy => primero
    ])
    parts = expand_installments(parsed, TODAY)
    assert parts[0].payment_date is None and parts[0].amount == Decimal("129.00")
    assert parts[1].payment_date == date(2026, 9, 3) and parts[1].amount == Decimal("301.00")


def test_expand_dedupes_replicated_date():
    """Regresión: el LLM replicó la fecha del mensaje en TODAS las etapas
    ('12% de seña y el resto al ingresar el 6-oct' → ambas con 6-oct). Dos
    pagos el mismo día no son etapas: la fecha es solo de la última y la seña
    se paga hoy."""
    parsed = _parsed(amount=Decimal("300"), currency="PLN", description="hostel",
                     installments=[
                         Installment(percent=Decimal("12"), pay_date=date(2026, 10, 6)),
                         Installment(pay_date=date(2026, 10, 6)),  # "el resto"
                     ])
    parts = expand_installments(parsed, TODAY)
    assert [p.amount for p in parts] == [Decimal("36.00"), Decimal("264.00")]
    assert parts[0].payment_date is None  # la seña es de HOY => confirmed
    assert parts[1].payment_date == date(2026, 10, 6)


def test_expand_keeps_distinct_dates():
    # Fechas distintas legítimas: no se toca nada.
    parsed = _parsed(installments=[
        Installment(percent=Decimal("30"), pay_date=date(2026, 8, 1)),
        Installment(pay_date=date(2026, 9, 3)),
    ])
    parts = expand_installments(parsed, TODAY)
    assert parts[0].payment_date == date(2026, 8, 1)
    assert parts[1].payment_date == date(2026, 9, 3)


def test_expand_invalid_returns_none():
    # Sin total.
    assert expand_installments(_parsed(amount=None, installments=[
        Installment(percent=Decimal("30")), Installment()]), TODAY) is None
    # Dos "resto".
    assert expand_installments(_parsed(installments=[
        Installment(), Installment()]), TODAY) is None
    # Remanente <= 0 (las etapas se comen el total).
    assert expand_installments(_parsed(installments=[
        Installment(percent=Decimal("100")), Installment()]), TODAY) is None
    # Una sola etapa.
    assert expand_installments(_parsed(installments=[
        Installment(percent=Decimal("30"))]), TODAY) is None


def test_expand_mixed_currency_explicit_amounts():
    """'34 usd hoy, el resto 134 gbp al ingresar': montos explícitos con moneda
    propia por etapa — sin total único ni aritmética, cada parte va tal cual."""
    parsed = _parsed(amount=Decimal("34"), currency="USD", description="hostel fw",
                     installments=[
                         Installment(amount=Decimal("34"), currency="USD"),
                         Installment(amount=Decimal("134"), currency="GBP",
                                     pay_date=date(2026, 8, 18)),
                     ])
    parts = expand_installments(parsed, TODAY)
    assert [(p.amount, p.currency) for p in parts] == [
        (Decimal("34"), "USD"), (Decimal("134"), "GBP"),
    ]
    assert parts[0].payment_date is None
    assert parts[1].payment_date == date(2026, 8, 18)
    assert parts[0].description == "hostel fw (1/2)"


def test_expand_direct_mode_ignores_wrong_total():
    # Todos los montos explícitos: no dependemos del total del LLM.
    parsed = _parsed(amount=Decimal("34"), installments=[
        Installment(amount=Decimal("30")),
        Installment(amount=Decimal("400"), pay_date=date(2026, 9, 3)),
    ])
    parts = expand_installments(parsed, TODAY)
    assert [p.amount for p in parts] == [Decimal("30"), Decimal("400")]


def test_expand_mixed_currency_with_percent_is_invalid():
    # percent contra un total en otra moneda no se puede calcular.
    parsed = _parsed(installments=[
        Installment(percent=Decimal("30"), currency="GBP"),
        Installment(pay_date=date(2026, 9, 3)),
    ])
    assert expand_installments(parsed, TODAY) is None


async def test_capture_batch_item_with_mixed_currency_installments(db_session):
    """El caso real: mensaje multi-gasto donde un ítem se paga en dos monedas
    (seña USD hoy + resto GBP al ingresar) y otro ítem es simple."""
    u1, _ = await _setup(db_session)
    db_session.add(FxRate(currency="GBP", rate_date=TODAY, rate_to_usd=Decimal("1.30")))
    await db_session.commit()
    item_fw = _payload(
        amount="34", currency="USD", description="hostel fort william",
        category="Alojamiento", kind="expense",
        installments=[
            {"percent": None, "amount": "34", "date": None, "currency": "USD"},
            {"percent": None, "amount": "134", "date": "2026-08-18", "currency": "GBP"},
        ],
    )
    item_simple = _payload(
        amount="403", currency="EUR", description="hostel clinkmama",
        category="Alojamiento", kind="expense", date="2026-08-25", installments=[],
    )
    fake = FakeLLM(_payload(
        amount="34", currency="USD", description="hostel fort william",
        category="Alojamiento", expenses=[item_fw, item_simple],
    ))
    db_session.add(FxRate(currency="EUR", rate_date=TODAY, rate_to_usd=Decimal("1.10")))
    await db_session.commit()
    await handle_capture(
        db_session, u1, "549111",
        "34 usd hostel fort william hoy, el resto (134 gbp) al ingresar el 18. "
        "hostel clinkmama 403 euros el 25 de agosto",
        TODAY, llm_client=fake,
    )
    mvs = (await db_session.execute(select(Movement).order_by(Movement.id))).scalars().all()
    assert len(mvs) == 3
    fw1, fw2, clink = mvs
    assert (fw1.amount, fw1.currency, fw1.status) == (Decimal("34"), "USD", "confirmed")
    assert (fw2.amount, fw2.currency, fw2.status) == (Decimal("134"), "GBP", "pending")
    assert fw2.payment_date == date(2026, 8, 18)
    assert fw2.amount_usd == Decimal("174.20")  # 134 × 1.30 (TC proxy de hoy)
    assert "(1/2)" in fw1.description and "(2/2)" in fw2.description
    assert (clink.amount, clink.currency, clink.status) == (Decimal("403"), "EUR", "pending")
    # Todos hermanos del mismo mensaje: un solo batch_key.
    assert fw1.batch_key == fw2.batch_key == clink.batch_key


async def test_batch_duplicate_descriptions_get_city_suffix(db_session):
    """Dos hostels con la misma descripción genérica ('Hostel') en el mismo
    mensaje: recuperan su ciudad para poder editarlos/borrarlos por texto."""
    u1, _ = await _setup(db_session)
    db_session.add(FxRate(currency="CHF", rate_date=TODAY, rate_to_usd=Decimal("1.20")))
    await db_session.commit()
    fake = FakeLLM(_payload(
        amount="30", currency="CHF", description="Hostel", category="Alojamiento",
        expenses=[
            _payload(amount="30", currency="CHF", description="Hostel",
                     city="Interlaken", category="Alojamiento", kind="expense",
                     installments=[]),
            _payload(amount="50", currency="CHF", description="Hostel",
                     city="Interlaken", category="Alojamiento", kind="expense",
                     installments=[]),
        ],
    ))
    await handle_capture(db_session, u1, "549111", "hostel 30 y hostel 50", TODAY,
                         llm_client=fake)
    descs = (await db_session.execute(
        select(Movement.description).order_by(Movement.id)
    )).scalars().all()
    assert all("Interlaken" in d for d in descs)


async def test_capture_installments_end_to_end(db_session):
    u1, _ = await _setup(db_session)
    db_session.add(FxRate(currency="CHF", rate_date=TODAY, rate_to_usd=Decimal("1.20")))
    await db_session.commit()
    fake = FakeLLM(_payload(
        amount="430", currency="CHF", description="hostel interlaken",
        category="Alojamiento",
        installments=[
            {"percent": "30", "amount": None, "date": None},
            {"percent": None, "amount": None, "date": "2026-09-03"},
        ],
    ))
    reply = await handle_capture(
        db_session, u1, "549111",
        "430 CHF en Hostel Interlaken. 30% hoy y el resto al ingresar el 3 de septiembre",
        TODAY, llm_client=fake,
    )
    mvs = (await db_session.execute(select(Movement).order_by(Movement.id))).scalars().all()
    assert len(mvs) == 2
    first, second = mvs
    assert first.amount == Decimal("129.00") and first.status == "confirmed"
    assert second.amount == Decimal("301.00") and second.status == "pending"
    assert second.payment_date == date(2026, 9, 3)
    assert first.batch_key == second.batch_key and first.batch_key
    assert "(1/2)" in first.description and "(2/2)" in second.description
    assert "(1/2)" in reply.text and "(2/2)" in reply.text


async def test_installments_share_one_place_and_split(db_session):
    """Las cuotas de UN gasto van todas a la misma parada. Cada etapa resolvía
    su lugar por su propia fecha, así que 'hoy y el 3-sep' mandaba las mitades a
    ciudades distintas — y con owner_split de por medio, a splits distintos."""
    u1, _ = await _setup(db_session)
    db_session.add(FxRate(currency="CHF", rate_date=TODAY, rate_to_usd=Decimal("1.20")))
    await db_session.commit()
    fake = FakeLLM(_payload(
        amount="430", currency="CHF", description="hostel interlaken",
        category="Alojamiento",
        installments=[
            {"percent": "30", "amount": None, "date": None},
            {"percent": None, "amount": None, "date": "2026-09-03"},
        ],
    ))
    await handle_capture(
        db_session, u1, "549111",
        "430 CHF en Hostel Interlaken. 30% hoy y el resto al ingresar el 3 de septiembre",
        TODAY, llm_client=fake,
    )
    mvs = (await db_session.execute(select(Movement).order_by(Movement.id))).scalars().all()
    # La referencia de lugar es el check-in (última etapa), no hoy: las dos van
    # a Interlaken aunque la primera se pague en julio.
    assert [m.stop_slug for m in mvs] == ["interlaken", "interlaken"]
    assert {m.split for m in mvs} == {"shared"}
    # Pero cada una conserva SU fecha de pago y su status.
    assert [m.status for m in mvs] == ["confirmed", "pending"]


def test_expand_stamps_place_date_on_every_part():
    parsed = _parsed(installments=[
        Installment(percent=Decimal("30"), amount=None, pay_date=None, currency=None),
        Installment(percent=None, amount=None, pay_date=date(2026, 9, 3), currency=None),
    ])
    parts = expand_installments(parsed, TODAY)
    assert [p.place_date for p in parts] == [date(2026, 9, 3), date(2026, 9, 3)]


async def test_batch_cap_applies_to_expenses_not_stages(db_session):
    """El tope de _BATCH_MAX se aplicaba DESPUÉS de expandir cuotas: 3 gastos de
    4 etapas daban 12 ítems, se guardaban 10 y el último gasto quedaba partido,
    con el total sin cerrar y sin ningún aviso."""
    from app.bot.capture import _BATCH_MAX, handle_capture

    u1, _ = await _setup(db_session)
    db_session.add(FxRate(currency="CHF", rate_date=TODAY, rate_to_usd=Decimal("1.20")))
    await db_session.commit()

    stages = [{"percent": "25", "amount": None, "date": None},
              {"percent": None, "amount": None, "date": "2026-09-03"}]
    expenses = [
        {"kind": "expense", "amount": "100", "currency": "CHF",
         "description": f"gasto {i}", "category": "Alojamiento", "installments": stages}
        for i in range(_BATCH_MAX + 2)
    ]
    fake = FakeLLM(_payload(expenses=expenses))
    await handle_capture(db_session, u1, "549111", "muchos gastos en cuotas",
                         TODAY, llm_client=fake)

    mvs = (await db_session.execute(select(Movement))).scalars().all()
    # Se cortan GASTOS enteros: 10 gastos × 2 etapas, ninguno partido al medio.
    assert len(mvs) == _BATCH_MAX * 2
    by_desc: dict[str, int] = {}
    for m in mvs:
        by_desc[m.description.rsplit(" (", 1)[0]] = by_desc.get(m.description.rsplit(" (", 1)[0], 0) + 1
    assert set(by_desc.values()) == {2}, by_desc
