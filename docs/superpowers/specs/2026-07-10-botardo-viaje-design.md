# Botardo Viaje — Diseño

**Fecha:** 2026-07-10 (revisado el mismo día tras revisión crítica: hosting → Railway, LLM → Claude Haiku 4.5, ARS → dólar MEP, fechas → timezone de la parada activa)
**Repo:** `~/Desktop/Trip/Botardo` (nuevo, git init). Recicla lo útil de `~/Desktop/Expenses`; ese repo queda intacto.
**Integra con:** Andiamo (`~/Desktop/Trip/andiamo`, prod: `https://andiamo-production.up.railway.app`) — el plan de implementación incluye cambios chicos del lado Andiamo.

## 1. Propósito

Tracker de gastos de un viaje (Europa 2026, 108 noches / 26 paradas) usado por **2 personas** (Bruno y novia) como un **Splitwise simple**: ambos cargan gastos por WhatsApp o web, se imputan a quién corresponda, y la app calcula **cuánto le debe uno al otro en USD**, más allá de que se gaste en muchas divisas. Dashboard para ver gasto **por ciudad** y **por categoría**.

Cambio de paradigma respecto de Expenses: aquél era aislado por `owner` (cada quien ve solo lo suyo). Éste es un **libro único compartido**: ambos ven todo.

**Andiamo** es la app co-piloto del viaje (reservas, itinerario, documentos) y **la fuente de verdad del itinerario**. Botardo y Andiamo son **2 apps separadas** que se hablan por HTTP y se complementan: Andiamo aporta itinerario/fechas/moneda a Botardo; Botardo aporta gasto-por-ciudad a Andiamo (resumido, sin el detalle fino).

## 2. Alcance y no-objetivos

**Incluye:** captura por WhatsApp (2 números → un libro), parser LLM multi-moneda, split 50/50 con override, conversión a USD, neto entre las 2 personas, settlement (saldar), dashboard por ciudad/categoría, web con login, e **integración HTTP con Andiamo** (consumir itinerario, exponer gasto por ciudad).

**No incluye (retirado de Expenses):** modo personal aislado, imputación a tarjeta de crédito, movimientos recurrentes, cuotas/installments, `income`, gating de categoría por embeddings, `UserCategoryExample`, `MerchantAlias`, Redis. Splits arbitrarios (>2 personas o proporciones ≠ 50/0/100). Vista comparativa "de pareja" más allá del neto. **Seed/mantenimiento propio del itinerario** (viene de Andiamo). No se comparte base de datos entre apps.

## 3. Decisiones de diseño

| Tema | Decisión |
|------|----------|
| Alcance | Reemplazo total: solo modo viaje, un libro compartido |
| Split | Denormalizado a 2 personas: `paid_by` + enum `split` (`shared`/`payer_only`/`other_only`). Default `shared` (50/50) |
| Moneda | Auto vía API FX (Frankfurter/ECB, sin key), cache por día+moneda, override manual. **ARS no está en Frankfurter → se resuelve con dólar MEP (dolarapi.com `/v1/dolares/bolsa`, tasa `venta`)**. Base del neto = USD. Divisa default del parser = `currencyCode` de la parada activa (de Andiamo) |
| Ciudad | Derivada de las fechas del itinerario de Andiamo (parada cuyo rango contiene hoy). Override puntual por bot para day-trips; editable en web. El movimiento guarda el `slug` de la parada |
| Fecha/TZ | "Hoy" se calcula en la **timezone de la parada activa** (campo `timezone` del `Stop` de Andiamo, expuesto en `/api/stops`), fallback `Europe/Madrid`. Nunca UTC del servidor (evita gastos imputados al día equivocado de noche) |
| Categorías | 7 fijas: Alojamiento, Comida, Transporte, Actividades, Compras, Bebidas/Salidas, Otros. LLM clasifica directo (sin embeddings) |
| LLM parser | **Claude Haiku 4.5** (`claude-haiku-4-5`, Anthropic SDK) con structured outputs (`client.messages.parse` + schema Pydantic). Reemplaza OpenAI de Expenses |
| Settlement | Sí: registrar pago entre ellos que baja el neto |
| Integración | HTTP bidireccional con API key compartida. Andiamo = fuente de verdad del itinerario. Sin DB compartida |
| Hosting | **Todo en Railway**: backend FastAPI (proceso siempre vivo) + Railway Postgres en el mismo proyecto; el frontend estático (Vite build) lo sirve el propio FastAPI → un solo servicio, mismo origen, sin CORS. Andiamo sigue en su servicio Railway con su DB. (Se descartó Vercel serverless: sin background tasks tras responder, timeout 10s Hobby, y el webhook de Meta exige 200 en <5s) |
| Servicios | Uno solo (Botardo): webhook WhatsApp + API + frontend en la misma app FastAPI (se fusiona wpp-bot) |
| Webhook | Responde 200 **inmediato** tras verify HMAC + dedupe; el procesamiento (LLM + FX + respuesta por Graph) corre en background task de FastAPI. Meta reintenta si no hay 2xx en ~5s y entrega at-least-once |
| Dedupe | Tabla Postgres con `wamid` + TTL (reemplaza Redis) |

