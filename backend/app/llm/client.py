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
    "- split: SIEMPRE 'shared' por defecto. Usá payer_only/other_only SOLO si el "
    "mensaje dice EXPLÍCITAMENTE que el gasto es de una sola persona "
    "('solo mío', 'solo katia', 'solo para bruno'). Que alguien haya hecho o "
    "pagado el gasto NO lo hace individual: 'gasté 100 en el teleférico'→shared.\n"
    "  'solo <nombre>' dice DE QUIÉN ES el gasto, NUNCA quién lo pagó: "
    "'solo katia' NO significa que pagó Katia. Si el mensaje no dice quién pagó, "
    "paga {sender} igual.\n"
    "  El valor es RELATIVO A QUIEN PAGÓ: si el gasto es de quien pagó → "
    "'payer_only'; si es de la otra persona → 'other_only'. Ejemplos con "
    "{sender} escribiendo y sin decir quién pagó (⇒ paga {sender}): "
    "'solo {sender}'/'solo mío' → payer_only; 'solo {other}'/'solo de {other}' → "
    "other_only.\n"
    "- paid_by: username de quien pagó SOLO si el texto lo dice "
    "('pagó {other}', 'pagué yo'→{sender}); si no lo dice, null. "
    "'solo {other}' NO dice quién pagó ⇒ null.\n"
    "- date: fecha del gasto en ISO (YYYY-MM-DD) SOLO si el texto menciona una fecha "
    "('ayer', 'el 23 de septiembre', 'el martes'); resolvela usando la fecha de hoy dada; "
    "si no menciona fecha, null.\n"
    "- city: nombre de ciudad SOLO si el texto menciona literalmente una parada "
    "('en Londres', 'Roma'); si no, null. Nunca infieras ciudad por el destino "
    "del viaje, la primera parada, ni por ítems previos (seguro de viaje, pasajes, "
    "visa, equipaje). Sin ciudad explícita => null (queda General).\n"
    "  Abajo va la lista de paradas del itinerario: algunas NO son ciudades "
    "conocidas (apodos, regiones, nombres propios del viaje) y aun así son "
    "paradas válidas. Si el mensaje nombra una, devolvé el nombre EXACTO de la "
    "lista y sacala de la descripción. Ojo con el orden de las palabras: la "
    "parada puede venir antes de lo comprado y sin 'en' delante "
    "('10 usd roma en helados' → city 'Roma', description 'helados').\n"
    "- confidence: 0..1, qué tan clara es la categoría.\n"
    "- candidates: si confidence < 0.6, 2-3 categorías candidatas de la lista; si no, [].\n\n"
    "Multi-gasto: si el mensaje carga MÁS DE UN gasto con montos separados "
    "('cena 40, taxi 12, helado 5'), intent='expense' y llená `expenses` con TODOS "
    "los ítems, con los mismos campos y reglas de arriba. kind='expense', o "
    "'settlement' si ese ítem es un pago entre ustedes (category null). Cada ítem "
    "va COMPLETO y autocontenido: los calificativos a nivel mensaje ('ayer', "
    "'en Roma', 'pagó katia') se replican en cada ítem, salvo que un ítem diga "
    "otra cosa. Los campos sueltos (amount, category, …) llevan el PRIMER ítem. "
    "Con UN solo gasto, `expenses` queda VACÍO. NO inventes ítems: partí SOLO "
    "cuando hay montos separados; 'cena 40 con vino' es UN gasto de 40.\n\n"
    "CORRECCIÓN DE UN GASTO RECIÉN CARGADO: si abajo se te da un 'Último gasto', "
    "{sender} acaba de cargarlo y este mensaje puede ser una corrección. Si el "
    "mensaje NO carga un gasto nuevo (no trae un monto propio junto a algo "
    "comprado) y en cambio ajusta uno de sus campos —monto, moneda, ciudad, "
    "categoría, división o quién pagó—, es intent='edit' con ref_last=true y solo "
    "los new_* que cambian. Ejemplos (Último gasto = 'tren · USD 39 · Pititas · "
    "pagó Katia · 50/50'): 'no, contalo solo para katia' → edit, "
    "new_split='payer_only' (Katia pagó, es de ella); 'ponelo solo de bruno' → "
    "edit, new_split='other_only'; 'era en Paris' → edit, new_city='Paris'; "
    "'fueron 45' → edit, new_amount='45'; 'en realidad pagó bruno' → edit, "
    "new_paid_by='bruno'; 'es transporte' → edit, new_category='Transporte'. "
    "Pero si trae un gasto nuevo con su propio monto ('café 5'), es expense, NO "
    "edit. Sin 'Último gasto' abajo, no apliques esta regla.\n\n"
    "Para edit/delete extraé la referencia al movimiento:\n"
    "- ref_last: true si se refiere al último movimiento o no da ninguna referencia.\n"
    "- ref_text: palabras que identifican el movimiento ('cena', 'museo'), o null.\n"
    "- ref_date: fecha del movimiento referido en ISO si la menciona ('de ayer'), o null.\n"
    "Y para edit, los campos NUEVOS (solo los que el mensaje pide cambiar, resto null):\n"
    "- new_amount, new_currency (ISO), new_date (ISO), new_city, new_category (de la lista), "
    "new_description, new_split (shared/payer_only/other_only), new_paid_by (username).\n\n"
    "No inventes categorías fuera de la lista. Hablan castellano rioplatense."
)


