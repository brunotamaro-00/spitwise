import hashlib
import hmac
from dataclasses import dataclass


def verify_signature(app_secret: str, body: bytes, header: str | None) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len("sha256="):])


@dataclass
class MediaInfo:
    media_id: str
    mime_type: str | None = None
    caption: str | None = None
    filename: str | None = None


@dataclass
class IncomingMessage:
    wa_id: str
    wamid: str
    type: str
    text: str | None = None
    interactive_id: str | None = None
    media: MediaInfo | None = None


def iter_incoming_messages(payload: dict) -> list[IncomingMessage]:
    out: list[IncomingMessage] = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            for m in value.get("messages", []) or []:
                wa_id = m.get("from", "")
                wamid = m.get("id", "")
                mtype = m.get("type", "other")
                if mtype == "text":
                    out.append(IncomingMessage(wa_id, wamid, "text", text=(m.get("text") or {}).get("body")))
                elif mtype == "interactive":
                    inter = m.get("interactive", {}) or {}
                    reply = inter.get("button_reply") or inter.get("list_reply") or {}
                    out.append(IncomingMessage(wa_id, wamid, "interactive", interactive_id=reply.get("id")))
                elif mtype in ("image", "document"):
                    body = m.get(mtype) or {}
                    media = MediaInfo(
                        media_id=body.get("id", ""),
                        mime_type=body.get("mime_type"),
                        caption=body.get("caption"),
                        filename=body.get("filename"),
                    )
                    out.append(IncomingMessage(wa_id, wamid, mtype, media=media))
                elif mtype in ("audio", "video", "sticker"):
                    # Media que el bot no procesa: pasa con su tipo para que el
                    # dispatcher conteste algo útil (no "mensaje vacío").
                    out.append(IncomingMessage(wa_id, wamid, mtype))
                else:
                    out.append(IncomingMessage(wa_id, wamid, "other"))
    return out
