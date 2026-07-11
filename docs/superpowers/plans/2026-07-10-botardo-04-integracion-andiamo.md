# Botardo Viaje — Plan 4: Integración con Andiamo

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Conectar Botardo ↔ Andiamo por HTTP con `X-Api-Key`. Botardo sincroniza el itinerario (`stops`, **incluida la `timezone` de cada parada**), deriva la parada activa por fecha (moneda default + timezone para "hoy"), mantiene el snapshot fresco con **refresh perezoso (TTL 6h) en background**, y expone gasto por ciudad. Andiamo expone `/api/stops` y muestra un chip "Gastado: USD X" por parada.

**Architecture:** Sin DB compartida. Botardo: `app/andiamo.py` (sync stops + `ensure_stops_fresh`), `resolve_active_stop` derivada por fecha, `resolve_trip_timezone` (alimenta `today_in_tz`), `GET /api/v1/cities/spend` (X-Api-Key). Andiamo (repo `~/Desktop/Trip/andiamo`): nuevo route `GET /api/stops` (X-Api-Key, excluido del proxy auth) y un widget cliente que consume Botardo, degradando en silencio.

**Tech Stack:** Botardo (FastAPI, httpx). Andiamo (Next.js 16 App Router, Prisma 7, React 19, Tailwind 4 / design system Panini).

## Global Constraints

- **Identidad git personal** (`brunotamaro-00` / `brunotamaro@hotmail.com`) en AMBOS repos. En Andiamo, verificar `git config user.email` antes del primer commit y setear local si hiciera falta.
- Comunicación por header `X-Api-Key` = `TRIP_SHARED_API_KEY` (mismo valor en ambos). Nunca DB compartida.
- Ninguna llamada externa puede romper el flujo crítico: sync de stops usa snapshot si falla; el widget de Andiamo degrada a nada si Botardo no responde (patrón `rates.ts` de Andiamo: "never let a third-party failure 500 a page").
- **Andiamo (gotchas de AGENTS.md):** Prisma client se importa de `@/generated/prisma/client` (no `@prisma/client`); `db` singleton de `@/lib/db`; Tailwind tokens en `src/app/globals.css` `@theme{}` (no arbitrary values); auth edge en `src/proxy.ts` (matcher — hay que excluir `api/stops`); rutas `/api/*` con sesión inválida dan 401 JSON. Fechas: helpers de `@/lib/trip` (`todayStr()` Europe/Madrid, comparación `YYYY-MM-DD`).
- **Andiamo design system (widget):** usar Lucide (`Wallet`), tokens Panini (`gold`/`ink`/`surface`), label convention `text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-3`, card `rounded-[4px] border-2 border-border card-shadow`. **Mobile-first.** Usar los commands de `~/Desktop/Trip/andiamo/.claude/commands/` (`frontend-design`, `baseline-ui`, `icons-system`, `fixing-accessibility`) al construir/auditar el widget.

**Referencia:** Andiamo `src/app/api/geocode/route.ts` (patrón API route), `src/lib/db.ts`, `src/app/stops/[slug]/` (página de parada), `src/proxy.ts` (matcher).

---

## Estructura de archivos (Plan 4)

**Botardo:**
- Create: `backend/app/andiamo.py` — sync + upsert de `stops`.
- Modify: `backend/app/bot/active_stop.py` — `resolve_active_stop` derivada por fecha.
- Create: `backend/app/api/integration.py` — `GET /api/v1/cities/spend` (X-Api-Key) + `POST /api/v1/andiamo/sync`.
- Modify: `backend/app/api/router.py`.
- Test: `test_andiamo_sync.py`, `test_active_stop_by_date.py`, `test_cities_spend.py`.

**Andiamo:**
- Create: `src/app/api/stops/route.ts` — GET stops (X-Api-Key).
- Modify: `src/proxy.ts` — excluir `api/stops` del auth de sesión.
- Create: `src/lib/botardo.ts` — fetch de gasto (server-side, degrada).
- Create: `src/components/StopSpendChip.tsx` — chip "Gastado: USD X".
- Modify: `src/app/stops/[slug]/page.tsx` (o el componente de detalle) — montar el chip.
- Test: `src/app/api/stops/route.test.ts`.

