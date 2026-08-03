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
| `AUTH_USERS` | `bruno:<pwd>:<wa_id_bruno>,katia:<pwd>:<wa_id_katia>` (hoy solo mapea `wa_id`: el login no usa esta contraseña) |
| `LOGIN_PASSWORDS` | contraseñas válidas del login web, separadas por comas (ej. `bruny1003,sandia12#`). **Obligatoria fuera de la demo**: sin ella el servicio no arranca. |
| `DEMO_URL` | `https://demo.spitwise.lat` — el CTA "Entrar a la demo" del `/login` de prod |
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
| `LOGIN_PASSWORDS` | mismas contraseñas que Spitwise (las dos apps comparten el gate) |
| `NEXT_PUBLIC_DEMO_URL` | `https://demo.andiamo.lat` |

Redeploy de Andiamo después de agregarlas (habilita `GET /api/stops` y el chip "Gastado").

**Q&A de viaje del bot (guías/notas/documentos):** usa los endpoints
`GET /api/guides/export`, `GET /api/notes` y `GET /api/integration/documents` de
Andiamo (misma `TRIP_SHARED_API_KEY`, sin variables nuevas). El bot también
**escribe** notas dictadas por chat en `POST /api/integration/notes`, con la
misma key.
Orden de deploy cuando cambian ambos repos: **Andiamo primero** (expone la API),
Spitwise después (la migración corre en el arranque y el lifespan hace el primer
sync de contenido). Si Andiamo está caído, el bot sigue con el último snapshot
(`guide_docs`/`trip_notes`/`trip_documents`); el sync lazy (TTL 6h) y los pings
`notes.changed` / `documents.changed` lo actualizan solos. Dictar una nota con
Andiamo caído no rompe: el pending queda abierto y re-tocar *Guardar* reintenta.

Los links de documento que devuelve el bot (`{ANDIAMO_URL}/api/documents/<id>`)
están detrás de la **cookie de sesión de Andiamo**, no son signed URLs: se abren
si el celular ya está logueado, que es el caso normal.

## Alta inicial (una vez)

1. Railway → New Project `spitwise` → Add **PostgreSQL** → Add service desde el repo (o `railway up`).
2. Cargar las envs de la tabla. Settings → Networking → Generate Domain + custom domain `spitwise.lat` (Andiamo usa `andiamo.lat`).
3. Smoke: `curl https://spitwise.lat/health` → `{"status":"ok"}`; login → `curl -X POST .../api/v1/auth/login -d "username=bruno&password=<una de LOGIN_PASSWORDS>"` devuelve `access_token` (con una contraseña cualquiera, 401); el dashboard web carga con balance "a mano".
4. **Meta** (App → WhatsApp → Configuration): Callback URL `https://spitwise.lat/webhooks/whatsapp`, Verify token = `WHATSAPP_VERIFY_TOKEN`, suscribir el campo `messages`. El GET de verificación debe devolver el `hub.challenge`.
5. Primer sync del itinerario:
   ```bash
   curl -X POST https://spitwise.lat/api/v1/andiamo/sync -H "Authorization: Bearer <jwt>"
   # => {"synced": <n paradas, con timezone>}
   ```
6. Planes de presupuesto (**después** del sync: los slugs se validan contra las paradas ya
   sincronizadas). Es idempotente por inserción — nunca pisa lo editado desde la web:
   ```bash
   cd backend
   DATABASE_URL="postgresql+asyncpg://..." .venv/bin/python scripts/seed_stop_budgets.py --dry-run
   DATABASE_URL="postgresql+asyncpg://..." .venv/bin/python scripts/seed_stop_budgets.py
   ```

### One-off de la migración 0013 (plan puntual → rango)

`alembic upgrade head` convierte cada target de un solo número en una **banda de
ancho cero** (`min = max = daily_usd`): no cambia ningún veredicto, pero tampoco
abre el rango. Las bandas reales se re-derivan del `PRESUPUESTO.md` con:

```bash
DATABASE_URL="postgresql+asyncpg://..." .venv/bin/python scripts/seed_stop_budgets.py --dry-run --force
DATABASE_URL="postgresql+asyncpg://..." .venv/bin/python scripts/seed_stop_budgets.py --force
```

