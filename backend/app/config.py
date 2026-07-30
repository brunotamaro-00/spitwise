from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Tasas fallback aproximadas currency -> USD (se usan solo si la API de FX falla).
# Valores de referencia; se corrigen a mano en el dashboard cuando aplique.
_FX_FALLBACK: dict[str, str] = {
    "USD": "1.0",
    "EUR": "1.08",
    "GBP": "1.27",
    "CHF": "1.22",
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

    # Deploy público de muestra (demo.spitwise.lat): mismo repo y rama que prod,
    # solo cambian las env vars. Apaga el canal de WhatsApp — la demo es solo la
    # web — y marca la data como ficticia en el frontend vía /public-config.
    demo_mode: bool = False
    # "Hoy" congelado de la demo (YYYY-MM-DD), leído en trip_time.today_in_tz.
    # Sin esto el itinerario sembrado se corre contra el día en que arranca el
    # cron y deja de coincidir con Andiamo. Misma fecha que NEXT_PUBLIC_DEMO_TODAY.
    demo_today: str = ""
    # URL de la demo pública, el CTA principal del /login de producción.
    # Vacío => el frontend cae al dominio conocido (ver useConfig.ts).
    demo_url: str = ""

    # Auth
    secret_key: str = "change-me-in-production-use-a-long-random-string"
    jwt_expire_days: int = 90
    bot_api_key: str = "change-me-bot-key"
    auth_users: str = ""  # "user:pass:wa_id,user2:pass2:wa_id2"
    # Contraseñas válidas del login web, separadas por comas. Más de una a la vez
    # para poder rotar sin dejar a nadie afuera en medio del viaje. Vacío =>
    # el login rechaza todo (salvo en demo_mode, que es de entrada libre).
    # Ojo en archivos .env: comillar el valor si alguna contraseña tiene "#".
    login_passwords: str = ""
    cors_origins: str = Field(default="", alias="CORS_ORIGINS")

    # Integración Andiamo
    trip_shared_api_key: str = "change-me-shared-key"
    andiamo_url: str = ""  # ej. https://andiamo.lat

    # Stop local "Pititas" (4-11 sept): username dueño de esa parada. Vacío =>
    # no se siembra y el itinerario se comporta como si no existiera.
    pititas_owner: str = ""

    # Dominio público de esta app (para deep-links del bot hacia el frontend).
    # ej. https://spitwise.lat ; vacío => el bot omite el link.
    spitwise_url: str = Field(default="", alias="SPITWISE_URL")

    # LLM (parser de gastos). Proveedor: "anthropic" | "openai" | "" (auto:
    # anthropic salvo que SOLO haya OPENAI_API_KEY configurada).
    llm_provider: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5"
    anthropic_timeout_seconds: float = 20.0
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"  # parser: con reasoning minimal (ver client.py)

    # Agente Q&A conversacional (modelo más capaz, separado del parser).
    openai_chat_model: str = "gpt-5-mini"
    anthropic_chat_model: str = "claude-sonnet-4-6"
    chat_timeout_seconds: float = 30.0  # por request; el loop hace hasta qa_max_iterations
    qa_max_iterations: int = 5  # la mayoría de consultas se resuelven en 1-2 tool-calls
    # Presupuesto de tool calls del turno, independiente de las rondas: una sola
    # ronda puede pedir 6 tools en paralelo. Al agotarse, el loop no descarta lo
    # que ya juntó: reserva una llamada final sin tools para sintetizarlo.
    qa_max_tool_calls: int = 10
    qa_history_max_turns: int = 8  # turnos (pregunta+respuesta) que se recuerdan
    qa_history_ttl_minutes: int = 60
    # Ventana en la que un gasto recién cargado sigue siendo "corregible": el
    # parser recibe ese último gasto como contexto para pescar correcciones
    # naturales ('contalo solo para katia', 'era en Paris') como edit.
    edit_recent_ttl_minutes: int = 15

    # Canal documentos (adjuntos WPP → Andiamo). Vision separado del parser:
    # lee PDFs/imágenes y extrae kind/fecha/parada, siempre por OpenAI.
    openai_vision_model: str = "gpt-5"
    vision_timeout_seconds: float = 90.0  # PDFs de varias páginas tardan
    # Ventana en la que un preview de documento sin confirmar acepta
    # correcciones por texto ('es en York', 'fecha 15-ago').
    doc_pending_fresh_minutes: int = 15

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
