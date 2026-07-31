from datetime import date, datetime, time
from decimal import Decimal

from app.api.auth import hash_password
from app.db.models import Movement, Stop, User
import pytest

from app.qa.tools import (
    aggregate_expenses,
    budget_status,
    get_balance,
    get_itinerary,
    list_movements,
)


def _mv(payer, creator, desc, amount, d, *, split="shared", city=None, slug=None,
        cat_id=None, typ="expense", currency="USD"):
    # created_at controla el eje temporal (fecha de carga); mediodía UTC para que
    # el día no cambie al convertir a la tz del viaje.
    return Movement(type=typ, amount=Decimal(amount), currency=currency,
                    amount_usd=Decimal(amount), fx_rate=Decimal("1"), fx_source="frankfurter",
                    paid_by=payer.id, split=split, description=desc, category_id=cat_id,
                    created_at=datetime.combine(d, time(12)), city_name=city, stop_slug=slug,
                    created_by=creator.id)


async def _setup(db_session):
    u1 = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    u2 = User(username="katia", password_hash=hash_password("pw"), whatsapp_wa_id="549222")
    db_session.add_all([
        u1, u2,
        Stop(slug="edimburgo", order=1, name="Edimburgo", country="Escocia",
             arrival_date=date(2026, 8, 1), departure_date=date(2026, 8, 4),
             currency_code="GBP", timezone="Europe/London"),
        Stop(slug="glasgow", order=2, name="Glasgow", country="Escocia",
             arrival_date=date(2026, 8, 4), departure_date=date(2026, 8, 6),
             currency_code="GBP", timezone="Europe/London"),
        Stop(slug="roma", order=3, name="Roma", country="Italia",
             arrival_date=date(2026, 9, 20), departure_date=date(2026, 9, 26),
             currency_code="EUR", timezone="Europe/Rome"),
    ])
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    await db_session.commit()
    from sqlalchemy import select
    from app.db.models import Category
    cats = {c.name: c.id for c in (await db_session.execute(select(Category))).scalars().all()}
    db_session.add_all([
        _mv(u1, u1, "cena", "100", date(2026, 8, 2), city="Edimburgo", slug="edimburgo",
            cat_id=cats["Comida"]),
        _mv(u1, u1, "taxi", "40", date(2026, 8, 5), split="payer_only", city="Glasgow",
            slug="glasgow", cat_id=cats["Transporte"]),
        _mv(u1, u1, "museo", "60", date(2026, 9, 21), split="other_only", city="Roma",
            slug="roma", cat_id=cats["Actividades"]),
        _mv(u2, u2, "saldo", "30", date(2026, 9, 22), typ="settlement"),
    ])
    await db_session.commit()
    return u1, u2


async def test_aggregate_default_is_asker_share(db_session):
    u1, u2 = await _setup(db_session)
    got = await aggregate_expenses(db_session, [u1, u2], u1)
    # bruno: 50 (mitad cena) + 40 (taxi payer_only) + 0 (museo other_only) = 90
    assert got["rows"] == [{"key": "total", "total_usd": "90.00", "count": 2}]
    assert got["person"] == "bruno"
    assert got["attribution"] == "share"


async def test_aggregate_paid_attribution(db_session):
    u1, u2 = await _setup(db_session)
    got = await aggregate_expenses(db_session, [u1, u2], u1, person="katia", attribution="paid")
    assert got["rows"] == []  # katia no pagó ningún gasto de bolsillo


async def test_aggregate_total_by_city(db_session):
    u1, u2 = await _setup(db_session)
    got = await aggregate_expenses(db_session, [u1, u2], u1, attribution="total", group_by="city")
    assert got["rows"] == [
        {"key": "Edimburgo", "total_usd": "100.00", "count": 1},
        {"key": "Roma", "total_usd": "60.00", "count": 1},
        {"key": "Glasgow", "total_usd": "40.00", "count": 1},
    ]


async def test_aggregate_country_filter(db_session):
    u1, u2 = await _setup(db_session)
    got = await aggregate_expenses(db_session, [u1, u2], u1, attribution="total",
                                   countries=["escocia"])
    assert got["rows"] == [{"key": "total", "total_usd": "140.00", "count": 2}]


async def test_aggregate_group_by_person(db_session):
    u1, u2 = await _setup(db_session)
    got = await aggregate_expenses(db_session, [u1, u2], u1, group_by="person")
    by_key = {r["key"]: r["total_usd"] for r in got["rows"]}
    # katia: 50 (mitad cena) + 60 (museo other_only, no pagó ella) = 110
    assert by_key == {"katia": "110.00", "bruno": "90.00"}


async def test_aggregate_date_filter_and_group_day(db_session):
    u1, u2 = await _setup(db_session)
    got = await aggregate_expenses(db_session, [u1, u2], u1, attribution="total",
                                   date_from="2026-08-01", date_to="2026-08-31", group_by="day")
    assert got["rows"] == [
        {"key": "2026-08-02", "total_usd": "100.00", "count": 1},
        {"key": "2026-08-05", "total_usd": "40.00", "count": 1},
    ]