---

### Task 1: Sync de stops desde Andiamo (Botardo)

**Files:**
- Create: `backend/app/andiamo.py`
- Test: `backend/tests/test_andiamo_sync.py`

**Interfaces:**
- Consumes: `app.db.models.Stop`, `app.config` (`andiamo_url`, `trip_shared_api_key`).
- Produces:
  - `async app.andiamo.fetch_stops(*, client: httpx.AsyncClient | None = None) -> list[dict]` — GET `{andiamo_url}/api/stops` con `X-Api-Key`. Lanza en error de red (el caller decide fallback).
  - `async app.andiamo.sync_stops(session, *, client=None) -> int` — upsert por `slug`; devuelve cantidad sincronizada. Si `fetch_stops` falla, no toca la tabla y devuelve `0`.
  - `async app.andiamo.ensure_stops_fresh(session) -> None` — si `max(stops.synced_at)` es más viejo que **6 horas** (o no hay stops), dispara `sync_stops` en background (`asyncio.create_task` con su propia sesión) y retorna al instante. **Nunca bloquea el camino crítico**: la request actual usa el snapshot existente. Se llama desde el webhook/dispatcher antes de resolver la parada activa.
  - Mapea camelCase de Andiamo → snake_case de `Stop`: `arrivalDate→arrival_date`, `departureDate→departure_date`, `currencyCode→currency_code`, `countryFlag→country_flag`, `timezone→timezone`, `isTransit→is_transit`, etc. Fechas `YYYY-MM-DD`→`date`.

- [x] **Step 1: Escribir el test que falla**

`backend/tests/test_andiamo_sync.py`:
```python
from datetime import date

import httpx

from app.andiamo import sync_stops
from app.db.models import Stop
from sqlalchemy import select

_STOPS = [
    {"slug": "londres", "order": 1, "name": "Londres", "country": "Reino Unido",
     "countryFlag": "🇬🇧", "arrivalDate": "2026-08-05", "departureDate": "2026-08-13",
     "currencyCode": "GBP", "timezone": "Europe/London",
     "isTransit": False, "isCandidate": False, "isFlexMargin": False},
    {"slug": "paris", "order": 6, "name": "París", "country": "Francia",
     "countryFlag": "🇫🇷", "arrivalDate": "2026-08-29", "departureDate": "2026-09-04",
     "currencyCode": "EUR", "timezone": "Europe/Paris",
     "isTransit": False, "isCandidate": False, "isFlexMargin": False},
]


def _client(payload, status=200):
    def handler(request):
        return httpx.Response(status, json=payload)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://andiamo")


async def test_sync_upserts(db_session, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("ANDIAMO_URL", "http://andiamo")
    get_settings.cache_clear()
    async with _client(_STOPS) as c:
        n = await sync_stops(db_session, client=c)
    assert n == 2
    rows = (await db_session.execute(select(Stop).order_by(Stop.order))).scalars().all()
    assert rows[0].slug == "londres"
    assert rows[0].currency_code == "GBP"
    assert rows[0].timezone == "Europe/London"
    assert rows[0].arrival_date == date(2026, 8, 5)
    # Idempotente
    async with _client(_STOPS) as c:
        await sync_stops(db_session, client=c)
    assert len((await db_session.execute(select(Stop))).scalars().all()) == 2
    get_settings.cache_clear()


async def test_sync_returns_zero_on_error(db_session, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("ANDIAMO_URL", "http://andiamo")
    get_settings.cache_clear()
    async with _client({}, status=500) as c:
        n = await sync_stops(db_session, client=c)
    assert n == 0
    get_settings.cache_clear()
```

- [x] **Step 2: Correr y verificar fallo**

Run: `cd backend && pytest tests/test_andiamo_sync.py -v`
Expected: FAIL — import error.

- [x] **Step 3: Implementar `andiamo.py`**

