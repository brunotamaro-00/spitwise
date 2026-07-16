import asyncio
import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.andiamo import ensure_stops_fresh
from app.bot import copy
from app.bot.active_stop import resolve_trip_timezone
from app.users import username_for_wa_id
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


async def _notify_user(meta: MetaClient, wa_id: str, text: str) -> None:
    """Best-effort: si Meta también falla, solo logueamos."""
    try:
        await meta.send_text(wa_id, text)
    except Exception:
        logger.exception("webhook_notify_failed wa_id=%s", wa_id)


async def _react(meta: MetaClient, wa_id: str, wamid: str, emoji: str) -> None:
    """Best-effort: la reacción es cosmética, nunca voltea el flujo."""
    try:
        await meta.send_reaction(wa_id, wamid, emoji)
    except Exception:
        logger.warning("reaction_failed wamid=%s emoji=%r", wamid, emoji)


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
        # Reloj de arena mientras procesamos: feedback instantáneo en el chat.
        await _react(meta, m.wa_id, m.wamid, "⏳")
        async with _lock(m.wa_id):
            async with maker() as session:
                await ensure_stops_fresh(session)  # lazy TTL, no bloquea
                # La tz sale de la parada del remitente: durante Pititas, Katia
                # y Bruno están en husos distintos.
                tz = await resolve_trip_timezone(
                    session, await username_for_wa_id(session, m.wa_id)
                )
                reply = await dispatch(session, m.wa_id, m.type, m.text, m.interactive_id, today_in_tz(tz))
        try:
            if reply.buttons:
                await meta.send_buttons(m.wa_id, reply.text or "", reply.buttons)
            elif reply.text:
                await meta.send_text(m.wa_id, reply.text)
            # Respuesta enviada: el reloj pasa a tick verde.
            await _react(meta, m.wa_id, m.wamid, "✅")
        except Exception:
            logger.exception("webhook_send_failed wamid=%s", m.wamid)
            await _react(meta, m.wa_id, m.wamid, "")  # sin tick: no confirmamos de mentira
            # El gasto/acción pudo haberse persistido: avisamos para no reenviar a ciegas.
            home = copy.link_home()
            msg = copy.SAVED_BUT_UNCONFIRMED
            if home:
                msg = f"{msg}\n{home}"
            await _notify_user(meta, m.wa_id, msg)
    except Exception:
        logger.exception("webhook_background_error wamid=%s", m.wamid)
        await _react(meta, m.wa_id, m.wamid, "")  # limpiar el reloj: esto falló
        # Meta ya recibió 200 + wamid claimed: sin este aviso el mensaje se pierde en silencio.
        await _notify_user(meta, m.wa_id, copy.SOMETHING_FAILED)
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
