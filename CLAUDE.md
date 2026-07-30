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

**Demo pública (`demo.spitwise.lat`):** mismo repo y rama que prod, gobernada por `DEMO_MODE`. Apaga el router del webhook (la demo es solo la web), **saltea el gate de contraseña del login** (entrada libre: es el punto del deploy) y `DEMO_TODAY` **congela el reloj del viaje** en `trip_time.today_in_tz` — el único punto donde la web lee la fecha. Tiene que ser el mismo valor que congela Andiamo (`NEXT_PUBLIC_DEMO_TODAY`) o cada app muestra una parada actual distinta. Seed: `scripts/seed_demo_money.py` (ver `DEPLOY.md`).

**Login (`POST /auth/login`):** contraseña **del deploy**, no del usuario — `LOGIN_PASSWORDS` es una lista separada por comas y se compara constant-time contra todas las entradas, sin cortar en la primera. `AUTH_USERS`/`password_hash` siguen siendo solo el mapeo de `wa_id`: no los mezcles con el gate (el `AUTH_USERS` de la demo es literalmente `bruno:demo:`). El `username` sigue eligiendo *quién* sos. Falla cerrado y `main._assert_prod_secrets` no deja arrancar sin la variable fuera de `DEMO_MODE`. Throttle in-process de 8 fallos/10 min por IP en `api/auth.py` — depende del proceso único, igual que los locks del bot. La pantalla `/login` de prod lleva arriba el CTA a `DEMO_URL` (vía `/public-config`, porque el bundle se compila en el Dockerfile y ninguna `VITE_*` de runtime llega): es la puerta de entrada de quien viene del CV.

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
│   │   ├── qa/tools.py       # tools del agente Q&A financiero
│   │   ├── qa/trip_tools.py  # tools del agente Q&A de viaje (guías/notas)
│   │   ├── whatsapp/         # Meta client, dedupe, signature
│   │   ├── categories/       # catálogo fijo de 11 categorías
│   │   ├── andiamo.py        # sync de stops
│   │   ├── andiamo_content.py # sync de guías + notas (Q&A de viaje)
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

## Escenarios del bot WhatsApp (sin Meta)

Para validar que el bot entiende bien charlas reales **sin pasar por Meta**: el
script espeja `webhook.process_message` (stops → due → **dispatch**) con LLM real
(OpenAI desde `.env`) y DB SQLite in-memory. No llama a Graph API.

| Qué | Dónde |
|-----|--------|
| Runner | `backend/scripts/bot_scenario_runner.py` |
| Transcript de la última corrida | `backend/scripts/bot_scenarios.md` |
| Suite crítica (default, **10**) | `SUITE_CRITICAL` — óptima para **una** sesión Claude/Fable |
| Extras de valor (**16**) | `CONVERSATIONS_EXTRA` — con `--all` / `--only` (incluye 2 de guías/trip Q&A) |

**Default = 10 críticas** (cuotas, batch+split, day-trip, pending+saldo, corrección
corta, delete, settlement, batch+borrar, Pititas owner, moneda). Cada escenario
lleva checklist **Mirar** (qué falla / qué DB esperar) + **Dónde tocar**.

**Verificador, no solo transcript:** cada escenario declara **checks
deterministas** (estado de la DB, intent ruteado, tools llamadas — nunca
wording) y el runner sale con **exit code 1** si alguno falla. La traza sale de
`app/trace.py` (contextvar que solo encienden los runners). Cada conversación
corre con **DB e historial propios**: compartir sesión hacía que un escenario
contaminara el contexto reciente del siguiente.

**Contrato del `.md`:** cada corrida **borra y reescribe** `bot_scenarios.md`.
No acumula historial. Por mensaje publica latencia `stops_s` / `due_s` /
`dispatch_s` / `total_s`, la traza del turno y el resultado de los checks. El
catálogo editable es el Python, no el markdown.

