async def test_health(app_client):
    r = await app_client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
