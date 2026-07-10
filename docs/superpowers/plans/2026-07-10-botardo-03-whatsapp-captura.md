# Botardo Viaje — Plan 3: Captura por WhatsApp

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capturar gastos por WhatsApp en un solo backend: webhook (verify HMAC + dedupe → **200 inmediato**, procesamiento en background) → parser LLM (monto, moneda, categoría, split) → dispatcher determinista → auto-registro del movimiento, con botones para override de split, comando de settlement, comando de borrado con confirmación y override de parada activa.

**Architecture:** El webhook vive dentro del backend FastAPI (no hay servicio wpp-bot separado). **Meta exige 200 en ~5s y entrega at-least-once**: el POST valida firma, parsea y reclama el `wamid` (dedupe) de forma síncrona, y despacha el resto (LLM + FX + envío por Graph) como background task de FastAPI — viable porque el deploy es Railway (proceso persistente). El dispatcher es determinista (sin FSM): botones → settlement → borrado → captura. El parser hace **1 llamada LLM a Claude Haiku 4.5 con structured outputs** (`client.messages.parse` + schema Pydantic) que devuelve monto/moneda/categoría/split. `paid_by` = usuario del `wa_id`. La parada activa se resuelve con `app.bot.active_stop.resolve_active_stop` (en este plan: override de sesión o `None`; Plan 4 la deriva de Andiamo por fecha).

**Tech Stack:** FastAPI (BackgroundTasks), Anthropic SDK (`anthropic`, Claude Haiku 4.5, structured outputs), SQLAlchemy async, httpx (Meta Graph client), hmac/hashlib (verify), pytest.

## Global Constraints

- **Un solo backend.** No portar el servicio `wpp-bot` de Expenses; su lógica de webhook/meta_client se funde acá (`app/whatsapp/*`).
- **Webhook ACK-fast:** el POST devuelve 200 apenas verifica firma y reclama el `wamid`; el procesamiento corre en `BackgroundTasks`. El dedupe absorbe los reintentos at-least-once de Meta.
- Dedupe de `wamid` en tabla Postgres (`WhatsAppDedupe`), no Redis. Lock por chat en proceso (`asyncio.Lock` por `wa_id`) — funciona de verdad en Railway (proceso único persistente).
- Bot de **captura pura**: registra/edita/borra + settlement. Sin recurrentes, sin tarjeta, sin cuotas, sin consultas por chat (los números se ven en el dashboard → CTA).
- Auto-registra sin confirmación salvo: categoría genuinamente ambigua (botones), o borrado (irreversible; comando "borrar" → botones de confirmación sobre el último movimiento **de ese usuario**).
- Los botones de split se cuelgan del **`movement_id` que devuelve la captura** (campo `BotReply.movement_id`), nunca de "el último movimiento global" — con 2 usuarios cargando a la vez eso edita el gasto del otro (race).
- "Hoy" del dispatcher = `today_in_tz(...)` (Plan 1); Plan 4 le pasa la timezone de la parada activa.
- Errores del bot: nunca genéricos → `⚠️ {Tipo}: {mensaje}`, un solo try/except en el borde del dispatcher.
- Botones: ids planos con token opaco del pending. `split_shared:`, `split_mine:`, `split_theirs:`, `del_confirm:`, `del_cancel:`, `cat_pick:{token}|{cat_id}`.
- `wa_id` desconocido se rechaza salvo `WHATSAPP_AUTO_REGISTER` (default dev).
- LLM: **Claude Haiku 4.5** (`claude-haiku-4-5`) vía SDK `anthropic`, structured outputs con `client.messages.parse` — la respuesta ya viene validada contra el schema, sin parseo manual de JSON.

**Referencia de reutilización:** `~/Desktop/Expenses/wpp-bot/wpp_bot/{webhook.py,meta_client.py}` (verify HMAC + envío Graph), `~/Desktop/Expenses/backend/app/bot/dispatcher.py` (patrón de ruteo). El parser LLM se reescribe (era OpenAI): queda solo el patrón de prompt.

---

## Estructura de archivos (Plan 3)

- Create: `backend/app/whatsapp/__init__.py`, `backend/app/whatsapp/verify.py` (HMAC + parse payload), `backend/app/whatsapp/meta_client.py` (envío Graph), `backend/app/whatsapp/dedupe.py` (tabla).
- Create: `backend/app/llm/__init__.py`, `backend/app/llm/client.py` (OpenAI singleton), `backend/app/llm/parser.py` (`parse_movement`).
- Create: `backend/app/bot/__init__.py`, `backend/app/bot/active_stop.py`, `backend/app/bot/render.py`, `backend/app/bot/pending.py`, `backend/app/bot/capture.py`, `backend/app/bot/interactive.py`, `backend/app/bot/settlement.py`, `backend/app/bot/dispatcher.py`.
- Create: `backend/app/api/webhook.py` (rutas GET verify + POST receive).
- Modify: `backend/app/main.py` (montar webhook fuera de `/api/v1`).
- Test: `test_llm_parser.py`, `test_whatsapp_verify.py`, `test_dedupe.py`, `test_dispatcher_capture.py`, `test_dispatcher_split_settlement.py`.

---

### Task 1: Parser LLM de movimientos

**Files:**
- Create: `backend/app/llm/__init__.py`, `backend/app/llm/client.py`, `backend/app/llm/parser.py`
- Test: `backend/tests/test_llm_parser.py`

**Interfaces:**
- Produces:
  - `@dataclass app.llm.parser.ParsedMovement`: `amount: Decimal | None`, `currency: str | None`, `description: str | None`, `category_name: str | None`, `split: str` (`shared` default), `is_settlement: bool`, `confidence: float`, `category_candidates: list[str]`.
  - `async app.llm.parser.parse_movement(text: str, *, default_currency: str, category_names: list[str], client=None) -> ParsedMovement`. `client` es un objeto con `.parse(text, default_currency, category_names) -> dict` (inyectable; default = OpenAI). Normaliza moneda (símbolos/nombres → ISO), valida categoría contra la lista.

- [ ] **Step 1: Escribir el test que falla**

