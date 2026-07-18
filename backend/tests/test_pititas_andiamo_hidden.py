"""Andiamo no conoce el stop local Pititas: no debe recibirlo como ciudad.
El total del viaje sí lo incluye — es plata realmente gastada."""
from datetime import date
from decimal import Decimal

import pytest

from app.api.auth import hash_password


@pytest.fixture
def api_key(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("TRIP_SHARED_API_KEY", "k")
    get_settings.cache_clear()
    yield {"X-Api-Key": "k"}
    get_settings.cache_clear()


async def _seed(app_client):
    from app.db.models import Movement, Stop, User
    async with app_client._maker() as s:
        u = User(username="katia", password_hash=hash_password("pw"))
        s.add(u)
        s.add_all([
            Stop(slug="portugal", order=7, name="Portugal", currency_code="EUR",
                 arrival_date=date(2026, 9, 4), departure_date=date(2026, 9, 12)),
            Stop(slug="pititas", order=7, name="Pititas", country_flag="😊",
                 currency_code="EUR", arrival_date=date(2026, 9, 4),
                 departure_date=date(2026, 9, 12), is_local=True, owner_username="katia"),
        ])
        await s.flush()
        s.add_all([
            Movement(type="expense", amount=Decimal("40"), currency="EUR", amount_usd=Decimal("40"),
                     fx_rate=Decimal("1"), fx_source="frankfurter", paid_by=u.id, split="shared",
                     stop_slug="portugal", city_name="Portugal",
                      created_by=u.id),
            Movement(type="expense", amount=Decimal("30"), currency="EUR", amount_usd=Decimal("30"),
                     fx_rate=Decimal("1"), fx_source="frankfurter", paid_by=u.id, split="shared",
                     stop_slug="pititas", city_name="Pititas",
                      created_by=u.id),
            # Gasto general (sin ciudad): el filtro de locales no debe comérselo.
            Movement(type="expense", amount=Decimal("10"), currency="USD", amount_usd=Decimal("10"),
                     fx_rate=Decimal("1"), fx_source="direct", paid_by=u.id, split="shared",
                     stop_slug=None, city_name=None,
                      created_by=u.id),
        ])
        await s.commit()


async def test_cities_spend_no_expone_pititas(app_client, api_key):
    await _seed(app_client)
    r = await app_client.get("/api/v1/cities/spend", headers=api_key)
    assert r.status_code == 200
    slugs = {c["slug"] for c in r.json()}
    assert "pititas" not in slugs
    assert "portugal" in slugs


async def test_cities_spend_conserva_los_gastos_generales(app_client, api_key):
    """El filtro de slugs locales usa coalesce: sin eso, `stop_slug NOT IN (...)`
    evalúa NULL y se comería los gastos sin ciudad."""
    await _seed(app_client)
    r = await app_client.get("/api/v1/cities/spend", headers=api_key)
    rows = {c["slug"]: c for c in r.json()}
    assert None in rows  # el grupo "sin ciudad" sigue estando
    assert rows[None]["total_usd"] == "10.00"


async def test_spend_detail_de_pititas_devuelve_ceros(app_client, api_key):
    await _seed(app_client)
    r = await app_client.get("/api/v1/cities/spend-detail?slug=pititas", headers=api_key)
    assert r.status_code == 200  # nunca 404
    body = r.json()
    assert body["total_usd"] == "0.00"
    assert body["movement_count"] == 0
    assert body["city_name"] is None  # no filtra el nombre del stop local


async def test_trip_spend_sigue_incluyendo_pititas(app_client, api_key):
    await _seed(app_client)
    r = await app_client.get("/api/v1/trip/spend", headers=api_key)
    assert r.status_code == 200
    assert r.json()["total_usd"] == "80.00"  # 40 Portugal + 30 Pititas + 10 general