`--force` **pisa lo editado desde la web** (es la única forma de reescribir filas
existentes). Correrlo una sola vez, justo después de la migración; los centros de
las bandas caen a menos de USD 0,20 de los targets viejos, así que el plan no se
mueve, se abre.

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
- [ ] `/presupuesto`: la ciudad en curso muestra el $/día que queda hasta el check-out, su barra con la banda del plan y el badge (`ahorrando` / `en plan` / `+N%`); la línea de cobertura dice cuántas noches tienen plan.
- [ ] Con el viaje en curso, la card de colchón muestra cuánto llevan ahorrado (o de más) y a cuánto por día pueden ir en lo que queda. Antes de arrancar el viaje no aparece.
- [ ] "¿vamos bien de guita en <ciudad>?" por WhatsApp responde contra el rango de esa parada, no con el promedio del viaje; una parada sin plan lo dice en vez de estimarlo.

## Runbook

- **Logs:** `railway logs` (o el panel del servicio). Errores del bot salen como `dispatch_error` / `webhook_background_error` con traceback.
- **Resync del itinerario:** `POST /api/v1/andiamo/sync` con JWT (o esperar el refresh perezoso de 6h que dispara cualquier mensaje de WhatsApp).
- **Paradas nuevas sin plan:** `/presupuesto` muestra la cobertura y nombra los slugs que faltan. Se cargan desde la web (tap en la ciudad → modal, dos campos mínimo/máximo) o re-corriendo `scripts/seed_stop_budgets.py`, que solo inserta los faltantes. Si el país de la parada nueva no está mapeado, el script la lista como *SIN MAPEO* en vez de saltearla en silencio.
- **Rotar `TRIP_SHARED_API_KEY`:** generar valor nuevo → actualizarlo en **ambos** servicios (Spitwise y Andiamo) → redeploy de los dos. Hasta que coincidan, el sync devuelve 0 (usa snapshot) y el chip de Andiamo desaparece — nada se rompe.
- **Rotar token de WhatsApp:** Meta → System User token nuevo → actualizar `WHATSAPP_ACCESS_TOKEN` → redeploy. El webhook sigue validando con `WHATSAPP_APP_SECRET` (no cambia).
- **Cold starts / sleep:** si el plan gratuito duerme el servicio, pasar a Hobby (~USD 5/mes) — el webhook de Meta no tolera bien arranques fríos.

## Demo pública (demo.spitwise.lat + demo.andiamo.lat)

Par de servicios de muestra linkeados desde el CV. **Mismos repos y misma rama `main`** que producción — no hay rama `demo`, para que no drifteen: todo lo que cambia son env vars y la base de datos. La demo es **solo la web**: el canal de WhatsApp queda exclusivamente en producción.

Los servicios demo viven **dentro de los proyectos existentes** (`Andiamo` y `spitwise`), no en proyectos aparte: un servicio nuevo nace sin variables, así que ninguna credencial de prod se filtra por accidente. Inventario real:

| Proyecto | Servicios | Postgres |
|---|---|---|
| `Andiamo` | `andiamo` (prod) · `andiamo-demo` · `andiamo-demo-cron` | `Postgres` (prod) · `Postgres-7098` (demo) |
| `spitwise` | `spitwise` (prod) · `spitwise-demo` · `spitwise-demo-cron` | `Postgres` (prod) · `Postgres-ftfA` (demo) |

Los nombres de las Postgres de demo los generó Railway (`railway add -d postgres` no acepta nombre). **Renombrarlas en el dashboard rompe las referencias** `${{Postgres-7098.DATABASE_URL}}` de los servicios demo — si las renombrás, actualizá también esas variables.

### Qué cambia con `DEMO_MODE`

| App | Efecto |
|---|---|
| Spitwise | No se monta el router del webhook (`main.py`); `GET /api/v1/public-config` devuelve `demo: true` y el frontend pinta el banner "Demo pública" + `DemoIntro` (presentación de una sola vez, recordada en `localStorage`). Los dos salen también en `/login`, que es donde aterriza quien viene del CV |
| Andiamo | Banner e intro equivalentes; `/` redirige a `/stops#current` en vez de al detalle de la parada de hoy; se desactiva la subida de archivos (sin credenciales R2 el upload 500ea) — los documentos se agregan por link, que es lo que usa el seed |
| Las dos | **El login no pide contraseña**: la demo es de entrada libre, que es todo el punto del deploy. El picker Bruno/Katia queda como estaba y el CTA "Entrar a la demo" no se renderiza (ya estás ahí) |