`backend/tests/test_llm_parser.py`:
```python
from decimal import Decimal

import pytest

from app.llm.parser import ParsedMovement, parse_movement

CATS = ["Alojamiento", "Comida", "Transporte", "Actividades", "Compras", "Bebidas/Salidas", "Otros"]


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    async def parse(self, text, default_currency, category_names):
        return self.payload


async def test_parses_amount_currency_category():
    fake = FakeLLM({
        "amount": "45", "currency": "GBP", "description": "cena", "category": "Comida",
        "split": "shared", "is_settlement": False, "confidence": 0.95, "candidates": [],
    })
    got = await parse_movement("cena 45 libras", default_currency="GBP", category_names=CATS, client=fake)
    assert got.amount == Decimal("45")
    assert got.currency == "GBP"
    assert got.category_name == "Comida"
    assert got.split == "shared"
    assert got.is_settlement is False


async def test_default_currency_when_absent():
    fake = FakeLLM({"amount": "12", "currency": None, "description": "helado",
                    "category": "Comida", "split": "shared", "is_settlement": False,
                    "confidence": 0.9, "candidates": []})
    got = await parse_movement("helado 12", default_currency="EUR", category_names=CATS, client=fake)
    assert got.currency == "EUR"


async def test_invalid_category_falls_to_otros():
    fake = FakeLLM({"amount": "5", "currency": "USD", "description": "x",
                    "category": "Museos", "split": "shared", "is_settlement": False,
                    "confidence": 0.9, "candidates": []})
    got = await parse_movement("x 5", default_currency="USD", category_names=CATS, client=fake)
    assert got.category_name == "Otros"


async def test_low_confidence_keeps_candidates():
    fake = FakeLLM({"amount": "5", "currency": "USD", "description": "x", "category": "Comida",
                    "split": "shared", "is_settlement": False, "confidence": 0.4,
                    "candidates": ["Comida", "Compras"]})
    got = await parse_movement("x 5", default_currency="USD", category_names=CATS, client=fake)
    assert got.confidence == 0.4
    assert got.category_candidates == ["Comida", "Compras"]
```

- [ ] **Step 2: Correr y verificar fallo**

Run: `cd backend && pytest tests/test_llm_parser.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Crear `client.py` (Anthropic, Claude Haiku 4.5 + structured outputs)**

`backend/app/llm/__init__.py`: (vacío)

`backend/app/llm/client.py`:
```python
from pydantic import BaseModel

from anthropic import AsyncAnthropic

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
        return parsed.model_dump() if parsed is not None else {}
```

Nota: structured outputs garantiza JSON válido contra el schema (sin `json.loads` frágil). `parsed_output` puede ser `None` solo ante refusal/max_tokens — el `{}` cae en el manejo de "monto no leído" del parser.

- [ ] **Step 4: Crear `parser.py`**

`backend/app/llm/parser.py`:
```python
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

# Símbolos/nombres comunes → ISO.
_CURRENCY_ALIASES = {
    "£": "GBP", "libra": "GBP", "libras": "GBP", "pound": "GBP", "pounds": "GBP",
    "€": "EUR", "euro": "EUR", "euros": "EUR",
    "$": "USD", "usd": "USD", "dolar": "USD", "dólar": "USD", "dolares": "USD",
    "chf": "CHF", "franco": "CHF", "francos": "CHF",
    "czk": "CZK", "corona": "CZK", "coronas": "CZK",
    "pln": "PLN", "zloty": "PLN", "zlotys": "PLN",
    "huf": "HUF", "florin": "HUF", "forinto": "HUF", "forintos": "HUF",
    "ars": "ARS", "peso": "ARS", "pesos": "ARS",
}
_VALID_SPLIT = {"shared", "payer_only", "other_only"}


@dataclass
class ParsedMovement:
    amount: Decimal | None
    currency: str | None
    description: str | None
    category_name: str | None
    split: str = "shared"
    is_settlement: bool = False
    confidence: float = 1.0
    category_candidates: list[str] = field(default_factory=list)


def _norm_currency(v, default_currency: str) -> str:
    if v is None:
        return default_currency.upper()
    s = str(v).strip().lower()
    if s in _CURRENCY_ALIASES:
        return _CURRENCY_ALIASES[s]
    up = s.upper()
    return up if len(up) == 3 else default_currency.upper()


def _to_decimal(v):
    if v is None:
        return None
    try:
        return Decimal(str(v).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


async def parse_movement(text, *, default_currency, category_names, client=None):
    if client is None:
        from app.llm.client import AnthropicLLM
        client = AnthropicLLM()
    raw = await client.parse(text, default_currency, category_names)

    category = raw.get("category")
    if category not in category_names:
        category = "Otros"
    split = raw.get("split", "shared")
    if split not in _VALID_SPLIT:
        split = "shared"
    candidates = [c for c in (raw.get("candidates") or []) if c in category_names]

    return ParsedMovement(
        amount=_to_decimal(raw.get("amount")),
        currency=_norm_currency(raw.get("currency"), default_currency),
        description=(raw.get("description") or None),
        category_name=category,
        split=split,
        is_settlement=bool(raw.get("is_settlement")),
        confidence=float(raw.get("confidence", 1.0)),
        category_candidates=candidates,
    )
```

- [ ] **Step 5: Correr los tests**

Run: `cd backend && pytest tests/test_llm_parser.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/app/llm backend/tests/test_llm_parser.py
git commit -m "feat(bot): parser LLM de movimientos (monto/moneda/categoría/split)"
```

---

### Task 2: Verify HMAC + parse de payload + Meta client

**Files:**
- Create: `backend/app/whatsapp/__init__.py`, `backend/app/whatsapp/verify.py`, `backend/app/whatsapp/meta_client.py`
- Test: `backend/tests/test_whatsapp_verify.py`

**Interfaces:**
- Produces:
  - `app.whatsapp.verify.verify_signature(app_secret: str, body: bytes, header: str | None) -> bool` (HMAC-SHA256, `sha256=` prefix, `hmac.compare_digest`).
  - `@dataclass app.whatsapp.verify.IncomingMessage`: `wa_id: str`, `wamid: str`, `type: str` (`text`|`interactive`|`other`), `text: str | None`, `interactive_id: str | None`.
  - `app.whatsapp.verify.iter_incoming_messages(payload: dict) -> list[IncomingMessage]`.
  - `app.whatsapp.meta_client.MetaClient(access_token, phone_number_id, graph_version)` con `async send_text(wa_id, text)`, `async send_buttons(wa_id, text, buttons: list[tuple[str,str]])` (id, label), `async aclose()`.

- [ ] **Step 1: Escribir el test que falla**

`backend/tests/test_whatsapp_verify.py`:
```python
import hashlib
import hmac

from app.whatsapp.verify import iter_incoming_messages, verify_signature


def test_verify_signature_ok():
    secret = "s3cr3t"
    body = b'{"a":1}'
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_signature(secret, body, sig)
    assert not verify_signature(secret, body, "sha256=deadbeef")
    assert not verify_signature(secret, body, None)


def test_iter_text_message():
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "5491100000000", "id": "wamid.ABC", "type": "text",
                        "text": {"body": "cena 20 euros"},
                    }]
                }
            }]
        }]
    }
    msgs = iter_incoming_messages(payload)
    assert len(msgs) == 1
    assert msgs[0].wa_id == "5491100000000"
    assert msgs[0].wamid == "wamid.ABC"
    assert msgs[0].type == "text"
    assert msgs[0].text == "cena 20 euros"