```bash
cd backend
# Suite crítica (10)
.venv/bin/python scripts/bot_scenario_runner.py

# Crítica + 16 extras (26)
.venv/bin/python scripts/bot_scenario_runner.py --all

# Subconjunto: por índice o por id estable (los ids sobreviven al reordenamiento)
.venv/bin/python scripts/bot_scenario_runner.py --only 1,4,6
.venv/bin/python scripts/bot_scenario_runner.py --only cuotas-total,pititas-owner
.venv/bin/python scripts/bot_scenario_runner.py --from 11 --to 14

# Proveedor: default el de .env (= producción); forzable
.venv/bin/python scripts/bot_scenario_runner.py --provider anthropic
```

Requiere la API key del proveedor elegido. Hoy ficticio fijo mid-trip
(`2026-08-20`, Lisboa). Seed incluye Pititas (`is_local`,
`owner_username=katia`).

**Gate prompt→escenario:** `tests/test_prompt_coverage.py` hashea los tres
`_SYSTEM` (parser, Q&A financiero, Q&A de viaje) contra
`tests/prompt_manifest.json`. Tocar un prompt sin declarar los escenarios que
lo cubren (y el comando `--only` para reproducirlos) rompe el test.

### Canal viaje (guías + notas)

Script aparte, no mezclado con la suite financiera:

```bash
cd backend
.venv/bin/python scripts/bot_trip_scenario_runner.py
.venv/bin/python scripts/bot_trip_scenario_runner.py --only 2,3,6
.venv/bin/python scripts/bot_trip_scenario_runner.py --only auschwitz-nota,cambio-canal
.venv/bin/python scripts/bot_trip_scenario_runner.py --provider anthropic
```

Mismos checks deterministas y exit code que el runner financiero (acá miran
canal ruteado y tools: ningún escenario de viaje puede tocar `qa/tools.py`).

Carga markdown real desde `../andiamo/content/guides` + notas alineadas al
Itinerary. Hoy fijo `2026-09-25` (Viena). **11 escenarios**. Transcript →
`scripts/bot_trip_scenarios.md`.

## Demo local (datos dummy, mid-trip)

`backend/scripts/seed_demo_data.py` construye una DB SQLite local lista para
navegar la app **como si estuvieras en el medio del viaje**: itinerario de **108
noches** (alineado a Andiamo/PRESUPUESTO: paradas + Sur Italia 10n + margen flex 3n)
donde **HOY cae en el día 40** (faltan 68). Las fechas se
derivan de `date.today()`, así que siempre luce mid-trip. Es self-bootstrapping
(crea tablas + siembra categorías y usuarios), idempotente, y deja `backend/demo.db`
(gitignoreada). Sirve para probar `/viaje`, `/ciudades` (mano a mano) y `/movimientos`
con paradas pasadas / en curso / futuras (estas últimas solo con la reserva de
alojamiento, cargada hoy con `payment_date` al check-in → movimiento *pending* /
ciudad "reservado").

```bash
cd backend
# 1) Reconstruir la DB dummy
DATABASE_URL="sqlite+aiosqlite:///$(pwd)/demo.db" \
SECRET_KEY=demo-secret-key-local-only \
AUTH_USERS="bruno:demo:5491111,katia:demo:5492222" \
ENVIRONMENT=dev \
.venv/bin/python scripts/seed_demo_data.py

# 2) Levantar el backend contra esa DB (login: elegir Bruno o Katia en /login)
DATABASE_URL="sqlite+aiosqlite:///$(pwd)/demo.db" \
SECRET_KEY=demo-secret-key-local-only ENVIRONMENT=dev \
AUTH_USERS="bruno:demo:5491111,katia:demo:5492222" \
CORS_ORIGINS=http://localhost:5173 \
.venv/bin/uvicorn app.main:app --port 8000
```

Sin `--reload` ni `--workers` (el demo comparte las reglas de proceso único del bot).
Todo `/api/*` responde `Cache-Control: no-store` (middleware en `main.py`): sin eso el browser cachea heurísticamente sobre disco y llegó a servir un catálogo de categorías viejo contra una DB ya migrada — como los chips mandan `category_id`, imputaba la categoría equivocada.

## Modelo de dominio

Definido en `backend/app/db/models.py`. Tipos API en `api/schemas.py`; mirror TS en `frontend/src/types/index.ts`.

