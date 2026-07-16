"""Coreografía de reacciones del webhook: ⏳ al procesar, ✅ al responder,
y sin reacción colgada si el envío falla."""
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import webhook
from app.bot.render import text_reply
from app.db.models import Base
from app.whatsapp.verify import IncomingMessage


class FakeMeta:
    def __init__(self, *a, **kw):
        self.calls: list[tuple] = []
        self.fail_send = False

    async def send_typing(self, message_id):
        self.calls.append(("typing", message_id))

    async def send_reaction(self, wa_id, message_id, emoji):
        self.calls.append(("react", emoji))

    async def send_text(self, wa_id, text):
        if self.fail_send:
            raise RuntimeError("boom")
        self.calls.append(("text", text))

    async def send_buttons(self, wa_id, text, buttons):
        self.calls.append(("buttons", text))

    async def aclose(self):
        self.calls.append(("close",))


@pytest.fixture
def fake_env(monkeypatch):
    """process_message con Meta, sessionmaker y dispatch falsos."""
    meta = FakeMeta()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr(webhook, "MetaClient", lambda *a, **kw: meta)
    monkeypatch.setattr(webhook, "get_sessionmaker", lambda: maker)

    async def fake_stops(session):
        return None

    async def fake_tz(session, username=None):
        return "UTC"

    monkeypatch.setattr(webhook, "ensure_stops_fresh", fake_stops)
    monkeypatch.setattr(webhook, "resolve_trip_timezone", fake_tz)
    monkeypatch.setattr(webhook, "today_in_tz", lambda tz: date(2026, 8, 6))
    return meta, init, monkeypatch


def _msg():
    return IncomingMessage(wamid="wamid.1", wa_id="549110", type="text",
                           text="saldo", interactive_id=None)


async def test_reaccion_reloj_y_tick(fake_env):
    meta, init, monkeypatch = fake_env
    await init()

    async def fake_dispatch(*a, **kw):
        return text_reply("respuesta")

    monkeypatch.setattr(webhook, "dispatch", fake_dispatch)
    await webhook.process_message(_msg())
    reacts = [c for c in meta.calls if c[0] == "react"]
    assert reacts == [("react", "⏳"), ("react", "✅")]
    assert ("text", "respuesta") in meta.calls


async def test_envio_fallido_limpia_reaccion(fake_env):
    meta, init, monkeypatch = fake_env
    await init()

    async def fake_dispatch(*a, **kw):
        return text_reply("respuesta")

    monkeypatch.setattr(webhook, "dispatch", fake_dispatch)
    meta.fail_send = True
    await webhook.process_message(_msg())
    reacts = [c for c in meta.calls if c[0] == "react"]
    # Nunca ✅ si el envío falló: el reloj se quita (emoji vacío).
    assert reacts == [("react", "⏳"), ("react", "")]


async def test_error_de_fondo_limpia_reaccion(fake_env):
    meta, init, monkeypatch = fake_env
    await init()

    async def boom(*a, **kw):
        raise RuntimeError("dispatch roto")

    monkeypatch.setattr(webhook, "dispatch", boom)
    await webhook.process_message(_msg())
    reacts = [c for c in meta.calls if c[0] == "react"]
    assert reacts == [("react", "⏳"), ("react", "")]
    assert meta.calls[-1] == ("close",)
