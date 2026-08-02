import httpx

# Límites reales de la Cloud API. Pasarse es un 400 de Graph: el usuario se
# queda sin respuesta aunque el gasto ya esté guardado. Truncar es feo pero
# recuperable; perder la respuesta, no.
_TEXT_LIMIT = 4096
_BUTTONS_BODY_LIMIT = 1024


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit - 1] + "…"


class MetaClient:
    def __init__(self, access_token: str, phone_number_id: str, graph_version: str = "v21.0") -> None:
        self._token = access_token
        self._graph_base = f"https://graph.facebook.com/{graph_version}"
        self._url = f"{self._graph_base}/{phone_number_id}/messages"
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
            "text": {"body": _clip(text, _TEXT_LIMIT)},
        })

    async def send_buttons(self, wa_id: str, text: str, buttons: list[tuple[str, str]]) -> None:
        await self._post({
            "messaging_product": "whatsapp", "to": wa_id, "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": _clip(text, _BUTTONS_BODY_LIMIT)},
                "action": {"buttons": [
                    {"type": "reply", "reply": {"id": bid, "title": label[:20]}}
                    for bid, label in buttons[:3]
                ]},
            },
        })

    async def download_media(self, media_id: str) -> tuple[bytes, str | None]:
        """Baja un adjunto de la Graph API: GET /{media_id} da una URL lookaside
        efímera (~5 min) que se descarga con el mismo Bearer token."""
        headers = {"Authorization": f"Bearer {self._token}"}
        meta = await self._client.get(f"{self._graph_base}/{media_id}", headers=headers)
        meta.raise_for_status()
        info = meta.json()
        blob = await self._client.get(info["url"], headers=headers, timeout=60.0)
        blob.raise_for_status()
        return blob.content, info.get("mime_type")

    async def aclose(self) -> None:
        await self._client.aclose()