| Entidad | Rol |
|---------|-----|
| **User** | Login web + `whatsapp_wa_id` |
| **Category** | 11 fijas: Alojamiento, Comida, Cafetería, Supermercado, Transporte, Actividades, Compras, Salidas, Lavandería, Salud, Otros |
| **Movement** | `expense` \| `settlement`; `split`: `shared` \| `payer_only` \| `other_only`; FX + ciudad. Eje temporal de lista/agrupación: `created_at` (fecha de carga). `payment_date` opcional (fecha en que se paga/pagó) + `status`: `confirmed` \| `pending` (futuro con TC proxy). `cashback_kind`/`cashback_value` opcionales: cashback de tarjeta (ver invariante 10) |
| **Stop** | Parada de itinerario cacheada desde Andiamo (+ locales: ver `is_local`) |
| **GuideDoc / StopGuide / TripNote / SyncMeta** | Cache del contenido de viaje de Andiamo (guías markdown, mapeo stop→guía, notas, version del export) para el Q&A de viaje del bot — sync en `app/andiamo_content.py` |
| **FxRate** | Cache diario de tasas |
| **BotPendingAction** | Flujos multi-step (categoría ambigua, confirm delete) |
| **WhatsAppSessionState** | Historial Q&A por wa_id (`qa_history` finanzas / `trip_qa_history` viaje — nunca mezclar) |
| **WhatsAppDedupe** | Idempotencia por `wamid` |

### Invariantes de negocio (no romper)

1. **Exactamente 2 usuarios** — `get_trip_users` / balance fallan si no.
2. **Balance** (`balance.py`): gastos `shared` = 50/50; `payer_only` no mueve neto; `other_only` = el otro debe todo; settlements reducen deuda del que paga.
3. **Spend personal** (`spend.py` / `user_share`) — usado en dashboard, distinto del neto.
4. **Fecha de pago** (`Movement.payment_date`, opcional; NULL = día de carga): la fecha que traiga un mensaje ("ayer", "se paga el 3-sep") elige la parada mirando el itinerario (`resolve_place`) **y se persiste**. Reglas derivadas (todas server-side, `status` nunca lo escribe el cliente):
   - **TC = fecha de pago capeada a hoy** (`fx.fx_reference_date`): pasada → histórico Frankfurter; futura o NULL → proxy del día de carga. ARS es la excepción (DolarAPI solo publica MEP vivo → siempre tasa del día en que se procesa).
   - **Futura → `status='pending'`**: cuenta en totales/analytics pero **no** en el balance (`compute_balance` lo excluye vía `balance.UNSETTLED`) ni en las líneas "le debe" del bot. Al llegar la fecha, la liquidación lazy (`app/due.py`, throttle 15 min colgado de webhook/API/lifespan, sin cron) recalcula el TC real y lo deja en **`status='awaiting'`** (TC lockeado, **una sola vez**; el query filtra solo `pending`, así ARS no driftea). `awaiting` sigue afuera del balance: espera **confirmación manual** en la web. Tasa `fallback` no liquida (reintenta) y `fx_source=manual` se liquida sin recalcular.
   - **`awaiting` → confirmación manual (web-only)**: `POST /movements/{id}/confirm` (body `{paid_by?}`) valida el pagador y lo pasa a `confirmed` — recién ahí entra al balance. Único camino de confirmación (el cliente nunca escribe `status`). Dos guardas server-side lo sostienen: un movimiento en `awaiting` **conserva** ese estado si le editan la fecha (`due.next_status_for_date` — derivarlo solo de la fecha dejaba que un edit lo confirmara de prepo), y `/confirm` **rechaza** (409) un `pending` a más de 1 día, que quedaría clavado al TC proxy porque la liquidación solo mira `status='pending'`. `/movimientos` muestra un **banner** (`PendingConfirmBanner`) con los gastos por confirmar + un **badge** en la nav; el aviso aparece desde 1 día antes de la fecha (`lib/share.needsConfirmation`: `awaiting` siempre, `pending` a ≤1 día) y sale al confirmar. El bot **no** confirma ni avisa (evita templates pagos de Meta).
   - **Pago en etapas** ("30% hoy y el resto el 3-sep"): el parser devuelve `installments` (percent/amount/date por etapa, sin aritmética del LLM) y `capture.expand_installments` genera N movimientos hermanos vía el camino batch — montos que cierran exacto con el total (la última etapa absorbe el redondeo) y sufijo `(i/n)` en la descripción. Todas las etapas comparten **una** parada y un split: `place_date` (fijado a la fecha de la última etapa, el check-in) manda en `resolve_place`, así "30% hoy y el resto el 3-sep" no parte el gasto en dos ciudades.
   - La lista y el agrupamiento por día siguen por `created_at`; `payment_date` se muestra como dato (card del bot, sheet de la web). **Nunca countdowns.**
