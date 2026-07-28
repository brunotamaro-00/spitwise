# Deploy — Spitwise en Railway

Un solo servicio web (FastAPI: API + webhook de WhatsApp + frontend estático) + Postgres, en el proyecto Railway `spitwise` de la **cuenta personal** (la misma de Andiamo — nunca la de Kavak). Proceso único persistente: los background tasks del webhook y los locks por chat dependen de eso — **no** subir `--workers`.

## Arquitectura

- Build: `Dockerfile` multi-stage (Vite build → runtime Python 3.12). Railway lo detecta vía `railway.json`.
- Arranque: `alembic upgrade head && uvicorn app.main:app` (migraciones en cada deploy; seed de categorías/usuarios idempotente en el lifespan).
- El frontend se sirve desde FastAPI (`FRONTEND_DIST`, ya seteado en la imagen) → mismo origen, sin CORS ni `VITE_API_URL` en prod.
- `DATABASE_URL` puede venir como `postgresql://` (formato Railway): `config.py` la convierte a `postgresql+asyncpg://` solo.

## Variables de entorno

### Spitwise (servicio Railway)

| Variable | Valor |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (reference a la DB del proyecto) |
| `ENVIRONMENT` | `prod` |
| `SECRET_KEY` | random largo (`openssl rand -hex 32`) |
| `AUTH_USERS` | `bruno:<pwd>:<wa_id_bruno>,katia:<pwd>:<wa_id_katia>` |
| `ANTHROPIC_API_KEY` | key de Anthropic (parser por defecto) |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5` |
| `OPENAI_API_KEY` | *(alternativa)* key de OpenAI — si es la única cargada, el parser usa OpenAI solo |
| `OPENAI_MODEL` | `gpt-4o-mini` |
| `LLM_PROVIDER` | *(opcional)* `anthropic` \| `openai` — fuerza el proveedor si hay ambas keys |
| `WHATSAPP_ACCESS_TOKEN` | token permanente de la app de Meta |
| `WHATSAPP_PHONE_NUMBER_ID` | id del número en WhatsApp Cloud |
| `WHATSAPP_VERIFY_TOKEN` | string random propio (se repite en la config de Meta) |
| `WHATSAPP_APP_SECRET` | app secret de Meta (firma HMAC del webhook) |
| `WHATSAPP_GRAPH_VERSION` | `v21.0` |
| `TRIP_SHARED_API_KEY` | **mismo valor** que en Andiamo |
| `ANDIAMO_URL` | `https://andiamo.lat` |
| `PITITAS_OWNER` | `katia` (ver *Stop local Pititas*; vacío ⇒ feature apagada) |
| `CORS_ORIGINS` | (vacío — mismo origen; solo dev usa localhost) |

Secretos **solo** acá: nunca en el repo (`.env` está gitignoreado).

### Andiamo (servicio Railway existente)

| Variable | Valor |
|---|---|
| `TRIP_SHARED_API_KEY` | mismo valor que arriba |
| `SPITWISE_URL` | `https://spitwise.lat` |

Redeploy de Andiamo después de agregarlas (habilita `GET /api/stops` y el chip "Gastado").

**Q&A de viaje del bot (guías/notas):** usa los endpoints `GET /api/guides/export` y
`GET /api/notes` de Andiamo (misma `TRIP_SHARED_API_KEY`, sin variables nuevas).
Orden de deploy cuando cambian ambos repos: **Andiamo primero** (expone la API),
Spitwise después (la migración corre en el arranque y el lifespan hace el primer
sync de contenido). Si Andiamo está caído, el bot sigue con el último snapshot
(`guide_docs`/`trip_notes`); el sync lazy (TTL 6h) y el ping `notes.changed`
lo actualizan solos.

## Alta inicial (una vez)

1. Railway → New Project `spitwise` → Add **PostgreSQL** → Add service desde el repo (o `railway up`).
2. Cargar las envs de la tabla. Settings → Networking → Generate Domain + custom domain `spitwise.lat` (Andiamo usa `andiamo.lat`).
3. Smoke: `curl https://spitwise.lat/health` → `{"status":"ok"}`; login → `curl -X POST .../api/v1/auth/login -d "username=bruno&password=<pwd>"` devuelve `access_token`; el dashboard web carga con balance "a mano".
4. **Meta** (App → WhatsApp → Configuration): Callback URL `https://spitwise.lat/webhooks/whatsapp`, Verify token = `WHATSAPP_VERIFY_TOKEN`, suscribir el campo `messages`. El GET de verificación debe devolver el `hub.challenge`.
5. Primer sync del itinerario:
   ```bash
   curl -X POST https://spitwise.lat/api/v1/andiamo/sync -H "Authorization: Bearer <jwt>"
   # => {"synced": <n paradas, con timezone>}
   ```

