"""GET/PUT/DELETE /budget: serialización, validación y coherencia con /pace."""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.api.auth import hash_password


def _freeze_today(monkeypatch, d: date):
    # El helper vive en dashboard.py (load_trip_pace), así que el patch sigue
    # apuntando ahí aunque el endpoint sea /budget.
    import app.api.dashboard as dash
    monkeypatch.setattr(dash, "today_in_tz", lambda tz, **kw: d)


async def _seed_and_auth(app_client):
    """Londres (3 noches, 5-8 ago) + París (3 noches, 29 ago-1 sep).

    Londres: alojamiento 90 + comida 30, ambos shared => bruno 45 + 15.
    Vivir de bruno en Londres = 15. General 60 sin ciudad => share 30.
    """
    from app.db.models import Category, Movement, Stop, User

    async with app_client._maker() as s:
        u1 = User(username="bruno", password_hash=hash_password("pw"))
        u2 = User(username="katia", password_hash=hash_password("pw"))
        s.add_all([u1, u2])
        await s.flush()
        cats = (await s.execute(select(Category))).scalars().all()
        lodging = next(c.id for c in cats if c.name == "Alojamiento")
        comida = next(c.id for c in cats if c.name == "Comida")
        s.add_all([
            Stop(slug="londres", order=1, name="Londres", country_flag="🇬🇧",
                 arrival_date=date(2026, 8, 5), departure_date=date(2026, 8, 8)),
            Stop(slug="paris", order=2, name="París", country_flag="🇫🇷",
                 arrival_date=date(2026, 8, 29), departure_date=date(2026, 9, 1)),
            Stop(slug="vieja", order=3, name="Vieja", is_archived=True,
                 arrival_date=date(2026, 7, 1), departure_date=date(2026, 7, 3)),
            Movement(type="expense", amount=Decimal("90"), currency="USD",
                     amount_usd=Decimal("90"), fx_rate=Decimal("1"), fx_source="frankfurter",
                     paid_by=u1.id, split="shared", category_id=lodging,
                     stop_slug="londres", city_name="Londres", created_by=u1.id),
            Movement(type="expense", amount=Decimal("30"), currency="USD",
                     amount_usd=Decimal("30"), fx_rate=Decimal("1"), fx_source="frankfurter",
                     paid_by=u2.id, split="shared", category_id=comida,
                     stop_slug="londres", city_name="Londres", created_by=u2.id),
            Movement(type="expense", amount=Decimal("60"), currency="USD",
                     amount_usd=Decimal("60"), fx_rate=Decimal("1"), fx_source="frankfurter",
                     paid_by=u1.id, split="shared", category_id=None,
                     stop_slug=None, city_name=None, created_by=u1.id),
        ])
        await s.commit()
    r = await app_client.post("/api/v1/auth/login", data={"username": "bruno", "password": "pw"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _city(j, slug):
    return next(c for c in j["cities"] if c["stop_slug"] == slug)


async def test_get_budget_serializes_money_as_string(app_client, monkeypatch):
    h = await _seed_and_auth(app_client)
    _freeze_today(monkeypatch, date(2026, 8, 6))  # día 2 de Londres
    await app_client.put("/api/v1/budget/londres", json={"daily_usd": "10"}, headers=h)

    j = (await app_client.get("/api/v1/budget", headers=h)).json()
    c = _city(j, "londres")
    assert c["living_usd"] == "15.00"          # str, 2 decimales
    assert c["target_daily_usd"] == "10.00"
    assert isinstance(c["delta_pct"], float)   # los % sí son float
    assert j["fixed"]["lodging_usd"] == "45.00"
    assert j["fixed"]["general_usd"] == "30.00"
    assert j["current"]["stop_slug"] == "londres"


async def test_current_matches_pace(app_client, monkeypatch):
    """El canario: si budget.py empieza a re-agregar por su cuenta, esto rompe."""
    h = await _seed_and_auth(app_client)
    _freeze_today(monkeypatch, date(2026, 8, 6))
    await app_client.put("/api/v1/budget/londres", json={"daily_usd": "10"}, headers=h)

    budget = (await app_client.get("/api/v1/budget", headers=h)).json()
    pace = (await app_client.get("/api/v1/dashboard/pace", headers=h)).json()
    londres = next(c for c in pace["cities"] if c["stop_slug"] == "londres")

    assert budget["current"]["living_usd"] == londres["other_usd"]
    assert _city(budget, "londres")["living_per_day_usd"] == londres["other_per_day_usd"]


async def test_remaining_daily_counts_today(app_client, monkeypatch):
    h = await _seed_and_auth(app_client)
    _freeze_today(monkeypatch, date(2026, 8, 6))  # día 2 de 3
    await app_client.put("/api/v1/budget/londres", json={"daily_usd": "20"}, headers=h)

    cur = (await app_client.get("/api/v1/budget", headers=h)).json()["current"]
    assert (cur["lived_nights"], cur["total_nights"]) == (2, 3)
    assert cur["remaining_days"] == 2                  # 3 - 2 + 1
    assert cur["budget_to_date_usd"] == "40.00"
    assert cur["remaining_budget_usd"] == "45.00"      # 60 - 15
    assert cur["remaining_daily_usd"] == "22.50"


async def test_pre_trip_shows_plan(app_client, monkeypatch):
    h = await _seed_and_auth(app_client)
    _freeze_today(monkeypatch, date(2026, 7, 1))
    await app_client.put("/api/v1/budget/londres", json={"daily_usd": "20"}, headers=h)
    await app_client.put("/api/v1/budget/paris", json={"daily_usd": "30"}, headers=h)

    j = (await app_client.get("/api/v1/budget", headers=h)).json()
    assert j["current"] is None
    assert j["plan"]["living_budget_usd"] == "150.00"   # 20*3 + 30*3
    assert j["plan"]["avg_target_daily_usd"] == "25.00"
    assert j["plan"]["coverage_pct"] == 100.0
    assert j["plan"]["next_stop"]["stop_slug"] == "londres"
    assert j["projection"]["projected_living_usd"] is None


async def test_partial_coverage_reports_uncovered(app_client, monkeypatch):
    h = await _seed_and_auth(app_client)
    _freeze_today(monkeypatch, date(2026, 8, 6))
    await app_client.put("/api/v1/budget/londres", json={"daily_usd": "20"}, headers=h)

    p = (await app_client.get("/api/v1/budget", headers=h)).json()["projection"]
    assert p["budget_nights"] == 6          # la archivada no cuenta
    assert p["covered_nights"] == 3
    assert p["uncovered_slugs"] == ["paris"]
    assert p["living_budget_usd"] == "60.00"  # sin extrapolar a París


async def test_put_creates_and_updates(app_client, monkeypatch):
    h = await _seed_and_auth(app_client)
    _freeze_today(monkeypatch, date(2026, 8, 6))

    r = await app_client.put("/api/v1/budget/londres",
                             json={"daily_usd": "20", "note": "hostel con cocina"}, headers=h)
    assert r.status_code == 200
    assert r.json()["daily_usd"] == "20.00"
    assert r.json()["note"] == "hostel con cocina"

    r2 = await app_client.put("/api/v1/budget/londres", json={"daily_usd": "35"}, headers=h)
    assert r2.status_code == 200
    assert r2.json()["daily_usd"] == "35.00"
    assert r2.json()["note"] is None  # el PUT reemplaza la fila entera

    j = (await app_client.get("/api/v1/budget", headers=h)).json()
    assert _city(j, "londres")["target_daily_usd"] == "35.00"


async def test_put_unknown_slug_is_422(app_client, monkeypatch):
    h = await _seed_and_auth(app_client)
    r = await app_client.put("/api/v1/budget/narnia", json={"daily_usd": "20"}, headers=h)
    assert r.status_code == 422
    assert "narnia" in r.json()["detail"]


async def test_put_archived_slug_is_422(app_client, monkeypatch):
    """Una parada archivada no es un target válido: ya no se viaja."""
    h = await _seed_and_auth(app_client)
    r = await app_client.put("/api/v1/budget/vieja", json={"daily_usd": "20"}, headers=h)
    assert r.status_code == 422


async def test_put_rejects_bad_amounts(app_client, monkeypatch):
    h = await _seed_and_auth(app_client)
    for bad in ("0", "-5", "10000"):
        r = await app_client.put("/api/v1/budget/londres", json={"daily_usd": bad}, headers=h)
        assert r.status_code == 422, bad


async def test_delete_drops_coverage(app_client, monkeypatch):
    h = await _seed_and_auth(app_client)
    _freeze_today(monkeypatch, date(2026, 8, 6))
    await app_client.put("/api/v1/budget/londres", json={"daily_usd": "20"}, headers=h)
    assert (await app_client.get("/api/v1/budget", headers=h)).json()["projection"]["covered_nights"] == 3

    r = await app_client.delete("/api/v1/budget/londres", headers=h)
    assert r.status_code == 204
    j = (await app_client.get("/api/v1/budget", headers=h)).json()
    assert j["projection"]["covered_nights"] == 0
    assert j["projection"]["living_budget_usd"] is None
    assert _city(j, "londres")["delta_pct"] is None


async def test_delete_unknown_is_404(app_client, monkeypatch):
    h = await _seed_and_auth(app_client)
    assert (await app_client.delete("/api/v1/budget/londres", headers=h)).status_code == 404


async def test_budget_requires_auth(app_client):
    await _seed_and_auth(app_client)
    assert (await app_client.get("/api/v1/budget")).status_code == 401
    assert (await app_client.put("/api/v1/budget/londres", json={"daily_usd": "20"})).status_code == 401
    assert (await app_client.delete("/api/v1/budget/londres")).status_code == 401


async def test_budget_is_personal(app_client, monkeypatch):
    """other_only pagado por bruno es consumo de katia: no es su vivir."""
    from app.db.models import Category, Movement, User

    h = await _seed_and_auth(app_client)
    _freeze_today(monkeypatch, date(2026, 8, 6))
    async with app_client._maker() as s:
        u1 = (await s.execute(select(User).where(User.username == "bruno"))).scalar_one()
        comida = (await s.execute(select(Category).where(Category.name == "Comida"))).scalar_one()
        s.add(Movement(type="expense", amount=Decimal("100"), currency="USD",
                       amount_usd=Decimal("100"), fx_rate=Decimal("1"), fx_source="frankfurter",
                       paid_by=u1.id, split="other_only", category_id=comida.id,
                       stop_slug="londres", city_name="Londres", created_by=u1.id))
        await s.commit()

    j = (await app_client.get("/api/v1/budget", headers=h)).json()
    assert _city(j, "londres")["living_usd"] == "15.00"  # los 100 son de katia


async def test_trip_status_is_explicit(app_client, monkeypatch):
    """El frontend elige el copy del bloque focal con esto: deducirlo de "no hay
    próxima parada" miente con un itinerario vacío."""
    h = await _seed_and_auth(app_client)
    for day, expected in (
        (date(2026, 7, 1), "not_started"),
        (date(2026, 8, 6), "in_progress"),
        (date(2026, 12, 1), "finished"),
    ):
        _freeze_today(monkeypatch, day)
        j = (await app_client.get("/api/v1/budget", headers=h)).json()
        assert j["trip_status"] == expected, day