def test_iter_interactive_button():
    payload = {"entry": [{"changes": [{"value": {"messages": [{
        "from": "549110", "id": "wamid.X", "type": "interactive",
        "interactive": {"type": "button_reply", "button_reply": {"id": "split_mine:tok123"}},
    }]}}]}]}
    msgs = iter_incoming_messages(payload)
    assert msgs[0].type == "interactive"
    assert msgs[0].interactive_id == "split_mine:tok123"
```

- [ ] **Step 2: Correr y verificar fallo**

Run: `cd backend && pytest tests/test_whatsapp_verify.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Crear `verify.py`** (adaptado de `wpp-bot/wpp_bot/webhook.py`)

`backend/app/whatsapp/__init__.py`: (vacío)

`backend/app/whatsapp/verify.py`:
```python
import hashlib
import hmac
from dataclasses import dataclass


def verify_signature(app_secret: str, body: bytes, header: str | None) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len("sha256="):])


@dataclass
class IncomingMessage:
    wa_id: str
    wamid: str
    type: str
    text: str | None = None
    interactive_id: str | None = None


def iter_incoming_messages(payload: dict) -> list[IncomingMessage]:
    out: list[IncomingMessage] = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            for m in value.get("messages", []) or []:
                wa_id = m.get("from", "")
                wamid = m.get("id", "")
                mtype = m.get("type", "other")
                if mtype == "text":
                    out.append(IncomingMessage(wa_id, wamid, "text", text=(m.get("text") or {}).get("body")))
                elif mtype == "interactive":
                    inter = m.get("interactive", {}) or {}
                    reply = inter.get("button_reply") or inter.get("list_reply") or {}
                    out.append(IncomingMessage(wa_id, wamid, "interactive", interactive_id=reply.get("id")))
                else:
                    out.append(IncomingMessage(wa_id, wamid, "other"))
    return out
```

- [ ] **Step 4: Crear `meta_client.py`** (adaptado de `wpp-bot/wpp_bot/meta_client.py`)

`backend/app/whatsapp/meta_client.py`:
```python
import httpx


class MetaClient:
    def __init__(self, access_token: str, phone_number_id: str, graph_version: str = "v21.0") -> None:
        self._token = access_token
        self._url = f"https://graph.facebook.com/{graph_version}/{phone_number_id}/messages"
        self._client = httpx.AsyncClient(timeout=15.0)

    async def _post(self, payload: dict) -> None:
        headers = {"Authorization": f"Bearer {self._token}"}
        resp = await self._client.post(self._url, json=payload, headers=headers)
        resp.raise_for_status()

    async def send_text(self, wa_id: str, text: str) -> None:
        await self._post({
            "messaging_product": "whatsapp", "to": wa_id, "type": "text",
            "text": {"body": text},
        })

    async def send_buttons(self, wa_id: str, text: str, buttons: list[tuple[str, str]]) -> None:
        await self._post({
            "messaging_product": "whatsapp", "to": wa_id, "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": text},
                "action": {"buttons": [
                    {"type": "reply", "reply": {"id": bid, "title": label[:20]}}
                    for bid, label in buttons[:3]
                ]},
            },
        })

    async def aclose(self) -> None:
        await self._client.aclose()
```

- [ ] **Step 5: Correr los tests**

Run: `cd backend && pytest tests/test_whatsapp_verify.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/app/whatsapp/__init__.py backend/app/whatsapp/verify.py backend/app/whatsapp/meta_client.py backend/tests/test_whatsapp_verify.py
git commit -m "feat(bot): verify HMAC + parse payload + Meta Graph client"
```

---

### Task 3: Dedupe de wamid (Postgres)

**Files:**
- Create: `backend/app/whatsapp/dedupe.py`
- Test: `backend/tests/test_dedupe.py`

**Interfaces:**
- Consumes: `app.db.models.WhatsAppDedupe`.
- Produces: `async app.whatsapp.dedupe.claim_wamid(session, wamid: str) -> bool` — `True` si es la primera vez (lo inserta), `False` si ya existía. `async app.whatsapp.dedupe.purge_old(session, older_than_hours: int = 48) -> int`.

- [ ] **Step 1: Escribir el test que falla**

`backend/tests/test_dedupe.py`:
```python
from app.whatsapp.dedupe import claim_wamid


async def test_claim_is_idempotent(db_session):
    assert await claim_wamid(db_session, "wamid.1") is True
    assert await claim_wamid(db_session, "wamid.1") is False
    assert await claim_wamid(db_session, "wamid.2") is True
```

- [ ] **Step 2: Correr y verificar fallo**

Run: `cd backend && pytest tests/test_dedupe.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Implementar `dedupe.py`**

`backend/app/whatsapp/dedupe.py`:
```python
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WhatsAppDedupe


async def claim_wamid(session: AsyncSession, wamid: str) -> bool:
    exists = (
        await session.execute(select(WhatsAppDedupe).where(WhatsAppDedupe.wamid == wamid))
    ).scalar_one_or_none()
    if exists is not None:
        return False
    session.add(WhatsAppDedupe(wamid=wamid))
    await session.commit()
    return True


async def purge_old(session: AsyncSession, older_than_hours: int = 48) -> int:
    cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
    res = await session.execute(
        delete(WhatsAppDedupe).where(WhatsAppDedupe.created_at < cutoff)
    )
    await session.commit()
    return res.rowcount or 0
