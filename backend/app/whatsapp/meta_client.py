import httpx


class MetaClient:
    def __init__(self, access_token: str, phone_number_id: str, graph_version: str = "v21.0") -> None:
        self._token = access_token
        self._url = f"https://graph.facebook.com/{graph_version}/{phone_number_id}/messages"
        self._client = httpx.AsyncClient(timeout=15.0)

    async def _post(self, payload: dict) -> None:
        headers = {"Authorization": f"Bearer {self._token}"}
        resp = await self._client.post(self._url, json=payload, headers=headers)
        resp.raise_for_status()

    async def send_typing(self, message_id: str) -> None:
        """Marca el mensaje como leído y muestra 'escribiendo…' (hasta 25s o
        hasta que se envía la respuesta)."""
        await self._post({
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
            "typing_indicator": {"type": "text"},
        })

    async def send_reaction(self, wa_id: str, message_id: str, emoji: str) -> None:
        """Reacciona al mensaje del usuario (emoji="" quita la reacción)."""
        await self._post({
            "messaging_product": "whatsapp", "to": wa_id, "type": "reaction",
            "reaction": {"message_id": message_id, "emoji": emoji},
        })

    async def send_text(self, wa_id: str, text: str) -> None:
        await self._post({
            "messaging_product": "whatsapp", "to": wa_id, "type": "text",
            "text": {"body": text},
        })

    async def send_buttons(self, wa_id: str, text: str, buttons: list[tuple[str, str]]) -> None:
        await self._post({
            "messaging_product": "whatsapp", "to": wa_id, "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": text},
                "action": {"buttons": [
                    {"type": "reply", "reply": {"id": bid, "title": label[:20]}}
                    for bid, label in buttons[:3]
                ]},
            },
        })

    async def aclose(self) -> None:
        await self._client.aclose()
