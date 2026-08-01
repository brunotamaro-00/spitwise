"""Canal notas: dictado por chat → preview + botones → alta en Andiamo.

Igual que el canal documentos, la escritura recién ocurre en el confirm: el
handler solo deja un pending. Y Spitwise nunca escribe `trip_notes` (eso es
cache del sync) — la fuente de verdad es Andiamo.
"""
from datetime import date

import pytest
from sqlalchemy import select

from app.andiamo_notes import AndiamoNoteError
from app.api.auth import hash_password
from app.bot.dispatcher import dispatch
from app.bot.interactive import handle_interactive
from app.bot.trip_notes import cancel_note, confirm_note, handle_note_capture
from app.db.models import BotPendingAction, Movement, Stop, TripNote, User
from app.llm.parser import ParsedMessage

TODAY = date(2026, 8, 6)


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    async def parse(self, text, **kwargs):
        return self.payload


class FakeAndiamo:
    """Registra las altas y, opcionalmente, falla las primeras N veces."""

    def __init__(self, fail_times=0):
        self.calls = []
        self.fail_times = fail_times

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) <= self.fail_times:
            raise AndiamoNoteError("boom")
        return {"id": "n-new", "stopSlug": kwargs.get("stop_slug"), "title": kwargs.get("title")}


@pytest.fixture(autouse=True)
def _andiamo_url(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("ANDIAMO_URL", "http://andiamo")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _setup(db_session):
    u1 = User(username="bruno", password_hash=hash_password("x"), whatsapp_wa_id="549111")
    u2 = User(username="katia", password_hash=hash_password("x"), whatsapp_wa_id="549222")
    db_session.add_all([u1, u2])
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    db_session.add_all([
        Stop(slug="roma", order=1, name="Roma", country="Italia",
             arrival_date=date(2026, 8, 1), departure_date=date(2026, 8, 10)),
        Stop(slug="florencia", order=2, name="Florencia", country="Italia",
             arrival_date=date(2026, 8, 10), departure_date=date(2026, 8, 14)),
    ])
    await db_session.commit()
    return u1, u2


def _parsed(**kw):
    return ParsedMessage(intent="trip_note", **kw)


async def _pendings(db_session):
    return (await db_session.execute(select(BotPendingAction))).scalars().all()


async def test_capture_creates_pending_with_buttons(db_session):
    u1, _ = await _setup(db_session)
    reply = await handle_note_capture(
        db_session, u1, _parsed(note_title="Hostel", note_body="Pide efectivo", city="Roma"), TODAY)
    assert "Hostel" in reply.text and "Pide efectivo" in reply.text and "Roma" in reply.text
    assert [b[1] for b in reply.buttons] == ["Guardar 📝", "Cancelar"]

    rows = await _pendings(db_session)
    assert len(rows) == 1 and rows[0].action_type == "note_create"
    # Preview: todavía no se escribió nada en Andiamo ni en el cache local.
    assert (await db_session.execute(select(TripNote))).scalars().all() == []


async def test_capture_without_city_uses_todays_stop(db_session):
    u1, _ = await _setup(db_session)
    reply = await handle_note_capture(
        db_session, u1, _parsed(note_body="Comprar adaptador"), TODAY)
    assert "Roma" in reply.text  # hoy cae en Roma
    import json
    payload = json.loads((await _pendings(db_session))[0].payload_json)
    assert payload["stop_slug"] == "roma"


async def test_capture_outside_itinerary_is_general(db_session):
    u1, _ = await _setup(db_session)
    reply = await handle_note_capture(
        db_session, u1, _parsed(note_body="Renovar el pasaporte"), date(2027, 1, 1))
    assert "General" in reply.text
    import json
    assert json.loads((await _pendings(db_session))[0].payload_json)["stop_slug"] is None


async def test_capture_without_body_asks_instead_of_saving(db_session):
    u1, _ = await _setup(db_session)
    reply = await handle_note_capture(db_session, u1, _parsed(note_title="Hostel"), TODAY)
    assert "anotar" in reply.text.lower()
    assert await _pendings(db_session) == []


async def test_confirm_posts_to_andiamo_and_closes_pending(db_session, monkeypatch):
    u1, _ = await _setup(db_session)
    fake = FakeAndiamo()
    monkeypatch.setattr("app.bot.trip_notes.create_note", fake)
    monkeypatch.setattr("app.andiamo_content.force_content_sync_soon", lambda **kw: None)

    await handle_note_capture(
        db_session, u1, _parsed(note_title="Hostel", note_body="Pide efectivo", city="Roma"), TODAY)
    token = (await _pendings(db_session))[0].token
    reply = await confirm_note(db_session, u1, token)

    assert fake.calls == [{"title": "Hostel", "body": "Pide efectivo",
                           "stop_slug": "roma", "client": None}]
    assert "guardada" in reply.text.lower()
    assert "http://andiamo/stops/roma" in reply.text
    assert (await _pendings(db_session))[0].confirmed_at is not None


async def test_confirm_retries_once_then_keeps_pending_open(db_session, monkeypatch):
    u1, _ = await _setup(db_session)
    fake = FakeAndiamo(fail_times=99)
    monkeypatch.setattr("app.bot.trip_notes.create_note", fake)

    await handle_note_capture(db_session, u1, _parsed(note_body="Algo"), TODAY)
    token = (await _pendings(db_session))[0].token
    reply = await confirm_note(db_session, u1, token)

    assert len(fake.calls) == 2  # un reintento inmediato
    assert "Guardar" in reply.text  # se invita a re-tocar el botón
    row = (await _pendings(db_session))[0]
    assert row.confirmed_at is None and row.cancelled_at is None


async def test_confirm_succeeds_on_retry(db_session, monkeypatch):
    u1, _ = await _setup(db_session)
    fake = FakeAndiamo(fail_times=1)
    monkeypatch.setattr("app.bot.trip_notes.create_note", fake)
    monkeypatch.setattr("app.andiamo_content.force_content_sync_soon", lambda **kw: None)

    await handle_note_capture(db_session, u1, _parsed(note_body="Algo"), TODAY)
    token = (await _pendings(db_session))[0].token
    reply = await confirm_note(db_session, u1, token)
    assert len(fake.calls) == 2 and "guardada" in reply.text.lower()


async def test_confirm_rejects_other_users_pending(db_session, monkeypatch):
    u1, u2 = await _setup(db_session)
    fake = FakeAndiamo()
    monkeypatch.setattr("app.bot.trip_notes.create_note", fake)

    await handle_note_capture(db_session, u1, _parsed(note_body="Algo"), TODAY)
    token = (await _pendings(db_session))[0].token
    reply = await confirm_note(db_session, u2, token)
    assert fake.calls == [] and "Expiró" in reply.text


async def test_cancel_leaves_nothing(db_session, monkeypatch):
    u1, _ = await _setup(db_session)
    fake = FakeAndiamo()
    monkeypatch.setattr("app.bot.trip_notes.create_note", fake)

    await handle_note_capture(db_session, u1, _parsed(note_body="Algo"), TODAY)
    token = (await _pendings(db_session))[0].token
    await cancel_note(db_session, u1, token)
    assert fake.calls == []
    assert (await _pendings(db_session))[0].cancelled_at is not None


async def test_buttons_route_to_the_note_channel(db_session, monkeypatch):
    u1, _ = await _setup(db_session)
    fake = FakeAndiamo()
    monkeypatch.setattr("app.bot.trip_notes.create_note", fake)
    monkeypatch.setattr("app.andiamo_content.force_content_sync_soon", lambda **kw: None)

    await handle_note_capture(db_session, u1, _parsed(note_body="Algo"), TODAY)
    token = (await _pendings(db_session))[0].token
    reply = await handle_interactive(db_session, u1, "549111", f"note_save:{token}", TODAY)
    assert len(fake.calls) == 1 and "guardada" in reply.text.lower()


async def test_dispatch_routes_trip_note_and_creates_no_movement(db_session):
    """El borde caro: una nota con un número adentro no es un gasto."""
    await _setup(db_session)
    payload = {"intent": "trip_note", "note_title": "Hostel",
               "note_body": "Cobra 20 en efectivo", "city": "Roma"}
    reply = await dispatch(db_session, "549111", "text",
                           "anotá que el hostel cobra 20 en efectivo", None, TODAY,
                           llm_client=FakeLLM(payload))
    assert "Hostel" in reply.text
    assert (await db_session.execute(select(Movement))).scalars().all() == []
    assert (await _pendings(db_session))[0].action_type == "note_create"


async def test_capture_without_andiamo_says_so(db_session, monkeypatch):
    u1, _ = await _setup(db_session)
    from app.config import get_settings
    monkeypatch.setenv("ANDIAMO_URL", "")
    get_settings.cache_clear()
    reply = await handle_note_capture(db_session, u1, _parsed(note_body="Algo"), TODAY)
    assert "Andiamo" in reply.text
    assert await _pendings(db_session) == []
