from anthropic import AsyncAnthropic
from pydantic import BaseModel

from app.config import get_settings

_SYSTEM = (
    "Sos un parser de gastos de un viaje de una pareja. Extraé del mensaje: "
    "amount (string decimal o null si no hay monto), "
    "currency (código ISO 4217 si el texto menciona la moneda — '45 libras'→GBP, '12€'→EUR — o null), "
    "description (string corta en minúsculas), "
    "category (exactamente una de la lista dada), "
    "split ('shared' salvo que el texto diga que es solo de uno: 'solo mío'→payer_only, "
    "'de ella'/'de él'→other_only), "
    "is_settlement (true solo si es un pago ENTRE las dos personas para saldar deuda, no un gasto), "
    "confidence (0..1: qué tan clara es la categoría), "
    "candidates (si confidence < 0.6, 2-3 categorías candidatas de la lista; si no, lista vacía). "
    "No inventes categorías fuera de la lista."
)


class ParsedMovementSchema(BaseModel):
    amount: str | None
    currency: str | None
    description: str | None
    category: str | None
    split: str
    is_settlement: bool
    confidence: float
    candidates: list[str]


def make_llm():
    """Elige el proveedor del parser: LLM_PROVIDER explícito, o auto
    (anthropic por defecto; openai solo si es la única key configurada)."""
    s = get_settings()
    provider = s.llm_provider.lower() or (
        "openai" if (s.openai_api_key and not s.anthropic_api_key) else "anthropic"
    )
    if provider == "openai":
        return OpenAILLM()
    return AnthropicLLM()


class AnthropicLLM:
    def __init__(self) -> None:
        s = get_settings()
        self._client = AsyncAnthropic(
            api_key=s.anthropic_api_key, timeout=s.anthropic_timeout_seconds
        )
        self._model = s.anthropic_model  # claude-haiku-4-5

    async def parse(self, text: str, default_currency: str, category_names: list[str]) -> dict:
        user = (
            f"Categorías válidas: {', '.join(category_names)}.\n"
            f"Moneda por defecto (ciudad actual): {default_currency}.\n"
            f"Mensaje: {text}"
        )
        resp = await self._client.messages.parse(
            model=self._model,
            max_tokens=1024,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user}],
            output_format=ParsedMovementSchema,
        )
        parsed = resp.parsed_output
        # parsed_output es None solo ante refusal/max_tokens; {} cae en "monto no leído".
        return parsed.model_dump() if parsed is not None else {}


class OpenAILLM:
    """Misma interfaz .parse() que AnthropicLLM, contra OpenAI structured outputs."""

    def __init__(self) -> None:
        from openai import AsyncOpenAI

        s = get_settings()
        self._client = AsyncOpenAI(
            api_key=s.openai_api_key, timeout=s.anthropic_timeout_seconds
        )
        self._model = s.openai_model

    async def parse(self, text: str, default_currency: str, category_names: list[str]) -> dict:
        user = (
            f"Categorías válidas: {', '.join(category_names)}.\n"
            f"Moneda por defecto (ciudad actual): {default_currency}.\n"
            f"Mensaje: {text}"
        )
        resp = await self._client.chat.completions.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user},
            ],
            response_format=ParsedMovementSchema,
        )
        parsed = resp.choices[0].message.parsed
        # parsed es None solo ante refusal; {} cae en "monto no leído".
        return parsed.model_dump() if parsed is not None else {}
