# Botardo Viaje — Plan 6: Deploy (Railway)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publicar Botardo en Railway como **un solo servicio**: FastAPI (API + webhook + frontend estático) + Railway Postgres en el mismo proyecto. Configurar WhatsApp Cloud apuntando al webhook, conectar Andiamo por envs compartidas, y verificar end-to-end.

**Architecture:** Railway proyecto `botardo` con 2 recursos: el servicio web (FastAPI, proceso persistente — los background tasks del webhook y el `asyncio.Lock` por chat funcionan de verdad) y Postgres (la `DATABASE_URL` interna la inyecta Railway). El build compila el frontend (Vite) y FastAPI lo sirve como estático en `/` → mismo origen, **sin CORS en prod**, sin `VITE_API_URL`. Andiamo sigue en su propio servicio Railway.

**Por qué no Vercel serverless (decisión cerrada):** Meta exige 200 en ~5s y el procesamiento del webhook (LLM + FX + Graph) debe correr después de responder — Vercel Python congela la función al responder, no tiene background tasks y limita a 10s en Hobby. Supabase free además pausa la DB tras 7 días de inactividad. Railway elimina toda esa clase de problemas.

**Tech Stack:** Railway (service + Postgres), Nixpacks o Dockerfile, Vite build, FastAPI StaticFiles, WhatsApp Cloud API, Anthropic API.

## Global Constraints

- **Identidad git personal** (`brunotamaro-00` / `brunotamaro@hotmail.com`). Cuenta Railway: la **personal** (la misma donde vive Andiamo), nunca la de Kavak.
- Un solo servicio web: API + webhook + frontend. Un solo proceso (sin `--workers N`>1: los locks por chat son en-proceso).
- Migraciones Alembic corren en el deploy (`release` / start command), no a mano.
- Seed de categorías/usuarios: idempotente en el lifespan del startup (ya implementado en Plan 2) — válido porque el proceso arranca una vez, no por request.
- Secretos solo en variables de Railway (nunca commiteados). `.env` está en `.gitignore`.
- El webhook debe responder 2xx rápido — ya garantizado por diseño (ACK + background, Plan 3).

---

## Estructura de archivos (Plan 6)

- Create: `Dockerfile` (multi-stage: build frontend → runtime Python) o `railway.json` + Nixpacks.
- Modify: `backend/app/main.py` — servir `frontend/dist` como estático con SPA fallback.
- Create: `DEPLOY.md` (matriz de envs + runbook).

---