### El gate de producción — `LOGIN_PASSWORDS`

`andiamo.lat` y `spitwise.lat` están impresos en el CV y tienen datos personales reales detrás, así que su `/login` pide contraseña. La variable es una **lista separada por comas**: más de una contraseña válida a la vez, para poder rotar sin cortarle el acceso a nadie en medio del viaje. Va con el mismo valor en los dos servicios de producción.

Falla cerrado: sin `LOGIN_PASSWORDS` no entra nadie, y Spitwise directamente **no arranca** (`_assert_prod_secrets`, salvo `DEMO_MODE`). Los servicios de demo **no la llevan**.

> Si alguna contraseña tiene `#`, en la UI de Railway se pega tal cual; en un archivo `.env` local hay que comillar el valor entero (`LOGIN_PASSWORDS="a,b#"`), si no dotenv corta en el `#`.

Y como contracara, el `/login` de producción es la puerta de entrada del portfolio: quien llega desde el CV encuentra arriba de todo la card "¿Venís desde mi CV o LinkedIn?" con el CTA primario hacia la demo (`DEMO_URL` / `NEXT_PUBLIC_DEMO_URL`), y la contraseña abajo, separada. Por eso el CV sigue apuntando a los dominios de producción y no a los `demo.*`: el muro es la prueba de que la app es real y está en uso.

### El "hoy" congelado — `DEMO_TODAY`

Las dos apps congelan el reloj del viaje en **`2026-09-25`** (Viena, noche 2 de 5). Sin eso, cada seed rebasea el itinerario contra el día en que corre el cron: quien abra el link en noviembre ve un viaje distinto al probado, y cualquier desfase entre los dos crons desalinea las apps.

| Servicio | Variable |
|---|---|
| `andiamo-demo`, `andiamo-demo-cron` | `NEXT_PUBLIC_DEMO_TODAY=2026-09-25` |
| `spitwise-demo`, `spitwise-demo-cron` | `DEMO_TODAY=2026-09-25` |

**Las cuatro llevan la misma fecha.** Si divergen, cada app muestra una parada actual distinta. En Andiamo lo lee `todayStr()` (`src/lib/trip.ts`) y en Spitwise `today_in_tz()` (`app/trip_time.py`) — un único punto por app, y en Andiamo tiene que ser `NEXT_PUBLIC_` porque Next inlinea la variable **en build time**.

Efecto lateral bueno: con `random.seed(42)` + hoy fijo, el reset nocturno produce una demo idéntica, no una parecida.

Cambiar la fecha no es gratis: `seed_demo_money.py` falla si el hoy congelado cae a ≤1 día de un check-in, porque esa reserva entraría sola al aviso de "por confirmar" y la demo abriría con dos pendientes en vez del único que se quiere mostrar.

### Variables

**`andiamo-demo`**

| Variable | Valor |
|---|---|
| `DATABASE_URL` | `${{Postgres-7098.DATABASE_URL}}` |
| `SESSION_SECRET` | valor nuevo, distinto de prod |
| `DEMO_MODE` / `NEXT_PUBLIC_DEMO_MODE` | `1` |
| `NEXT_PUBLIC_SITE_URL` | `https://demo.andiamo.lat` |
| `SPITWISE_URL` | `https://demo.spitwise.lat` |
| `TRIP_SHARED_API_KEY` | **valor nuevo, distinto del de prod** |
| `NEXT_PUBLIC_DEMO_TODAY` | `2026-09-25` |
| `HOSTNAME` | `0.0.0.0` — **imprescindible** |
| `NODE_ENV` | `production` |
| `LOGIN_PASSWORDS`, `NEXT_PUBLIC_DEMO_URL` | **ausentes** (la demo entra sin contraseña) |
| `R2_*` | ausentes |

Sin `HOSTNAME=0.0.0.0` el server standalone de Next bindea al hostname del contenedor (`http://cf98e52f8eb8:8080`) y el proxy de Railway devuelve **502 con la app perfectamente Online** en el panel. Prod ya lo tiene seteado; un servicio nuevo no lo hereda. El otro 502 posible es el **target port del dominio**: hay que fijarlo en `8080` (`railway domain update <dominio> --port 8080 -s andiamo-demo`), porque Railway lo deja vacío al crear el dominio.

