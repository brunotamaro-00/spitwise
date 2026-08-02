"""Truncado defensivo a los límites de la Cloud API.

Pasarse es un 400 de Graph: el usuario se queda sin respuesta aunque el gasto
ya esté guardado."""
from app.whatsapp.meta_client import _BUTTONS_BODY_LIMIT, _TEXT_LIMIT, MetaClient


class Spy(MetaClient):
    def __init__(self):
        super().__init__("tok", "123")
        self.payloads = []

    async def _post(self, payload: dict) -> None:
        self.payloads.append(payload)


async def test_send_text_clips_at_the_meta_limit():
    spy = Spy()
    await spy.send_text("549110", "a" * (_TEXT_LIMIT + 500))
    body = spy.payloads[0]["text"]["body"]
    assert len(body) == _TEXT_LIMIT and body.endswith("…")
    await spy.aclose()


async def test_send_buttons_clips_the_body():
    spy = Spy()
    await spy.send_buttons("549110", "b" * (_BUTTONS_BODY_LIMIT + 10),
                           [("del_confirm:t", "Borrar 🗑️")])
    body = spy.payloads[0]["interactive"]["body"]["text"]
    assert len(body) == _BUTTONS_BODY_LIMIT and body.endswith("…")
    await spy.aclose()


async def test_short_messages_are_untouched():
    spy = Spy()
    await spy.send_text("549110", "Listo ✅")
    await spy.send_buttons("549110", "¿Borrar?", [("del_confirm:t", "Borrar")])
    assert spy.payloads[0]["text"]["body"] == "Listo ✅"
    assert spy.payloads[1]["interactive"]["body"]["text"] == "¿Borrar?"
    await spy.aclose()