## 4. Modelo de datos (Botardo)

Se recicla el esquema de `expenses` de Expenses con estos cambios. Un solo libro: no hay aislamiento por usuario; `paid_by` indica el pagador entre los 2.

### `movements` (renombra `expenses`)
- `id`
- `type`: `expense` (default) | `settlement`
- `amount`: Numeric — monto en moneda original
- `currency`: String(3) — ISO (`GBP`, `EUR`, `USD`, `CHF`, `CZK`, `PLN`, `HUF`, `ARS`, …)
- `amount_usd`: Numeric — convertido; **base del neto**
- `fx_rate`: Numeric — tasa usada (currency→USD)
- `fx_source`: String — `frankfurter` | `manual` | `fallback` (flag para revisar)
- `paid_by`: user_id (FK users) — quién puso la plata
- `split`: enum `shared` | `payer_only` | `other_only` (ignorado para `settlement`)
- `description`: String
- `category_id`: FK categories (null para `settlement`)
- `stop_slug`: String — slug de la parada de Andiamo (id estable); heredado de la parada activa; editable
- `city_name`: String — nombre denormalizado de la parada (para mostrar sin depender del sync)
- `movement_date`: Date
- `raw_message`: Text
- `created_by`: user_id — quién lo cargó (auditoría)
- `created_at` / `updated_at`

Para `settlement`: `paid_by` = quien paga la deuda; el monto reduce el neto a favor del otro.

### `users`
Igual que Expenses (id, username, password_hash, whatsapp_wa_id). Exactamente 2 filas. Ambos wa_ids resuelven al mismo libro; el usuario identifica al pagador por defecto.

### `categories`
Catálogo global de 7 (sin `user_id`; el libro es único). Semilla al startup.

### `stops` (cache del itinerario de Andiamo)
Snapshot local sincronizado desde Andiamo (no fuente de verdad; se refresca):
- `slug` (unique), `order`, `name`, `country`, `country_flag`, `arrival_date`, `departure_date`, `currency_code`, `timezone`, `is_transit`, `is_candidate`, `is_flex_margin`, `synced_at`.
- Uso: derivar parada activa (rango de fechas ∋ hoy), moneda default, timezone para "hoy", lista de ciudades del dashboard, y resiliencia si Andiamo no responde.

### `fx_rates` (cache)
- `currency`, `rate_date`, `rate_to_usd`, `fetched_at`. Unique (`currency`,`rate_date`).

### `whatsapp_dedupe`
- `wamid` (unique), `created_at`. Limpieza por TTL. Reemplaza Redis.

### `bot_pending_actions` / `whatsapp_session_states`
Se reciclan de Expenses (flujos multi-paso y botones). `whatsapp_session_states` puede alojar override puntual de parada activa por chat (day-trips). (`bot_pending_confirmations` de Expenses no se porta: `bot_pending_actions` cubre todos los flujos con botones.)

