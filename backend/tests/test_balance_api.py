from app.api.auth import hash_password


async def test_balance_endpoint(app_client):
    from app.db.models import Movement, User
    async with app_client._maker() as s:
        u1 = User(username="bruno", password_hash=hash_password("pw"))
        u2 = User(username="katia", password_hash=hash_password("pw"))
        s.add_all([u1, u2])
        await s.flush()
        from decimal import Decimal
        from datetime import date
        s.add(Movement(type="expense", amount=Decimal("100"), currency="USD",
                       amount_usd=Decimal("100"), fx_rate=Decimal("1"), fx_source="frankfurter",
                       paid_by=u1.id, split="shared", movement_date=date(2026, 8, 6), created_by=u1.id))
        await s.commit()
    r = await app_client.post("/api/v1/auth/login", data={"username": "bruno", "password": "pw"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    b = await app_client.get("/api/v1/balance", headers=h)
    assert b.status_code == 200
    # katia (u2) le debe 50 a bruno (u1)
    body = b.json()
    assert body["amount_usd"] == "50.00"
    assert body["debtor_id"] == u2.id
    assert body["creditor_id"] == u1.id
