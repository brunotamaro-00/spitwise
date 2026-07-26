async def test_health(app_client):
    r = await app_client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_api_responses_are_not_cacheable(app_client):
    """Sin Cache-Control el browser cachea /api/* heurísticamente sobre disco:
    se vio /categories servir un catálogo viejo contra una DB ya migrada, y como
    los chips de la web mandan category_id, imputaba la categoría equivocada."""
    from app.api.auth import hash_password
    from app.db.models import User

    async with app_client._maker() as s:
        s.add(User(username="bruno", password_hash=hash_password("pw")))
        await s.commit()
    r = await app_client.post("/api/v1/auth/login", data={"username": "bruno", "password": "pw"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    for path in ("/api/v1/categories", "/api/v1/movements", "/api/v1/stops"):
        resp = await app_client.get(path, headers=h)
        assert resp.headers.get("cache-control") == "no-store", path


async def test_health_is_not_touched_by_the_api_no_store(app_client):
    """La regla es del prefijo /api/: el resto (SPA hasheada por Vite) sigue igual."""
    r = await app_client.get("/health")
    assert "cache-control" not in r.headers
