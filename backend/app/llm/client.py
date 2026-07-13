from datetime import date

from anthropic import AsyncAnthropic
from pydantic import BaseModel

from app.config import get_settings

_SYSTEM = (
    "Sos el intérprete de mensajes del bot de gastos de un viaje de una pareja "
    "({users}). Clasificá la intención del mensaje y extraé campos.\n\n"
    "intent:\n"
    "- 'expense': carga un gasto (caso más común).\n"
    "- 'settlement': un pago ENTRE las dos personas para saldar deuda ('le pasé 50').\n"
    "- 'edit': corrige un movimiento ya guardado ('la cena de ayer fue 25', "
    "'cambiá la categoría del último a transporte').\n"
    "- 'delete': pide borrar un movimiento ('borrá el museo de ayer').\n"
    "- 'question': pregunta sobre gastos/saldos/itinerario ('¿cuánto gastamos en Roma?', "
    "'dame el detalle', '¿quién debe plata?'), o un saludo/charla ('hola', 'gracias', "
    "'¿cómo te uso?'). REGLA: si el mensaje CARGA un gasto (tiene monto y algo "
    "comprado/pagado), es 'expense', nunca 'question'.\n"
    "- 'unknown': nada de lo anterior.\n\n"
    "Para expense/settlement extraé:\n"
    "- amount: string decimal, o null si no hay monto.\n"
    "- currency: código ISO 4217 SOLO si el texto menciona la moneda "
    "('45 libras'→GBP, '12€'→EUR, '10usd'→USD); si no, null (el sistema usa la de la ciudad).\n"
    "- description: string corta en minúsculas.\n"
    "- category: exactamente una de la lista dada (null para settlement).\n"
    "- split: 'shared' salvo que el texto diga que el gasto es solo de uno: "
    "'solo mío'→payer_only, 'solo de ella/él' (del que NO pagó)→other_only. "
    "Es relativo a quien pagó.\n"
    "- paid_by: username de quien pagó SOLO si el texto lo dice "
    "('pagó {other}', 'pagué yo'→{sender}); si no lo dice, null.\n"
    "- date: fecha del gasto en ISO (YYYY-MM-DD) SOLO si el texto menciona una fecha "
    "('ayer', 'el 23 de septiembre', 'el martes'); resolvela usando la fecha de hoy dada; "
    "si no menciona fecha, null.\n"
    "- city: nombre de ciudad SOLO si el texto la menciona explícitamente; si no, null.\n"
    "- confidence: 0..1, qué tan clara es la categoría.\n"
    "- candidates: si confidence < 0.6, 2-3 categorías candidatas de la lista; si no, [].\n\n"
    "Para edit/delete extraé la referencia al movimiento:\n"
    "- ref_last: true si se refiere al último movimiento o no da ninguna referencia.\n"
    "- ref_text: palabras que identifican el movimiento ('cena', 'museo'), o null.\n"
    "- ref_date: fecha del movimiento referido en ISO si la menciona ('de ayer'), o null.\n"
    "Y para edit, los campos NUEVOS (solo los que el mensaje pide cambiar, resto null):\n"
    "- new_amount, new_currency (ISO), new_date (ISO), new_city, new_category (de la lista), "
    "new_description, new_split (shared/payer_only/other_only), new_paid_by (username).\n\n"
    "No inventes categorías fuera de la lista. Hablan castellano rioplatense."
)


class ParsedMessageSchema(BaseModel):
    intent: str
    amount: str | None
    currency: str | None
    description: str | None
    category: str | None
    split: str | None
    paid_by: str | None
    date: str | None
    city: str | None
    confidence: float
    candidates: list[str]
    ref_last: bool
    ref_text: str | None
    ref_date: str | None
    new_amount: str | None
    new_currency: str | None
    new_date: str | None
    new_city: str | None
    new_category: str | None
    new_description: str | None
    new_split: str | None
    new_paid_by: str | None


def _render_system(usernames: list[str], sender: str) -> str:
    other = next((u for u in usernames if u != sender), sender)
    return _SYSTEM.format(users=" y ".join(usernames), sender=sender, other=other)


def _render_categories(category_names: list[str], categories) -> str:
    """Bloque de categorías del prompt; con descripciones si están disponibles."""
    if categories and any(d for _, d in categories):
        lines = "\n".join(f"- {n}: {d}" for n, d in categories)
        return (
            "Categorías válidas (elegí exactamente una por la NATURALEZA del gasto):\n"
            f"{lines}\n"
            "Usá 'Otros' SOLO si el gasto de verdad no encaja en ninguna otra categoría."
        )
    return f"Categorías válidas: {', '.join(category_names)}."


def _render_user(text: str, today: date, category_names: list[str], usernames: list[str],
                 sender: str, categories=None) -> str:
    other = next((u for u in usernames if u != sender), sender)
    return (
        f"Hoy es {today.isoformat()}.\n"
        f"{_render_categories(category_names, categories)}\n"
        f"Escribe: {sender}. La otra persona es {other} "
        f"('yo'→{sender}; 'él'→bruno, 'ella'→katia si existen esos usuarios).\n"
        f"Mensaje: {text}"
    )


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

    async def parse(self, text, *, today, category_names, usernames, sender, categories=None) -> dict:
        resp = await self._client.messages.parse(
            model=self._model,
            max_tokens=1024,
            system=_render_system(usernames, sender),
            messages=[{"role": "user", "content": _render_user(
                text, today, category_names, usernames, sender, categories
            )}],
            output_format=ParsedMessageSchema,
        )
        parsed = resp.parsed_output
        # parsed_output es None solo ante refusal/max_tokens; {} cae en "no entendí".
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

    async def parse(self, text, *, today, category_names, usernames, sender, categories=None) -> dict:
        resp = await self._client.chat.completions.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": _render_system(usernames, sender)},
                {"role": "user", "content": _render_user(
                    text, today, category_names, usernames, sender, categories
                )},
            ],
            response_format=ParsedMessageSchema,
        )
        parsed = resp.choices[0].message.parsed
        # parsed es None solo ante refusal; {} cae en "no entendí".
        return parsed.model_dump() if parsed is not None else {}
