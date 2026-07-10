from datetime import datetime, timezone

from app.trip_time import today_in_tz

# 2026-08-05 22:30 UTC == 2026-08-06 00:30 en Madrid (CEST, UTC+2)
#                       == 2026-08-05 23:30 en Londres (BST, UTC+1)
_NOW = datetime(2026, 8, 5, 22, 30, tzinfo=timezone.utc)


def test_today_crosses_midnight_in_local_tz():
    assert today_in_tz("Europe/Madrid", now=_NOW).isoformat() == "2026-08-06"
    # Londres (UTC+1 en agosto) sigue en el día 5.
    assert today_in_tz("Europe/London", now=_NOW).isoformat() == "2026-08-05"


def test_invalid_or_missing_tz_falls_back_to_default():
    assert today_in_tz(None, now=_NOW).isoformat() == "2026-08-06"      # Madrid
    assert today_in_tz("No/Existe", now=_NOW).isoformat() == "2026-08-06"
