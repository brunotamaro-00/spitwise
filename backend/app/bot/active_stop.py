import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WhatsAppSessionState


async def _get_state(session: AsyncSession, wa_id: str) -> WhatsAppSessionState | None:
    return (
        await session.execute(select(WhatsAppSessionState).where(WhatsAppSessionState.wa_id == wa_id))
    ).scalar_one_or_none()


def _pick_stop(stops, d: date):
    """Parada activa 'hoy': rango arrival<=d<departure, o la última arribada (gaps/tránsito)."""
    for s in stops:
        if s.arrival_date and s.departure_date and s.arrival_date <= d < s.departure_date:
            return s
    arrived = [s for s in stops if s.arrival_date and s.arrival_date <= d]
    return arrived[-1] if arrived else stops[0]


def _stop_in_range(stops, d: date):
    """Parada estricta: solo si d cae en [arrival, departure). Gaps y post-viaje => None."""
    for s in stops:
        if s.arrival_date and s.departure_date and s.arrival_date <= d < s.departure_date:
            return s
        # Sin departure_date: vigente desde arrival en adelante.
        if s.arrival_date and not s.departure_date and s.arrival_date <= d:
            return s
    return None


async def _load_stops(session: AsyncSession):
    from app.db.models import Stop
    stops = (await session.execute(select(Stop).order_by(Stop.arrival_date))).scalars().all()
    if not stops:
        # Snapshot vacío (p.ej. el sync del startup corrió antes de que Andiamo
        # tuviera la key): intentar un sync inline; si falla, sigue sin ciudad.
        from app.andiamo import sync_stops
        from app.config import get_settings
        if get_settings().andiamo_url:
            await sync_stops(session)
            stops = (await session.execute(select(Stop).order_by(Stop.arrival_date))).scalars().all()
    return list(stops)


async def stop_for_date(session: AsyncSession, d: date):
    """Stop 'activo' (leniente) para timezone / WhatsApp hoy. Ver place_for_date para imputación."""
    stops = await _load_stops(session)
    return _pick_stop(stops, d) if stops else None


async def place_for_date(session: AsyncSession, d: date):
    """Stop para imputar un gasto a una fecha (bot backdate + API web). Estricto: fuera de rango => None."""
    stops = await _load_stops(session)
    return _stop_in_range(stops, d) if stops else None

async def resolve_active_stop(session: AsyncSession, wa_id: str, today: date):
    # 1) Override de sesión (day-trips).
    st = await _get_state(session, wa_id)
    if st:
        data = json.loads(st.payload_json or "{}")
        ov = data.get("active_stop")
        if ov:
            return ov.get("stop_slug"), ov.get("city_name"), ov.get("currency_code", "USD")

    # 2/3) Derivar de stops por fecha.
    current = await stop_for_date(session, today)
    if current is None:
        return None, None, "USD"
    return current.slug, current.name, (current.currency_code or "USD")


async def resolve_trip_timezone(session: AsyncSession) -> str | None:
    """Timezone de la parada activa por fecha (para today_in_tz). None => fallback default."""
    from datetime import datetime, timezone as _tz
    from zoneinfo import ZoneInfo

    from app.config import get_settings

    # Aproximación de "hoy" con la tz default para elegir la parada (el error de ±1h no cambia la parada).
    probe = datetime.now(_tz.utc).astimezone(ZoneInfo(get_settings().trip_default_timezone)).date()
    current = await stop_for_date(session, probe)
    return current.timezone if current else None


async def get_state_payload(session: AsyncSession, wa_id: str) -> dict:
    st = await _get_state(session, wa_id)
    return json.loads(st.payload_json or "{}") if st else {}


async def update_state_payload(session: AsyncSession, wa_id: str, **keys) -> None:
    """Mergea claves en el payload de sesión sin pisar las demás (active_stop,
    qa_history, etc. conviven)."""
    st = await _get_state(session, wa_id)
    if st is None:
        session.add(WhatsAppSessionState(wa_id=wa_id, owner=wa_id, payload_json=json.dumps(keys)))
    else:
        data = json.loads(st.payload_json or "{}")
        data.update(keys)
        st.payload_json = json.dumps(data)
    await session.commit()


async def set_active_stop_override(session, wa_id, stop_slug, city_name, currency_code):
    await update_state_payload(
        session, wa_id,
        active_stop={"stop_slug": stop_slug, "city_name": city_name, "currency_code": currency_code},
    )