### Task 1: Servir el frontend desde FastAPI

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_static_spa.py` (con un `dist` de fixture)

**Interfaces:**
- `GET /` y cualquier ruta no-API → `index.html` (SPA fallback); assets desde `frontend/dist/assets`. Las rutas `/api/v1/*`, `/webhooks/*`, `/health` tienen prioridad (los routers se montan antes que el estático).

- [x] **Step 1: Escribir el test que falla**

`backend/tests/test_static_spa.py`:
```python
async def test_spa_fallback_serves_index(app_client, tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>botardo</html>")
    monkeypatch.setenv("FRONTEND_DIST", str(dist))
    from app.config import get_settings
    get_settings.cache_clear()
    # Remontar la app con el dist configurado (o testear el helper mount_frontend directamente).
    from app.main import create_static_app  # helper testeable
    ...
```
(Si montar el estático condicionalmente complica el fixture, alcanza con un helper `mount_frontend(app, dist_path)` unit-testeado: registra `StaticFiles` + catch-all que devuelve `index.html` para rutas sin extensión que no empiecen con `/api`, `/webhooks`, `/health`.)

- [x] **Step 2: Implementar en `main.py`**

Al final de `backend/app/main.py` (después de incluir todos los routers):
```python
import os
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_frontend(app: FastAPI, dist: Path) -> None:
    if not dist.exists():
        logger.warning("frontend_dist_missing path=%s (solo API)", dist)
        return
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        candidate = dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")


mount_frontend(app, Path(os.environ.get("FRONTEND_DIST", "../frontend/dist")))
```
Nota: el catch-all se registra último, así que `/api/v1/*`, `/webhooks/*` y `/health` (registrados antes) ganan. En dev el `dist` no existe → solo API + proxy de Vite, igual que siempre.

- [x] **Step 3: Verificar local**

Run: `cd frontend && npm run build && cd ../backend && FRONTEND_DIST=../frontend/dist uvicorn app.main:app --port 8000`
Verify: `curl -s localhost:8000/ | grep -qi html && curl -s localhost:8000/health` → index.html y `{"status":"ok"}`.

- [x] **Step 4: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/app/main.py backend/tests/test_static_spa.py
git commit -m "feat(deploy): FastAPI sirve el frontend estático con SPA fallback"
```

---

### Task 2: Dockerfile multi-stage + config Railway

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `railway.json`

- [x] **Step 1: Crear `Dockerfile`**

```dockerfile
# --- Stage 1: frontend ---
FROM node:22-slim AS frontend
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: backend ---
FROM python:3.12-slim
WORKDIR /app
COPY backend/pyproject.toml ./backend/
RUN pip install --no-cache-dir ./backend || true
COPY backend/ ./backend/
RUN pip install --no-cache-dir ./backend
COPY --from=frontend /fe/dist ./frontend/dist
ENV FRONTEND_DIST=/app/frontend/dist
WORKDIR /app/backend
# Migraciones + un solo worker (locks en proceso).
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

`railway.json` (raíz):
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": { "builder": "DOCKERFILE" },
  "deploy": { "restartPolicyType": "ON_FAILURE" }
}
```

`.dockerignore`: `node_modules`, `.venv`, `__pycache__`, `.git`, `frontend/dist`, `*.env`.

- [x] **Step 2: Verificar build local**

Run: `docker build -t botardo . && docker run --rm -e DATABASE_URL=... -p 8000:8000 botardo` (contra el Postgres local del docker-compose).
Expected: migra y sirve `/health` + `/`.

- [x] **Step 3: Commit**

```bash
git add Dockerfile .dockerignore railway.json
git commit -m "chore(deploy): Dockerfile multi-stage + config Railway"
```

---

### Task 3: Proyecto Railway — Postgres + servicio + envs

- [ ] **Step 1: Crear el proyecto (manual, cuenta personal)**

- Railway → New Project → `botardo`.
- Add **PostgreSQL** (genera `DATABASE_URL` interna, formato `postgresql://...` → el servicio la consume como `postgresql+asyncpg://` — convertir en env o en `config.py` con un `replace("postgresql://", "postgresql+asyncpg://")`).
- Add service desde el repo `Botardo` (GitHub) o `railway up` desde local.

- [ ] **Step 2: Variables del servicio (Production)**

| Variable | Valor |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (reference) convertida a `+asyncpg` |
| `ENVIRONMENT` | `prod` |
| `SECRET_KEY` | random largo |
| `AUTH_USERS` | `bruno:<pwd>:<wa_id_bruno>,novia:<pwd>:<wa_id_novia>` |
| `ANTHROPIC_API_KEY` | key personal |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5` |
| `WHATSAPP_ACCESS_TOKEN` / `WHATSAPP_PHONE_NUMBER_ID` / `WHATSAPP_VERIFY_TOKEN` / `WHATSAPP_APP_SECRET` | de Meta |
| `WHATSAPP_GRAPH_VERSION` | `v21.0` |
| `TRIP_SHARED_API_KEY` | mismo valor que en Andiamo |
| `ANDIAMO_URL` | `https://andiamo-production.up.railway.app` |
| `CORS_ORIGINS` | vacío (mismo origen; solo dev usa localhost) |

- [ ] **Step 3: Deploy + smoke test**

- Generar dominio público del servicio (Settings → Networking → `botardo-production.up.railway.app`).
- Verify: `curl https://<botardo>.up.railway.app/health` → `{"status":"ok"}`.
- Verify login: `curl -X POST .../api/v1/auth/login -d "username=bruno&password=<pwd>"` → `access_token`.
- Verify seed: login web (mobile) → dashboard carga, balance "a mano", total 0.

---

### Task 4: WhatsApp + Andiamo + verificación end-to-end

**Files:**
- Create: `DEPLOY.md`

- [ ] **Step 1: Configurar el webhook en Meta**

Manual (Meta App → WhatsApp → Configuration):
- Callback URL: `https://<botardo>.up.railway.app/webhooks/whatsapp`
- Verify token: el valor de `WHATSAPP_VERIFY_TOKEN`. Suscribir el campo `messages`.
- Meta hace `GET` de verificación → debe responder el `hub.challenge` (200).

- [ ] **Step 2: Envs de Andiamo (Railway)**

En el servicio Andiamo agregar: `TRIP_SHARED_API_KEY` (mismo valor) y `BOTARDO_URL=https://<botardo>.up.railway.app`. Redeploy.

- [ ] **Step 3: Primer sync de itinerario**

```bash
curl -X POST https://<botardo>.up.railway.app/api/v1/andiamo/sync -H "Authorization: Bearer <jwt>"
```
Expected: `{"synced": <n>}` con n = paradas de Andiamo (con `timezone` poblada).

- [ ] **Step 4: Verificación end-to-end completa**

Checklist (en el número real):
- [ ] "cena 45 libras" por WhatsApp → responde en <2s con `✅ ... GBP 45 (USD ~57) · <ciudad activa>` + botones de split (el 200 a Meta salió antes de procesar — revisar logs Railway: sin reintentos de Meta).
- [ ] Tap "Solo mío" → confirma cambio de split.
- [ ] "borrar" → botones de confirmación → tap "Borrar 🗑️" → borrado.
- [ ] Mandar el mismo gasto dos veces seguidas rápido desde los 2 números → cada botón de split edita el movimiento correcto (no hay race).
- [ ] Dashboard web (mobile): gasto visible, balance actualizado, ciudad activa correcta según fecha/timezone del itinerario.
- [ ] "le pasé 20 usd" → settlement, el neto baja.
- [ ] Gasto en ARS ("empanadas 5000 pesos") → convertido con MEP, `fx_source=dolarapi`.
- [ ] En Andiamo, `/stops/<ciudad-activa>` → chip "Gastado: USD X" visible.
- [ ] Corregir un `fx_rate` en la web → `amount_usd` recalculado, `fx_source=manual`; editar luego la descripción NO pisa la tasa.

- [x] **Step 5: Escribir `DEPLOY.md`**

`DEPLOY.md` con: matriz de envs (Botardo Railway / Andiamo Railway), URLs, runbook de "resync itinerario", cómo rotar `TRIP_SHARED_API_KEY` y el token de WhatsApp, y cómo ver logs (`railway logs`). Documentar los nombres de envs, nunca los secretos.

- [x] **Step 6: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add DEPLOY.md
git commit -m "docs(deploy): runbook + matriz de envs (Railway)"
```

---

## Self-review (Plan 6)

- **Cobertura de spec §10:** Railway Postgres + migraciones en el start command (Task 2/3), servicio único FastAPI con frontend estático same-origin (Tasks 1/2), envs + WhatsApp webhook + Andiamo (Tasks 3/4), verificación end-to-end que cubre los fixes de la revisión (ACK rápido, race de split, borrado, ARS/MEP, PATCH sin pisar manual).
- **Placeholders:** los pasos "Manual (dashboard...)" son acciones de infra inherentemente no-código, con valores exactos de env y `curl` de verificación.
- **Consistencia:** un solo worker uvicorn ⇒ locks y `ensure_stops_fresh` en proceso válidos. `ENVIRONMENT=prod` ya no activa hacks (NullPool/pgbouncer eliminados con Vercel). `CORS_ORIGINS` vacío en prod porque el frontend es same-origin.
- **Riesgos restantes:** si Railway duerme el servicio en el plan gratuito, actualizar al plan Hobby (~USD 5/mes) — para un viaje de 108 noches es el costo de una cerveza y elimina cold starts.