async def test_aggregate_invalid_person_raises(db_session):
    u1, u2 = await _setup(db_session)
    try:
        await aggregate_expenses(db_session, [u1, u2], u1, person="carlos")
        raise AssertionError("debería levantar ValueError")
    except ValueError as e:
        assert "carlos" in str(e)


async def test_list_movements_detail_and_limit(db_session):
    u1, u2 = await _setup(db_session)
    got = await list_movements(db_session, [u1, u2], limit=2)
    assert got["total_matches"] == 3  # el settlement no cuenta
    assert got["truncated"] is True
    assert [r["description"] for r in got["rows"]] == ["museo", "taxi"]  # recientes primero
    assert got["rows"][0]["country"] == "Italia"
    assert got["rows"][0]["paid_by"] == "bruno"


async def test_get_balance(db_session):
    u1, u2 = await _setup(db_session)
    got = await get_balance(db_session, [u1, u2])
    # katia debe: 50 (cena) + 60 (museo other_only) - 30 (settlement que pagó) = 80
    assert got == {
        "debtor": "katia", "creditor": "bruno", "amount_usd": "80.00",
        "pending_excluded_count": 0, "pending_excluded_usd": "0.00",
        "note": got["note"],
    }
    assert "pending" in got["note"]


async def test_get_itinerary_days(db_session):
    u1, u2 = await _setup(db_session)
    got = await get_itinerary(db_session)
    rows = {s["slug"]: s for s in got["stops"]}
    assert rows["edimburgo"]["days"] == 3
    assert rows["glasgow"]["days"] == 2
    assert rows["edimburgo"]["country"] == "Escocia"
    # días de Escocia (para el promedio) = 5
    assert sum(s["days"] for s in got["stops"] if s["country"] == "Escocia") == 5


async def _with_budgets(db_session, targets: dict[str, str]):
    from app.db.models import StopBudget

    db_session.add_all([
        StopBudget(stop_slug=slug, daily_usd=Decimal(v)) for slug, v in targets.items()
    ])
    await db_session.commit()


async def test_budget_status_compares_against_target(db_session):
    """Edimburgo: 3 noches, vivir de bruno = 50 (mitad de la cena) => 16,67/día
    contra un target de 20 => -16,7%."""
    u1, u2 = await _setup(db_session)
    await _with_budgets(db_session, {"edimburgo": "20", "glasgow": "20"})

    got = await budget_status(db_session, u1, today=date(2026, 8, 10))
    rows = {c["slug"]: c for c in got["cities"]}
    assert rows["edimburgo"]["target_daily_usd"] == "20.00"
    assert rows["edimburgo"]["living_usd"] == "50.00"
    assert rows["edimburgo"]["living_per_day_usd"] == "16.67"
    assert rows["edimburgo"]["delta_pct"] == -16.7
    # El alojamiento no es vivir y los targets no se inventan.
    assert "roma" not in rows  # futura: fuera del default
    assert got["app_link"] is None or got["app_link"].endswith("/presupuesto")


async def test_budget_status_current_city_remaining_daily(db_session):
    u1, u2 = await _setup(db_session)
    await _with_budgets(db_session, {"edimburgo": "30"})

    got = await budget_status(db_session, u1, today=date(2026, 8, 2))  # día 2 de 3
    cur = got["current_city"]
    assert cur["city"] == "Edimburgo"
    assert (cur["elapsed_nights"], cur["nights"]) == (2, 3)
    assert cur["remaining_days"] == 2          # 3 - 2 + 1: hoy cuenta
    assert cur["remaining_daily_usd"] == "20.00"  # (30*3 - 50) / 2


async def test_budget_status_without_target_says_so(db_session):
    """Una parada sin target no se compara ni se estima: baja la cobertura."""
    u1, u2 = await _setup(db_session)
    await _with_budgets(db_session, {"edimburgo": "20"})

    got = await budget_status(db_session, u1, today=date(2026, 8, 10))
    glasgow = next(c for c in got["cities"] if c["slug"] == "glasgow")
    assert glasgow["target_daily_usd"] is None
    assert glasgow["delta_pct"] is None
    assert "glasgow" in got["trip"]["uncovered_slugs"]
    assert got["trip"]["coverage_pct"] is not None and got["trip"]["coverage_pct"] < 100
    assert "cargado a mano" in got["note"].casefold() or "A MANO" in got["note"]


async def test_budget_status_unknown_city_raises(db_session):
    u1, u2 = await _setup(db_session)
    await _with_budgets(db_session, {"edimburgo": "20"})

    with pytest.raises(ValueError) as exc:
        await budget_status(db_session, u1, today=date(2026, 8, 10), cities=["Narnia"])
    assert "edimburgo" in str(exc.value)  # le devuelve los slugs válidos al modelo


async def test_budget_status_is_read_only(db_session):
    from sqlalchemy import func, select

    u1, u2 = await _setup(db_session)
    await _with_budgets(db_session, {"edimburgo": "20"})
    before = (await db_session.execute(select(func.count()).select_from(Movement))).scalar_one()

    await budget_status(db_session, u1, today=date(2026, 8, 10))

    after = (await db_session.execute(select(func.count()).select_from(Movement))).scalar_one()
    assert after == before
