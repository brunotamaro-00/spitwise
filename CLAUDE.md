# CLAUDE.md — Spitwise

Contexto de arranque para cualquier agente que trabaje en este repo. Leé esto antes de tocar código.

## Qué es

**Spitwise** es el ledger de gastos de un viaje de pareja (Bruno + Katia). Registra gastos compartidos, splits, FX a USD, analytics por ciudad y el neto entre dos personas.

Dos canales:

1. **WhatsApp bot** (entrada principal) — captura en lenguaje natural, edits, borrados, Q&A y settlements ("le pasé 20 usd").
2. **Web mobile-first** — dashboard, balance, CRUD manual, drill-down por ciudad.

**Andiamo** (app hermana de itinerario) es la fuente de verdad de las paradas (ciudades, fechas, timezones, moneda local). Spitwise sincroniza stops y expone gasto a Andiamo con una API key compartida.

No hay Telegram. No es multi-grupo: el negocio asume **exactamente 2 usuarios**.

## Stack

| Capa | Tecnología |
|------|------------|
| Backend | Python ≥3.11 / 3.12, FastAPI, SQLAlchemy 2 async, asyncpg, Alembic |
| DB | PostgreSQL (Railway en prod; local en dev) |
| LLM | Anthropic (default) o OpenAI — parser (Haiku / gpt-4o-mini) + chat Q&A (Sonnet / gpt-5-mini) |
| WhatsApp | Meta Cloud API + HMAC webhook |
| FX | Frankfurter + DolarAPI (ARS/MEP) + override manual |
| Frontend | React 19, Vite 8, TypeScript, Tailwind v4, TanStack Query, React Router 7, Recharts, Lucide |
| Deploy | Railway — **un solo** proceso Docker (API + SPA + webhook). **Nunca** `uvicorn --workers` (locks del bot son in-process) |

## Layout del repo

```
spitwise/
├── CLAUDE.md                 ← este archivo
├── DEPLOY.md                 ← runbook de producción (Railway, Meta, Andiamo)
├── Dockerfile                ← multi-stage: Vite build → Python runtime
├── railway.json
├── .claude/commands/         ← skills de UI genéricos (no lógica de dominio)
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI + lifespan seed + SPA mount
│   │   ├── config.py         # pydantic-settings
│   │   ├── db/models.py      # entidades SQLAlchemy
│   │   ├── api/              # REST /api/v1 + schemas
│   │   ├── bot/              # dispatcher, capture, editor, QA, render, copy
│   │   ├── llm/              # parser + chat tool-use
│   │   ├── qa/tools.py       # tools del agente Q&A
│   │   ├── whatsapp/         # Meta client, dedupe, signature
│   │   ├── categories/       # catálogo fijo de 10 categorías
│   │   ├── andiamo.py        # sync de stops
│   │   ├── balance.py        # neto puro (sin I/O)
│   │   ├── spend.py          # user_share para analytics
│   │   ├── fx.py
│   │   └── trip_time.py
│   ├── alembic/
│   └── tests/
└── frontend/
    └── src/
        ├── App.tsx           # rutas + auth guard
        ├── pages/            # Dashboard, Cities, Movements, Login
        ├── components/       # feature + ui/*
        ├── api/              # axios wrappers
        ├── lib/              # format, charts, cn
        └── types/
```

No hay README de producto: `DEPLOY.md` es la doc operativa.

## Cómo correr local

```bash
# Backend
cd backend
cp .env.example .env          # completar SECRET_KEY, AUTH_USERS, LLM keys, etc.
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend (otra terminal)
cd frontend
npm ci
npm run dev                   # :5173, proxy /api y /webhooks → :8000
```

Lifespan de `main.py`: seed idempotente de categorías, usuarios desde `AUTH_USERS`, y sync de Andiamo si `ANDIAMO_URL` está seteada.

```bash
# Tests
cd backend && pytest
cd frontend && npm test
```

## Modelo de dominio

Definido en `backend/app/db/models.py`. Tipos API en `api/schemas.py`; mirror TS en `frontend/src/types/index.ts`.

| Entidad | Rol |
|---------|-----|
| **User** | Login web + `whatsapp_wa_id` |
| **Category** | 10 fijas: Alojamiento, Comida, Supermercado, Transporte, Actividades, Compras, Bebidas/Salidas, Regalos, Salud, Otros |
| **Movement** | `expense` \| `settlement`; `split`: `shared` \| `payer_only` \| `other_only`; FX + ciudad |
| **Stop** | Parada de itinerario cacheada desde Andiamo (+ locales: ver `is_local`) |
| **FxRate** | Cache diario de tasas |
| **BotPendingAction** | Flujos multi-step (categoría ambigua, confirm delete) |
| **WhatsAppSessionState** | Override de ciudad activa + historial Q&A |
| **WhatsAppDedupe** | Idempotencia por `wamid` |

