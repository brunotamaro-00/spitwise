from functools import lru_cache

from pydantic import Field, field_validator
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

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/spitwise"

    @field_validator("database_url")
    @classmethod
    def _force_asyncpg(cls, v: str) -> str:
        # Railway inyecta postgresql://...; SQLAlchemy async necesita el driver explícito.
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v
    frankfurter_url: str = Field(default="https://api.frankfurter.dev/v1", alias="FRANKFURTER_URL")
    dolarapi_url: str = Field(default="https://dolarapi.com/v1", alias="DOLARAPI_URL")
    environment: str = "dev"
    trip_default_timezone: str = "Europe/Madrid"

    # Auth
    secret_key: str = "change-me-in-production-use-a-long-random-string"
    jwt_expire_days: int = 30
    bot_api_key: str = "change-me-bot-key"
    auth_users: str = ""  # "user:pass:wa_id,user2:pass2:wa_id2"
    cors_origins: str = Field(default="", alias="CORS_ORIGINS")

    # Integración Andiamo
    trip_shared_api_key: str = "change-me-shared-key"
    andiamo_url: str = ""  # ej. https://andiamo-production.up.railway.app

    # LLM (parser de gastos). Proveedor: "anthropic" | "openai" | "" (auto:
    # anthropic salvo que SOLO haya OPENAI_API_KEY configurada).
    llm_provider: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5"
    anthropic_timeout_seconds: float = 20.0
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Agente Q&A conversacional (modelo más capaz, separado del parser).
    openai_chat_model: str = "gpt-5-mini"
    anthropic_chat_model: str = "claude-sonnet-4-6"
    chat_timeout_seconds: float = 30.0  # por request; el loop hace hasta qa_max_iterations
    qa_max_iterations: int = 8
    qa_history_max_turns: int = 8  # turnos (pregunta+respuesta) que se recuerdan
    qa_history_ttl_minutes: int = 60

    # WhatsApp Cloud — usado en Plan 3
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_graph_version: str = "v21.0"
    whatsapp_auto_register: bool = False

    # No es env: se expone como propiedad para tests/servicios.
    @property
    def fx_fallback_rates(self) -> dict[str, str]:
        return dict(_FX_FALLBACK)


_DEFAULT_CORS = ["http://localhost:5173", "http://localhost:3000"]


def parse_cors(v: str) -> list[str]:
    if not v or not v.strip():
        return _DEFAULT_CORS
    v = v.strip()
    if v.startswith("["):
        import json
        return json.loads(v)
    return [o.strip() for o in v.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
