import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WhatsAppSessionState


async def _get_state(session: AsyncSession, wa_id: str) -> WhatsAppSessionState | None:
    return (
        await session.execute(select(WhatsAppSessionState).where(WhatsAppSessionState.wa_id == wa_id))
    ).scalar_one_or_none()


async def resolve_active_stop(session: AsyncSession, wa_id: str, today: date):
    # 1) Override de sesión (day-trips).
    st = await _get_state(session, wa_id)
    if st:
        data = json.loads(st.payload_json or "{}")
        ov = data.get("active_stop")
        if ov:
            return ov.get("stop_slug"), ov.get("city_name"), ov.get("currency_code", "USD")

    # 2/3) Derivar de stops por fecha.
    from app.db.models import Stop
    stops = (await session.execute(select(Stop).order_by(Stop.arrival_date))).scalars().all()
    if not stops:
        return None, None, "USD"

    current = None
    for s in stops:
        if s.arrival_date and s.departure_date and s.arrival_date <= today < s.departure_date:
            current = s
            break
    if current is None:
        arrived = [s for s in stops if s.arrival_date and s.arrival_date <= today]
        current = arrived[-1] if arrived else stops[0]

    return current.slug, current.name, (current.currency_code or "USD")


async def resolve_trip_timezone(session: AsyncSession) -> str | None:
    """Timezone de la parada activa por fecha (para today_in_tz). None => fallback default."""
    from datetime import datetime, timezone as _tz
    from zoneinfo import ZoneInfo

    from app.config import get_settings
    from app.db.models import Stop

    stops = (await session.execute(select(Stop).order_by(Stop.arrival_date))).scalars().all()
    if not stops:
        return None
    # Aproximación de "hoy" con la tz default para elegir la parada (el error de ±1h no cambia la parada).
    probe = datetime.now(_tz.utc).astimezone(ZoneInfo(get_settings().trip_default_timezone)).date()
    for s in stops:
        if s.arrival_date and s.departure_date and s.arrival_date <= probe < s.departure_date:
            return s.timezone
    arrived = [s for s in stops if s.arrival_date and s.arrival_date <= probe]
    return (arrived[-1] if arrived else stops[0]).timezone


async def set_active_stop_override(session, wa_id, stop_slug, city_name, currency_code):
    st = await _get_state(session, wa_id)
    payload = {"active_stop": {"stop_slug": stop_slug, "city_name": city_name, "currency_code": currency_code}}
    if st is None:
        session.add(WhatsAppSessionState(wa_id=wa_id, owner=wa_id, payload_json=json.dumps(payload)))
    else:
        st.payload_json = json.dumps(payload)
    await session.commit()
