import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WhatsAppSessionState


async def _get_state(session: AsyncSession, wa_id: str) -> WhatsAppSessionState | None:
    return (
        await session.execute(select(WhatsAppSessionState).where(WhatsAppSessionState.wa_id == wa_id))
    ).scalar_one_or_none()


def _by_priority(stops):
    """Un stop propio del usuario gana sobre el compartido cuando solapan (p.ej.
    Pititas vs Portugal del 4 al 11 de sept). Sin esto el empate sería arbitrario.
    sorted() es estable: dentro de cada grupo se mantiene el orden por fecha."""
    return sorted(stops, key=lambda s: (s.owner_username is None,))


def _pick_stop(stops, d: date):
    """Parada activa 'hoy': rango arrival<=d<departure, o la última arribada (gaps/tránsito)."""
    for s in _by_priority(stops):
        if s.arrival_date and s.departure_date and s.arrival_date <= d < s.departure_date:
            return s
    arrived = [s for s in stops if s.arrival_date and s.arrival_date <= d]
    if not arrived:
        return stops[0]
    # Última arribada; si varias comparten fecha (Pititas y Portugal empiezan el
    # mismo día), gana la propia del usuario.
    latest = max(s.arrival_date for s in arrived)
    return _by_priority([s for s in arrived if s.arrival_date == latest])[0]


def _stop_in_range(stops, d: date):
    """Parada estricta: solo si d cae en [arrival, departure). Gaps y post-viaje => None."""
    for s in _by_priority(stops):
        if s.arrival_date and s.departure_date and s.arrival_date <= d < s.departure_date:
            return s
        # Sin departure_date: vigente desde arrival en adelante.
        if s.arrival_date and not s.departure_date and s.arrival_date <= d:
            return s
    return None


async def visible_stops(session: AsyncSession, username: str | None = None) -> list:
    """Stops visibles para imputar los gastos de `username`.

    Los stops con owner_username solo aplican a su dueño. Sin username (contextos
    sin usuario, p.ej. la timezone del viaje) se descartan todos: nunca se imputa
    a una parada ajena por defecto.
    """
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
    u = (username or "").strip().lower() or None
    return [s for s in stops if s.owner_username is None or s.owner_username == u]


async def stop_for_date(session: AsyncSession, d: date, username: str | None = None):
    """Stop 'activo' (leniente) para timezone / WhatsApp hoy. Ver place_for_date para imputación."""
    stops = await visible_stops(session, username)
    return _pick_stop(stops, d) if stops else None


async def place_for_date(session: AsyncSession, d: date, username: str | None = None):
    """Stop para imputar un gasto a una fecha (bot + API web). Estricto: fuera de rango => None."""
    stops = await visible_stops(session, username)
    return _stop_in_range(stops, d) if stops else None

async def resolve_trip_timezone(session: AsyncSession, username: str | None = None) -> str | None:
    """Timezone de la parada activa por fecha (para today_in_tz). None => fallback default.

    Con username, respeta su parada propia: durante Pititas (Europe/Paris) el
    'hoy' de Katia no lo define Portugal (Europe/Lisbon), que va una hora atrás.
    """
    from datetime import datetime, timezone as _tz
    from zoneinfo import ZoneInfo

    from app.config import get_settings

    # Aproximación de "hoy" con la tz default para elegir la parada (el error de ±1h no cambia la parada).
    probe = datetime.now(_tz.utc).astimezone(ZoneInfo(get_settings().trip_default_timezone)).date()
    current = await stop_for_date(session, probe, username)
    return current.timezone if current else None


async def get_state_payload(session: AsyncSession, wa_id: str) -> dict:
    st = await _get_state(session, wa_id)
    return json.loads(st.payload_json or "{}") if st else {}


async def update_state_payload(session: AsyncSession, wa_id: str, **keys) -> None:
    """Mergea claves en el payload de sesión sin pisar las demás (qa_history, etc.)."""
    st = await _get_state(session, wa_id)
    if st is None:
        session.add(WhatsAppSessionState(wa_id=wa_id, owner=wa_id, payload_json=json.dumps(keys)))
    else:
        data = json.loads(st.payload_json or "{}")
        data.update(keys)
        st.payload_json = json.dumps(data)
    await session.commit()
