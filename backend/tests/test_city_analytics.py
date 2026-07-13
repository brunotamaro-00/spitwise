from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.api.auth import hash_password


async def _seed_and_auth(app_client):
    """bruno + katia; gastos en Londres (2 días) y París (1 día), todos shared."""
    from app.db.models import Category, Movement, Stop, User

    async with app_client._maker() as s:
        u1 = User(username="bruno", password_hash=hash_password("pw"))
        u2 = User(username="katia", password_hash=hash_password("pw"))
        s.add_all([u1, u2])
        await s.flush()
        cats = (await s.execute(select(Category))).scalars().all()
        c0, c1 = cats[0].id, cats[1].id
        s.add_all([
            Stop(slug="londres", order=1, name="Londres", country="Reino Unido",
                 country_flag="🇬🇧", currency_code="GBP",
                 arrival_date=date(2026, 8, 5), departure_date=date(2026, 8, 8)),
            Stop(slug="paris", order=2, name="París", country="Francia",
                 country_flag="🇫🇷", currency_code="EUR",
                 arrival_date=date(2026, 8, 29), departure_date=date(2026, 9, 1)),
            Movement(type="expense", amount=Decimal("50"), currency="USD", amount_usd=Decimal("50"),
                     fx_rate=Decimal("1"), fx_source="frankfurter", paid_by=u1.id, split="shared",
                     category_id=c0, stop_slug="londres", city_name="Londres",
                     movement_date=date(2026, 8, 6), created_by=u1.id),
            Movement(type="expense", amount=Decimal("20"), currency="USD", amount_usd=Decimal("20"),
                     fx_rate=Decimal("1"), fx_source="frankfurter", paid_by=u2.id, split="shared",
                     category_id=c1, stop_slug="londres", city_name="Londres",
                     movement_date=date(2026, 8, 7), created_by=u2.id),
            Movement(type="expense", amount=Decimal("30"), currency="USD", amount_usd=Decimal("30"),
                     fx_rate=Decimal("1"), fx_source="frankfurter", paid_by=u2.id, split="shared",
                     category_id=c0, stop_slug="paris", city_name="París",
                     movement_date=date(2026, 8, 30), created_by=u2.id),
        ])
        await s.commit()
    r = await app_client.post("/api/v1/auth/login", data={"username": "bruno", "password": "pw"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_summary_all_cities(app_client):
    h = await _seed_and_auth(app_client)
    # bruno shared => mitad de cada gasto: (50+20+30)/2 = 50.
    # días = itinerario: Londres (5→8 = 3) + París (29 ago→1 sep = 3) = 6.
    r = await app_client.get("/api/v1/dashboard/city/summary", headers=h)
    j = r.json()
    assert j["total_usd"] == "50.00"
    assert j["movement_count"] == 3
    assert j["days"] == 6
    assert j["avg_per_day_usd"] == "8.33"


async def test_summary_single_city_includes_dates(app_client):
    h = await _seed_and_auth(app_client)
    r = await app_client.get("/api/v1/dashboard/city/summary?slugs=londres", headers=h)
    j = r.json()
    # Londres: (50+20)/2 = 35; días de itinerario = 3 (5→8 ago), avg = 11.67.
    assert j["total_usd"] == "35.00"
    assert j["days"] == 3
    assert j["avg_per_day_usd"] == "11.67"
    assert j["arrival_date"] == "2026-08-05"
    assert j["departure_date"] == "2026-08-08"


async def test_summary_multi_city_no_dates(app_client):
    h = await _seed_and_auth(app_client)
    r = await app_client.get(
        "/api/v1/dashboard/city/summary?slugs=londres&slugs=paris", headers=h
    )
    j = r.json()
    assert j["total_usd"] == "50.00"
    assert j["arrival_date"] is None


async def test_by_category_scoped_to_city(app_client):
    h = await _seed_and_auth(app_client)
    r = await app_client.get("/api/v1/dashboard/city/by-category?slugs=paris", headers=h)
    rows = r.json()
    # Solo el gasto de París (30/2 = 15) en la categoría c0.
    assert len(rows) == 1
    assert rows[0]["total_usd"] == "15.00"


async def test_daily_is_not_cumulative(app_client):
    h = await _seed_and_auth(app_client)
    r = await app_client.get("/api/v1/dashboard/city/daily?slugs=londres", headers=h)
    pts = r.json()
    assert [p["total_usd"] for p in pts] == ["25.00", "10.00"]


async def test_daily_excludes_general_expenses(app_client):
    """Sin filtro de ciudad, /daily no suma los gastos generales (sin stop):
    cuentan para el total del viaje pero no son gasto diario en destino."""
    from datetime import date as d
    from app.db.models import Movement, User

    h = await _seed_and_auth(app_client)
    async with app_client._maker() as s:
        u1 = (await s.execute(select(User).where(User.username == "bruno"))).scalar_one()
        s.add(Movement(type="expense", amount=Decimal("100"), currency="USD",
                       amount_usd=Decimal("100"), fx_rate=Decimal("1"),
                       fx_source="frankfurter", paid_by=u1.id, split="shared",
                       category_id=None, stop_slug=None, city_name=None,
                       movement_date=d(2026, 8, 6), created_by=u1.id))
        await s.commit()

    r = await app_client.get("/api/v1/dashboard/city/daily", headers=h)
    pts = {p["date"]: p["total_usd"] for p in r.json()}
    # El 6 de agosto solo cuenta el gasto de Londres (50/2), no el general (100/2).
    assert pts["2026-08-06"] == "25.00"
    assert sum(Decimal(v) for v in pts.values()) == Decimal("50.00")


async def test_breakdown_all_cities(app_client):
    h = await _seed_and_auth(app_client)
    r = await app_client.get("/api/v1/dashboard/city/breakdown", headers=h)
    rows = {row["city_name"]: row for row in r.json()}
    assert rows["Londres"]["total_usd"] == "35.00"
    assert rows["Londres"]["movement_count"] == 2
    assert rows["Londres"]["days"] == 2
    assert rows["Londres"]["country_flag"] == "🇬🇧"
    assert rows["París"]["total_usd"] == "15.00"
    # Ordenado por total desc.
    assert [row["city_name"] for row in r.json()][0] == "Londres"


async def test_movements_filtered_by_city(app_client):
    h = await _seed_and_auth(app_client)
    r = await app_client.get("/api/v1/dashboard/city/movements?slugs=londres", headers=h)
    rows = r.json()
    assert {m["city_name"] for m in rows} == {"Londres"}
    # Orden por fecha desc.
    assert [m["movement_date"] for m in rows] == ["2026-08-07", "2026-08-06"]


async def test_stops_exposes_dates_and_country(app_client):
    h = await _seed_and_auth(app_client)
    r = await app_client.get("/api/v1/stops", headers=h)
    londres = next(s for s in r.json() if s["slug"] == "londres")
    assert londres["country"] == "Reino Unido"
    assert londres["arrival_date"] == "2026-08-05"
    assert londres["order"] == 1
