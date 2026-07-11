from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.api.auth import hash_password


async def _seed_and_auth(app_client):
    from app.db.models import Category, Movement, User
    async with app_client._maker() as s:
        u1 = User(username="bruno", password_hash=hash_password("pw"))
        u2 = User(username="novia", password_hash=hash_password("pw"))
        s.add_all([u1, u2])
        await s.flush()
        cat = (await s.execute(select(Category))).scalars().first()
        s.add_all([
            Movement(type="expense", amount=Decimal("50"), currency="USD", amount_usd=Decimal("50"),
                     fx_rate=Decimal("1"), fx_source="frankfurter", paid_by=u1.id, split="shared",
                     category_id=cat.id, stop_slug="londres", city_name="Londres",
                     movement_date=date(2026, 8, 6), created_by=u1.id),
            Movement(type="expense", amount=Decimal("30"), currency="USD", amount_usd=Decimal("30"),
                     fx_rate=Decimal("1"), fx_source="frankfurter", paid_by=u2.id, split="shared",
                     category_id=cat.id, stop_slug="paris", city_name="París",
                     movement_date=date(2026, 8, 30), created_by=u2.id),
        ])
        await s.commit()
    r = await app_client.post("/api/v1/auth/login", data={"username": "bruno", "password": "pw"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_categories_endpoint(app_client):
    h = await _seed_and_auth(app_client)
    r = await app_client.get("/api/v1/categories", headers=h)
    assert [c["name"] for c in r.json()][0] == "Alojamiento"


async def test_summary_and_by_city(app_client):
    h = await _seed_and_auth(app_client)
    summ = await app_client.get("/api/v1/dashboard/summary", headers=h)
    assert summ.json()["total_usd"] == "80.00"
    assert summ.json()["movement_count"] == 2
    by_city = await app_client.get("/api/v1/dashboard/by-city", headers=h)
    cities = {c["city_name"]: c["total_usd"] for c in by_city.json()}
    assert cities["Londres"] == "50.00"
    assert cities["París"] == "30.00"


async def test_by_category(app_client):
    h = await _seed_and_auth(app_client)
    by_cat = await app_client.get("/api/v1/dashboard/by-category", headers=h)
    rows = by_cat.json()
    assert rows[0]["total_usd"] == "80.00"


async def test_timeseries(app_client):
    h = await _seed_and_auth(app_client)
    ts = await app_client.get("/api/v1/dashboard/timeseries", headers=h)
    pts = ts.json()
    assert pts[-1]["cumulative_usd"] == "80.00"