### Se elimina (de Expenses)
`scheduled_expenses`, `recurring_movements`, `user_category_examples`, `merchant_aliases`, `trip_state` (la "ciudad activa" ya no es estado propio: se deriva de `stops`).

## 5. Lógica de neto (USD)

Para cada `movement`:
- `expense` + `shared`: pagador cubrió `amount_usd`; el otro le debe `amount_usd / 2`.
- `expense` + `payer_only`: no mueve el neto.
- `expense` + `other_only`: el otro le debe `amount_usd` completo.
- `settlement`: `paid_by` reduce lo que debe (o genera crédito) por `amount_usd`.

**Neto** = suma sobre todos los movimientos de (lo que B le debe a A) − (lo que A le debe a B). Resultado: "X le debe USD N a Y". Se calcula on-the-fly desde `movements`; sin tabla de balance.

## 6. Integración con Andiamo (itinerario ↔ gasto)

Dos apps separadas, DBs separadas (Supabase vs Railway), se comunican por **HTTP con API key compartida** en header (`X-Api-Key`). Andiamo es la fuente de verdad del itinerario; ustedes ajustan fechas ahí sobre la marcha y Botardo lo hereda.

### 6.1 Andiamo → Botardo (itinerario)
- **Contrato (nuevo endpoint read-only en Andiamo):** `GET /api/stops` → JSON de paradas:
  `[{ slug, order, name, country, countryFlag, arrivalDate, departureDate, nights, datesFixed, currencyCode, timezone, isTransit, isCandidate, isFlexMargin }]`.
  Deriva del modelo `Stop` existente (que ya tiene `timezone`); protegido por `X-Api-Key`.
- **Botardo:** módulo de sync (`app/andiamo.py`) que llama al endpoint, upsertea la tabla `stops`, guarda `synced_at`. Se dispara: al startup, on-demand (endpoint/botón), y **perezosamente con TTL de 6 horas**: cuando se resuelve la parada activa y el snapshot está viejo, se lanza un refresh en background (`asyncio.create_task`) sin bloquear la request — la request actual usa el snapshot existente.
- **Uso:** parada activa = `stops` cuyo `[arrival_date, departure_date)` contiene hoy (fallback: la de mayor `arrival_date ≤ hoy`). Moneda default del parser = `currency_code` de esa parada.
- **Resiliencia:** si el sync falla, se usa el último snapshot en `stops`. Si nunca hubo sync, un seed estático mínimo del itinerario. La carga de un gasto **nunca** se bloquea por Andiamo.

### 6.2 Botardo → Andiamo (gasto por ciudad)
- **Contrato (nuevo endpoint en Botardo):** `GET /api/v1/cities/spend` → `[{ slug, name, total_usd, movement_count }]`, agregando `movements` (type `expense`) por `stop_slug`. Protegido por `X-Api-Key`. Opcional `?slug=` para una sola parada.
- **Andiamo:** en la página de cada parada (`/stops/[slug]`), un widget/chip liviano "**Gastado: USD X**" que hace fetch a Botardo. Resumen, sin el detalle fino (que vive en Botardo). Degrada en silencio si Botardo no responde.

### 6.3 Auth entre apps
- Secreto compartido `TRIP_SHARED_API_KEY` (nuevo env en ambos). Header `X-Api-Key`. Simple y suficiente para 2 apps personales. No se comparte identidad de usuario: la integración es a nivel viaje, no por persona.

### 6.4 Cambios del lado Andiamo (repo `andiamo`, incluidos en el plan)
1. `GET /api/stops` (read-only, `X-Api-Key`) exponiendo el modelo `Stop`.
2. Widget de gasto en `/stops/[slug]` que consume `GET {BOTARDO_URL}/api/v1/cities/spend?slug=…`.
3. Envs nuevos: `TRIP_SHARED_API_KEY`, `BOTARDO_URL`.

## 7. Captura por WhatsApp (Botardo)

