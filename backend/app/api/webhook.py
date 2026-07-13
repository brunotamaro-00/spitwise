import asyncio
import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.andiamo import ensure_stops_fresh
from app.bot.active_stop import resolve_trip_timezone
from app.bot.dispatcher import dispatch
from app.config import get_settings
from app.db.engine import get_session, get_sessionmaker
from app.trip_time import today_in_tz
from app.whatsapp.dedupe import claim_wamid
from app.whatsapp.meta_client import MetaClient
from app.whatsapp.verify import IncomingMessage, iter_incoming_messages, verify_signature

router = APIRouter(prefix="/webhooks", tags=["webhook"])
logger = logging.getLogger(__name__)

# Locks por chat: válidos porque Railway corre un único proceso persistente.
_wa_locks: dict[str, asyncio.Lock] = {}


def _lock(wa_id: str) -> asyncio.Lock:
    lock = _wa_locks.get(wa_id)
    if lock is None:
        lock = asyncio.Lock()
        _wa_locks[wa_id] = lock
    return lock


@router.get("/whatsapp")
async def verify(request: Request) -> Response:
    s = get_settings()
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == s.whatsapp_verify_token:
        return PlainTextResponse(params.get("hub.challenge", ""))
    return Response(status_code=403)


async def process_message(m: IncomingMessage) -> None:
    """Corre en background: LLM + FX + respuesta por Graph, fuera del camino del 200."""
    s = get_settings()
    meta = MetaClient(s.whatsapp_access_token, s.whatsapp_phone_number_id, s.whatsapp_graph_version)
    maker = get_sessionmaker()
    try:
        # 'Escribiendo…' + visto apenas entra el mensaje; si falla, seguimos igual.
        try:
            await meta.send_typing(m.wamid)
        except Exception:
            logger.warning("typing_indicator_failed wamid=%s", m.wamid)
        async with _lock(m.wa_id):
            async with maker() as session:
                await ensure_stops_fresh(session)  # lazy TTL, no bloquea
                tz = await resolve_trip_timezone(session)
                reply = await dispatch(session, m.wa_id, m.type, m.text, m.interactive_id, today_in_tz(tz))
        if reply.buttons:
            await meta.send_buttons(m.wa_id, reply.text or "", reply.buttons)
        elif reply.text:
            await meta.send_text(m.wa_id, reply.text)
    except Exception:
        logger.exception("webhook_background_error wamid=%s", m.wamid)
    finally:
        await meta.aclose()


@router.post("/whatsapp")
async def receive(
    request: Request,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> Response:
    s = get_settings()
    body = await request.body()
    sig = request.headers.get("X-Hub-Signature-256")
    # Siempre verificar salvo dev explícito sin secret configurado.
    if s.whatsapp_app_secret or s.environment != "dev":
        if not verify_signature(s.whatsapp_app_secret, body, sig):
            return Response(status_code=403)

    payload = json.loads(body or b"{}")
    # Camino síncrono mínimo: dedupe + encolar. Meta exige 2xx en ~5s.
    for m in iter_incoming_messages(payload):
        if not await claim_wamid(session, m.wamid):
            continue  # reintento at-least-once de Meta: ya lo procesamos/estamos procesando
        background.add_task(process_message, m)
    return Response(content='{"status":"ok"}', media_type="application/json")
