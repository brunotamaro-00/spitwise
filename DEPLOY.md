# Deploy — Botardo en Railway

Un solo servicio web (FastAPI: API + webhook de WhatsApp + frontend estático) + Postgres, en el proyecto Railway `botardo` de la **cuenta personal** (la misma de Andiamo — nunca la de Kavak). Proceso único persistente: los background tasks del webhook y los locks por chat dependen de eso — **no** subir `--workers`.

## Arquitectura

- Build: `Dockerfile` multi-stage (Vite build → runtime Python 3.12). Railway lo detecta vía `railway.json`.
- Arranque: `alembic upgrade head && uvicorn app.main:app` (migraciones en cada deploy; seed de categorías/usuarios idempotente en el lifespan).
- El frontend se sirve desde FastAPI (`FRONTEND_DIST`, ya seteado en la imagen) → mismo origen, sin CORS ni `VITE_API_URL` en prod.
- `DATABASE_URL` puede venir como `postgresql://` (formato Railway): `config.py` la convierte a `postgresql+asyncpg://` solo.

## Variables de entorno

### Botardo (servicio Railway)

| Variable | Valor |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (reference a la DB del proyecto) |
| `ENVIRONMENT` | `prod` |
| `SECRET_KEY` | random largo (`openssl rand -hex 32`) |
| `AUTH_USERS` | `bruno:<pwd>:<wa_id_bruno>,novia:<pwd>:<wa_id_novia>` |
| `ANTHROPIC_API_KEY` | key personal de Anthropic |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5` |
| `WHATSAPP_ACCESS_TOKEN` | token permanente de la app de Meta |
| `WHATSAPP_PHONE_NUMBER_ID` | id del número en WhatsApp Cloud |
| `WHATSAPP_VERIFY_TOKEN` | string random propio (se repite en la config de Meta) |
| `WHATSAPP_APP_SECRET` | app secret de Meta (firma HMAC del webhook) |
| `WHATSAPP_GRAPH_VERSION` | `v21.0` |
| `TRIP_SHARED_API_KEY` | **mismo valor** que en Andiamo |
| `ANDIAMO_URL` | `https://andiamo-production.up.railway.app` |
| `CORS_ORIGINS` | (vacío — mismo origen; solo dev usa localhost) |

Secretos **solo** acá: nunca en el repo (`.env` está gitignoreado).

### Andiamo (servicio Railway existente)

| Variable | Valor |
|---|---|
| `TRIP_SHARED_API_KEY` | mismo valor que arriba |
| `BOTARDO_URL` | `https://<botardo>.up.railway.app` |

Redeploy de Andiamo después de agregarlas (habilita `GET /api/stops` y el chip "Gastado").

## Alta inicial (una vez)

1. Railway → New Project `botardo` → Add **PostgreSQL** → Add service desde el repo (o `railway up`).
2. Cargar las envs de la tabla. Settings → Networking → Generate Domain.
3. Smoke: `curl https://<botardo>.up.railway.app/health` → `{"status":"ok"}`; login → `curl -X POST .../api/v1/auth/login -d "username=bruno&password=<pwd>"` devuelve `access_token`; el dashboard web carga con balance "a mano".
4. **Meta** (App → WhatsApp → Configuration): Callback URL `https://<botardo>.up.railway.app/webhooks/whatsapp`, Verify token = `WHATSAPP_VERIFY_TOKEN`, suscribir el campo `messages`. El GET de verificación debe devolver el `hub.challenge`.
5. Primer sync del itinerario:
   ```bash
   curl -X POST https://<botardo>.up.railway.app/api/v1/andiamo/sync -H "Authorization: Bearer <jwt>"
   # => {"synced": <n paradas, con timezone>}
   ```

## Checklist end-to-end (con los números reales)

- [ ] "cena 45 libras" → `✅ Comida: GBP 45 (USD ~57) · <ciudad activa>` + botones de split; en logs de Railway no hay reintentos de Meta (el 200 salió antes del LLM).
- [ ] Tap "Solo mío" → confirma el cambio de split.
- [ ] "borrar" → botones de confirmación → "Borrar 🗑️" borra.
- [ ] Mismo gasto desde los 2 números a la vez → cada botón de split edita el movimiento propio (sin race).
- [ ] Dashboard mobile: gasto visible, balance actualizado, ciudad activa correcta por fecha/timezone.
- [ ] "le pasé 20 usd" → settlement, el neto baja.
- [ ] "empanadas 5000 pesos" → ARS por dólar MEP, `fx_source=dolarapi`.
- [ ] Andiamo `/stops/<ciudad-activa>` → chip "Gastado: USD X".
- [ ] Corregir `fx_rate` en la web → recalcula USD (`fx_source=manual`); editar después la descripción NO pisa la tasa.

## Runbook

- **Logs:** `railway logs` (o el panel del servicio). Errores del bot salen como `dispatch_error` / `webhook_background_error` con traceback.
- **Resync del itinerario:** `POST /api/v1/andiamo/sync` con JWT (o esperar el refresh perezoso de 6h que dispara cualquier mensaje de WhatsApp).
- **Rotar `TRIP_SHARED_API_KEY`:** generar valor nuevo → actualizarlo en **ambos** servicios (Botardo y Andiamo) → redeploy de los dos. Hasta que coincidan, el sync devuelve 0 (usa snapshot) y el chip de Andiamo desaparece — nada se rompe.
- **Rotar token de WhatsApp:** Meta → System User token nuevo → actualizar `WHATSAPP_ACCESS_TOKEN` → redeploy. El webhook sigue validando con `WHATSAPP_APP_SECRET` (no cambia).
- **Cold starts / sleep:** si el plan gratuito duerme el servicio, pasar a Hobby (~USD 5/mes) — el webhook de Meta no tolera bien arranques fríos.