**`spitwise-demo`**

| Variable | Valor |
|---|---|
| `DATABASE_URL` | `${{Postgres-ftfA.DATABASE_URL}}` |
| `SECRET_KEY` | valor nuevo |
| `AUTH_USERS` | `bruno:demo:,katia:demo:` (sin `wa_id`: no hay WhatsApp) |
| `DEMO_MODE` | `true` |
| `DEMO_TODAY` | `2026-09-25` |
| `ANDIAMO_URL` | `https://demo.andiamo.lat` |
| `SPITWISE_URL` | `https://demo.spitwise.lat` |
| `TRIP_SHARED_API_KEY` | el mismo valor nuevo de `andiamo-demo` |
| `ENVIRONMENT` | `prod` (para que `_assert_prod_secrets` valide) |
| `PITITAS_OWNER` | **vacío** (ver más abajo) |
| `LOGIN_PASSWORDS`, `DEMO_URL` | **ausentes** (`DEMO_MODE` saltea el gate; sin él, `ENVIRONMENT=prod` no dejaría arrancar) |
| `WHATSAPP_*`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | ausentes |

**La `TRIP_SHARED_API_KEY` de la demo tiene que ser distinta de la de producción.** Con la misma key, un `ANDIAMO_URL` mal tipeado en la demo sincronizaría contra `andiamo.lat` real y publicaría el itinerario y las notas personales en una URL pública. Antes de exponer los dominios, comparar las variables de los cuatro servicios y confirmar que ninguna env de demo apunta a la DB, el bucket o la key de prod.

**Pititas no existe en la demo**, ni del lado de Spitwise (`PITITAS_OWNER` vacío) ni del de Andiamo (el slug está en `excludeSlugs` del seed). Es una parada personal y no aporta nada a quien evalúa el proyecto. Como consecuencia el seed de Andiamo también limpia `ownerPerson` de Lisboa/Oporto (`clearOwners`): sin la parada paralela, dejar el dueño le abriría a Katia un hueco de 8 noches y cada viewer vería un total de noches distinto al de Spitwise.

### DNS (Namecheap)

Los `.lat` están en Namecheap (BasicDNS, `dns1.registrar-servers.com`). Por cada subdominio, dos registros en *Advanced DNS* — el `Host` va **sin** el dominio:

| Type | Host | Value |
|---|---|---|
| CNAME | `demo` | el `*.up.railway.app` que devuelve `railway domain <dominio>` |
| TXT | `_railway-verify.demo` | el `railway-verify=…` de la misma salida |

Railway emite el certificado solo cuando ve los dos. Verificación: `railway domain status demo.andiamo.lat -s andiamo-demo` hasta `Certificate status: VALID`.

### Seeds

Ambos son destructivos e idempotentes. Corridos desde local apuntan a la DB de la demo con la **URL pública** de la Postgres (`DATABASE_PUBLIC_URL`; la interna `*.railway.internal` no resuelve fuera de Railway).

```bash
# 1) Andiamo primero: es la fuente de verdad del itinerario.
cd andiamo
DATABASE_URL="<DATABASE_PUBLIC_URL de Postgres-7098>" \
NEXT_PUBLIC_SITE_URL=https://demo.andiamo.lat \
NEXT_PUBLIC_DEMO_TODAY=2026-09-25 \
npm run db:seed:demo

# 2) Spitwise después: sincroniza las paradas desde la demo de Andiamo
#    y siembra SOLO movimientos sobre ellas.
cd spitwise/backend
PYTHONPATH=scripts \
DATABASE_URL="<DATABASE_PUBLIC_URL de Postgres-ftfA>" \
SECRET_KEY=... TRIP_SHARED_API_KEY=... AUTH_USERS="bruno:demo:,katia:demo:" \
ANDIAMO_URL=https://demo.andiamo.lat PITITAS_OWNER= ENVIRONMENT=prod \
DEMO_MODE=true DEMO_TODAY=2026-09-25 \
.venv/bin/python scripts/seed_demo_money.py
```

`seed_demo_money.py` también siembra las bandas de presupuesto (destructivo y determinista, derivadas de `scripts/seed_stop_budgets.py` para que la demo muestre los mismos números que produciría producción) y **aborta si la cobertura no da 100%**, listando los slugs sin plan: la demo pública no puede abrir `/presupuesto` a medio llenar. Cae antes del commit, así que un fallo deja la demo de ayer en pie.