```

- [ ] **Step 4: Correr los tests**

Run: `cd backend && pytest tests/test_dedupe.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/app/whatsapp/dedupe.py backend/tests/test_dedupe.py
git commit -m "feat(bot): dedupe de wamid en Postgres"
```

---

### Task 4: Render + parada activa + resolución de usuario

**Files:**
- Create: `backend/app/bot/__init__.py`, `backend/app/bot/render.py`, `backend/app/bot/active_stop.py`
- Test: `backend/tests/test_active_stop.py`

**Interfaces:**
- Produces:
  - `@dataclass app.bot.render.BotReply`: `text: str | None`, `buttons: list[tuple[str,str]] = []`, `movement_id: int | None = None` (id del movimiento recién creado, para que el dispatcher cuelgue los botones de split sin consultar "el último global" — evita la race con 2 usuarios). Helpers `text_reply(s)`, `buttons_reply(s, buttons)`.
  - `async app.bot.active_stop.resolve_active_stop(session, wa_id: str, today: date) -> tuple[str | None, str | None, str]` → `(stop_slug, city_name, currency_code)`. En este plan: si `whatsapp_session_states` tiene override (`{"stop_slug","city_name","currency_code"}`) lo usa; si no, `(None, None, "USD")`. **Plan 4 reemplaza el cuerpo** para derivar de `stops` por fecha.
  - `async app.bot.active_stop.set_active_stop_override(session, wa_id, stop_slug, city_name, currency_code)`.
  - `async app.bot.resolve_user_by_wa_id(session, wa_id) -> User | None` (en `app/bot/__init__.py`).

- [ ] **Step 1: Escribir el test que falla**

`backend/tests/test_active_stop.py`:
```python
from datetime import date

from app.bot.active_stop import resolve_active_stop, set_active_stop_override


async def test_default_no_stop(db_session):
    slug, city, cur = await resolve_active_stop(db_session, "549110", date(2026, 8, 6))
    assert (slug, city, cur) == (None, None, "USD")


async def test_override_used(db_session):
    await set_active_stop_override(db_session, "549110", "paris", "París", "EUR")
    slug, city, cur = await resolve_active_stop(db_session, "549110", date(2026, 8, 6))
    assert (slug, city, cur) == ("paris", "París", "EUR")
```

- [ ] **Step 2: Correr y verificar fallo**

Run: `cd backend && pytest tests/test_active_stop.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Crear `render.py`, `active_stop.py`, `__init__.py`**

`backend/app/bot/render.py`:
```python
from dataclasses import dataclass, field


@dataclass
class BotReply:
    text: str | None = None
    buttons: list[tuple[str, str]] = field(default_factory=list)
    movement_id: int | None = None  # seteado por la captura al crear un movimiento


def text_reply(s: str) -> BotReply:
    return BotReply(text=s)


def buttons_reply(s: str, buttons: list[tuple[str, str]]) -> BotReply:
    return BotReply(text=s, buttons=buttons)
```

`backend/app/bot/active_stop.py`:
```python
import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WhatsAppSessionState


async def _get_state(session: AsyncSession, wa_id: str) -> WhatsAppSessionState | None:
    return (
        await session.execute(select(WhatsAppSessionState).where(WhatsAppSessionState.wa_id == wa_id))
    ).scalar_one_or_none()


async def resolve_active_stop(session: AsyncSession, wa_id: str, today: date):
    st = await _get_state(session, wa_id)
    if st:
        data = json.loads(st.payload_json or "{}")
        ov = data.get("active_stop")
        if ov:
            return ov.get("stop_slug"), ov.get("city_name"), ov.get("currency_code", "USD")
    return None, None, "USD"


async def set_active_stop_override(session, wa_id, stop_slug, city_name, currency_code):
    st = await _get_state(session, wa_id)
    payload = {"active_stop": {"stop_slug": stop_slug, "city_name": city_name, "currency_code": currency_code}}
    if st is None:
        session.add(WhatsAppSessionState(wa_id=wa_id, owner=wa_id, payload_json=json.dumps(payload)))
    else:
        st.payload_json = json.dumps(payload)
    await session.commit()
```

`backend/app/bot/__init__.py`:
```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def resolve_user_by_wa_id(session: AsyncSession, wa_id: str) -> User | None:
    return (
        await session.execute(select(User).where(User.whatsapp_wa_id == wa_id))
    ).scalar_one_or_none()
```

- [ ] **Step 4: Correr los tests**

Run: `cd backend && pytest tests/test_active_stop.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/app/bot/__init__.py backend/app/bot/render.py backend/app/bot/active_stop.py backend/tests/test_active_stop.py
git commit -m "feat(bot): render + parada activa (override de sesión) + resolución de usuario"
```

---

### Task 5: Captura (auto-registro) + pending de categoría

**Files:**
- Create: `backend/app/bot/pending.py`, `backend/app/bot/capture.py`
- Test: `backend/tests/test_dispatcher_capture.py`

**Interfaces:**
- Consumes: `parse_movement`, `convert_to_usd`, `resolve_active_stop`, `Movement`, `Category`, `resolve_user_by_wa_id`, `BotReply`.
- Produces:
  - `app.bot.pending`: `async create_pending(session, owner, payload: dict, kind: str) -> str` (token); `async load_pending(session, token) -> dict | None`; `async close_pending(session, token)`. (Usa `BotPendingAction`.)
  - `async app.bot.capture.handle_capture(session, user, wa_id, text, today, *, llm_client=None) -> BotReply`. Parsea, resuelve parada activa, convierte a USD, crea `Movement`. Si `confidence < 0.6` y hay ≥2 candidatas → NO crea, guarda pending y devuelve botones `cat_pick:{token}|{cat_id}`. Al auto-registrar un gasto devuelve la confirmación **con `BotReply.movement_id` seteado** (el dispatcher lo usa para los botones de split).
  - `async app.bot.capture.apply_category_pick(session, user, token, category_id) -> BotReply` — materializa el movimiento pendiente con la categoría elegida (`paid_by`/`created_by` = `user.id`).

- [ ] **Step 1: Escribir el test que falla**

