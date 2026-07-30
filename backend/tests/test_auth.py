import pytest

from app.api.auth import (
    _failures,
    hash_password,
    is_valid_login_password,
    login_passwords,
    verify_password,
)
from app.config import get_settings


@pytest.fixture(autouse=True)
def _clean_throttle():
    """El throttle vive en un dict de módulo: sin limpiarlo, un test de fuerza
    bruta dejaría a los siguientes bloqueados."""
    _failures.clear()
    yield
    _failures.clear()


async def _seed_bruno(app_client):
    from app.db.models import User

    async with app_client._maker() as s:
        s.add(User(username="bruno", password_hash=hash_password("pw")))
        await s.commit()


def test_password_roundtrip():
    h = hash_password("secreto")
    assert verify_password("secreto", h)
    assert not verify_password("malo", h)


async def test_login_and_protected_route(app_client):
    await _seed_bruno(app_client)

    r = await app_client.post("/api/v1/auth/login", data={"username": "bruno", "password": "pw"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    r2 = await app_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["username"] == "bruno"

    r3 = await app_client.get("/api/v1/auth/me")
    assert r3.status_code == 401


async def test_login_unknown_user(app_client):
    r = await app_client.post("/api/v1/auth/login", data={"username": "nadie", "password": "pw"})
    assert r.status_code == 401


async def test_login_wrong_password(app_client):
    await _seed_bruno(app_client)
    r = await app_client.post(
        "/api/v1/auth/login", data={"username": "bruno", "password": "no-es"}
    )
    assert r.status_code == 401
    assert "ontraseña" in r.json()["detail"]


async def test_login_accepts_every_configured_password(app_client, monkeypatch):
    """Más de una contraseña válida a la vez: así se rota sin cortarle a nadie."""
    await _seed_bruno(app_client)
    monkeypatch.setenv("LOGIN_PASSWORDS", " bruny1003 , sandia12# ,")
    get_settings.cache_clear()

    for password in ("bruny1003", "sandia12#"):
        r = await app_client.post(
            "/api/v1/auth/login", data={"username": "bruno", "password": password}
        )
        assert r.status_code == 200, password

    # Se trimea y la coma final no crea una entrada vacía que matchearía un
    # campo sin completar (el form ya rechaza el string vacío con 422, pero la
    # lista no puede depender de eso).
    assert login_passwords() == ["bruny1003", "sandia12#"]
    assert not is_valid_login_password("")
    assert not is_valid_login_password(" ")


async def test_login_fails_closed_without_configured_passwords(app_client, monkeypatch):
    await _seed_bruno(app_client)
    monkeypatch.setenv("LOGIN_PASSWORDS", "")
    get_settings.cache_clear()
    r = await app_client.post("/api/v1/auth/login", data={"username": "bruno", "password": "pw"})
    assert r.status_code == 401


async def test_demo_mode_is_passwordless(app_client, monkeypatch):
    """La demo pública es de entrada libre: ese es todo el punto del deploy."""
    await _seed_bruno(app_client)
    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()
    r = await app_client.post(
        "/api/v1/auth/login", data={"username": "bruno", "password": "cualquiera"}
    )
    assert r.status_code == 200


async def test_login_throttles_after_repeated_failures(app_client):
    await _seed_bruno(app_client)
    for _ in range(8):
        r = await app_client.post(
            "/api/v1/auth/login", data={"username": "bruno", "password": "no-es"}
        )
        assert r.status_code == 401

    # Novena vez: ni siquiera con la contraseña correcta.
    r = await app_client.post("/api/v1/auth/login", data={"username": "bruno", "password": "pw"})
    assert r.status_code == 429


async def test_users_endpoint(app_client):
    from app.db.models import User

    async with app_client._maker() as s:
        s.add_all(
            [
                User(username="bruno", password_hash=hash_password("pw")),
                User(username="katia", password_hash=hash_password("pw")),
            ]
        )
        await s.commit()
    r = await app_client.post("/api/v1/auth/login", data={"username": "bruno", "password": "pw"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    users = await app_client.get("/api/v1/users", headers=h)
    assert users.status_code == 200
    assert [u["username"] for u in users.json()] == ["bruno", "katia"]