`seed_demo_money.py` no define paradas propias a propósito: duplicar el itinerario garantizaba que los slugs divergieran de Andiamo y que el primer arranque archivara paradas con gastos. Si el sync falla o vuelve vacío, aborta sin sembrar. El ritmo de gasto por región y los helpers de `Movement` viven en `scripts/demo_common.py`, compartidos con el seed de la demo local (`seed_demo_data.py`).

Antes de commitear valida y aborta si algo no cierra, **antes** del commit — un fallo deja la demo de ayer en pie en vez de publicar una rota. Dos guardas: que las 11 categorías tengan al menos un movimiento (una vacía en el donut se lee como feature a medio hacer) y que haya **exactamente un** gasto por confirmar, espejando `lib/share.needsConfirmation` del frontend.

### Reset diario

Un servicio cron por app, del mismo repo y rama, con las variables de la DB de demo pero **sin dominio**. Cada uno apunta a su propio config-as-code (`railway.cron.json` en la raíz del repo) vía *Settings → Config-as-code → Railway Config File* = `/railway.cron.json`. Sin eso, el `railway.json` de la app pisa el start command y el cron levanta Next/Uvicorn 24/7 en vez de reseedeear.

| Servicio | Config file | Start (en el file) | Cron (UTC) |
|---|---|---|---|
| `andiamo-demo-cron` | `/railway.cron.json` | `npx tsx prisma/seed-demo.ts` | `0 7 * * *` |
| `spitwise-demo-cron` | `/railway.cron.json` | `alembic upgrade head && python -u scripts/seed_demo_money.py` | `10 7 * * *` |

**Andiamo diez minutos antes que Spitwise**: el segundo sincroniza el itinerario desde la demo de Andiamo y necesita el dataset ya regenerado. `0 7 * * *` UTC ≈ 4am ART.

Notas:

- `npx tsx` y no `npm run db:seed:demo` porque `tsx` es devDependency y el build de producción puede podarla; `npx` la baja si falta.
- El `Dockerfile` de Spitwise deja `WORKDIR /app/backend`, así que el path del script es relativo a ahí. `PYTHONPATH=scripts` ya está en las variables del servicio (el seed importa `demo_common`).
- `restartPolicyType: NEVER` en el cron: el seed tiene que salir solo. Si queda un proceso vivo, Railway saltea la corrida siguiente.
- Entre deploys el cron no tiene que estar Online: `railway down -s <servicio> -y` baja el deployment activo y el schedule lo vuelve a levantar a la hora.

## Stop local Pititas

Del **4 al 11 de septiembre de 2026** Bruno está solo en Portugal y Katia viaja con sus amigas. Los gastos de Katia en ese tramo se imputan a una parada **Pititas** (👭, EUR, `Europe/Paris`) en vez de Portugal; los de Bruno siguen yendo a Portugal. El 12 ya es Estrasburgo para los dos.

Pititas es un **stop local** (`Stop.is_local`): existe solo en Spitwise.

- **Andiamo no la conoce ni la debe conocer.** El sync la excluye de la reconciliación (si no, el primer `sync-hook` la borraría) y `/cities/spend` + `/cities/spend-detail` no la exponen. `/trip/spend` sí la suma: es plata gastada.
- **Se siembra sola** en el arranque (`app/stops_local.py`), después del sync, y es idempotente. Con `PITITAS_OWNER` vacío no se crea nada.
- **La imputación por fecha es por remitente**, no por pagador: si Katia carga "pagó bruno 30", el gasto igual cae en Pititas porque ella es la que está ahí.
- **Nombrar la parada la imputa para los dos**: "cena 30 en Pititas" desde el teléfono de Bruno va a Pititas (útil si le paga algo de ese tramo). Solo el default por fecha es exclusivo de ella.
- En la web la ven **los dos** (el balance ya mezcla esa plata; ocultarla dejaría un neto sin explicación), pero a Bruno nunca se le imputa ahí.
- **Para desactivarla:** borrar `PITITAS_OWNER` y redeploy. La fila queda en la DB con los gastos ya cargados; para que deje de imputar, borrar la fila `stops` con slug `pititas` (los movimientos conservan `city_name`).
