from app.config import get_settings


def test_settings_defaults():
    s = get_settings()
    assert s.frankfurter_url.startswith("https://")
    # Fallback USD siempre presente y = 1.
    assert s.fx_fallback_rates["USD"] == "1.0"
    assert "GBP" in s.fx_fallback_rates


def test_demo_today_freezes_the_trip_clock(monkeypatch):
    """La demo publica un viaje mid-trip que no se puede correr solo.

    `today_in_tz` es el único punto donde la web lee el reloj del viaje, así que
    es acá o en ningún lado. Si esto se rompe, la demo abre diciendo que el viaje
    todavía no empezó y deja de coincidir con Andiamo.
    """
    from datetime import date

    import app.trip_time as trip_time

    real = trip_time.today_in_tz("Europe/Madrid")

    s = get_settings()
    monkeypatch.setattr(s, "demo_mode", True)
    monkeypatch.setattr(s, "demo_today", "2026-09-25")
    assert trip_time.today_in_tz("Europe/Madrid") == date(2026, 9, 25)
    # La tz deja de importar: la fecha es literal, no derivada.
    assert trip_time.today_in_tz("Pacific/Auckland") == date(2026, 9, 25)

    # Sin demo_mode manda el reloj real, aunque quede la fecha cargada.
    monkeypatch.setattr(s, "demo_mode", False)
    assert trip_time.today_in_tz("Europe/Madrid") == real