5. **Resolución de ciudad** (`bot/capture.py::resolve_place` + API): (a) ciudad explícita que matchea una parada → esa; (b) ciudad que no matchea (day-trip "Sintra") → la parada base de la fecha de referencia — `city_name` **siempre** sale de un `Stop` o es `null`, nunca texto libre; (c) sin ciudad ni fecha → parada de hoy (estricta: fuera de rango => General); (d) sin ciudad solo con flag `general` explícito o settlements. La API valida `stop_slug` contra paradas reales (422 si no existe) y deriva `city_name` del Stop.
6. **Re-precio de FX** (`fx.reprice_movement`, política única de API/editor/batch): al cambiar el neto de un movimiento existente **no** se re-cotiza a ciegas. Dos tasas están **lockeadas** (`fx.is_rate_locked`): `fx_source=manual` (invariante 6 de siempre) y `status='awaiting'` (el TC real ya lo fijó `due.py`; recotizar lo rompe en ARS, donde `get_rate_to_usd` fuerza `cache_date=today`). Y si el proveedor está caído (`src='fallback'`) pero ya había tasa buena, se **conserva** la buena — misma guarda que `due.py`. Además los bordes comparan **valores**, no presencia de campos: un cliente que re-manda el body entero no gatilla nada (`AddMovementDialog` manda diff contra `editing`). `map_fx_source` también vive en `fx.py`: no volver a duplicarlo.
7. **Itinerario** no se hardcodea: usar filas `Stop` sincronizadas.
8. **Stops locales** (`Stop.is_local`, hoy solo *Pititas*): existen solo en Spitwise. El sync de Andiamo **no** los reconcilia y las APIs de integración **no** los exponen. Un `Stop.owner_username` seteado imputa **por fecha** solo a ese usuario, y **por remitente** (no por `paid_by`). Nombrar la parada es intención explícita y matchea para **los dos** (Bruno puede mandar un gasto a Pititas si le pagó algo de ese tramo); lo que no cambia es el default por fecha. Ver `app/stops_local.py` y la sección *Stop local Pititas* de `DEPLOY.md`.
   - **Split por default según dueño** (`capture.owner_split`, aplicado en el bot **y** en `POST /movements`): un gasto que cae en una parada con `owner_username` no se reparte 50/50 — es de esa persona por default, sin aclararlo. El valor es relativo al pagador: paga el dueño → `payer_only`; paga el otro → `other_only` (la card muestra *Solo Katia* / *Solo Bruno* en ambos casos). Solo pisa el default `shared`; un split individual explícito en el mensaje se respeta. Pititas tiene `owner_username=katia` desde el seed; Portugal (Lisboa/Porto) lo recibe de `stops_local._sync_counterpart_owner` (paradas contenidas enteras en la ventana de Pititas → dueño = el otro viajero). Sin owner seteado, degrada a `shared`.