`backend/tests/test_dispatcher_capture.py`:
```python
from datetime import date
from decimal import Decimal

from app.api.auth import hash_password
from app.bot.capture import handle_capture
from app.db.models import Category, Movement, User


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    async def parse(self, text, default_currency, category_names):
        return self.payload


async def _user(db_session):
    u = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549110")
    db_session.add(u)
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    await db_session.commit()
    return u


async def test_autoregister_high_confidence(db_session):
    u = await _user(db_session)
    fake = FakeLLM({"amount": "20", "currency": "USD", "description": "taxi", "category": "Transporte",
                    "split": "shared", "is_settlement": False, "confidence": 0.95, "candidates": []})
    reply = await handle_capture(db_session, u, "549110", "taxi 20", date(2026, 8, 6), llm_client=fake)
    assert "Transporte" in (reply.text or "")
    movs = (await db_session.execute(__import__("sqlalchemy").select(Movement))).scalars().all()
    assert len(movs) == 1
    assert movs[0].amount_usd == Decimal("20.00")
    assert movs[0].paid_by == u.id


async def test_ambiguous_category_asks_buttons(db_session):
    u = await _user(db_session)
    fake = FakeLLM({"amount": "20", "currency": "USD", "description": "cosa", "category": "Comida",
                    "split": "shared", "is_settlement": False, "confidence": 0.4,
                    "candidates": ["Comida", "Compras"]})
    reply = await handle_capture(db_session, u, "549110", "cosa 20", date(2026, 8, 6), llm_client=fake)
    assert reply.buttons  # pide categoría
    assert (await db_session.execute(__import__("sqlalchemy").select(Movement))).scalars().all() == []
```

- [ ] **Step 2: Correr y verificar fallo**

Run: `cd backend && pytest tests/test_dispatcher_capture.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Implementar `pending.py`**

`backend/app/bot/pending.py`:
```python
import json
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BotPendingAction


async def create_pending(session: AsyncSession, owner: str, payload: dict, kind: str) -> str:
    token = secrets.token_urlsafe(18)
    session.add(BotPendingAction(
        token=token, channel="whatsapp", owner=owner, action_type=kind,
        payload_json=json.dumps(payload),
        expires_at=datetime.utcnow() + timedelta(hours=6),
    ))
    await session.commit()
    return token


async def load_pending(session: AsyncSession, token: str) -> dict | None:
    row = (await session.execute(
        select(BotPendingAction).where(BotPendingAction.token == token)
    )).scalar_one_or_none()
    if row is None or row.confirmed_at is not None or row.cancelled_at is not None:
        return None
    data = json.loads(row.payload_json)
    data["_action_type"] = row.action_type
    return data


async def close_pending(session: AsyncSession, token: str) -> None:
    row = (await session.execute(
        select(BotPendingAction).where(BotPendingAction.token == token)
    )).scalar_one_or_none()
    if row is not None:
        row.confirmed_at = datetime.utcnow()
        await session.commit()
```

- [ ] **Step 4: Implementar `capture.py`**

`backend/app/bot/capture.py`:
```python
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.active_stop import resolve_active_stop
from app.bot.pending import close_pending, create_pending, load_pending
from app.bot.render import BotReply, buttons_reply, text_reply
from app.categories.catalog import CATEGORIES
from app.db.models import Category, Movement, User
from app.fx import convert_to_usd

_CONF_THRESHOLD = 0.6


def _cat_names() -> list[str]:
    return [c[0] for c in CATEGORIES]


async def _category_id(session: AsyncSession, name: str | None) -> int | None:
    if not name:
        return None
    return (await session.execute(select(Category.id).where(Category.name == name))).scalar_one_or_none()


def _map_source(src: str, currency: str) -> str:
    # Igual que app/api/movements.py (Plan 2).
    if src == "fallback":
        return "fallback"
    if currency.upper() == "ARS":
        return "dolarapi"
    return "frankfurter"


async def _persist(session, *, user, parsed, amount_usd, rate, src, stop_slug, city_name, cat_id, today, raw):
    mv = Movement(
        type="settlement" if parsed.is_settlement else "expense",
        amount=parsed.amount, currency=parsed.currency, amount_usd=amount_usd,
        fx_rate=rate, fx_source=_map_source(src, parsed.currency), paid_by=user.id, split=parsed.split,
        description=parsed.description, category_id=cat_id, stop_slug=stop_slug, city_name=city_name,
        movement_date=today, created_by=user.id, raw_message=raw,
    )
    session.add(mv)
    await session.commit()
    return mv


async def handle_capture(session, user: User, wa_id: str, text: str, today: date, *, llm_client=None) -> BotReply:
    from app.llm.parser import parse_movement

    stop_slug, city_name, currency_code = await resolve_active_stop(session, wa_id, today)
    parsed = await parse_movement(text, default_currency=currency_code, category_names=_cat_names(), client=llm_client)
    if parsed.amount is None:
        return text_reply("⚠️ Monto: no pude leer el monto. Probá 'cena 20 euros'.")

    amount_usd, rate, src = await convert_to_usd(session, parsed.amount, parsed.currency, today)

    # Categoría ambigua → pending con botones (solo gastos, no settlement).
    if not parsed.is_settlement and parsed.confidence < _CONF_THRESHOLD and len(parsed.category_candidates) >= 2:
        payload = {
            "amount": str(parsed.amount), "currency": parsed.currency, "amount_usd": str(amount_usd),
            "fx_rate": str(rate), "fx_source": _map_source(src, parsed.currency), "split": parsed.split,
            "description": parsed.description, "stop_slug": stop_slug, "city_name": city_name,
            "movement_date": today.isoformat(),
        }
        token = await create_pending(session, owner=user.username, payload=payload, kind="cat_pick")
        buttons = []
        for name in parsed.category_candidates[:3]:
            cid = await _category_id(session, name)
            buttons.append((f"cat_pick:{token}|{cid}", name))
        return buttons_reply(f"¿Qué categoría? ({parsed.description or 'gasto'} · {parsed.currency} {parsed.amount})", buttons)

    cat_id = await _category_id(session, parsed.category_name)
    mv = await _persist(session, user=user, parsed=parsed, amount_usd=amount_usd, rate=rate, src=src,
                        stop_slug=stop_slug, city_name=city_name, cat_id=cat_id, today=today, raw=text)
    kind = "Pago (saldo)" if parsed.is_settlement else (parsed.category_name or "Otros")
    loc = f" · {city_name}" if city_name else ""
    reply = text_reply(f"✅ {kind}: {parsed.currency} {parsed.amount} (USD {amount_usd}){loc}")
    if not parsed.is_settlement:
        reply.movement_id = mv.id  # el dispatcher cuelga acá los botones de split
    return reply


