from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.api.auth import hash_password


async def _seed_and_auth(app_client):
    from app.db.models import Category, Movement, User
    async with app_client._maker() as s:
        u1 = User(username="bruno", password_hash=hash_password("pw"))
        u2 = User(username="katia", password_hash=hash_password("pw"))
        s.add_all([u1, u2])
        await s.flush()
        cat = (await s.execute(select(Category))).scalars().first()
        s.add_all([
            Movement(type="expense", amount=Decimal("50"), currency="USD", amount_usd=Decimal("50"),
                     fx_rate=Decimal("1"), fx_source="frankfurter", paid_by=u1.id, split="shared",
                     category_id=cat.id, stop_slug="londres", city_name="Londres",
                      created_by=u1.id),
            Movement(type="expense", amount=Decimal("30"), currency="USD", amount_usd=Decimal("30"),
                     fx_rate=Decimal("1"), fx_source="frankfurter", paid_by=u2.id, split="shared",
                     category_id=cat.id, stop_slug="paris", city_name="París",
                      created_by=u2.id),
        ])
        await s.commit()
    r = await app_client.post("/api/v1/auth/login", data={"username": "bruno", "password": "pw"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_categories_endpoint(app_client):
    h = await _seed_and_auth(app_client)
    r = await app_client.get("/api/v1/categories", headers=h)
    assert [c["name"] for c in r.json()][0] == "Alojamiento"


async def test_summary(app_client):
    # bruno logueado; ambos gastos son shared => su parte es la mitad de cada uno.
    h = await _seed_and_auth(app_client)
    summ = await app_client.get("/api/v1/dashboard/summary", headers=h)
    assert summ.json()["total_usd"] == "40.00"
    assert summ.json()["movement_count"] == 2


async def test_by_category(app_client):
    h = await _seed_and_auth(app_client)
    by_cat = await app_client.get("/api/v1/dashboard/by-category", headers=h)
    rows = by_cat.json()
    assert rows[0]["total_usd"] == "40.00"


async def test_summary_excludes_other_only_paid_by_other(app_client):
    # Un gasto other_only pagado por bruno => consumo del otro, no cuenta para bruno.
    from app.db.models import Movement, User
    from sqlalchemy import select

    h = await _seed_and_auth(app_client)
    async with app_client._maker() as s:
        bruno = (await s.execute(select(User).where(User.username == "bruno"))).scalar_one()
        s.add(
            Movement(type="expense", amount=Decimal("10"), currency="USD", amount_usd=Decimal("10"),
                     fx_rate=Decimal("1"), fx_source="frankfurter", paid_by=bruno.id, split="other_only",
                     stop_slug="paris", city_name="París",
                      created_by=bruno.id),
        )
        await s.commit()
    summ = await app_client.get("/api/v1/dashboard/summary", headers=h)
    # Sigue siendo 40: el other_only pagado por bruno no suma a su consumo.
    assert summ.json()["total_usd"] == "40.00"


async def test_list_stops(app_client):
    from app.db.models import Stop

    h = await _seed_and_auth(app_client)
    async with app_client._maker() as s:
        s.add_all([
            Stop(slug="paris", order=2, name="París", currency_code="EUR", country_flag="🇫🇷"),
            Stop(slug="londres", order=1, name="Londres", currency_code="GBP", country_flag="🇬🇧"),
        ])
        await s.commit()
    r = await app_client.get("/api/v1/stops", headers=h)
    assert [x["slug"] for x in r.json()] == ["londres", "paris"]

