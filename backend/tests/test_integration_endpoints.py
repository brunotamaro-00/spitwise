"""Endpoints de integración con Andiamo: sync-hook, spend-detail, trip/spend, config."""

from datetime import date
from decimal import Decimal

from app.api.auth import hash_password


async def _seed(app_client):
    from app.db.models import Movement, Stop, User
    async with app_client._maker() as s:
        u = User(username="bruno", password_hash=hash_password("pw"))
        k = User(username="katia", password_hash=hash_password("pw"))
        s.add_all([u, k])
        await s.flush()
        s.add(Stop(
            slug="paris", order=6, name="París", country="Francia", country_flag="🇫🇷",
            arrival_date=date(2026, 8, 29), departure_date=date(2026, 9, 4),
            currency_code="EUR", timezone="Europe/Paris",
        ))
        s.add_all([
            Movement(type="expense", amount=Decimal("50"), currency="EUR", amount_usd=Decimal("55"),
                     fx_rate=Decimal("1.1"), fx_source="frankfurter", paid_by=u.id, split="shared",
                     description="Cena bistró", category_id=2, stop_slug="paris", city_name="París",
                     movement_date=date(2026, 8, 30), created_by=u.id),
            Movement(type="expense", amount=Decimal("20"), currency="EUR", amount_usd=Decimal("22"),
                     fx_rate=Decimal("1.1"), fx_source="frankfurter", paid_by=k.id, split="shared",
                     description="Metro", category_id=3, stop_slug="paris", city_name="París",
                     movement_date=date(2026, 8, 31), created_by=k.id),
            # Settlement: no debe contar en spend.
            Movement(type="settlement", amount=Decimal("10"), currency="USD", amount_usd=Decimal("10"),
                     fx_rate=Decimal("1"), fx_source="manual", paid_by=u.id, split="shared",
                     stop_slug="paris", city_name="París",
                     movement_date=date(2026, 8, 31), created_by=u.id),
        ])
        await s.commit()


