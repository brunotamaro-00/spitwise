from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import get_settings


def utcnow_naive() -> datetime:
    """Ahora en UTC, sin tzinfo. Es el reloj de todas las columnas DateTime del
    proyecto (`server_default=now()` de Postgres tampoco lleva tz) — Railway
    corre en UTC, así que app y DB miran el mismo reloj."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def today_in_tz(tz_name: str | None, *, now: datetime | None = None) -> date:
    """'Hoy' en la timezone del viaje. Nunca usar date.today() (UTC del server).

    En la demo pública el reloj está congelado (`DEMO_TODAY`): el itinerario no
    se corre solo, así que quien abra el link en noviembre ve el mismo viaje
    mid-trip que hoy. Andiamo congela el suyo con NEXT_PUBLIC_DEMO_TODAY y las
    dos variables llevan la misma fecha — si divergen, las apps muestran
    paradas actuales distintas. Es el único punto donde la web lee el reloj del
    viaje, así que alcanza con interceptarlo acá.
    """
    settings = get_settings()
    if settings.demo_mode and settings.demo_today:
        return date.fromisoformat(settings.demo_today)
    if now is None:
        now = datetime.now(timezone.utc)
    name = tz_name or get_settings().trip_default_timezone
    try:
        tz = ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        tz = ZoneInfo(get_settings().trip_default_timezone)
    return now.astimezone(tz).date()


def day_in_tz(dt: datetime, tz_name: str | None) -> date:
    """Día de un timestamp de carga (created_at, naive-UTC en DB) en la tz del viaje."""
    aware = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    name = tz_name or get_settings().trip_default_timezone
    try:
        tz = ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        tz = ZoneInfo(get_settings().trip_default_timezone)
    return aware.astimezone(tz).date()