### Invariantes de negocio (no romper)

1. **Exactamente 2 usuarios** — `get_trip_users` / balance fallan si no.
2. **Balance** (`balance.py`): gastos `shared` = 50/50; `payer_only` no mueve neto; `other_only` = el otro debe todo; settlements reducen deuda del que paga.
3. **Spend personal** (`spend.py` / `user_share`) — usado en dashboard, distinto del neto.
4. **Fecha FX = hoy (load date)**, no la fecha del movimiento.
5. **PATCH con `fx_rate` manual** → `fx_source=manual`; editar descripción después **no** debe pisar la tasa.
6. **Itinerario** no se hardcodea: usar filas `Stop` sincronizadas.
7. **Stops locales** (`Stop.is_local`, hoy solo *Pititas*): existen solo en Spitwise. El sync de Andiamo **no** los reconcilia y las APIs de integración **no** los exponen. Un `Stop.owner_username` seteado imputa **por fecha** solo a ese usuario, y **por remitente** (no por `paid_by`). Nombrar la parada es intención explícita y matchea para **los dos** (Bruno puede mandar un gasto a Pititas si le pagó algo de ese tramo); lo que no cambia es el default por fecha. Ver `app/stops_local.py` y la sección *Stop local Pititas* de `DEPLOY.md`.
8. **El parser recibe el catálogo de paradas** (`load_city_names`): sin él, el LLM solo reconoce ciudades por cultura general y se pierde las de nombre propio (*Pititas*, *Highlands*). Si agregás una parada de nombre raro, no hace falta tocar el prompt — sale de la DB.

## API (prefijo `/api/v1`)

Auth JWT Bearer salvo lo indicado.

| Área | Endpoints |
|------|-----------|
| Auth | `POST /auth/login`, `GET /auth/me` |
| Users | `GET /users` |
| Movements | CRUD + `?sort=date\|created` |
| Balance | `GET /balance` |
| Categories | `GET /categories` |
| Dashboard | `/dashboard/summary`, `/by-city`, `/by-category`, `/timeseries` |
| City analytics | `/dashboard/city/*` filtrado por `slugs` |
| Stops | `GET /stops` (excluye candidatas y archivadas) |
| Config | `GET /config` (JWT) — `andiamo_url` para deep links del frontend |
| Integration | `GET /cities/spend`, `GET /cities/spend-detail?slug=`, `GET /trip/spend`, `POST /andiamo/sync-hook` (todos `X-Api-Key`), `POST /andiamo/sync` (JWT) |
| Webhook | `GET/POST /webhooks/whatsapp` |
| Health | `GET /health` |

## Bot WhatsApp

Flujo (`api/webhook.py` → `bot/dispatcher.py`):

```
Meta POST → HMAC → dedupe wamid → 200 inmediato
         → BackgroundTasks + asyncio.Lock por wa_id
         → ensure_stops_fresh (lazy 6h)
         → dispatch() → Meta send
```

Orden en `dispatch`:

1. Resolver usuario por `whatsapp_wa_id`
2. Interactive (botones) → `interactive.py`
3. Fast path: `borrar` / `ayuda` / `help` sin LLM
4. Parser LLM → intents: `expense`/`settlement` → `capture.py`; `edit`/`delete` → `editor.py`; `question` → `qa.py`; `unknown` → QA si hay historial fresco, si no help

Reglas del bot:

- Strings UX → `bot/copy.py` y `bot/render.py` (voseo rioplatense; nunca exponer errores técnicos).
- Números en es-AR (`1.234,5`) — mismo criterio en backend `render.ar_number` y frontend `lib/format.ts`.
- Q&A: tools en `qa/tools.py`; **delete nunca es directo** — crea pending + botones de confirmación.
- Split por defecto shared; cambio de split vía NL (`edit`) o botones legacy `split_*`.

## Frontend

Rutas (`App.tsx`): `/login`, `/` Dashboard, `/ciudades`, `/movimientos` (JWT en `localStorage.auth_token`).

- Tokens de diseño en `frontend/src/index.css` (Anton + Hanken Grotesk, paleta brick/terracotta).
- Primitivos en `components/ui/*`; charts con Recharts + `lib/chartTheme.ts`.
- Iconos: Lucide (no emoji en chrome UI; banderas de país OK).
- Alias `@/` → `src/`.

## Patrones a seguir

