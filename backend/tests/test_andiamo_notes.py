"""Contrato HTTP del alta de notas contra Andiamo (POST /api/integration/notes)."""
import httpx
import pytest

from app.andiamo_notes import AndiamoNoteError, create_note


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("ANDIAMO_URL", "http://andiamo")
    monkeypatch.setenv("TRIP_SHARED_API_KEY", "k")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _client(seen: list, status=200, payload=None):
    def handler(request):
        seen.append(request)
        return httpx.Response(status, json=payload if payload is not None else {"id": "n1"})
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://andiamo")


async def test_create_note_posts_json_with_api_key():
    seen: list = []
    async with _client(seen) as c:
        out = await create_note(title="Hostel", body="Pide efectivo",
                                stop_slug="roma", client=c)
    assert out == {"id": "n1"}
    req = seen[0]
    assert req.method == "POST"
    assert str(req.url) == "http://andiamo/api/integration/notes"
    assert req.headers["X-Api-Key"] == "k"
    import json
    assert json.loads(req.content) == {
        "title": "Hostel", "body": "Pide efectivo", "pinned": False, "stopSlug": "roma",
    }


async def test_create_note_omits_stop_slug_when_general():
    seen: list = []
    async with _client(seen) as c:
        await create_note(title=None, body="Renovar pasaporte", stop_slug=None, client=c)
    import json
    body = json.loads(seen[0].content)
    assert "stopSlug" not in body and body["title"] == ""


async def test_create_note_raises_on_non_2xx():
    seen: list = []
    async with _client(seen, status=422, payload={"error": "stop desconocido: atlantis"}) as c:
        with pytest.raises(AndiamoNoteError):
            await create_note(title="x", body="y", stop_slug="atlantis", client=c)


async def test_create_note_requires_andiamo_url(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("ANDIAMO_URL", "")
    get_settings.cache_clear()
    with pytest.raises(AndiamoNoteError):
        await create_note(title="x", body="y", stop_slug=None)
