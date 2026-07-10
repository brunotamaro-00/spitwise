# Botardo Viaje — Diseño

**Fecha:** 2026-07-10
**Repo:** `~/Desktop/Trip/Botardo` (nuevo, git init). Recicla lo útil de `~/Desktop/Expenses`; ese repo queda intacto.

## 1. Propósito

Tracker de gastos de un viaje (Europa 2026, 108 noches) usado por **2 personas** (Bruno y novia) como un **Splitwise simple**: ambos cargan gastos por WhatsApp o web, se imputan a quién corresponda, y la app calcula **cuánto le debe uno al otro en USD**, más allá de que se gaste en muchas divisas. Dashboard para ver gasto **por ciudad** y **por categoría**.

Cambio de paradigma respecto de Expenses: aquél era aislado por `owner` (cada quien ve solo lo suyo). Éste es un **libro único compartido**: ambos ven todo.

## 2. Alcance y no-objetivos

**Incluye:** captura por WhatsApp (2 números → un libro), parser LLM multi-moneda, split 50/50 con override, conversión a USD, neto entre las 2 personas, settlement (saldar), ciudad activa, dashboard por ciudad/categoría, web con login.

**No incluye (retirado de Expenses):** modo personal aislado, imputación a tarjeta de crédito, movimientos recurrentes, cuotas/installments, `income`, gating de categoría por embeddings, `UserCategoryExample`, `MerchantAlias`, Redis. Splits arbitrarios (>2 personas o proporciones ≠ 50/0/100). Vista comparativa "de pareja" más allá del neto.

## 3. Decisiones de diseño

| Tema | Decisión |
|------|----------|
| Alcance | Reemplazo total: solo modo viaje, un libro compartido |
| Split | Denormalizado a 2 personas: `paid_by` + enum `split` (`shared`/`payer_only`/`other_only`). Default `shared` (50/50) |
| Moneda | Auto vía API FX (Frankfurter/ECB, sin key), cache por día+moneda, override manual. Base del neto = USD |
| Ciudad | "Ciudad activa" sembrada del itinerario; ajustable por el bot; cada gasto la hereda; editable en web |
| Categorías | 7 fijas: Alojamiento, Comida, Transporte, Actividades, Compras, Bebidas/Salidas, Otros. LLM clasifica directo (sin embeddings) |
| Settlement | Sí: registrar pago entre ellos que baja el neto |
| Hosting | Frontend estático en Vercel; Postgres en Supabase; backend FastAPI como funciones serverless Python en Vercel |
| Servicios | Uno solo: webhook WhatsApp + API en la misma app FastAPI (se fusiona wpp-bot) |
| Dedupe | Tabla Postgres con `wamid` + TTL (reemplaza Redis) |

## 4. Modelo de datos

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
- `city`: String — heredada de la ciudad activa; editable
- `movement_date`: Date
- `raw_message`: Text
- `created_by`: user_id — quién lo cargó (auditoría)
- `created_at` / `updated_at`

Para `settlement`: `paid_by` = quien paga la deuda; el monto reduce el neto a favor del otro.

### `users`
Igual que Expenses (id, username, password_hash, whatsapp_wa_id). Exactamente 2 filas. Ambos wa_ids resuelven al mismo libro; el usuario identifica al pagador por defecto.

### `categories`
Catálogo global de 7 (sin `user_id`; el libro es único). Semilla al startup.

### `trip_state`
Estado del viaje (singleton o por libro):
- `active_city`: String
- `active_city_since`: Date
- `base_currency`: `USD` (constante v1)

### `fx_rates` (cache)
- `currency`, `rate_date`, `rate_to_usd`, `fetched_at`. Unique (`currency`,`rate_date`).

### `whatsapp_dedupe`
- `wamid` (unique), `created_at`. Limpieza por TTL (borrar > N horas). Reemplaza Redis.

### `bot_pending_confirmations` / `bot_pending_actions` / `whatsapp_session_states`
Se reciclan de Expenses (soporte de flujos multi-paso y botones). `whatsapp_session_states` también puede alojar overrides de ciudad activa por chat si hace falta.

### Se elimina
`scheduled_expenses`, `recurring_movements`, `user_category_examples`, `merchant_aliases`.

## 5. Lógica de neto (USD)

Para cada `movement`:
- `expense` + `shared`: pagador cubrió `amount_usd`; el otro le debe `amount_usd / 2`.
- `expense` + `payer_only`: no mueve el neto.
- `expense` + `other_only`: el otro le debe `amount_usd` completo.
- `settlement`: `paid_by` reduce lo que debe (o genera crédito) por `amount_usd`.

**Neto** = suma sobre todos los movimientos de (lo que B le debe a A) − (lo que A le debe a B). Resultado: "X le debe USD N a Y". Se calcula on-the-fly desde `movements`; sin tabla de balance.

## 6. Captura por WhatsApp

Reusa `app/bot/dispatcher.py` (ruteo determinista) y el parser LLM, simplificados:

1. `wpp-bot` se fusiona: la ruta del webhook vive en el backend. Verify HMAC + dedupe (tabla Postgres) + lock por chat.
2. Mensaje de texto → 1 llamada LLM que extrae: `amount`, `currency` (si el texto la trae: "45 libras", "12€", default = moneda de la ciudad activa), `description`, `category` (de las 7), y señal de split.
3. `paid_by` = usuario del wa_id que manda. `split` default `shared`. `city` = ciudad activa. FX → `amount_usd`.
4. Auto-registra sin confirmación salvo:
   - Categoría genuinamente ambigua → botones con candidatas (sin embeddings; el LLM devuelve alternativas si baja confianza).
   - Borrado → confirmación (irreversible).
5. Override de split vía botones sobre el pending: `[Compartido ✓] [Solo mío] [Solo de ella]`.
6. Comando/botón para mover **ciudad activa** ("estamos en París") → actualiza `trip_state`.
7. Settlement por comando ("le pasé USD 100" / "saldamos 200").

Flujos retirados del ruteo: tarjeta de crédito, recurrentes, cuotas.

Errores: mismo patrón `⚠️ {Tipo}: {mensaje}`, un try/except en el borde del dispatcher.

## 7. Conversión de moneda (FX)

- Módulo `app/fx.py`: al registrar, si `currency != USD`, busca tasa en cache `fx_rates` para la fecha; si no, pega a **Frankfurter** (`https://api.frankfurter.dev`, ECB, gratis, sin key), guarda en cache, setea `fx_rate`/`amount_usd`/`fx_source='frankfurter'`.
- Fallback: si la API falla, usa tabla de tasas semilla en config, marca `fx_source='fallback'` para revisar en la web.
- Override manual desde el dashboard (editar `fx_rate` recalcula `amount_usd`).

## 8. Dashboard (web)

Mismo shell React 19 + Vite reciclado. Vistas:
- **Balance destacado arriba**: "Bruno le debe USD 320 a [novia]" + botón **Saldar** (crea `settlement`).
- **Total del viaje en USD**.
- **Gasto por ciudad** (bar/composición).
- **Gasto por categoría** (composición).
- **Timeline** de gasto acumulado.
- **Lista de movimientos**: fecha, ciudad, categoría, quién pagó, cómo se dividió, moneda original + USD; editar/borrar; corregir `fx_rate`; marcar los `fx_source='fallback'`.
- Login web (JWT, reciclado de Expenses). Ambos usuarios ven el mismo libro.

## 9. Arquitectura de deploy

```text
WhatsApp Cloud ──> Vercel (FastAPI serverless)
                     ├─ /webhooks/whatsapp  (verify HMAC, dedupe Postgres, dispatch)
                     └─ /api/v1/*           (auth, movements, dashboard, categories)
                          │
                          └─> Supabase Postgres (DATABASE_URL)
Browser ──> Vercel (frontend estático, VITE_API_URL → backend) ──> /api/v1/* (JWT)
Backend ──> OpenAI (parse) · Frankfurter (FX)
```

Consideraciones serverless: sin estado en proceso (todo en Postgres); el webhook responde rápido; sin Redis; funciones Python de Vercel (límite de ejecución compatible con 1 llamada LLM + 1 FX).

## 10. Reutilización desde Expenses

| Reciclar (adaptar) | Retirar |
|--------------------|---------|
| Dispatcher del bot, botones/pending, session state | Orchestrator/FSM (ya no existe) |
| Parser LLM + prompts (simplificados, +moneda, categorías fijas) | Embeddings, gating, `eval_categories`, `UserCategoryExample`, `MerchantAlias` |
| Auth JWT + login web | `AUTH_USERS` con aislamiento por owner → 2 usuarios de un libro |
| Shell dashboard (api/components/pages), tipos con Decimal-string | Vistas personales de aislamiento |
| Esquema `expenses` → `movements` | `scheduled_expenses`, `recurring_movements` |
| Endpoints movimientos/summary/timeseries/composition | Endpoints de recurrentes/pending de tarjeta |
| `wpp-bot` webhook (verify/dispatch) → fusionado al backend | Servicio wpp-bot separado, Redis |
| docker-compose (dev local) | backup service; ajustar a Supabase para prod |

## 11. Estrategia de migración de datos

No hay migración: libro nuevo, arranca vacío. Alembic (o migraciones Supabase) desde cero con el esquema de la sección 4.

## 12. Testing

- Backend: `pytest` — neto (todos los splits + settlement), FX (cache/fallback), parser (monedas, categorías), dispatcher (override de split, ciudad activa).
- Frontend: `npm run build && npm run lint`.

## 13. Preguntas abiertas / a validar en implementación

- Nombre exacto del repo (`Botardo` asumido).
- Vercel Python serverless con FastAPI: confirmar límites de ejecución y empaquetado ASGI en la fase de plan.
- Identidad de la "otra persona" en los copies del bot (usar username configurable).
