from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import get_settings


def today_in_tz(tz_name: str | None, *, now: datetime | None = None) -> date:
    """'Hoy' en la timezone del viaje. Nunca usar date.today() (UTC del server)."""
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
