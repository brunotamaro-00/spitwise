# Botardo Viaje — Plan 6: Deploy (Vercel + Supabase)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publicar Botardo: Postgres en Supabase (migraciones + seed), backend FastAPI como funciones serverless de Python en Vercel, frontend estático en Vercel, WhatsApp Cloud apuntando al webhook, y verificación end-to-end. Integración con Andiamo por env compartidas.

**Architecture:** Supabase = DB (pooler pgBouncer para serverless). Vercel proyecto backend = `api/index.py` (ASGI) con rewrites de todas las rutas. Vercel proyecto frontend = build estático de `frontend/` con `VITE_API_URL` al backend + CORS habilitado. Envs `TRIP_SHARED_API_KEY`/`BOTARDO_URL`/`ANDIAMO_URL` conectan con Andiamo.

**Tech Stack:** Supabase (Postgres 16 + pooler), Vercel Python runtime (`@vercel/python`), Vite build, WhatsApp Cloud API.

## Global Constraints

- **Identidad git personal** (`brunotamaro-00` / `brunotamaro@hotmail.com`). Cuentas de Vercel/Supabase: usar la **personal**, nunca la de Kavak.
- Serverless: **sin pool persistente**. El engine usa `NullPool` y el **connection string del pooler** de Supabase (puerto 6543, `pgbouncer=true`). Nada de estado en proceso entre requests.
- Seed de categorías/usuarios se corre **una vez** como script contra Supabase (no depender del lifespan en serverless). El lifespan queda como fallback idempotente pero no es la vía principal.
- El webhook debe responder 2xx rápido; Meta reintenta si no.
- Secretos solo en envs de Vercel (nunca commiteados). `.env` está en `.gitignore`.

**Nota de decisión (validar al ejecutar):** FastAPI en Vercel Python serverless es viable pero puede tener fricción (cold starts, límites de ejecución, webhook siempre-activo). **Fallback**: si molesta, deployar el backend en Railway (donde ya vive Andiamo) y dejar solo el frontend en Vercel. El resto del plan (Supabase, envs, WhatsApp) no cambia. Confirmar el approach en el primer intento de deploy del backend.

---

## Estructura de archivos (Plan 6)

- Create: `api/index.py` (entrypoint ASGI Vercel), `vercel.json` (backend), `requirements.txt`.
- Modify: `backend/app/db/engine.py` (NullPool en serverless).
- Modify: `backend/app/main.py` (lifespan seed guardado por env).
- Create: `backend/scripts/seed_prod.py` (seed one-off).
- Create: `frontend/vercel.json` (SPA fallback) + doc de `VITE_API_URL`.
- Create: `DEPLOY.md` (matriz de envs + runbook).

---

### Task 1: Supabase — DB, migraciones y seed

**Files:**
- Create: `backend/scripts/__init__.py`, `backend/scripts/seed_prod.py`
- Test/verify: comandos `alembic` + `psql`/`curl`.

**Interfaces:**
- Produces: `python -m scripts.seed_prod` — corre `seed_categories` + `seed_users_from_env` contra `DATABASE_URL`.

- [ ] **Step 1: Crear el proyecto Supabase**

Manual (dashboard Supabase, cuenta personal):
- Nuevo proyecto (región cercana). Anotar la password del DB.
- Settings → Database → Connection string:
  - **Direct** (puerto 5432) → para migraciones Alembic.
  - **Pooler / Transaction** (puerto 6543, `?pgbouncer=true`) → para el runtime serverless.
- Convertir a formato async: `postgresql+asyncpg://...`.

- [ ] **Step 2: Crear el seed script**

`backend/scripts/__init__.py`: (vacío)

`backend/scripts/seed_prod.py`:
```python
import asyncio

from app.categories.seed import seed_categories
from app.db.engine import get_sessionmaker
from app.users import seed_users_from_env


async def main() -> None:
    maker = get_sessionmaker()
    async with maker() as session:
        await seed_categories(session)
        await session.commit()
        await seed_users_from_env(session)
    print("seed ok")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Correr migraciones + seed contra Supabase**

Run (con la **Direct connection** en `DATABASE_URL`):
```bash
cd backend
export DATABASE_URL="postgresql+asyncpg://postgres:<pwd>@db.<ref>.supabase.co:5432/postgres"
export AUTH_USERS="bruno:<pwd>:<wa_id_bruno>,novia:<pwd>:<wa_id_novia>"
alembic upgrade head
python -m scripts.seed_prod
```
Expected: `alembic` aplica `0001_initial`; imprime `seed ok`.

- [ ] **Step 4: Verificar**

Run: `psql "<direct-conn-no-async>" -c "select name from categories order by sort_order;"`
Expected: las 7 categorías. Y `select count(*) from users;` → 2.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/scripts
git commit -m "chore(deploy): seed script para Supabase"
```