Reusa `app/bot/dispatcher.py` (ruteo determinista) y el parser LLM, simplificados:

1. `wpp-bot` se fusiona: la ruta del webhook vive en el backend. Verify HMAC + dedupe (tabla Postgres) + lock por chat. **El webhook responde 200 inmediato tras verify+dedupe; el resto (LLM, FX, respuesta) corre en background task** (Meta exige 2xx en ~5s y reintenta; el dedupe absorbe los reintentos).
2. Mensaje de texto → 1 llamada LLM (Claude Haiku 4.5, structured outputs) que extrae: `amount`, `currency` (si el texto la trae: "45 libras", "12€"; default = moneda de la parada activa), `description`, `category` (de las 7), y señal de split.
3. `paid_by` = usuario del wa_id que manda. `split` default `shared`. `stop_slug`/`city_name` = parada activa (de `stops`). `movement_date` = hoy en la timezone de la parada activa. FX → `amount_usd`.
4. Auto-registra sin confirmación salvo:
   - Categoría genuinamente ambigua → botones con candidatas (el LLM devuelve alternativas si baja confianza).
   - Borrado → confirmación (irreversible). Comando de texto "borrar" / "borrar último": muestra el último movimiento **creado por ese usuario** con botones `[Borrar 🗑️] [Cancelar]`.
5. Override de split vía botones sobre el movimiento **recién creado** (el handler de captura devuelve el `movement_id`; nunca "el último movimiento global", que es una race si ambos cargan a la vez): `[Compartido ✓] [Solo mío] [Solo de ella]`.
6. Override puntual de parada activa por bot ("estamos en París" / day-trip) → `whatsapp_session_states`. Lo normal es que la parada la derive Andiamo por fecha.
7. Settlement por comando ("le pasé USD 100" / "saldamos 200").

Flujos retirados del ruteo: tarjeta de crédito, recurrentes, cuotas.

Errores: patrón `⚠️ {Tipo}: {mensaje}`, un try/except en el borde del dispatcher.

## 8. Conversión de moneda (FX)

- Módulo `app/fx.py`: al registrar, si `currency != USD`, busca tasa en cache `fx_rates` para la fecha; si no, pega a **Frankfurter** (`https://api.frankfurter.dev`, ECB, gratis, sin key), guarda en cache, setea `fx_rate`/`amount_usd`/`fx_source='frankfurter'`.
- **ARS (no soportado por Frankfurter):** se resuelve con **dólar MEP** vía dolarapi.com (`GET /v1/dolares/bolsa`, sin key) → `rate_to_usd = 1 / venta`. Cache igual que el resto; `fx_source='dolarapi'`.
- Fallback: si la API falla, usa tabla de tasas semilla en config, marca `fx_source='fallback'` para revisar en la web.
- Override manual desde el dashboard (editar `fx_rate` recalcula `amount_usd`; una tasa `manual` **no** se pisa al editar otros campos del movimiento).

## 9. Dashboard (web, Botardo)

Mismo shell React 19 + Vite reciclado. Vistas:
- **Balance destacado arriba**: "Bruno le debe USD 320 a [novia]" + botón **Saldar** (crea `settlement`).
- **Total del viaje en USD**.
- **Gasto por ciudad** (bar/composición) — ciudades ordenadas por `stops.order`.
- **Gasto por categoría** (composición).
- **Timeline** de gasto acumulado.
- **Lista de movimientos**: fecha, ciudad, categoría, quién pagó, cómo se dividió, moneda original + USD; editar/borrar; corregir `fx_rate`; marcar los `fx_source='fallback'`.
- Login web (JWT, reciclado de Expenses). Ambos usuarios ven el mismo libro.

## 10. Arquitectura de deploy

