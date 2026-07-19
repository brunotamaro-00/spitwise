"""Liquidación lazy de gastos pendientes (payment_date futura).

Un pending nace con TC proxy de su fecha de carga; cuando llega su fecha de
pago, acá se recalcula con el TC real de ese día y pasa a confirmed —
silencioso, sin mensajes. Sin cron: el proceso es único (invariante del
deploy), así que alcanza con colgar `ensure_due_settled` de los puntos de
tráfico (webhook del bot, lecturas de la API, lifespan) con un throttle
módulo-level, mismo patrón que `andiamo.ensure_stops_fresh`.
"""
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Movement
from app.fx import get_rate_to_usd

logger = logging.getLogger(__name__)

_TWO = Decimal("0.01")
_CHECK_TTL = timedelta(minutes=15)
_last_check: datetime | None = None


async def settle_due_movements(session: AsyncSession, today: date) -> int:
    """Confirma los pending con payment_date <= today recalculando el TC real
    de esa fecha. Idempotente (solo toca status='pending'). Reglas:

    - fx_source == 'manual' → flip a confirmed SIN recalcular (invariante 6).
    - Tasa 'fallback' (Frankfurter caído) → NO tocar: sigue pending y se
      reintenta en el próximo touch. Nunca confirmar con fallback.
    - ARS: dolarapi solo publica MEP vivo → se confirma con la tasa del día en
      que corre esta pasada (limitación documentada en fx.fx_reference_date).

    Devuelve cuántos confirmó.
    """
    from app.bot.capture import _map_source

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
            mv.fx_source = _map_source(src, mv.currency)
            mv.amount_usd = (Decimal(mv.amount) * rate).quantize(_TWO, rounding=ROUND_HALF_UP)
        mv.status = "confirmed"
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
    except Exception:
        logger.exception("due_settle_failed")
        await session.rollback()