`backend/app/andiamo.py`:
```python
import logging
from datetime import date

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Stop

logger = logging.getLogger(__name__)


def _parse_date(v: str | None) -> date | None:
    return date.fromisoformat(v) if v else None


async def fetch_stops(*, client: httpx.AsyncClient | None = None) -> list[dict]:
    s = get_settings()
    url = f"{s.andiamo_url}/api/stops"
    headers = {"X-Api-Key": s.trip_shared_api_key}
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=10.0)
    try:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()
    finally:
        if owns:
            await client.aclose()


async def sync_stops(session: AsyncSession, *, client: httpx.AsyncClient | None = None) -> int:
    try:
        data = await fetch_stops(client=client)
    except Exception:
        logger.warning("andiamo_sync_failed; usando snapshot existente")
        return 0

    existing = {s.slug: s for s in (await session.execute(select(Stop))).scalars().all()}
    n = 0
    for item in data:
        slug = item["slug"]
        row = existing.get(slug) or Stop(slug=slug)
        row.order = item.get("order", 0)
        row.name = item.get("name", slug)
        row.country = item.get("country")
        row.country_flag = item.get("countryFlag")
        row.arrival_date = _parse_date(item.get("arrivalDate"))
        row.departure_date = _parse_date(item.get("departureDate"))
        row.currency_code = item.get("currencyCode")
        row.timezone = item.get("timezone")
        row.is_transit = bool(item.get("isTransit"))
        row.is_candidate = bool(item.get("isCandidate"))
        row.is_flex_margin = bool(item.get("isFlexMargin"))
        if slug not in existing:
            session.add(row)
        n += 1
    await session.commit()
    return n


_FRESH_TTL = timedelta(hours=6)
_refresh_running = False


async def _background_refresh() -> None:
    global _refresh_running
    from app.db.engine import get_sessionmaker
    try:
        maker = get_sessionmaker()
        async with maker() as session:
            await sync_stops(session)
    except Exception:
        logger.warning("andiamo_lazy_refresh_failed", exc_info=True)
    finally:
        _refresh_running = False


async def ensure_stops_fresh(session: AsyncSession) -> None:
    """Refresh perezoso del snapshot (TTL 6h). Nunca bloquea: dispara un task y retorna."""
    global _refresh_running
    if _refresh_running:
        return
    import asyncio
    from datetime import datetime
    from sqlalchemy import func
    last = (await session.execute(select(func.max(Stop.synced_at)))).scalar_one_or_none()
    if last is not None and datetime.utcnow() - last < _FRESH_TTL:
        return
    _refresh_running = True
    asyncio.create_task(_background_refresh())
```

(Agregar `from datetime import date, timedelta` arriba.)

- [x] **Step 4: Correr los tests**

Run: `cd backend && pytest tests/test_andiamo_sync.py -v`
Expected: PASS (2 tests).

- [x] **Step 5: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/app/andiamo.py backend/tests/test_andiamo_sync.py
git commit -m "feat(andiamo): sync de stops (itinerario) desde Andiamo"
```

---

### Task 2: Parada activa derivada por fecha (Botardo)

**Files:**
- Modify: `backend/app/bot/active_stop.py`
- Test: `backend/tests/test_active_stop_by_date.py`

**Interfaces:**
- `resolve_active_stop(session, wa_id, today)` nuevo orden de resolución:
  1. Override de sesión (si existe) → gana (day-trips).
  2. Parada de `stops` con `arrival_date <= today < departure_date`.
  3. Fallback: última parada con `arrival_date <= today` (o la primera si `today` es previo a todo).
  4. Si no hay stops sincronizadas → `(None, None, "USD")`.
  Devuelve `(stop_slug, city_name, currency_code or "USD")`.
- **Nuevo:** `async app.bot.active_stop.resolve_trip_timezone(session) -> str | None` — la `timezone` de la parada activa por fecha (misma lógica 2/3, sin override), o `None` si no hay stops (→ `today_in_tz` cae a Europe/Madrid). La usa el webhook para calcular "hoy" **antes** de despachar.
- **Cableado (nuevo Step):** en `app/api/webhook.py::process_message`, antes de despachar:
  ```python
  from app.andiamo import ensure_stops_fresh
  from app.bot.active_stop import resolve_trip_timezone
  ...
  async with maker() as session:
      await ensure_stops_fresh(session)          # lazy TTL, no bloquea
      tz = await resolve_trip_timezone(session)
      reply = await dispatch(session, m.wa_id, m.type, m.text, m.interactive_id, today_in_tz(tz))
  ```
  Y en el lifespan de `app/main.py`: `await sync_stops(session)` (tolerante a fallo) tras el seed — primer sync al startup.

- [x] **Step 1: Escribir el test que falla**

`backend/tests/test_active_stop_by_date.py`:
```python
from datetime import date