```text
WhatsApp Cloud ──> Railway (Botardo, FastAPI, proceso siempre vivo)
                     ├─ /webhooks/whatsapp  (verify HMAC + dedupe → 200 inmediato;
                     │                       LLM/FX/respuesta en background task)
                     ├─ /api/v1/*           (auth, movements, dashboard, categories, users)
                     ├─ /api/v1/cities/spend (X-Api-Key)  ◄── Andiamo
                     └─ /  (frontend estático Vite build servido por FastAPI, mismo origen)
                          │
                          ├─> Railway Postgres (mismo proyecto, red interna)
                          ├─> Anthropic (Claude Haiku 4.5, parse) · Frankfurter (FX) · dolarapi (ARS/MEP)
                          └─> GET {ANDIAMO_URL}/api/stops (X-Api-Key)  ──► sync itinerario

Andiamo (Railway, Next.js + Prisma + Postgres propio)
  ├─ GET /api/stops (X-Api-Key)                         ──► itinerario a Botardo
  └─ /stops/[slug] widget "Gastado: USD X" ── fetch ──► Botardo /api/v1/cities/spend

Browser ──> Railway Botardo (frontend + /api/v1/* JWT, mismo origen — sin CORS en prod)
```

Consideraciones (Botardo en Railway): proceso persistente → `asyncio.Lock` por chat y background tasks funcionan de verdad; pool de conexiones normal de SQLAlchemy; seed idempotente en el lifespan de startup; el sync de Andiamo nunca está en el camino crítico del webhook (snapshot + refresh perezoso en background). Un solo vendor (Railway) para las dos apps del viaje.

## 11. Reutilización desde Expenses

| Reciclar (adaptar) | Retirar |
|--------------------|---------|
| Dispatcher del bot, botones/pending, session state | Orchestrator/FSM (ya no existe) |
| Parser LLM + prompts (simplificados, +moneda, categorías fijas) | Embeddings, gating, `eval_categories`, `UserCategoryExample`, `MerchantAlias` |
| Auth JWT + login web | `AUTH_USERS` con aislamiento por owner → 2 usuarios de un libro |
| Shell dashboard (api/components/pages), tipos con Decimal-string | Vistas personales de aislamiento |
| Esquema `expenses` → `movements` | `scheduled_expenses`, `recurring_movements`, `trip_state` |
| Endpoints movimientos/summary/timeseries/composition | Endpoints de recurrentes/pending de tarjeta |
| `wpp-bot` webhook (verify/dispatch) → fusionado al backend | Servicio wpp-bot separado, Redis |
| docker-compose (dev local) | backup service; prod usa Railway Postgres |
| Itinerario / ciudades / moneda por ciudad | Seed propio → viene de Andiamo (`stops`) |

## 12. Estrategia de migración de datos

No hay migración: libro nuevo, arranca vacío. Alembic desde cero con el esquema de la sección 4 contra Railway Postgres. `stops` se puebla con el primer sync a Andiamo.

## 13. Testing

- **Botardo backend** (`pytest`): neto (todos los splits + settlement), FX (cache/fallback), parser (monedas, categorías), dispatcher (override de split, parada activa), sync Andiamo (upsert `stops`, resiliencia con endpoint caído), agregación `cities/spend`.
- **Botardo frontend**: `npm run build && npm run lint`.
- **Andiamo** (`vitest`): endpoint `/api/stops` (shape + auth `X-Api-Key`), widget de gasto (fetch + degradado silencioso).

## 14. Preguntas abiertas / a validar en implementación

- ~~Vercel Python serverless~~ → **Resuelto: Railway todo** (backend + Postgres + frontend en un servicio).
- ~~Frecuencia de refresco del sync `stops`~~ → **Resuelto: lazy TTL 6h en background + endpoint manual**.
- ~~LLM del parser~~ → **Resuelto: Claude Haiku 4.5 con structured outputs**.
- ~~ARS~~ → **Resuelto: dólar MEP vía dolarapi.com**.
- Identidad de la "otra persona" en los copies del bot (usar username configurable).
- Andiamo hoy es single-user con password; el endpoint `/api/stops` usa `X-Api-Key` aparte de la sesión de UI — el matcher de `src/proxy.ts` debe excluir `api/stops` (patrón `api/documents` existente, verificado en el repo).