async def apply_category_pick(session, user: User, token: str, category_id: int) -> BotReply:
    from datetime import date
    from decimal import Decimal

    data = await load_pending(session, token)
    if data is None:
        return text_reply("⚠️ Expiró: ese pending ya no está disponible.")
    mv = Movement(
        type="expense", amount=Decimal(data["amount"]), currency=data["currency"],
        amount_usd=Decimal(data["amount_usd"]), fx_rate=Decimal(data["fx_rate"]),
        fx_source=data["fx_source"], paid_by=user.id, split=data["split"],
        description=data.get("description"), category_id=category_id,
        stop_slug=data.get("stop_slug"), city_name=data.get("city_name"),
        movement_date=date.fromisoformat(data["movement_date"]), created_by=user.id,
    )
    session.add(mv)
    await session.commit()
    await close_pending(session, token)
    cat = (await session.execute(select(Category).where(Category.id == category_id))).scalar_one_or_none()
    reply = text_reply(f"✅ {cat.name if cat else 'Otros'}: {mv.currency} {mv.amount} (USD {mv.amount_usd})")
    reply.movement_id = mv.id
    return reply

- [ ] **Step 5: Correr los tests**

Run: `cd backend && pytest tests/test_dispatcher_capture.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/app/bot/pending.py backend/app/bot/capture.py backend/tests/test_dispatcher_capture.py
git commit -m "feat(bot): captura con auto-registro + pending de categoría"
```

---

### Task 6: Interactive (split override, borrado) + settlement + dispatcher

**Files:**
- Create: `backend/app/bot/interactive.py`, `backend/app/bot/settlement.py`, `backend/app/bot/dispatcher.py`
- Test: `backend/tests/test_dispatcher_split_settlement.py`

**Interfaces:**
- Produces:
  - `async app.bot.interactive.handle_interactive(session, user, wa_id, interactive_id, today) -> BotReply`. Rutea por prefijo: `cat_pick:` → `apply_category_pick`; `split_shared:|split_mine:|split_theirs:{movement_id}` → actualiza `Movement.split` (mine=`payer_only`, theirs=`other_only`) y responde; `del_confirm:{id}` → borra; `del_cancel:` → cancela.
  - `async app.bot.settlement.looks_like_settlement(text) -> bool` y manejo dentro de capture (el parser ya marca `is_settlement`). (Este archivo expone `format_settlement_confirm`.)
  - `async app.bot.dispatcher.dispatch(session, wa_id, message_type, text, interactive_id, today) -> BotReply`. Un solo try/except → `⚠️ {Tipo}: {msg}`. Resuelve usuario por `wa_id` (rechaza desconocidos salvo auto-register). Ruteo de texto: comando **"borrar"** (o "borrar último") → busca el último movimiento `created_by == user.id` y devuelve botones `[Borrar 🗑️](del_confirm:{id})` `[Cancelar](del_cancel:0)`; si no, captura. Tras auto-registrar un gasto, ofrece botones de split override `[Compartido ✓][Solo mío][Solo de ella]` usando **`reply.movement_id`** (nunca una query del "último global": race con 2 usuarios).

- [ ] **Step 1: Escribir el test que falla**

`backend/tests/test_dispatcher_split_settlement.py`:
```python
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.api.auth import hash_password
from app.bot.dispatcher import dispatch
from app.bot.interactive import handle_interactive
from app.db.models import Movement, User
from app.balance import compute_balance


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    async def parse(self, text, default_currency, category_names):
        return self.payload


async def _two_users(db_session):
    u1 = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    u2 = User(username="novia", password_hash=hash_password("pw"), whatsapp_wa_id="549222")
    db_session.add_all([u1, u2])
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    await db_session.commit()
    return u1, u2


async def test_capture_then_split_override_to_mine(db_session):
    u1, u2 = await _two_users(db_session)
    fake = FakeLLM({"amount": "100", "currency": "USD", "description": "hotel", "category": "Alojamiento",
                    "split": "shared", "is_settlement": False, "confidence": 0.95, "candidates": []})
    reply = await dispatch(db_session, "549111", "text", "hotel 100", None, date(2026, 8, 6), llm_client=fake)
    assert reply.buttons  # ofrece override de split
    mv = (await db_session.execute(select(Movement))).scalar_one()
    # Los botones apuntan al movimiento recién creado (no al "último global").
    assert reply.buttons[0][0] == f"split_shared:{mv.id}"
    # Simular tap en "Solo mío"
    r2 = await handle_interactive(db_session, u1, "549111", f"split_mine:{mv.id}", date(2026, 8, 6))
    await db_session.refresh(mv)
    assert mv.split == "payer_only"
    bal = compute_balance((await db_session.execute(select(Movement))).scalars().all(), u1.id, u2.id)
    assert bal.amount_usd == Decimal("0")  # solo mío => nadie debe


async def test_borrar_command_confirms_then_deletes(db_session):
    u1, u2 = await _two_users(db_session)
    db_session.add(Movement(type="expense", amount=Decimal("20"), currency="USD",
                            amount_usd=Decimal("20"), fx_rate=Decimal("1"), fx_source="frankfurter",
                            paid_by=u1.id, split="shared", movement_date=date(2026, 8, 6), created_by=u1.id))
    await db_session.commit()
    mv = (await db_session.execute(select(Movement))).scalar_one()
    # "borrar" pide confirmación con botones sobre el último movimiento del usuario.
    reply = await dispatch(db_session, "549111", "text", "borrar", None, date(2026, 8, 6))
    assert reply.buttons and reply.buttons[0][0] == f"del_confirm:{mv.id}"
    # Confirmar borra.
    await handle_interactive(db_session, u1, "549111", f"del_confirm:{mv.id}", date(2026, 8, 6))
    assert (await db_session.execute(select(Movement))).scalars().all() == []


async def test_settlement_capture(db_session):
    u1, u2 = await _two_users(db_session)
    # u2 le debe 50 a u1
    db_session.add(Movement(type="expense", amount=Decimal("100"), currency="USD",
                            amount_usd=Decimal("100"), fx_rate=Decimal("1"), fx_source="frankfurter",
                            paid_by=u1.id, split="shared", movement_date=date(2026, 8, 6), created_by=u1.id))
    await db_session.commit()
    fake = FakeLLM({"amount": "50", "currency": "USD", "description": "saldo", "category": "Otros",
                    "split": "shared", "is_settlement": True, "confidence": 0.9, "candidates": []})
    await dispatch(db_session, "549222", "text", "le pasé 50 usd", None, date(2026, 8, 7), llm_client=fake)
    bal = compute_balance((await db_session.execute(select(Movement))).scalars().all(), u1.id, u2.id)
    assert bal.amount_usd == Decimal("0")  # saldado
```

- [ ] **Step 2: Correr y verificar fallo**

Run: `cd backend && pytest tests/test_dispatcher_split_settlement.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Implementar `interactive.py`**

`backend/app/bot/interactive.py`:
```python
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.capture import apply_category_pick
from app.bot.render import BotReply, text_reply
from app.db.models import Movement, User

