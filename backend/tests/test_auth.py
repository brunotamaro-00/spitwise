from app.api.auth import create_jwt, hash_password, verify_password


def test_password_roundtrip():
    h = hash_password("secreto")
    assert verify_password("secreto", h)
    assert not verify_password("malo", h)


async def test_login_and_protected_route(app_client):
    # Sembrar un usuario directo en la DB del cliente.
    from app.db.models import User
    async with app_client._maker() as s:
        s.add(User(username="bruno", password_hash=hash_password("pw")))
        await s.commit()

    r = await app_client.post("/api/v1/auth/login", data={"username": "bruno", "password": "pw"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    r2 = await app_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["username"] == "bruno"

    r3 = await app_client.get("/api/v1/auth/me")
    assert r3.status_code == 401


async def test_users_endpoint(app_client):
    from app.db.models import User
    async with app_client._maker() as s:
        s.add_all([User(username="bruno", password_hash=hash_password("pw")),
                   User(username="novia", password_hash=hash_password("pw"))])
        await s.commit()
    r = await app_client.post("/api/v1/auth/login", data={"username": "bruno", "password": "pw"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    users = await app_client.get("/api/v1/users", headers=h)
    assert users.status_code == 200
    assert [u["username"] for u in users.json()] == ["bruno", "novia"]