9. **El parser recibe el catálogo de paradas** (`load_city_names`): sin él, el LLM solo reconoce ciudades por cultura general y se pierde las de nombre propio (*Pititas*, *Highlands*). Si agregás una parada de nombre raro, no hace falta tocar el prompt — sale de la DB.
10. **Cashback** (`app/cashback.py`, `Movement.cashback_kind`/`cashback_value`): cashback de tarjeta declarado al cargar el gasto. `amount` siempre guarda el **bruto** tipeado (lo que dice el ticket / lo que se ve al editar); el **neto** es derivado (`net_amount`, `kind='pct'`→% / `'amount'`→monto fijo local, clamp a ≥0) y se **hornea en `amount_usd`** con la regla única de todo borde de escritura: `amount_usd = net_amount(...) × fx_rate` (fx_rate = tasa de mercado pura). De ahí sale que balance, spend, analytics e integración reflejan el neto **sin tocarlos** (todos ya usan `amount_usd`). El cashback **baja el gasto para los dos** (un shared con cashback reparte el neto). NULL = sin cashback (net == gross). Solo en `expense` (nunca settlement). En la web se muestra el neto + badge/row; el bruto solo al editar. Un cashback fijo mayor al gasto se descarta en TODOS los canales (`normalize_cashback` con el monto, además de `validate_cashback` en la API): sin eso el bot aceptaba "20 euros con 50 de cashback" y el neto clampeaba a 0. Cuotas: el cashback en `pct` se replica a cada etapa; `amount` fijo + cuotas no se reparte (edge documentado). Sumar un sitio que compute `amount_usd` obliga a partir del neto — no dupliques `amount * rate`.

## API (prefijo `/api/v1`)

Auth JWT Bearer salvo lo indicado.

| Área | Endpoints |
|------|-----------|
| Auth | `POST /auth/login`, `GET /auth/me` |
| Users | `GET /users` |
| Movements | CRUD — orden fijo por `created_at` desc (sin `?sort`) |
| Balance | `GET /balance` |
| Categories | `GET /categories` |
| Dashboard | `/dashboard/summary`, `/by-category`, `/pace` (ritmo $/día: alojamiento prorrateado por noches, generales por todo el viaje — ver `app/analytics.py`) |
| City analytics | `/dashboard/city/summary\|by-category\|movements` filtrado por `slugs` |
| Stops | `GET /stops` (excluye candidatas y archivadas) |
| Config | `GET /config` (JWT) — `andiamo_url` para deep links del frontend; `GET /public-config` (sin auth) — agrega `demo`, que el frontend necesita en `/login` donde todavía no hay JWT |
| Integration | `GET /cities/spend`, `GET /cities/spend-detail?slug=`, `GET /trip/spend`, `POST /andiamo/sync-hook` (todos `X-Api-Key`; body opcional `{event}`: `stops.changed` default, `notes.changed`, `guides.changed`), `POST /andiamo/sync` (JWT) |
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
3. Fast path sin LLM: `borrar` / `ayuda` / `help`, y consultas `saldo` / `total` (`bot/quick.py`)
4. Parser LLM (un solo retry, **solo** ante falla técnica: refusal / structured output vacío / proveedor caído → `ParsedMessage.parse_failure`) → intents: `expense`/`settlement` → `capture.py`; `edit`/`delete` → `editor.py`; `question` → `qa.py`; `trip_question` → `trip_qa.py`; `unknown` → finanzas si el mensaje trae señales inequívocas de plata (`quick.ledger_signal`), si no el canal Q&A con historial fresco más reciente (`trip_qa.latest_fresh_channel`), si no help. Un `parse_failure` NO se rutea a ningún agente: se dice que se trabó.

Reglas del bot:

- Strings UX → `bot/copy.py` y `bot/render.py` (voseo rioplatense; nunca exponer errores técnicos).
- **Loop de chat** (`llm/chat.py`): `run()` devuelve `ChatResult` con outcome (`ok`,
  `iteration_cap`, `budget_exceeded`, `empty_completion`, `provider_error`,
  `tool_error`) + traza segura. Presupuestos separados de rondas, tool calls
  (`qa_max_tool_calls`) y tiempo, con una **llamada final sin tools** reservada
  para sintetizar la evidencia ya juntada. Sin texto usable, cada canal degrada
  con su copy (`copy.chat_degraded`) y **ese turno no se guarda en el historial**.
  Si una acción ya se aplicó (`ActionContext.performed`), se confirma el efecto real.
- **Guardas de grounding** (prohibir no alcanza, hay que verificar): en viaje, una
  respuesta con datos concretos, sin tools en el turno y sin hilo previo se
  reemplaza por una negativa grounded; en finanzas, negar gastos ("no hay gastos",
  "USD 0") sin haber llamado `aggregate_expenses`/`list_movements` tampoco se manda.