from app.bot.active_stop import resolve_active_stop, set_active_stop_override
from app.db.models import Stop


async def _seed_stops(session):
    session.add_all([
        Stop(slug="londres", order=1, name="Londres", currency_code="GBP",
             arrival_date=date(2026, 8, 5), departure_date=date(2026, 8, 13)),
        Stop(slug="paris", order=6, name="París", currency_code="EUR",
             arrival_date=date(2026, 8, 29), departure_date=date(2026, 9, 4)),
    ])
    await session.commit()


async def test_active_by_date_inside_range(db_session):
    await _seed_stops(db_session)
    slug, city, cur = await resolve_active_stop(db_session, "549110", date(2026, 8, 6))
    assert (slug, city, cur) == ("londres", "Londres", "GBP")


async def test_between_stops_uses_last_arrived(db_session):
    await _seed_stops(db_session)
    # 20-ago: ya salió de Londres, no llegó a París -> última con arrival<=today
    slug, city, cur = await resolve_active_stop(db_session, "549110", date(2026, 8, 20))
    assert slug == "londres"


async def test_override_beats_date(db_session):
    await _seed_stops(db_session)
    await set_active_stop_override(db_session, "549110", "paris", "París", "EUR")
    slug, city, cur = await resolve_active_stop(db_session, "549110", date(2026, 8, 6))
    assert slug == "paris"
```

- [x] **Step 2: Correr y verificar fallo**

Run: `cd backend && pytest tests/test_active_stop_by_date.py -v`
Expected: FAIL — el cuerpo actual no consulta `stops` (test_between_stops falla).

- [x] **Step 3: Reemplazar el cuerpo de `resolve_active_stop`**

En `backend/app/bot/active_stop.py`, reemplazar la función `resolve_active_stop` por:
```python
async def resolve_active_stop(session: AsyncSession, wa_id: str, today: date):
    # 1) Override de sesión (day-trips).
    st = await _get_state(session, wa_id)
    if st:
        data = json.loads(st.payload_json or "{}")
        ov = data.get("active_stop")
        if ov:
            return ov.get("stop_slug"), ov.get("city_name"), ov.get("currency_code", "USD")

    # 2/3) Derivar de stops por fecha.
    from app.db.models import Stop
    stops = (await session.execute(select(Stop).order_by(Stop.arrival_date))).scalars().all()
    if not stops:
        return None, None, "USD"

    current = None
    for s in stops:
        if s.arrival_date and s.departure_date and s.arrival_date <= today < s.departure_date:
            current = s
            break
    if current is None:
        arrived = [s for s in stops if s.arrival_date and s.arrival_date <= today]
        current = arrived[-1] if arrived else stops[0]

    return current.slug, current.name, (current.currency_code or "USD")


async def resolve_trip_timezone(session: AsyncSession) -> str | None:
    """Timezone de la parada activa por fecha (para today_in_tz). None => fallback default."""
    from datetime import datetime, timezone as _tz
    from app.db.models import Stop
    from app.config import get_settings
    from zoneinfo import ZoneInfo
    stops = (await session.execute(select(Stop).order_by(Stop.arrival_date))).scalars().all()
    if not stops:
        return None
    # Aproximación de "hoy" con la tz default para elegir la parada (el error de ±1h no cambia la parada).
    probe = datetime.now(_tz.utc).astimezone(ZoneInfo(get_settings().trip_default_timezone)).date()
    for s in stops:
        if s.arrival_date and s.departure_date and s.arrival_date <= probe < s.departure_date:
            return s.timezone
    arrived = [s for s in stops if s.arrival_date and s.arrival_date <= probe]
    return (arrived[-1] if arrived else stops[0]).timezone
