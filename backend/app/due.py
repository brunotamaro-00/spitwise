"""Liquidación lazy de gastos pendientes (payment_date futura).

Un pending nace con TC proxy de su fecha de carga; cuando llega su fecha de
pago, acá se recalcula con el TC real de ese día y pasa a `awaiting` —
silencioso, sin mensajes. `awaiting` = TC lockeado, esperando confirmación
manual en la web (`POST /movements/{id}/confirm`): recién ahí valida el
pagador y pasa a `confirmed`. Un `awaiting` NO entra al balance todavía (lo
excluye `compute_balance` junto con `pending`).

Se flipea a `awaiting` una sola vez (el query filtra solo `pending`), así que
el FX no se recalcula en cada corrida — clave para ARS, cuyo MEP es vivo y
driftearía si se re-liquidara. Sin cron: el proceso es único (invariante del
deploy), así que alcanza con colgar `ensure_due_settled` de los puntos de
tráfico (webhook del bot, lecturas de la API, lifespan) con un throttle
módulo-level, mismo patrón que `andiamo.ensure_stops_fresh`.
"""
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cashback import net_amount
from app.db.models import Movement
from app.fx import get_rate_to_usd, map_fx_source

logger = logging.getLogger(__name__)

_TWO = Decimal("0.01")
_CHECK_TTL = timedelta(minutes=15)
_last_check: datetime | None = None

# Estados que todavía no entran al balance (espejo de balance.UNSETTLED).
UNSETTLED = frozenset({"pending", "awaiting"})


def next_status_for_date(current: str, payment_date: date | None, today: date) -> str:
    """Status que corresponde tras cambiar la fecha de pago de un movimiento.

    Fecha futura → `pending` siempre (vuelve a la cola de liquidación). Fecha
    pasada o vacía → `confirmed`, EXCEPTO si venía en `awaiting`: ese ya venció
    y está esperando confirmación manual, que es la única vía válida para que
    entre al balance (invariante 4). Derivar el status solo de la fecha dejaba
    que "en realidad se pagó el 3-sep" confirmara el gasto de prepo, salteando
    el banner y sin validar quién pagó.
    """
    if payment_date is not None and payment_date > today:
        return "pending"
    return "awaiting" if current == "awaiting" else "confirmed"


async def settle_due_movements(session: AsyncSession, today: date) -> int:
    """Liquida los pending con payment_date <= today recalculando el TC real
    de esa fecha y dejándolos en `awaiting` (esperan confirmación manual, no
    entran al balance todavía). Idempotente (solo toca status='pending').
    Reglas:

    - fx_source == 'manual' → flip a awaiting SIN recalcular (invariante 6).
    - Tasa 'fallback' (Frankfurter caído) → NO tocar: sigue pending y se
      reintenta en el próximo touch. Nunca liquidar con fallback.
    - ARS: dolarapi solo publica MEP vivo → se liquida con la tasa del día en
      que corre esta pasada (limitación documentada en fx.fx_reference_date).

    Devuelve cuántos liquidó.
    """
    rows = (await session.execute(
        select(Movement).where(Movement.status == "pending", Movement.payment_date <= today)
    )).scalars().all()
    settled = 0
    for mv in rows:
        if mv.fx_source != "manual":
            rate, src = await get_rate_to_usd(session, mv.currency, mv.payment_date)
            if src == "fallback":
                continue
            mv.fx_rate = rate
            mv.fx_source = map_fx_source(src, mv.currency)
            net = net_amount(Decimal(mv.amount), mv.cashback_kind, mv.cashback_value)
            mv.amount_usd = (net * rate).quantize(_TWO, rounding=ROUND_HALF_UP)
        mv.status = "awaiting"
        settled += 1
    if settled:
        await session.commit()
    return settled


async def ensure_due_settled(session: AsyncSession, today: date | None = None) -> None:
    """Pasada throttled (15 min) de settle_due_movements. Nunca voltea el
    request que la dispara; los fallidos reintentan en el próximo TTL. Sin
    `today` explícito usa la fecha del viaje (tz de la parada activa)."""
    global _last_check
    now = datetime.utcnow()
    if _last_check is not None and now - _last_check < _CHECK_TTL:
        return
    _last_check = now
    try:
        if today is None:
            from app.bot.active_stop import resolve_trip_timezone
            from app.trip_time import today_in_tz

            today = today_in_tz(await resolve_trip_timezone(session, None))
        n = await settle_due_movements(session, today)
        if n:
            logger.info("due_settled count=%d", n)
        # Sin cron en el proyecto: la limpieza de las tablas de servicio se
        # cuelga acá, que ya viene con throttle. Sin esto crecían para siempre.
        from app.bot.pending import purge_closed
        from app.whatsapp.dedupe import purge_old

        purged = await purge_old(session)
        if purged:
            logger.info("dedupe_purged count=%d", purged)
        purged = await purge_closed(session)
        if purged:
            logger.info("pendings_purged count=%d", purged)
    except Exception:
        logger.exception("due_settle_failed")
        await session.rollback()
