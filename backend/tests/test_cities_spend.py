from datetime import date
from decimal import Decimal

from app.api.auth import hash_password


async def _seed(app_client):
    from app.db.models import Movement, User
    async with app_client._maker() as s:
        u = User(username="bruno", password_hash=hash_password("pw"))
        s.add(u)
        await s.flush()
        s.add_all([
            Movement(type="expense", amount=Decimal("50"), currency="USD", amount_usd=Decimal("50"),
                     fx_rate=Decimal("1"), fx_source="frankfurter", paid_by=u.id, split="shared",
                     stop_slug="londres", city_name="Londres",  created_by=u.id),
            Movement(type="expense", amount=Decimal("20"), currency="USD", amount_usd=Decimal("20"),
                     fx_rate=Decimal("1"), fx_source="frankfurter", paid_by=u.id, split="shared",
                     stop_slug="londres", city_name="Londres",  created_by=u.id),
        ])
        await s.commit()


async def test_cities_spend_requires_key(app_client):
    await _seed(app_client)
    r = await app_client.get("/api/v1/cities/spend")
    assert r.status_code == 422 or r.status_code == 401  # falta header


async def test_cities_spend_ok(app_client, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("TRIP_SHARED_API_KEY", "k")
    get_settings.cache_clear()
    await _seed(app_client)
    r = await app_client.get("/api/v1/cities/spend", headers={"X-Api-Key": "k"})
    assert r.status_code == 200
    data = {c["slug"]: c for c in r.json()}
    assert data["londres"]["total_usd"] == "70.00"
    assert data["londres"]["movement_count"] == 2
    get_settings.cache_clear()