class ExpenseItemSchema(BaseModel):
    """Un gasto dentro de un mensaje multi-gasto. Mismos campos/semántica que el flat."""

    kind: str  # expense | settlement
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
    # Vacío salvo mensaje con 2+ gastos; ahí lleva TODOS (flat = primer ítem).
    expenses: list[ExpenseItemSchema]


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


def _render_cities(city_names) -> str:
    """Paradas del itinerario. Sin esto el LLM solo reconoce ciudades por cultura
    general y se pierde las de nombre propio (Pititas, Highlands, Jungfrau…)."""
    if not city_names:
        return ""
    return f"Paradas del itinerario: {', '.join(city_names)}.\n"


def _render_last_expense(last_expense) -> str:
    """El gasto recién cargado (si sigue fresco). Habilita la regla de corrección."""
    if not last_expense:
        return ""
    return f"Último gasto cargado (puede que este mensaje lo corrija): {last_expense}.\n"


def _render_user(text: str, today: date, category_names: list[str], usernames: list[str],
                 sender: str, categories=None, city_names=None, last_expense=None) -> str:
    other = next((u for u in usernames if u != sender), sender)
    return (
        f"Hoy es {today.isoformat()}.\n"
        f"{_render_categories(category_names, categories)}\n"
        f"{_render_cities(city_names)}"
        f"{_render_last_expense(last_expense)}"
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

    async def parse(self, text, *, today, category_names, usernames, sender, categories=None,
                    city_names=None, last_expense=None) -> dict:
        resp = await self._client.messages.parse(
            model=self._model,
            max_tokens=1024,
            # System estable por (usuarios, remitente) → se cachea entre requests.
            system=[{"type": "text", "text": _render_system(usernames, sender),
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": _render_user(
                text, today, category_names, usernames, sender, categories, city_names,
                last_expense,
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

    async def parse(self, text, *, today, category_names, usernames, sender, categories=None,
                    city_names=None, last_expense=None) -> dict:
        resp = await self._client.chat.completions.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": _render_system(usernames, sender)},
                {"role": "user", "content": _render_user(
                    text, today, category_names, usernames, sender, categories, city_names,
                    last_expense,
                )},
            ],
            response_format=ParsedMessageSchema,
        )
        parsed = resp.choices[0].message.parsed
        # parsed es None solo ante refusal; {} cae en "no entendí".
        return parsed.model_dump() if parsed is not None else {}
