from decimal import Decimal

from app.api.auth import hash_password


async def _auth(app_client):
    from app.db.models import User
    async with app_client._maker() as s:
        s.add_all([User(username="bruno", password_hash=hash_password("pw")),
                   User(username="katia", password_hash=hash_password("pw"))])
        await s.commit()
    r = await app_client.post("/api/v1/auth/login", data={"username": "bruno", "password": "pw"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_create_usd_movement(app_client):
    h = await _auth(app_client)
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "30.00", "currency": "USD", "description": "taxi", "split": "shared",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["amount_usd"] == "30.00"
    assert body["fx_source"] == "direct"
    assert body["paid_by"] >= 1


async def test_manual_fx_override(app_client):
    h = await _auth(app_client)
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "100.00", "currency": "GBP", "fx_rate": "1.30",
    })
    assert r.status_code == 201
    assert r.json()["amount_usd"] == "130.00"
    assert r.json()["fx_source"] == "manual"


async def test_list_and_delete(app_client):
    h = await _auth(app_client)
    await app_client.post("/api/v1/movements", headers=h, json={"amount": "10", "currency": "USD"})
    lst = await app_client.get("/api/v1/movements", headers=h)
    assert len(lst.json()) == 1
    mid = lst.json()[0]["id"]
    d = await app_client.delete(f"/api/v1/movements/{mid}", headers=h)
    assert d.status_code == 204
    assert (await app_client.get("/api/v1/movements", headers=h)).json() == []


async def test_create_derives_city_from_date(app_client):
    # Gastos por web sin parada explícita: se imputan a la parada de HOY.
    from datetime import date, timedelta
    from app.db.models import Stop
    h = await _auth(app_client)
    today = date.today()
    async with app_client._maker() as s:
        s.add_all([
            Stop(slug="londres", order=1, name="Londres", currency_code="GBP",
                 arrival_date=today - timedelta(days=5), departure_date=today + timedelta(days=5)),
            Stop(slug="paris", order=6, name="París", currency_code="EUR",
                 arrival_date=today + timedelta(days=10), departure_date=today + timedelta(days=15)),
        ])
        await s.commit()
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "20", "currency": "USD",
    })
    assert r.status_code == 201
    assert r.json()["stop_slug"] == "londres"
    assert r.json()["city_name"] == "Londres"
    # PATCH con parada explícita: valida contra el itinerario y deriva city_name.
    mid = r.json()["id"]
    p = await app_client.patch(f"/api/v1/movements/{mid}", headers=h,
                               json={"stop_slug": "paris"})
    assert p.json()["stop_slug"] == "paris"
    assert p.json()["city_name"] == "París"
    # stop_slug null explícito re-deriva a la parada de hoy.
    p2 = await app_client.patch(f"/api/v1/movements/{mid}", headers=h,
                                json={"stop_slug": None})
    assert p2.json()["stop_slug"] == "londres"


async def test_explicit_stop_slug_derives_city_name(app_client):
    # El city_name siempre sale del Stop: la API no acepta texto libre.
    from datetime import date
    from app.db.models import Stop
    h = await _auth(app_client)
    async with app_client._maker() as s:
        s.add(Stop(slug="paris", order=1, name="París", currency_code="EUR",
                   arrival_date=date(2020, 8, 5), departure_date=date(2020, 8, 13)))
        await s.commit()
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "10", "currency": "EUR", "fx_rate": "1.10", "stop_slug": "paris",
    })
    assert r.status_code == 201
    assert r.json()["city_name"] == "París"


async def test_unknown_stop_slug_is_422(app_client):
    h = await _auth(app_client)
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "10", "currency": "USD", "stop_slug": "narnia",
    })
    assert r.status_code == 422


async def test_create_outside_itinerary_has_no_city(app_client):
    # Sin parada vigente hoy (itinerario en el pasado) => General.
    from datetime import date
    from app.db.models import Stop
    h = await _auth(app_client)
    async with app_client._maker() as s:
        s.add(Stop(slug="londres", order=1, name="Londres", currency_code="GBP",
                   arrival_date=date(2020, 8, 5), departure_date=date(2020, 8, 13)))
        await s.commit()
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "10", "currency": "USD",
    })
    assert r.status_code == 201
    assert r.json()["stop_slug"] is None
    assert r.json()["city_name"] is None


async def test_rejects_invalid_split_and_ars_manual_rate(app_client):
    h = await _auth(app_client)
    bad = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "10", "currency": "USD", "split": "half",
    })
    assert bad.status_code == 422
    ars = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "1000", "currency": "ARS", "fx_rate": "1600",
    })
    assert ars.status_code == 422


async def test_partial_patch_keeps_manual_fx(app_client):
    # Regresión del bug de diseño: editar la descripción NO debe pisar una tasa manual.
    h = await _auth(app_client)
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "100.00", "currency": "GBP", "fx_rate": "1.30",
    })
    mid = r.json()["id"]
    p = await app_client.patch(f"/api/v1/movements/{mid}", headers=h, json={"description": "cena rica"})
    assert p.status_code == 200
    body = p.json()
    assert body["description"] == "Cena rica"  # normalizada server-side
    assert body["fx_source"] == "manual"
    # Comparar como Decimal: la DB devuelve la tasa con scale 6 ("1.300000").
    assert Decimal(body["fx_rate"]) == Decimal("1.30")
    assert body["amount_usd"] == "130.00"
    # PATCH parcial sin amount no debe fallar por validación (MovementUpdate, no MovementIn).
    p2 = await app_client.patch(f"/api/v1/movements/{mid}", headers=h, json={"amount": "50.00"})
    assert p2.status_code == 200
    assert p2.json()["amount_usd"] == "65.00"  # recalcula con la tasa manual 1.30


async def test_create_with_future_payment_date_is_pending(app_client):
    from datetime import date, timedelta
    h = await _auth(app_client)
    future = (date.today() + timedelta(days=30)).isoformat()
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "301", "currency": "USD", "description": "hostel (2/2)",
        "payment_date": future,
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["payment_date"] == future


async def test_create_with_past_payment_date_uses_historic_rate(app_client):
    from datetime import date, timedelta
    from decimal import Decimal
    from app.db.models import FxRate
    h = await _auth(app_client)
    past = date.today() - timedelta(days=10)
    async with app_client._maker() as s:
        s.add_all([
            FxRate(currency="EUR", rate_date=past, rate_to_usd=Decimal("1.05")),
            FxRate(currency="EUR", rate_date=date.today(), rate_to_usd=Decimal("1.10")),
        ])
        await s.commit()
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "130", "currency": "EUR", "description": "hospedaje york",
        "payment_date": past.isoformat(),
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "confirmed"
    assert body["amount_usd"] == "136.50"  # 130 * 1.05 histórico


async def test_patch_payment_date_null_resets_and_status_not_writable(app_client):
    from datetime import date, timedelta
    h = await _auth(app_client)
    future = (date.today() + timedelta(days=30)).isoformat()
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "50", "currency": "USD", "payment_date": future,
        "status": "confirmed",  # no escribible: el server lo deriva igual
    })
    assert r.json()["status"] == "pending"
    mid = r.json()["id"]
    p = await app_client.patch(f"/api/v1/movements/{mid}", headers=h,
                               json={"payment_date": None})
    assert p.status_code == 200, p.text
    assert p.json()["payment_date"] is None
    assert p.json()["status"] == "confirmed"