## Checklist end-to-end (con los números reales)

- [ ] "cena 45 libras" → `✅ Gasto guardado` / tarjeta con monto + ciudad activa; **sin** botones de split (el split se cambia con lenguaje natural, ej. "esa cena fue solo mía").
- [ ] "la cena fue solo mía" → confirma el cambio de split.
- [ ] "borrar" → botones de confirmación → "Borrar 🗑️" borra.
- [ ] Mismo gasto desde los 2 números a la vez → cada uno crea su propio movimiento (locks por `wa_id`; no hay race sobre un split compartido).
- [ ] Dashboard mobile: gasto visible, balance actualizado, ciudad activa correcta por fecha/timezone.
- [ ] "le pasé 20 usd" → settlement, el neto baja.
- [ ] "empanadas 5000 pesos" → ARS por dólar MEP, `fx_source=dolarapi`.
- [ ] Andiamo `/stops/<ciudad-activa>` → chip "Gastado: USD X".
- [ ] Corregir `fx_rate` en la web → recalcula USD (`fx_source=manual`); editar después la descripción NO pisa la tasa.
- [ ] Si el bot falla en background, el usuario recibe un mensaje "Se me trabó…" (no silencio).

## Runbook

- **Logs:** `railway logs` (o el panel del servicio). Errores del bot salen como `dispatch_error` / `webhook_background_error` con traceback.
- **Resync del itinerario:** `POST /api/v1/andiamo/sync` con JWT (o esperar el refresh perezoso de 6h que dispara cualquier mensaje de WhatsApp).
- **Rotar `TRIP_SHARED_API_KEY`:** generar valor nuevo → actualizarlo en **ambos** servicios (Spitwise y Andiamo) → redeploy de los dos. Hasta que coincidan, el sync devuelve 0 (usa snapshot) y el chip de Andiamo desaparece — nada se rompe.
- **Rotar token de WhatsApp:** Meta → System User token nuevo → actualizar `WHATSAPP_ACCESS_TOKEN` → redeploy. El webhook sigue validando con `WHATSAPP_APP_SECRET` (no cambia).
- **Cold starts / sleep:** si el plan gratuito duerme el servicio, pasar a Hobby (~USD 5/mes) — el webhook de Meta no tolera bien arranques fríos.

## Demo pública (demo.spitwise.lat + demo.andiamo.lat)

Par de servicios de muestra linkeados desde el CV. **Mismos repos y misma rama `main`** que producción — no hay rama `demo`, para que no drifteen: todo lo que cambia son env vars y la base de datos. La demo es **solo la web**: el canal de WhatsApp queda exclusivamente en producción.

Cuatro servicios Railway en total: `andiamo` + `spitwise` (prod) y `andiamo-demo` + `spitwise-demo`, cada demo con su propia Postgres.

### Qué cambia con `DEMO_MODE`

| App | Efecto |
|---|---|
| Spitwise | No se monta el router del webhook (`main.py`); `GET /api/v1/public-config` devuelve `demo: true` y el frontend pinta la barra "Demo · datos ficticios" (también en `/login`, que es donde aterriza quien viene del CV) |
| Andiamo | Barra equivalente (`DemoBanner`); se desactiva la subida de archivos (sin credenciales R2 el upload 500ea) — los documentos se agregan por link, que es lo que usa el seed |

### Variables

**`andiamo-demo`**

| Variable | Valor |
|---|---|
| `DATABASE_URL` | la Postgres nueva de la demo |
| `SESSION_SECRET` | valor nuevo, distinto de prod |
| `DEMO_MODE` / `NEXT_PUBLIC_DEMO_MODE` | `1` |
| `NEXT_PUBLIC_SITE_URL` | `https://demo.andiamo.lat` |
| `SPITWISE_URL` | `https://demo.spitwise.lat` |
| `TRIP_SHARED_API_KEY` | **valor nuevo, distinto del de prod** |
| `R2_*` | ausentes |

**`spitwise-demo`**