_SPLIT_MAP = {"split_shared": "shared", "split_mine": "payer_only", "split_theirs": "other_only"}
_SPLIT_LABEL = {"shared": "compartido", "payer_only": "solo tuyo", "other_only": "solo del otro"}


async def handle_interactive(session: AsyncSession, user: User, wa_id: str, interactive_id: str, today: date) -> BotReply:
    if interactive_id.startswith("cat_pick:"):
        rest = interactive_id[len("cat_pick:"):]
        token, cid = rest.split("|", 1)
        return await apply_category_pick(session, user, token, int(cid))

    for prefix, split_val in _SPLIT_MAP.items():
        if interactive_id.startswith(prefix + ":"):
            mid = int(interactive_id.split(":", 1)[1])
            mv = (await session.execute(select(Movement).where(Movement.id == mid))).scalar_one_or_none()
            if mv is None:
                return text_reply("⚠️ No encontrado: ese movimiento ya no existe.")
            mv.split = split_val
            await session.commit()
            return text_reply(f"✅ División actualizada: {_SPLIT_LABEL[split_val]}.")

    if interactive_id.startswith("del_confirm:"):
        mid = int(interactive_id.split(":", 1)[1])
        mv = (await session.execute(select(Movement).where(Movement.id == mid))).scalar_one_or_none()
        if mv is not None:
            await session.delete(mv)
            await session.commit()
        return text_reply("🗑️ Borrado.")

    if interactive_id.startswith("del_cancel:"):
        return text_reply("Cancelado.")

    return text_reply("⚠️ Botón desconocido.")
```

- [ ] **Step 4: Implementar `settlement.py`**

`backend/app/bot/settlement.py`:
```python
def format_settlement_confirm(currency: str, amount, amount_usd) -> str:
    return f"🤝 Pago registrado: {currency} {amount} (USD {amount_usd}). Neto actualizado."
```

- [ ] **Step 5: Implementar `dispatcher.py`**

`backend/app/bot/dispatcher.py`:
```python
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import resolve_user_by_wa_id
from app.bot.capture import handle_capture
from app.bot.interactive import handle_interactive
from app.bot.render import BotReply, buttons_reply, text_reply
from app.config import get_settings
from app.db.models import Movement, User

logger = logging.getLogger(__name__)


_DELETE_COMMANDS = {"borrar", "borrar último", "borrar ultimo", "eliminar"}


async def _handle_delete_command(session, user: User) -> BotReply:
    last = (await session.execute(
        select(Movement).where(Movement.created_by == user.id).order_by(Movement.id.desc())
    )).scalars().first()
    if last is None:
        return text_reply("⚠️ Nada que borrar: no tenés movimientos cargados.")
    desc = last.description or last.type
    return buttons_reply(
        f"¿Borrar '{desc}' ({last.currency} {last.amount})? Es irreversible.",
        [(f"del_confirm:{last.id}", "Borrar 🗑️"), ("del_cancel:0", "Cancelar")],
    )


async def _dispatch_inner(session, wa_id, message_type, text, interactive_id, today, *, llm_client) -> BotReply:
    user = await resolve_user_by_wa_id(session, wa_id)
    if user is None:
        if not get_settings().whatsapp_auto_register:
            return text_reply("⚠️ No autorizado: este número no está vinculado.")
        user = User(username=f"wa_{wa_id[-8:]}", whatsapp_wa_id=wa_id)
        session.add(user)
        await session.commit()

    if message_type == "interactive":
        return await handle_interactive(session, user, wa_id, interactive_id or "", today)

    stripped = (text or "").strip()
    if not stripped:
        return text_reply("Mandame un gasto, ej: 'cena 20 euros'.")

    if stripped.lower() in _DELETE_COMMANDS:
        return await _handle_delete_command(session, user)

    reply = await handle_capture(session, user, wa_id, text, today, llm_client=llm_client)
    # Si se auto-registró un gasto, ofrecer override de split sobre ESE movimiento.
    if reply.movement_id is not None and not reply.buttons:
        return buttons_reply(reply.text or "", [
            (f"split_shared:{reply.movement_id}", "Compartido ✓"),
            (f"split_mine:{reply.movement_id}", "Solo mío"),
            (f"split_theirs:{reply.movement_id}", "Solo de ella"),
        ])
    return reply


async def dispatch(session: AsyncSession, wa_id, message_type, text, interactive_id, today: date, *, llm_client=None) -> BotReply:
    try:
        return await _dispatch_inner(session, wa_id, message_type, text, interactive_id, today, llm_client=llm_client)
    except Exception as exc:  # borde único de errores
        logger.exception("dispatch_error wa_id=%s", wa_id)
        return text_reply(f"⚠️ {type(exc).__name__}: {exc}")
```

- [ ] **Step 6: Correr los tests**

Run: `cd backend && pytest tests/test_dispatcher_split_settlement.py -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/app/bot/interactive.py backend/app/bot/settlement.py backend/app/bot/dispatcher.py backend/tests/test_dispatcher_split_settlement.py
git commit -m "feat(bot): interactive (split/borrado) + settlement + dispatcher"
```

---

### Task 7: Rutas del webhook (GET verify + POST receive)

**Files:**
- Create: `backend/app/api/webhook.py`
- Modify: `backend/app/main.py` (montar webhook fuera de `/api/v1`)
- Test: `backend/tests/test_webhook_route.py`

**Interfaces:**
- Produces:
  - `GET /webhooks/whatsapp` → verificación de Meta (`hub.mode=subscribe`, `hub.verify_token`, echo `hub.challenge`).
  - `POST /webhooks/whatsapp` → **camino síncrono mínimo**: valida HMAC (`X-Hub-Signature-256`), parsea mensajes y reclama cada `wamid` (dedupe); luego encola el procesamiento real (lock por chat → dispatch → envío por `MetaClient`) en `BackgroundTasks` y responde `200 {"status":"ok"}` de inmediato. Meta exige 2xx en ~5s; una llamada LLM + FX síncronas lo excederían y dispararían reintentos.
  - `async process_message(m: IncomingMessage)` — helper background: abre su propia sesión (`get_sessionmaker()`), toma el lock del chat, despacha con `today_in_tz(None)` (Plan 4 lo cambia por la tz de la parada activa) y envía la respuesta por Graph. Errores → log, nunca rompen el request original (ya respondido).
- Consumes: `verify_signature`, `iter_incoming_messages`, `claim_wamid`, `dispatch`, `MetaClient`, `today_in_tz`.

- [ ] **Step 1: Escribir el test que falla**

`backend/tests/test_webhook_route.py`:
```python
import hashlib
import hmac
import json