---

### Task 2: Backend en Vercel (Python serverless)

**Files:**
- Create: `api/index.py`, `vercel.json`, `requirements.txt`
- Modify: `backend/app/db/engine.py`, `backend/app/main.py`
- Verify: `curl` a la URL de Vercel.

**Interfaces:**
- Produces: deploy del backend en Vercel con `app` ASGI servido en todas las rutas; `/health` responde `{"status":"ok"}`.

- [ ] **Step 1: Engine con NullPool en serverless**

En `backend/app/db/engine.py`, modificar `make_engine`:
```python
from sqlalchemy.pool import NullPool

from app.config import get_settings


def make_engine(url: str) -> AsyncEngine:
    kwargs: dict = {"pool_pre_ping": True}
    if get_settings().environment == "prod":
        kwargs = {"poolclass": NullPool}  # serverless: sin pool persistente
    return create_async_engine(url, **kwargs)
```

- [ ] **Step 2: Lifespan seed guardado por env**

En `backend/app/main.py`, envolver el seed del lifespan:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().environment != "prod":
        maker = get_sessionmaker()
        async with maker() as session:
            await seed_categories(session)
            await session.commit()
            await seed_users_from_env(session)
    yield
```
(En prod el seed lo hace `scripts/seed_prod.py`; evitamos correrlo en cada cold start.)

- [ ] **Step 3: Entrypoint Vercel**

`api/index.py`:
```python
import sys
from pathlib import Path

# El código vive en backend/; agregarlo al path para importarlo desde api/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402

# Vercel Python runtime sirve la variable ASGI `app`.
```

`vercel.json` (raíz):
```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "functions": { "api/index.py": { "runtime": "@vercel/python@4.3.0" } },
  "rewrites": [{ "source": "/(.*)", "destination": "/api/index" }]
}
```

`requirements.txt` (raíz — Vercel Python lo instala):
```
fastapi>=0.115
sqlalchemy[asyncio]>=2.0
asyncpg>=0.29
httpx>=0.27
pydantic
pydantic-settings>=2.6
python-jose[cryptography]>=3.3
python-multipart>=0.0.9
bcrypt>=4.0
openai>=1.51
```

- [ ] **Step 4: Crear el proyecto Vercel (backend) + envs**

Manual (Vercel, cuenta personal, root del repo Botardo):
- Framework preset: **Other**. Root Directory: raíz del repo.
- Env vars (Production):
  - `ENVIRONMENT=prod`
  - `DATABASE_URL` = **pooler** async (`...pooler.supabase.com:6543/postgres?pgbouncer=true` → `postgresql+asyncpg://...`; para asyncpg, pasar `pgbouncer` vía `?prepared_statement_cache_size=0` — ver nota).
  - `SECRET_KEY`, `JWT_EXPIRE_DAYS=30`
  - `OPENAI_API_KEY`, `OPENAI_MODEL=gpt-4o-mini`
  - `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET`, `WHATSAPP_GRAPH_VERSION=v21.0`
  - `TRIP_SHARED_API_KEY` (mismo valor que Andiamo)
  - `ANDIAMO_URL=https://andiamo-production.up.railway.app`
  - `CORS_ORIGINS` = URL del frontend (se completa en Task 3)

  Nota asyncpg+pgBouncer: asyncpg usa prepared statements que pgBouncer en modo transaction no soporta. Setear en el engine `connect_args={"statement_cache_size": 0}` cuando `environment=='prod'`. Agregar a `make_engine`:
  ```python
  if get_settings().environment == "prod":
      kwargs = {"poolclass": NullPool, "connect_args": {"statement_cache_size": 0}}
  ```

- [ ] **Step 5: Deploy + verificar**