```
Asegurar el import de `Stop` (ya está dentro de la función) y que `select` esté importado arriba (lo está). Test extra en `test_active_stop_by_date.py`: con los stops sembrados y fecha dentro de Londres, `resolve_trip_timezone` devuelve `"Europe/London"` (usar `freezegun` o inyectar; alternativa simple: probar solo el caso "sin stops → None").

- [x] **Step 4: Correr los tests (nuevos + los del Plan 3)**

Run: `cd backend && pytest tests/test_active_stop_by_date.py tests/test_active_stop.py -v`
Expected: PASS. (El `test_default_no_stop` del Plan 3 sigue pasando: sin stops y sin override → `(None,None,"USD")`.)

- [x] **Step 5: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/app/bot/active_stop.py backend/tests/test_active_stop_by_date.py
git commit -m "feat(andiamo): parada activa derivada por fecha desde stops sincronizadas"
```

---

### Task 3: Endpoint cities/spend + sync manual (Botardo)

**Files:**
- Create: `backend/app/api/integration.py`
- Modify: `backend/app/api/router.py`, `backend/app/api/schemas.py`
- Test: `backend/tests/test_cities_spend.py`

**Interfaces:**
- Produces:
  - `app.api.integration.require_api_key(x_api_key: str = Header(...))` — 401 si `!= trip_shared_api_key`.
  - `GET /api/v1/cities/spend` (X-Api-Key, **no** JWT) → `[{slug, name, total_usd, movement_count}]` agregando `type='expense'` por `stop_slug`/`city_name`. Opcional `?slug=` filtra.
  - `POST /api/v1/andiamo/sync` (JWT) → `{"synced": n}` (dispara `sync_stops`).
- Schema `CitySpendPublicOut` (`slug`, `name`, `total_usd`, `movement_count`).

- [x] **Step 1: Escribir el test que falla**

`backend/tests/test_cities_spend.py`:
```python
from datetime import date
from decimal import Decimal

from app.api.auth import hash_password


async def _seed(app_client):
    from app.db.models import Movement, User
    async with app_client._maker() as s:
        u = User(username="bruno", password_hash=hash_password("pw"))
        s.add(u)
        await s.flush()
        s.add_all([
            Movement(type="expense", amount=Decimal("50"), currency="USD", amount_usd=Decimal("50"),
                     fx_rate=Decimal("1"), fx_source="frankfurter", paid_by=u.id, split="shared",
                     stop_slug="londres", city_name="Londres", movement_date=date(2026, 8, 6), created_by=u.id),
            Movement(type="expense", amount=Decimal("20"), currency="USD", amount_usd=Decimal("20"),
                     fx_rate=Decimal("1"), fx_source="frankfurter", paid_by=u.id, split="shared",
                     stop_slug="londres", city_name="Londres", movement_date=date(2026, 8, 7), created_by=u.id),
        ])
        await s.commit()


async def test_cities_spend_requires_key(app_client):
    await _seed(app_client)
    r = await app_client.get("/api/v1/cities/spend")
    assert r.status_code == 422 or r.status_code == 401  # falta header


async def test_cities_spend_ok(app_client, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("TRIP_SHARED_API_KEY", "k")
    get_settings.cache_clear()
    await _seed(app_client)
    r = await app_client.get("/api/v1/cities/spend", headers={"X-Api-Key": "k"})
    assert r.status_code == 200
    data = {c["slug"]: c for c in r.json()}
    assert data["londres"]["total_usd"] == "70.00"
    assert data["londres"]["movement_count"] == 2
    get_settings.cache_clear()
```

- [x] **Step 2: Correr y verificar fallo**

Run: `cd backend && pytest tests/test_cities_spend.py -v`
Expected: FAIL — import error / 404.

- [x] **Step 3: Agregar schema**

Agregar a `backend/app/api/schemas.py`:
```python
class CitySpendPublicOut(BaseModel):
    slug: str | None
    name: str | None
    total_usd: str
    movement_count: int
```

- [x] **Step 4: Implementar `integration.py`**