async def test_spend_detail_shape(app_client, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("TRIP_SHARED_API_KEY", "k")
    get_settings.cache_clear()
    await _seed(app_client)
    r = await app_client.get(
        "/api/v1/cities/spend-detail", params={"slug": "paris"}, headers={"X-Api-Key": "k"}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["slug"] == "paris"
    assert data["city_name"] == "París"
    assert data["total_usd"] == "77.00"
    assert data["movement_count"] == 2
    assert data["itinerary_days"] == 6
    assert data["avg_per_day_usd"] == "12.83"
    assert [c["total_usd"] for c in data["by_category"]] == ["55.00", "22.00"]
    assert data["by_category"][0]["name"] is not None
    assert data["last_movements"][0]["description"] == "Metro"  # más reciente primero
    assert data["last_movements"][0]["paid_by_name"] == "katia"
    get_settings.cache_clear()


async def test_spend_detail_unknown_slug_returns_zeros(app_client, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("TRIP_SHARED_API_KEY", "k")
    get_settings.cache_clear()
    r = await app_client.get(
        "/api/v1/cities/spend-detail", params={"slug": "nope"}, headers={"X-Api-Key": "k"}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total_usd"] == "0.00"
    assert data["movement_count"] == 0
    assert data["by_category"] == []
    assert data["last_movements"] == []
    get_settings.cache_clear()


async def test_spend_detail_requires_key(app_client, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("TRIP_SHARED_API_KEY", "k")
    get_settings.cache_clear()
    r = await app_client.get(
        "/api/v1/cities/spend-detail", params={"slug": "paris"}, headers={"X-Api-Key": "wrong"}
    )
    assert r.status_code == 401
    get_settings.cache_clear()


async def test_trip_spend(app_client, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("TRIP_SHARED_API_KEY", "k")
    get_settings.cache_clear()
    await _seed(app_client)
    r = await app_client.get("/api/v1/trip/spend", headers={"X-Api-Key": "k"})
    assert r.status_code == 200
    data = r.json()
    assert data["total_usd"] == "77.00"
    assert data["movement_count"] == 2
    assert "today_usd" in data
    get_settings.cache_clear()


async def test_sync_hook_auth_and_schedule(app_client, monkeypatch):
    from app.config import get_settings
    import app.andiamo as andiamo_mod

    monkeypatch.setenv("TRIP_SHARED_API_KEY", "k")
    get_settings.cache_clear()

    called = {"n": 0}
    monkeypatch.setattr(andiamo_mod, "force_sync_soon", lambda: called.__setitem__("n", called["n"] + 1))
    # El router importó el símbolo directamente; parchear ahí también.
    import app.api.integration as integration_mod
    monkeypatch.setattr(integration_mod, "force_sync_soon", lambda: called.__setitem__("n", called["n"] + 1))

    r = await app_client.post("/api/v1/andiamo/sync-hook", headers={"X-Api-Key": "bad"})
    assert r.status_code == 401
    assert called["n"] == 0

    r = await app_client.post("/api/v1/andiamo/sync-hook", headers={"X-Api-Key": "k"})
    assert r.status_code == 202
    assert r.json() == {"status": "scheduled"}
    assert called["n"] == 1
    get_settings.cache_clear()


async def test_config_endpoint(app_client, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("ANDIAMO_URL", "http://andiamo.test")
    get_settings.cache_clear()
    await _seed(app_client)
    login = await app_client.post(
        "/api/v1/auth/login", data={"username": "bruno", "password": "pw"}
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    r = await app_client.get("/api/v1/config", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"andiamo_url": "http://andiamo.test"}
    get_settings.cache_clear()


async def _seed_private(app_client):
    """París con un compartido y un gasto privado de cada uno."""
    from app.db.models import Movement, Stop, User
    async with app_client._maker() as s:
        u = User(username="bruno", password_hash=hash_password("pw"))
        k = User(username="katia", password_hash=hash_password("pw"))
        s.add_all([u, k])
        await s.flush()
        s.add(Stop(
            slug="paris", order=6, name="París", country="Francia", country_flag="🇫🇷",
            arrival_date=date(2026, 8, 29), departure_date=date(2026, 9, 4),
            currency_code="EUR", timezone="Europe/Paris",
        ))
        s.add_all([
            # Compartido: mitad y mitad.
            Movement(type="expense", amount=Decimal("100"), currency="EUR", amount_usd=Decimal("110"),
                     fx_rate=Decimal("1.1"), fx_source="frankfurter", paid_by=u.id, split="shared",
                     description="Hotel", category_id=1, stop_slug="paris", city_name="París",
                     movement_date=date(2026, 8, 30), created_by=u.id),
            # Privado de Bruno.
            Movement(type="expense", amount=Decimal("40"), currency="USD", amount_usd=Decimal("40"),
                     fx_rate=Decimal("1"), fx_source="manual", paid_by=u.id, split="payer_only",
                     description="Remera", category_id=2, stop_slug="paris", city_name="París",
                     movement_date=date(2026, 8, 31), created_by=u.id),
            # Privado de Katia, pagado por Bruno.
            Movement(type="expense", amount=Decimal("30"), currency="USD", amount_usd=Decimal("30"),
                     fx_rate=Decimal("1"), fx_source="manual", paid_by=u.id, split="other_only",
                     description="Perfume", category_id=2, stop_slug="paris", city_name="París",
                     movement_date=date(2026, 9, 1), created_by=u.id),
        ])
        await s.commit()


async def test_spend_detail_por_usuario_reparte_y_oculta(app_client, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("TRIP_SHARED_API_KEY", "k")
    get_settings.cache_clear()
    await _seed_private(app_client)

    # Bruno: mitad del hotel (55) + su remera (40). El perfume de Katia no existe.
    r = await app_client.get(
        "/api/v1/cities/spend-detail",
        params={"slug": "paris", "user": "bruno"}, headers={"X-Api-Key": "k"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total_usd"] == "95.00"
    assert data["movement_count"] == 2
    descs = [m["description"] for m in data["last_movements"]]
    assert "Perfume" not in descs
    assert set(descs) == {"Hotel", "Remera"}

    # Katia: mitad del hotel (55) + su perfume (30). La remera de Bruno no existe.
    r = await app_client.get(
        "/api/v1/cities/spend-detail",
        params={"slug": "paris", "user": "katia"}, headers={"X-Api-Key": "k"},
    )
    data = r.json()
    assert data["total_usd"] == "85.00"
    assert data["movement_count"] == 2
    descs = [m["description"] for m in data["last_movements"]]
    assert "Remera" not in descs
    assert set(descs) == {"Hotel", "Perfume"}
    get_settings.cache_clear()


async def test_spend_detail_share_escala_moneda_local(app_client, monkeypatch):
    """El importe en moneda original acompaña al share: medio hotel = 50 EUR / 55 USD."""
    from app.config import get_settings
    monkeypatch.setenv("TRIP_SHARED_API_KEY", "k")
    get_settings.cache_clear()
    await _seed_private(app_client)
    r = await app_client.get(
        "/api/v1/cities/spend-detail",
        params={"slug": "paris", "user": "bruno"}, headers={"X-Api-Key": "k"},
    )
    hotel = next(m for m in r.json()["last_movements"] if m["description"] == "Hotel")
    assert hotel["amount"] == "50.00"
    assert hotel["currency"] == "EUR"
    assert hotel["amount_usd"] == "55.00"
    get_settings.cache_clear()


async def test_spend_detail_sin_user_sigue_gross(app_client, monkeypatch):
    """El contrato viejo no cambia: sin ?user= es el total del hogar."""
    from app.config import get_settings
    monkeypatch.setenv("TRIP_SHARED_API_KEY", "k")
    get_settings.cache_clear()
    await _seed_private(app_client)
    r = await app_client.get(
        "/api/v1/cities/spend-detail", params={"slug": "paris"}, headers={"X-Api-Key": "k"}
    )
    data = r.json()
    assert data["total_usd"] == "180.00"
    assert data["movement_count"] == 3
    get_settings.cache_clear()


async def test_spend_detail_user_desconocido_es_400(app_client, monkeypatch):
    """Nunca degradar a gross: sería filtrarle a uno los gastos privados del otro."""
    from app.config import get_settings
    monkeypatch.setenv("TRIP_SHARED_API_KEY", "k")
    get_settings.cache_clear()
    await _seed_private(app_client)
    r = await app_client.get(
        "/api/v1/cities/spend-detail",
        params={"slug": "paris", "user": "nadie"}, headers={"X-Api-Key": "k"},
    )
    assert r.status_code == 400
    get_settings.cache_clear()


async def test_trip_spend_por_usuario(app_client, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("TRIP_SHARED_API_KEY", "k")
    get_settings.cache_clear()
    await _seed_private(app_client)
    r = await app_client.get(
        "/api/v1/trip/spend", params={"user": "katia"}, headers={"X-Api-Key": "k"}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total_usd"] == "85.00"
    assert data["movement_count"] == 2
    get_settings.cache_clear()
