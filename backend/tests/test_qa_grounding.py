"""Grounding y completitud del Q&A financiero.

El snapshot es un atajo (los últimos movimientos, ya verificados), no el
historial: contestar totales o negar gastos mirándolo produce datos falsos con
cara de verificados. Y varias preguntas normales del viaje —qué está pendiente,
qué se paga en septiembre, cuánto salió neto— no se podían expresar con las
tools y dependían de que el modelo improvisara.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.api.auth import hash_password
from app.bot import copy
from app.bot.qa import _context_snapshot, handle_question
from app.db.models import Movement, Stop, User
from app.llm.chat import ChatResult
from app.qa.tools import aggregate_expenses, get_itinerary, list_movements

TODAY = date(2026, 8, 20)


class Chat:
    """Responde un texto fijo declarando qué tools llamó (sin llamarlas)."""

    def __init__(self, text, tool_calls=(), tool_errors=()):
        self.result = ChatResult(text=text, outcome="ok", tool_calls=list(tool_calls),
                                 tool_errors=list(tool_errors))

    async def run(self, **kw):
        self.snapshot = kw["user_text"]
        return self.result


async def _setup(db_session):
    u1 = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    u2 = User(username="katia", password_hash=hash_password("pw"), whatsapp_wa_id="549222")
    db_session.add_all([u1, u2])
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    await db_session.commit()
    return u1, u2


def _mv(u, **over):
    base = dict(type="expense", amount=Decimal("10"), currency="EUR",
                amount_usd=Decimal("11"), fx_rate=Decimal("1.1"), fx_source="cache",
                paid_by=u.id, split="shared", created_by=u.id, status="confirmed",
                description="Gasto")
    base.update(over)
    return Movement(**base)


# --- snapshot -----------------------------------------------------------------

async def test_snapshot_orders_by_created_at_not_by_id(db_session):
    """Un gasto cargado con fecha vieja tiene id alto: ordenar por id mostraba
    'el último' que no era el último para el usuario."""
    u1, _ = await _setup(db_session)
    viejo = _mv(u1, description="Viejo",
                created_at=datetime(2026, 8, 1, 12, tzinfo=timezone.utc).replace(tzinfo=None))
    nuevo = _mv(u1, description="Nuevo",
                created_at=datetime(2026, 8, 19, 12, tzinfo=timezone.utc).replace(tzinfo=None))
    db_session.add(nuevo)      # id menor, fecha más nueva
    await db_session.flush()
    db_session.add(viejo)      # id mayor, fecha más vieja
    await db_session.commit()
    snap = await _context_snapshot(db_session, [u1], TODAY, None)
    assert snap.index("Nuevo") < snap.index("Viejo")


async def test_snapshot_declares_truncation(db_session):
    u1, _ = await _setup(db_session)
    for i in range(12):
        db_session.add(_mv(u1, description=f"Gasto {i}",
                           created_at=datetime(2026, 8, 1 + i, 12).replace(tzinfo=None)))
    await db_session.commit()
    snap = await _context_snapshot(db_session, [u1], TODAY, None)
    assert "4 movimientos más NO listados" in snap and "12 en total" in snap


async def test_snapshot_shows_net_amount_with_cashback(db_session):
    u1, _ = await _setup(db_session)
    db_session.add(_mv(u1, description="Super", amount=Decimal("100"),
                       amount_usd=Decimal("99"), cashback_kind="pct",
                       cashback_value=Decimal("10")))
    await db_session.commit()
    snap = await _context_snapshot(db_session, [u1], TODAY, None)
    assert "EUR 90" in snap and "bruto 100" in snap


# --- filtros nuevos -----------------------------------------------------------

async def test_status_filter_isolates_pending_and_awaiting(db_session):
    u1, u2 = await _setup(db_session)
    db_session.add_all([
        _mv(u1, description="Confirmado"),
        _mv(u1, description="Futuro", status="pending",
            payment_date=TODAY + timedelta(days=10)),
        _mv(u1, description="Vencido", status="awaiting",
            payment_date=TODAY - timedelta(days=1)),
    ])
    await db_session.commit()
    out = await aggregate_expenses(db_session, [u1, u2], u1, attribution="total",
                                   status=["pending", "awaiting"])
    assert out["rows"][0]["count"] == 2
    solo_conf = await list_movements(db_session, [u1, u2], status=["confirmed"])
    assert [r["description"] for r in solo_conf["rows"]] == ["Confirmado"]


async def test_invalid_status_is_a_value_error(db_session):
    u1, u2 = await _setup(db_session)
    try:
        await aggregate_expenses(db_session, [u1, u2], u1, status=["pagado"])
    except ValueError as exc:
        assert "pagado" in str(exc) and "confirmed" in str(exc)
    else:
        raise AssertionError("un status inventado tiene que ser ValueError")


async def test_payment_date_axis_is_opt_in(db_session):
    """El eje de listas sigue siendo la carga; 'qué se paga en septiembre' no."""
    u1, u2 = await _setup(db_session)
    db_session.add(_mv(u1, description="Hostel", status="pending",
                       payment_date=date(2026, 9, 15),
                       created_at=datetime(2026, 8, 10, 12).replace(tzinfo=None)))
    await db_session.commit()
    por_carga = await aggregate_expenses(db_session, [u1, u2], u1, attribution="total",
                                         date_from="2026-09-01", date_to="2026-09-30")
    por_pago = await aggregate_expenses(db_session, [u1, u2], u1, attribution="total",
                                        date_from="2026-09-01", date_to="2026-09-30",
                                        date_field="payment")
    assert por_carga["rows"] == []
    assert por_pago["rows"][0]["total_usd"] == "11.00"


async def test_list_movements_exposes_net_and_cashback(db_session):
    u1, u2 = await _setup(db_session)
    db_session.add(_mv(u1, amount=Decimal("100"), amount_usd=Decimal("99"),
                       cashback_kind="pct", cashback_value=Decimal("10")))
    await db_session.commit()
    row = (await list_movements(db_session, [u1, u2]))["rows"][0]
    assert row["amount"] == "90.00" and row["amount_gross"] == "100.00"
    assert row["cashback"].startswith("10") and row["cashback"].endswith("%")


async def test_itinerary_excludes_archived_stops(db_session):
    """Una parada archivada sobrevive por sus gastos, pero sus días no son del
    viaje: contarlos inflaba el promedio por día."""
    await _setup(db_session)
    db_session.add_all([
        Stop(slug="roma", order=1, name="Roma", arrival_date=date(2026, 8, 1),
             departure_date=date(2026, 8, 6)),
        Stop(slug="vieja", order=2, name="Vieja", arrival_date=date(2026, 8, 6),
             departure_date=date(2026, 8, 20), is_archived=True),
    ])
    await db_session.commit()
    out = await get_itinerary(db_session)
    assert [s["slug"] for s in out["stops"]] == ["roma"]


# --- falso cero ---------------------------------------------------------------

async def test_zero_claim_without_tools_is_blocked(db_session):
    u1, _ = await _setup(db_session)
    db_session.add(_mv(u1, description="Cena Roma", city_name="Roma"))
    await db_session.commit()
    reply = await handle_question(db_session, u1, "549111", "cuánto gastamos en Roma?",
                                  TODAY, chat_client=Chat("No hay gastos en Roma."))
    assert "de memoria" in reply.text and "filtro concreto" in reply.text


async def test_zero_claim_with_aggregate_is_trusted(db_session):
    u1, _ = await _setup(db_session)
    db_session.add(_mv(u1, description="Cena Roma", city_name="Roma"))
    await db_session.commit()
    reply = await handle_question(
        db_session, u1, "549111", "cuánto gastamos en Praga?", TODAY,
        chat_client=Chat("No hay gastos en Praga.", tool_calls=["aggregate_expenses"]),
    )
    assert reply.text == "No hay gastos en Praga."


async def test_real_zero_with_empty_db_is_allowed(db_session):
    u1, _ = await _setup(db_session)
    reply = await handle_question(db_session, u1, "549111", "cuánto gastamos?", TODAY,
                                  chat_client=Chat("Todavía no hay gastos cargados."))
    assert "Todavía no hay gastos" in reply.text


async def test_no_pending_claim_is_not_a_false_zero(db_session):
    """El snapshot SÍ verifica pendientes y saldo: eso se puede afirmar sin tools."""
    u1, _ = await _setup(db_session)
    db_session.add(_mv(u1, description="Cena"))
    await db_session.commit()
    reply = await handle_question(db_session, u1, "549111", "hay algo pendiente?", TODAY,
                                  chat_client=Chat("No hay gastos pendientes 👌"))
    assert "pendientes" in reply.text


async def test_evidence_tools_are_only_the_counting_ones(db_session):
    """Con el presupuesto fuera del bot, la única evidencia que sostiene un cero
    es haber sumado: si una tool que no cuenta habilitara la afirmación, un
    "USD 0" sin verificar se colaría."""
    from app.bot.qa import _EVIDENCE_TOOLS

    assert _EVIDENCE_TOOLS == {"aggregate_expenses", "list_movements"}

    u1, _ = await _setup(db_session)
    db_session.add(_mv(u1, description="Cena Roma", city_name="Roma"))
    await db_session.commit()
    reply = await handle_question(
        db_session, u1, "549111", "vamos bien en Viena?", TODAY,
        chat_client=Chat("En Viena todavía no hay gastos: USD 0.",
                         tool_calls=["get_itinerary"]),
    )
    assert reply.text == copy.QA_UNVERIFIED_ZERO


async def test_failed_tool_is_not_evidence(db_session):
    """`tool_calls` incluye las tools que explotaron. Un `aggregate_expenses`
    con error no contó nada: no puede habilitar un "no hay gastos"."""
    u1, _ = await _setup(db_session)
    db_session.add(_mv(u1, description="Cena Roma", city_name="Roma"))
    await db_session.commit()
    reply = await handle_question(
        db_session, u1, "549111", "cuánto gastamos en Roma?", TODAY,
        chat_client=Chat("No hay gastos cargados para eso.",
                         tool_calls=["aggregate_expenses"],
                         tool_errors=["aggregate_expenses"]),
    )
    assert reply.text == copy.QA_UNVERIFIED_ZERO

    # La misma tool llamada dos veces, fallando una: la que sí trajo datos vale.
    reply = await handle_question(
        db_session, u1, "549111", "cuánto gastamos en Roma?", TODAY,
        chat_client=Chat("No hay gastos cargados para eso.",
                         tool_calls=["aggregate_expenses", "aggregate_expenses"],
                         tool_errors=["aggregate_expenses"]),
    )
    assert reply.text == "No hay gastos cargados para eso."


def test_successful_tools_subtracts_errors_as_a_multiset():
    from app.llm.chat import ChatResult

    r = ChatResult(tool_calls=["a", "b", "a", "c"], tool_errors=["a", "c"])
    assert r.successful_tools == ["b", "a"]
    assert ChatResult(tool_calls=["a"], tool_errors=["a"]).successful_tools == []
    assert ChatResult(tool_calls=["a", "b"]).successful_tools == ["a", "b"]