`backend/app/api/integration.py`:
```python
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.andiamo import sync_stops
from app.api.auth import get_current_user
from app.api.schemas import CitySpendPublicOut
from app.config import get_settings
from app.db.engine import get_session
from app.db.models import Movement, User

router = APIRouter(tags=["integration"])


async def require_api_key(x_api_key: str = Header(...)) -> None:
    if x_api_key != get_settings().trip_shared_api_key:
        raise HTTPException(status_code=401, detail="API key inválida")


@router.get("/cities/spend", response_model=list[CitySpendPublicOut])
async def cities_spend(
    slug: str | None = Query(default=None),
    _: None = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> list[CitySpendPublicOut]:
    stmt = (
        select(Movement.stop_slug, Movement.city_name,
               func.sum(Movement.amount_usd), func.count())
        .where(Movement.type == "expense")
        .group_by(Movement.stop_slug, Movement.city_name)
    )
    if slug:
        stmt = stmt.where(Movement.stop_slug == slug)
    rows = (await session.execute(stmt)).all()
    return [
        CitySpendPublicOut(slug=s, name=c, total_usd=f"{Decimal(str(t)):.2f}", movement_count=cnt)
        for s, c, t, cnt in rows
    ]


@router.post("/andiamo/sync")
async def trigger_sync(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    n = await sync_stops(session)
    return {"synced": n}
```

En `backend/app/api/router.py`:
```python
from app.api.integration import router as integration_router

router.include_router(integration_router)
```

- [x] **Step 5: Correr los tests**

Run: `cd backend && pytest tests/test_cities_spend.py -v`
Expected: PASS (2 tests).

- [x] **Step 6: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/app/api/integration.py backend/app/api/router.py backend/app/api/schemas.py backend/tests/test_cities_spend.py
git commit -m "feat(andiamo): endpoint cities/spend (X-Api-Key) + sync manual"
```

---

### Task 4: `GET /api/stops` en Andiamo (repo andiamo)

**Files (repo `~/Desktop/Trip/andiamo`):**
- Create: `src/app/api/stops/route.ts`
- Modify: `src/proxy.ts` (excluir `api/stops` del auth de sesión)
- Test: `src/app/api/stops/route.test.ts`

**Interfaces:**
- `GET /api/stops` con header `X-Api-Key` == `TRIP_SHARED_API_KEY` → JSON `[{ slug, order, name, country, countryFlag, arrivalDate, departureDate, nights, datesFixed, currencyCode, timezone, isTransit, isCandidate, isFlexMargin }]`. Sin key válida → 401. Fechas serializadas `YYYY-MM-DD`. (`timezone` ya existe en el modelo `Stop` de Andiamo.)
- Nuevo env `TRIP_SHARED_API_KEY` en Andiamo.

- [x] **Step 0: Verificar identidad git del repo Andiamo**

Run: `cd ~/Desktop/Trip/andiamo && git config user.email`
Si no es `brunotamaro@hotmail.com`: `git config user.name "brunotamaro-00" && git config user.email "brunotamaro@hotmail.com"`.

- [x] **Step 1: Escribir el test que falla**

`src/app/api/stops/route.test.ts`:
```ts
import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("@/lib/db", () => ({
  db: {
    stop: {
      findMany: vi.fn().mockResolvedValue([
        {
          slug: "londres", order: 1, name: "Londres", country: "Reino Unido",
          countryFlag: "🇬🇧", arrivalDate: new Date("2026-08-05"),
          departureDate: new Date("2026-08-13"), nights: 8, datesFixed: true,
          currencyCode: "GBP", timezone: "Europe/London",
          isTransit: false, isCandidate: false, isFlexMargin: false,
        },
      ]),
    },
  },
}));

import { GET } from "./route";

function req(key?: string) {
  const headers = new Headers();
  if (key) headers.set("X-Api-Key", key);
  return new Request("http://x/api/stops", { headers });
}

beforeEach(() => {
  process.env.TRIP_SHARED_API_KEY = "k";
});

