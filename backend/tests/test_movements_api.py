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
        "movement_date": "2026-08-06",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["amount_usd"] == "30.00"
    assert body["fx_source"] == "frankfurter"  # USD -> direct -> mapea a frankfurter
    assert body["paid_by"] >= 1


async def test_manual_fx_override(app_client):
    h = await _auth(app_client)
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "100.00", "currency": "GBP", "fx_rate": "1.30", "movement_date": "2026-08-06",
    })
    assert r.status_code == 201
    assert r.json()["amount_usd"] == "130.00"
    assert r.json()["fx_source"] == "manual"


async def test_list_and_delete(app_client):
    h = await _auth(app_client)
    await app_client.post("/api/v1/movements", headers=h, json={"amount": "10", "currency": "USD", "movement_date": "2026-08-06"})
    lst = await app_client.get("/api/v1/movements", headers=h)
    assert len(lst.json()) == 1
    mid = lst.json()[0]["id"]
    d = await app_client.delete(f"/api/v1/movements/{mid}", headers=h)
    assert d.status_code == 204
    assert (await app_client.get("/api/v1/movements", headers=h)).json() == []


async def test_partial_patch_keeps_manual_fx(app_client):
    # Regresión del bug de diseño: editar la descripción NO debe pisar una tasa manual.
    h = await _auth(app_client)
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "100.00", "currency": "GBP", "fx_rate": "1.30", "movement_date": "2026-08-06",
    })
    mid = r.json()["id"]
    p = await app_client.patch(f"/api/v1/movements/{mid}", headers=h, json={"description": "cena rica"})
    assert p.status_code == 200
    body = p.json()
    assert body["description"] == "cena rica"
    assert body["fx_source"] == "manual"
    # Comparar como Decimal: la DB devuelve la tasa con scale 6 ("1.300000").
    assert Decimal(body["fx_rate"]) == Decimal("1.30")
    assert body["amount_usd"] == "130.00"
    # PATCH parcial sin amount no debe fallar por validación (MovementUpdate, no MovementIn).
    p2 = await app_client.patch(f"/api/v1/movements/{mid}", headers=h, json={"amount": "50.00"})
    assert p2.status_code == 200
    assert p2.json()["amount_usd"] == "65.00"  # recalcula con la tasa manual 1.30
