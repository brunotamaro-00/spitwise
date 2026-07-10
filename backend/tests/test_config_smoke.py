from app.config import get_settings


def test_settings_defaults():
    s = get_settings()
    assert s.frankfurter_url.startswith("https://")
    # Fallback USD siempre presente y = 1.
    assert s.fx_fallback_rates["USD"] == "1.0"
    assert "GBP" in s.fx_fallback_rates