describe("GET /api/stops", () => {
  it("401 sin key", async () => {
    const res = await GET(req());
    expect(res.status).toBe(401);
  });

  it("200 con key y fechas YYYY-MM-DD", async () => {
    const res = await GET(req("k"));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body[0].slug).toBe("londres");
    expect(body[0].arrivalDate).toBe("2026-08-05");
  });
});
```

- [x] **Step 2: Correr y verificar fallo**

Run: `cd ~/Desktop/Trip/andiamo && npx vitest run src/app/api/stops/route.test.ts`
Expected: FAIL — `./route` no existe.

- [x] **Step 3: Implementar el route**

`src/app/api/stops/route.ts`:
```ts
import { db } from "@/lib/db";

function toDateStr(d: Date | null): string | null {
  return d ? d.toISOString().slice(0, 10) : null;
}

export async function GET(request: Request): Promise<Response> {
  const key = request.headers.get("X-Api-Key");
  if (!key || key !== process.env.TRIP_SHARED_API_KEY) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }
  const stops = await db.stop.findMany({ orderBy: { order: "asc" } });
  const payload = stops.map((s) => ({
    slug: s.slug,
    order: s.order,
    name: s.name,
    country: s.country,
    countryFlag: s.countryFlag,
    arrivalDate: toDateStr(s.arrivalDate),
    departureDate: toDateStr(s.departureDate),
    nights: s.nights,
    datesFixed: s.datesFixed,
    currencyCode: s.currencyCode,
    timezone: s.timezone,
    isTransit: s.isTransit,
    isCandidate: s.isCandidate,
    isFlexMargin: s.isFlexMargin,
  }));
  return Response.json(payload);
}
```

- [x] **Step 4: Excluir `api/stops` del proxy auth**

Leer `src/proxy.ts`. Su `config.matcher` (o la lógica de exclusión, como `api/documents`) debe **excluir** `api/stops` para que valide su propia `X-Api-Key` (igual que `api/documents`). Agregar `api/stops` a la lista de exclusiones del matcher/condición, siguiendo el patrón existente de `api/documents`. (No cambiar la firma del `proxy`.)

- [x] **Step 5: Correr el test**

Run: `cd ~/Desktop/Trip/andiamo && npx vitest run src/app/api/stops/route.test.ts`
Expected: PASS (2 tests).

- [x] **Step 6: Commit (repo andiamo)**

```bash
cd ~/Desktop/Trip/andiamo
git add src/app/api/stops/route.ts src/app/api/stops/route.test.ts src/proxy.ts
git commit -m "feat(api): GET /api/stops for Botardo integration (X-Api-Key)"
```

---

### Task 5: Widget "Gastado: USD X" en la página de parada (repo andiamo)

**Files (repo `~/Desktop/Trip/andiamo`):**
- Create: `src/lib/botardo.ts`
- Create: `src/components/StopSpendChip.tsx`
- Modify: la página/detalle de parada (`src/app/stops/[slug]/page.tsx` o el componente de header de la parada)

**Interfaces:**
- `src/lib/botardo.ts`: `async fetchStopSpend(slug: string): Promise<{ total_usd: string } | null>` — GET `${process.env.BOTARDO_URL}/api/v1/cities/spend?slug=${slug}` con `X-Api-Key`. Degrada a `null` en cualquier error (patrón `rates.ts`). `next: { revalidate: 300 }`.
- `StopSpendChip`: Server Component que llama `fetchStopSpend` y renderiza un chip Panini con `Wallet` (Lucide). Si `null` o `total_usd === "0.00"` → no renderiza nada.
- Nuevos envs Andiamo: `BOTARDO_URL`, `TRIP_SHARED_API_KEY` (compartido).

**Skills:** antes de escribir el componente, aplicar el command `~/Desktop/Trip/andiamo/.claude/commands/frontend-design.md` y luego `baseline-ui.md` + `icons-system.md` + `fixing-accessibility.md` como pasada de calidad. Mobile-first.

- [x] **Step 1: Crear `src/lib/botardo.ts`**

```ts
export async function fetchStopSpend(slug: string): Promise<{ total_usd: string } | null> {
  const base = process.env.BOTARDO_URL;
  const key = process.env.TRIP_SHARED_API_KEY;
  if (!base || !key) return null;
  try {
    const res = await fetch(`${base}/api/v1/cities/spend?slug=${encodeURIComponent(slug)}`, {
      headers: { "X-Api-Key": key },
      next: { revalidate: 300 },
    });
    if (!res.ok) return null;
    const arr = (await res.json()) as Array<{ slug: string; total_usd: string }>;
    const hit = arr.find((c) => c.slug === slug);
    return hit ? { total_usd: hit.total_usd } : { total_usd: "0.00" };
  } catch {
    return null;
  }
}
```

- [x] **Step 2: Crear `src/components/StopSpendChip.tsx`**

Aplicá primero `frontend-design.md`. Implementación base (tokens Panini + Lucide, mobile-first):
```tsx
import { Wallet } from "lucide-react";