| Variable | Valor |
|---|---|
| `DATABASE_URL` | la Postgres nueva de la demo |
| `SECRET_KEY` | valor nuevo |
| `AUTH_USERS` | `bruno:demo:,katia:demo:` (sin `wa_id`: no hay WhatsApp) |
| `DEMO_MODE` | `true` |
| `ANDIAMO_URL` | `https://demo.andiamo.lat` |
| `SPITWISE_URL` | `https://demo.spitwise.lat` |
| `TRIP_SHARED_API_KEY` | el mismo valor nuevo de `andiamo-demo` |
| `ENVIRONMENT` | `prod` (para que `_assert_prod_secrets` valide) |
| `PITITAS_OWNER` | **vacío** (ver más abajo) |
| `WHATSAPP_*`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | ausentes |

**La `TRIP_SHARED_API_KEY` de la demo tiene que ser distinta de la de producción.** Con la misma key, un `ANDIAMO_URL` mal tipeado en la demo sincronizaría contra `andiamo.lat` real y publicaría el itinerario y las notas personales en una URL pública. Antes de exponer los dominios, comparar las variables de los cuatro servicios y confirmar que ninguna env de demo apunta a la DB, el bucket o la key de prod.

**Pititas queda apagada en la demo.** Sus fechas están hardcodeadas al 4–11 de septiembre de 2026 (`app/stops_local.py`), mientras que el seed de la demo rebasea todo el itinerario alrededor de *hoy*. Con `PITITAS_OWNER` seteado, la parada aparecería suelta en septiembre sin gastos y `_sync_counterpart_owner` no matchearía Portugal: se ve como un bug, no como una feature. Para mostrarla habría que parametrizar esas fechas.

### Seeds

Ambos son destructivos e idempotentes.

```bash
# 1) Andiamo primero: es la fuente de verdad del itinerario.
cd andiamo && npm run db:seed:demo

# 2) Spitwise después: sincroniza las paradas desde la demo de Andiamo
#    y siembra SOLO movimientos sobre ellas.
cd spitwise/backend && python scripts/seed_demo_money.py
```

`seed_demo_money.py` no define paradas propias a propósito: duplicar el itinerario garantizaba que los slugs divergieran de Andiamo y que el primer arranque archivara paradas con gastos. Si el sync falla o vuelve vacío, aborta sin sembrar. El ritmo de gasto por región y los helpers de `Movement` viven en `scripts/demo_common.py`, compartidos con el seed de la demo local (`seed_demo_data.py`).

### Reset diario

Un servicio cron por app en Railway, `0 7 * * *` UTC (≈4am ART), corriendo el seed correspondiente contra su DB de demo. **Andiamo unos minutos antes que Spitwise**, porque el segundo depende del itinerario ya regenerado.

## Stop local Pititas

Del **4 al 11 de septiembre de 2026** Bruno está solo en Portugal y Katia viaja con sus amigas. Los gastos de Katia en ese tramo se imputan a una parada **Pititas** (👭, EUR, `Europe/Paris`) en vez de Portugal; los de Bruno siguen yendo a Portugal. El 12 ya es Estrasburgo para los dos.

Pititas es un **stop local** (`Stop.is_local`): existe solo en Spitwise.

- **Andiamo no la conoce ni la debe conocer.** El sync la excluye de la reconciliación (si no, el primer `sync-hook` la borraría) y `/cities/spend` + `/cities/spend-detail` no la exponen. `/trip/spend` sí la suma: es plata gastada.
- **Se siembra sola** en el arranque (`app/stops_local.py`), después del sync, y es idempotente. Con `PITITAS_OWNER` vacío no se crea nada.
- **La imputación por fecha es por remitente**, no por pagador: si Katia carga "pagó bruno 30", el gasto igual cae en Pititas porque ella es la que está ahí.
- **Nombrar la parada la imputa para los dos**: "cena 30 en Pititas" desde el teléfono de Bruno va a Pititas (útil si le paga algo de ese tramo). Solo el default por fecha es exclusivo de ella.
- En la web la ven **los dos** (el balance ya mezcla esa plata; ocultarla dejaría un neto sin explicación), pero a Bruno nunca se le imputa ahí.
- **Para desactivarla:** borrar `PITITAS_OWNER` y redeploy. La fila queda en la DB con los gastos ya cargados; para que deje de imputar, borrar la fila `stops` con slug `pititas` (los movimientos conservan `city_name`).