- Lógica de bot en `app/bot/`, no en routers API.
- Reutilizar `compute_balance`, `user_share`, `convert_to_usd` — no duplicar reglas.
- Updates parciales de movimientos: `MovementUpdate` + `model_fields_set`, no `MovementIn`.
- Tests backend: `FakeLLM` + fixtures de `conftest.py` (SQLite in-memory).
- Secretos solo en env / Railway — nunca committear `.env`.
- Cuenta Railway **personal** (misma que Andiamo), no Kavak.

## Variables de entorno (nombres)

Mínimo local (`.env.example`): `DATABASE_URL`, `FRANKFURTER_URL`, `DOLARAPI_URL`, `SPITWISE_URL`, `ENVIRONMENT`.

Producción / features (ver `config.py` y `DEPLOY.md`):

- Auth: `SECRET_KEY`, `AUTH_USERS` (`user:pass:wa_id,...`), `JWT_EXPIRE_DAYS`, `CORS_ORIGINS`
- LLM: `LLM_PROVIDER`, `ANTHROPIC_*`, `OPENAI_*`, `CHAT_TIMEOUT_SECONDS`, `QA_*`
- WhatsApp: `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET`, `WHATSAPP_GRAPH_VERSION`
- Integración: `TRIP_SHARED_API_KEY`, `ANDIAMO_URL`
- Deploy: `FRONTEND_DIST` (seteado en Docker)

## Entry points rápidos

| Qué | Dónde |
|-----|--------|
| App factory | `backend/app/main.py` |
| Settings | `backend/app/config.py` |
| Models | `backend/app/db/models.py` |
| API aggregator | `backend/app/api/router.py` |
| Webhook | `backend/app/api/webhook.py` |
| Bot router | `backend/app/bot/dispatcher.py` |
| Parser LLM | `backend/app/llm/parser.py` |
| Q&A tools | `backend/app/qa/tools.py` |
| Frontend routes | `frontend/src/App.tsx` |
| Design tokens | `frontend/src/index.css` |
| Deploy | `DEPLOY.md` |

## Antes de cambiar cosas sensibles

- Webhook: Meta timeout ~5s → el 200 **siempre** antes del LLM.
- Multi-worker / horarios de process → rompe locks y pending del bot **y** las guardas del sync de Andiamo (`_refresh_running`/`_dirty` en `andiamo.py`).
- Sync de stops: Andiamo pushea `POST /andiamo/sync-hook` en cada alta/edición/borrado (patrón pull-on-ping); el TTL 6h queda como fallback. La reconciliación **archiva** (`Stop.is_archived`) los stops borrados en Andiamo que tienen movimientos y borra los que no; payload vacío o parcial nunca toca el snapshot.
- Catálogo de categorías (`categories/catalog.py`): el orden es `sort_order` y `Otros` va último. Todo lo demás es derivado (seed, prompt del parser vía `load_categories`, emojis del bot, API) — sumar una categoría son **3 lugares**: la tupla acá, una entrada en `CATEGORY_META` (`frontend/src/lib/chartTheme.ts`: ícono + color + fondo, más su token `--color-accent-*` en `index.css`) y el `MAP` de `andiamo/src/lib/categoryIcons.ts`. Los tres frontends degradan solos (ícono Tag + gris), así que olvidarse no rompe: se ve feo.
  - La **descripción es el clasificador**, no documentación: se inyecta en el prompt del parser. Si dos se pisan (p. ej. "supermercado" viviendo en Comida y en Supermercado), el LLM elige mal. Mantenerlas mutuamente excluyentes y marcar el borde explícito.
  - Color nuevo: correr `scripts/validate_palette.js` de la skill dataviz sobre los 10 hex antes de commitear. La paleta está validada a **pares adyacentes** (no all-pairs, que no pasa ni con los 6 originales); el peor caso CVD está en la banda 6–8, legal porque el color siempre viene con ícono + label.
  - Actualizar `tests/test_categories_seed.py` (lista exacta + count).
- Contrato Andiamo (`/cities/spend`, sync de stops): coordinar key `TRIP_SHARED_API_KEY` en ambos servicios.
- `?user=` en `/cities/spend-detail` y `/trip/spend`: filtra a la parte de esa persona vía `user_share` (mitad de un compartido, entero de uno propio) y **omite los privados del otro** — Andiamo lo usa para que cada uno vea solo sus gastos. `amount` se escala junto al share para que la moneda local cierre con el USD. Sin el param, gross del hogar (contrato original intacto). Un username desconocido es **400, nunca fallback a gross**: degradar le filtraría a uno los gastos privados del otro. `/cities/spend` sigue siendo gross-only.