async def test_verify_challenge(app_client, monkeypatch):
    from app.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "vtok")
    get_settings.cache_clear()
    r = await app_client.get("/webhooks/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": "vtok", "hub.challenge": "12345",
    })
    assert r.status_code == 200
    assert r.text == "12345"


async def test_post_ignores_bad_signature(app_client, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "s3cr3t")
    monkeypatch.setenv("ENVIRONMENT", "prod")
    get_settings.cache_clear()
    body = json.dumps({"entry": []}).encode()
    r = await app_client.post("/webhooks/whatsapp", content=body, headers={"X-Hub-Signature-256": "sha256=bad"})
    # Firma inválida => 403, sin procesar.
    assert r.status_code == 403
    get_settings.cache_clear()
```

- [ ] **Step 2: Correr y verificar fallo**

Run: `cd backend && pytest tests/test_webhook_route.py -v`
Expected: FAIL — 404 (ruta no existe).

- [ ] **Step 3: Implementar `webhook.py`**

`backend/app/api/webhook.py`:
```python
import asyncio
import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.dispatcher import dispatch
from app.config import get_settings
from app.db.engine import get_session, get_sessionmaker
from app.trip_time import today_in_tz
from app.whatsapp.dedupe import claim_wamid
from app.whatsapp.meta_client import MetaClient
from app.whatsapp.verify import IncomingMessage, iter_incoming_messages, verify_signature

router = APIRouter(prefix="/webhooks", tags=["webhook"])
logger = logging.getLogger(__name__)

# Locks por chat: válidos porque Railway corre un único proceso persistente.
_wa_locks: dict[str, asyncio.Lock] = {}


def _lock(wa_id: str) -> asyncio.Lock:
    lock = _wa_locks.get(wa_id)
    if lock is None:
        lock = asyncio.Lock()
        _wa_locks[wa_id] = lock
    return lock


@router.get("/whatsapp")
async def verify(request: Request) -> Response:
    s = get_settings()
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == s.whatsapp_verify_token:
        return PlainTextResponse(params.get("hub.challenge", ""))
    return Response(status_code=403)


async def process_message(m: IncomingMessage) -> None:
    """Corre en background: LLM + FX + respuesta por Graph, fuera del camino del 200."""
    s = get_settings()
    meta = MetaClient(s.whatsapp_access_token, s.whatsapp_phone_number_id, s.whatsapp_graph_version)
    maker = get_sessionmaker()
    try:
        async with _lock(m.wa_id):
            async with maker() as session:
                # Plan 4: today_in_tz(tz de la parada activa).
                reply = await dispatch(session, m.wa_id, m.type, m.text, m.interactive_id, today_in_tz(None))
        if reply.buttons:
            await meta.send_buttons(m.wa_id, reply.text or "", reply.buttons)
        elif reply.text:
            await meta.send_text(m.wa_id, reply.text)
    except Exception:
        logger.exception("webhook_background_error wamid=%s", m.wamid)
    finally:
        await meta.aclose()


@router.post("/whatsapp")
async def receive(
    request: Request,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> Response:
    s = get_settings()
    body = await request.body()
    sig = request.headers.get("X-Hub-Signature-256")
    # Siempre verificar salvo dev explícito sin secret configurado.
    if s.whatsapp_app_secret or s.environment != "dev":
        if not verify_signature(s.whatsapp_app_secret, body, sig):
            return Response(status_code=403)

    payload = json.loads(body or b"{}")
    # Camino síncrono mínimo: dedupe + encolar. Meta exige 2xx en ~5s.
    for m in iter_incoming_messages(payload):
        if not await claim_wamid(session, m.wamid):
            continue  # reintento at-least-once de Meta: ya lo procesamos/estamos procesando
        background.add_task(process_message, m)
    return Response(content='{"status":"ok"}', media_type="application/json")
```

- [ ] **Step 4: Montar el webhook en `main.py`**

En `backend/app/main.py`, después de `app.include_router(api_router)`:
```python
from app.api.webhook import router as webhook_router  # noqa: E402

app.include_router(webhook_router)
```

- [ ] **Step 5: Correr los tests**

Run: `cd backend && pytest tests/test_webhook_route.py -v`
Expected: PASS (2 tests). (Si `get_settings.cache_clear()` no aplica los env por orden de import, setear los envs con `monkeypatch.setenv` antes del primer `get_settings()` — el test ya limpia la cache.)

- [ ] **Step 6: Correr toda la suite**

Run: `cd backend && pytest -v`
Expected: PASS (todos los tests de Plans 1-3).

- [ ] **Step 7: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/app/api/webhook.py backend/app/main.py backend/tests/test_webhook_route.py
git commit -m "feat(bot): rutas del webhook de WhatsApp (verify + receive)"
```

---

## Self-review (Plan 3)

- **Cobertura de spec §7:** parser LLM (Claude Haiku 4.5, structured outputs) +moneda +split → Task 1. Webhook fusionado con **ACK inmediato + background** (verify HMAC, dedupe, lock) → Tasks 2/3/7. Auto-registro + categoría ambigua con botones → Task 5. Override de split por botones sobre `movement_id` (sin race) → Task 6. Comando "borrar" con confirmación → Task 6. Settlement → Tasks 1/5/6. Parada activa (override) → Task 4 (Plan 4 la deriva de Andiamo).
- **Placeholders:** ninguno; `apply_category_pick` quedó con la firma y código finales (sin notas de parche).
- **Consistencia de tipos:** `BotReply` (con `movement_id`) usado en todo el bot. `dispatch(...)` firma consistente entre dispatcher y webhook (el webhook no pasa `llm_client` → usa Claude real en prod; los tests inyectan `llm_client=fake`). `apply_category_pick(session, user, token, cid)`. `resolve_active_stop` devuelve `(slug, city, currency)` consumido por `handle_capture`. `_map_source(src, currency)` idéntico al del Plan 2.
- **Deuda para Plan 4:** `resolve_active_stop` hoy solo usa override de sesión; Plan 4 deriva la parada por fecha desde `stops` sincronizadas, expone `resolve_trip_timezone` (reemplaza el `today_in_tz(None)` del webhook) y agrega refresh perezoso del snapshot.