Run (o push a la branch conectada): `vercel --prod`
Verify: `curl https://<backend>.vercel.app/health`
Expected: `{"status":"ok"}`.
Verify auth: `curl -X POST https://<backend>.vercel.app/api/v1/auth/login -d "username=bruno&password=<pwd>"`
Expected: `{"access_token": "...", ...}`.

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add api vercel.json requirements.txt backend/app/db/engine.py backend/app/main.py
git commit -m "chore(deploy): backend FastAPI en Vercel serverless (NullPool + pgbouncer)"
```

---

### Task 3: Frontend en Vercel

**Files:**
- Create: `frontend/vercel.json`
- Modify: `frontend/.env.production` (o env de Vercel)
- Verify: abrir la URL.

**Interfaces:**
- Produces: frontend estático servido, hablando con el backend vía `VITE_API_URL` + CORS.

- [ ] **Step 1: Ajustar el cliente para `VITE_API_URL`**

En `frontend/src/api/client.ts`, cambiar `baseURL`:
```ts
export const api = axios.create({ baseURL: `${import.meta.env.VITE_API_URL ?? ""}/api/v1` });
```
(En dev `VITE_API_URL` vacío → usa el proxy de Vite. En prod → URL del backend.)

- [ ] **Step 2: SPA fallback**

`frontend/vercel.json`:
```json
{
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```

- [ ] **Step 3: Crear proyecto Vercel (frontend) + envs**

Manual:
- Root Directory: `frontend/`. Framework: **Vite**. Build: `npm run build`, Output: `dist`.
- Env: `VITE_API_URL=https://<backend>.vercel.app`.
- Tras deploy, copiar la URL del frontend y setear `CORS_ORIGINS` en el backend (Task 2) a esa URL; redeploy backend.

- [ ] **Step 4: Verificar end-to-end web**

- Abrir `https://<frontend>.vercel.app` en **mobile** (o devtools responsive).
- Login → dashboard carga (balance "a mano", total 0). Sin errores CORS en consola.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add frontend/vercel.json frontend/src/api/client.ts
git commit -m "chore(deploy): frontend Vite en Vercel (VITE_API_URL + SPA fallback)"
```

---

### Task 4: WhatsApp + Andiamo + verificación end-to-end

**Files:**
- Create: `DEPLOY.md`
- Config: Meta WhatsApp + envs Andiamo.

- [ ] **Step 1: Configurar el webhook en Meta**

Manual (Meta App → WhatsApp → Configuration):
- Callback URL: `https://<backend>.vercel.app/webhooks/whatsapp`
- Verify token: el valor de `WHATSAPP_VERIFY_TOKEN`.
- Suscribir el campo `messages`.
- Meta hace `GET` de verificación → debe responder el `hub.challenge` (200).

- [ ] **Step 2: Envs de Andiamo (repo/Railway)**

En Andiamo (Railway, cuenta personal), agregar envs:
- `TRIP_SHARED_API_KEY` = mismo valor que Botardo.
- `BOTARDO_URL` = `https://<backend>.vercel.app`.
Redeploy Andiamo.

- [ ] **Step 3: Primer sync de itinerario**

Run (JWT de un login):
```bash
curl -X POST https://<backend>.vercel.app/api/v1/andiamo/sync -H "Authorization: Bearer <jwt>"
```
Expected: `{"synced": <n>}` con n = cantidad de stops de Andiamo.
Verify: `GET /api/v1/dashboard/by-city` responde (vacío aún, pero 200).

- [ ] **Step 4: Verificación end-to-end completa**

Checklist (probar en el número real):
- [ ] Mandar por WhatsApp: "cena 45 libras" → responde `✅ ... GBP 45 (USD ~57) · <ciudad activa>` + botones de split.
- [ ] Tap "Solo mío" → confirma cambio de split.
- [ ] En el dashboard web (mobile): el gasto aparece, el balance se actualiza, la ciudad activa es la correcta según la fecha del itinerario.
- [ ] Mandar "le pasé 20 usd" → registra settlement, el neto baja.
- [ ] En Andiamo, abrir `/stops/<ciudad-activa>` → chip "Gastado: USD X" visible.
- [ ] Corregir un `fx_rate` en la web → `amount_usd` se recalcula, `fx_source=manual`.

- [ ] **Step 5: Escribir `DEPLOY.md`**

`DEPLOY.md` con: matriz de envs (backend Vercel / frontend Vercel / Andiamo Railway), URLs, runbook de "resync itinerario", y cómo rotar `TRIP_SHARED_API_KEY`. (Documentar los valores por nombre, nunca los secretos.)

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add DEPLOY.md
git commit -m "docs(deploy): runbook + matriz de envs"
```

---

## Self-review (Plan 6)

- **Cobertura de spec §10:** Supabase + migraciones + seed (Task 1), backend serverless con NullPool/pgbouncer (Task 2), frontend estático + CORS (Task 3), WhatsApp webhook + envs Andiamo + verificación end-to-end (Task 4). Resiliencia de sync/widget ya cubierta en Plan 4.
- **Placeholders:** los pasos "Manual (dashboard...)" son acciones de infra inherentemente no-código; se dan con valores exactos de env y comandos de verificación (`curl`). No hay lógica pendiente.
- **Consistencia:** `ENVIRONMENT=prod` activa NullPool + statement_cache_size=0 (asyncpg+pgBouncer) y desactiva el seed del lifespan — coherente con `scripts/seed_prod.py`. `TRIP_SHARED_API_KEY`/`BOTARDO_URL`/`ANDIAMO_URL` alineadas con los contratos del Plan 4.
- **Decisión abierta marcada:** Vercel Python vs Railway para el backend — validar en el primer deploy (Task 2), fallback documentado.
```