- Números en es-AR (`1.234,5`) — mismo criterio en backend `render.ar_number` y frontend `lib/format.ts`.
- Q&A: tools en `qa/tools.py`; **delete nunca es directo** — crea pending + botones de confirmación.
- **Q&A de viaje** (`bot/trip_qa.py` + `qa/trip_tools.py`): canal AISLADO del financiero — prompt, tools (search/list/read de guías + notas) e historial propios. Grounded: solo responde con lo que hay en `guide_docs`/`trip_notes`; si no está, lo dice. Respuestas cortas + deep-link `{andiamo_url}/guias/<guide>/<doc>`. Preguntas de plata las deriva al canal financiero. No mezclar tools/prompt entre los dos agentes.
- Escritura: nada entra a medias en silencio. Cuotas declaradas que no cierran no
  se guardan (se pide la aclaración), montos <= 0 se rechazan igual que en la API,
  y todo descarte (tope de 10 gastos, cashback fijo en cuotas, batch multi-moneda
  no reescalable) se dice en la respuesta.
- El "último movimiento corregible" es **por remitente** (`created_by`) e incluye
  los pagos de saldo: son dos chats contra el mismo ledger.
- Descripciones estandarizadas: el prompt pide sentence case + nombres propios; `app/textnorm.normalize_description` (nombres propios = Stops de la DB) es la red de seguridad en todos los bordes de escritura (capture, editor, API). One-off para datos viejos: `scripts/normalize_descriptions.py`.
- Split por defecto shared; cambio de split vía NL (`edit`) o botones legacy `split_*`.
- **Canal documentos** (`bot/documents/` + `llm/vision.py` + `andiamo_documents.py`): un adjunto (imagen/PDF) NUNCA entra al parser financiero — rama propia en `dispatch` antes del camino de texto. Vision (OpenAI, `OPENAI_VISION_MODEL`) extrae `{kind, doc_date, stop_slug, label, note}` con catálogo dinámico de Stops y kinds (`documents/kinds.py`, espejo del enum de Andiamo; desync degrada a `other`). Reglas del prompt: `doc_date` = fecha en que se NECESITA el doc (nunca compra/emisión; rango → primera), traslados → parada DESTINO, caption del usuario pisa ciudad/fecha y alimenta la nota (la IA redacta, no pega). Preview + botones `doc_save:`/`doc_cancel:` (pending `doc_upload`); al confirmar se re-descarga de Meta y se sube multipart a `POST {ANDIAMO_URL}/api/integration/documents` (X-Api-Key; Andiamo es dueño del storage R2). Con preview fresco (`DOC_PENDING_FRESH_MINUTES`), un texto puede corregirlo ('es en York') — costo en el camino financiero: UNA query indexada; sin pending, cero.
- **Corrección de gasto reciente** (`editor.recent_movement` + `describe_recent`): tras cargar un gasto, el parser recibe ese último gasto como contexto (`last_expense`, ventana `EDIT_RECENT_TTL_MINUTES`, default 15). Una corrección natural sin monto nuevo (_contalo solo para katia_, _era en Paris_, _fueron 45_, _pagó bruno_, _es transporte_) se clasifica `edit` con `ref_last` y edita ese movimiento. Red de seguridad en `dispatcher`: un `expense` sin monto con un gasto fresco a la vista no da dead-end ("no le pesqué el monto") sino que guía a corregir el último.

## Frontend

Rutas (`App.tsx`): `/login`, `/` Dashboard, `/ciudades`, `/movimientos` (JWT en `localStorage.auth_token`).

- Tokens de diseño en `frontend/src/index.css` (Anton + Hanken Grotesk, paleta brick/terracotta).
- Primitivos en `components/ui/*`; charts con Recharts + `lib/chartTheme.ts`.
- Iconos: Lucide (no emoji en chrome UI; banderas de país OK).
- Alias `@/` → `src/`.
- **Pruebas visuales / browser (MCP Playwright o Claude in Chrome):** siempre con viewport **iPhone 17** — `402×874` CSS px, `deviceScaleFactor: 3`, mobile UA. No probar el frontend en desktop por defecto.

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