import { fetchStopSpend } from "@/lib/botardo";

export default async function StopSpendChip({ slug }: { slug: string }) {
  const spend = await fetchStopSpend(slug);
  if (!spend || spend.total_usd === "0.00") return null;
  return (
    <div className="inline-flex items-center gap-2 rounded-[4px] border-2 border-border bg-surface px-3 py-1.5 card-shadow">
      <Wallet className="h-4 w-4 text-gold" strokeWidth={1.5} aria-hidden="true" />
      <span className="text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-3">
        Gastado
      </span>
      <span className="font-tabular text-sm font-bold text-ink">USD {spend.total_usd}</span>
    </div>
  );
}
```

- [x] **Step 3: Montar el chip en la página de parada**

En la página de detalle de parada (`src/app/stops/[slug]/page.tsx` o su header component), importar y renderizar `<StopSpendChip slug={slug} />` cerca del bloque de moneda/precio. Como es Server Component async, se puede envolver en `<Suspense fallback={null}>` para no bloquear el render de la página.

- [x] **Step 4: Pasada de calidad + verificación visual**

- Aplicar `baseline-ui.md`, `icons-system.md`, `fixing-accessibility.md` al chip.
- Run: `cd ~/Desktop/Trip/andiamo && npm run build`
Expected: build OK.
- Verificación manual (con `BOTARDO_URL` apuntando a un Botardo local con datos): abrir `/stops/londres` en viewport mobile y confirmar el chip.

- [x] **Step 5: Commit (repo andiamo)**

```bash
cd ~/Desktop/Trip/andiamo
git add src/lib/botardo.ts src/components/StopSpendChip.tsx src/app/stops
git commit -m "feat(stops): chip 'Gastado USD X' por parada (Botardo integration)"
```

---

## Self-review (Plan 4)

- **Cobertura de spec §6:** sync Andiamo→Botardo con `timezone` (Task 1), refresh perezoso TTL 6h + sync al startup (Task 1/2), parada activa por fecha + moneda + timezone (Task 2, incl. `resolve_trip_timezone` cableado al webhook), Botardo→Andiamo `cities/spend` (Task 3), Andiamo `/api/stops` (Task 4), widget de gasto (Task 5), auth `X-Api-Key` (Tasks 3/4/5). Resiliencia: `sync_stops` devuelve 0 sin tocar snapshot; `ensure_stops_fresh` nunca bloquea; `fetchStopSpend` degrada a `null`.
- **Placeholders:** el Step 4 de Task 4 (editar `proxy.ts`) describe la edición sin código exacto porque depende del matcher actual del repo — es una instrucción de "seguir el patrón `api/documents` existente" (matcher verificado: `/((?!api/documents|_next/static|_next/image|favicon.ico).*)`). No es un placeholder de lógica nueva.
- **Consistencia de tipos:** camelCase de `/api/stops` (Andiamo) ↔ mapeo snake_case en `sync_stops` (Botardo) — verificado campo por campo, incl. `timezone`. `cities/spend` devuelve `total_usd` string `.2f`, consumido por `fetchStopSpend`. `resolve_active_stop` firma sin cambios (solo cuerpo) → Plan 3 sigue funcionando; `resolve_trip_timezone` es aditiva.
- **Identidad git:** Task 4/Step 0 fuerza la verificación en el repo Andiamo.
