import json


async def test_verify_challenge(app_client, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "vtok")
    get_settings.cache_clear()
    r = await app_client.get("/webhooks/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": "vtok", "hub.challenge": "12345",
    })
    assert r.status_code == 200
    assert r.text == "12345"
    get_settings.cache_clear()


async def test_post_ignores_bad_signature(app_client, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "s3cr3t")
    monkeypatch.setenv("ENVIRONMENT", "prod")
    get_settings.cache_clear()
    body = json.dumps({"entry": []}).encode()
    r = await app_client.post("/webhooks/whatsapp", content=body, headers={"X-Hub-Signature-256": "sha256=bad"})
    # Firma inválida => 403, sin procesar.
    assert r.status_code == 403
    get_settings.cache_clear()