- Auth: `SECRET_KEY`, `LOGIN_PASSWORDS` (lista separada por comas), `AUTH_USERS` (`user:pass:wa_id,...` — solo el `wa_id` se usa), `JWT_EXPIRE_DAYS`, `CORS_ORIGINS`
- Demo: `DEMO_MODE`, `DEMO_TODAY`, `DEMO_URL`
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
| Q&A de viaje (guías/notas) | `backend/app/bot/trip_qa.py` + `backend/app/qa/trip_tools.py` |
| Sync contenido Andiamo | `backend/app/andiamo_content.py` |
| Frontend routes | `frontend/src/App.tsx` |
| Design tokens | `frontend/src/index.css` |
| Deploy | `DEPLOY.md` |
| Escenarios bot (sin Meta) | `backend/scripts/bot_scenario_runner.py` (default 10 críticas) → `bot_scenarios.md` |

## Antes de cambiar cosas sensibles

- Webhook: Meta timeout ~5s → el 200 **siempre** antes del LLM.
- Multi-worker / horarios de process → rompe locks y pending del bot **y** las guardas del sync de Andiamo (`_refresh_running`/`_dirty` en `andiamo.py` **y** en `andiamo_content.py`) **y** el throttle de la liquidación lazy (`_last_check` en `due.py`).
- Sync de stops: Andiamo pushea `POST /andiamo/sync-hook` en cada alta/edición/borrado (patrón pull-on-ping); el TTL 6h queda como fallback. La reconciliación **archiva** (`Stop.is_archived`) los stops borrados en Andiamo que tienen movimientos y borra los que no; payload vacío o parcial nunca toca el snapshot.
- Sync de contenido (guías/notas, `andiamo_content.py`): **NUNCA** colgarlo del path caliente del webhook — solo lifespan, sync-hook y lazy dentro de `handle_trip_question` (dispara task, no bloquea). Andiamo lo alimenta con `GET /api/guides/export` (bulk con `version`; no-op si no cambió) y `GET /api/notes`; las server actions de notas de Andiamo pingean `notes.changed`. Payload inválido nunca arrasa el snapshot.
- Catálogo de categorías (`categories/catalog.py`): el orden es `sort_order` y `Otros` va último. Todo lo demás es derivado (seed, prompt del parser vía `load_categories`, emojis del bot, API) — sumar una categoría son **3 lugares**: la tupla acá, una entrada en `CATEGORY_META` (`frontend/src/lib/chartTheme.ts`: ícono + color + fondo, más su token `--color-accent-*` en `index.css`) y el `MAP` de `andiamo/src/lib/categoryIcons.ts`. Los tres frontends degradan solos (ícono Tag + gris), así que olvidarse no rompe: se ve feo.
  - La **descripción es el clasificador**, no documentación: se inyecta en el prompt del parser. Si dos se pisan (p. ej. "supermercado" viviendo en Comida y en Supermercado), el LLM elige mal. Mantenerlas mutuamente excluyentes y marcar el borde explícito.
  - Color nuevo: correr `scripts/validate_palette.js` de la skill dataviz sobre los 11 hex antes de commitear. La paleta está validada a **pares adyacentes** (no all-pairs, que no pasa ni con los 6 originales); el peor caso CVD está en la banda 6–8, legal porque el color siempre viene con ícono + label.
  - Actualizar `tests/test_categories_seed.py` (lista exacta + count).
- Contrato Andiamo (`/cities/spend`, sync de stops): coordinar key `TRIP_SHARED_API_KEY` en ambos servicios.
- `?user=` en `/cities/spend-detail` y `/trip/spend`: filtra a la parte de esa persona vía `user_share` (mitad de un compartido, entero de uno propio) y **omite los privados del otro** — Andiamo lo usa para que cada uno vea solo sus gastos. `amount` se escala junto al share para que la moneda local cierre con el USD. Sin el param, gross del hogar (contrato original intacto). Un username desconocido es **400, nunca fallback a gross**: degradar le filtraría a uno los gastos privados del otro. `/cities/spend` sigue siendo gross-only.
