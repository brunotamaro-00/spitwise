from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Tasas fallback aproximadas currency -> USD (se usan solo si la API de FX falla).
# Valores de referencia; se corrigen a mano en el dashboard cuando aplique.
_FX_FALLBACK: dict[str, str] = {
    "USD": "1.0",
    "EUR": "1.08",
    "GBP": "1.27",
    "CHF": "1.12",
    "CZK": "0.043",
    "PLN": "0.25",
    "HUF": "0.0027",
    "ARS": "0.0007",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/botardo"
    frankfurter_url: str = Field(default="https://api.frankfurter.dev/v1", alias="FRANKFURTER_URL")
    dolarapi_url: str = Field(default="https://dolarapi.com/v1", alias="DOLARAPI_URL")
    environment: str = "dev"
    trip_default_timezone: str = "Europe/Madrid"

    # No es env: se expone como propiedad para tests/servicios.
    @property
    def fx_fallback_rates(self) -> dict[str, str]:
        return dict(_FX_FALLBACK)


@lru_cache
def get_settings() -> Settings:
    return Settings()
