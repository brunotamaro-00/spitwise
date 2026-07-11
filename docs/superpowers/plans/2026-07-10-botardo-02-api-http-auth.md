# Botardo Viaje — Plan 2: API HTTP + auth + dashboard

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exponer la app FastAPI (CORS + seed en startup), auth JWT reciclada de Expenses, CRUD de movimientos (con FX), el endpoint de balance (neto splitwise) y los agregados del dashboard (total, por ciudad, por categoría, timeseries).

**Architecture:** FastAPI con dependency `get_session` (AsyncSession por request, apto serverless). Endpoints bajo `/api/v1`. Los movimientos se crean convirtiendo a USD con `app.fx.convert_to_usd`; el balance usa `app.balance.compute_balance`. Un solo libro: no hay filtro por owner en las lecturas.

**Tech Stack:** FastAPI, SQLAlchemy async, python-jose (JWT), bcrypt, httpx (tests ASGI), pytest-asyncio.

## Global Constraints

- Reusa las piezas del Plan 1 (`app.config`, `app.db.*`, `app.fx`, `app.balance`, `app.categories`).
- Montos serializados como **string** (Decimal) en las respuestas JSON (igual que Expenses: `frontend/src/types/index.ts`).
- Auth: JWT `HS256`, claim `sub=username`, exp configurable. Login normaliza username a lowercase.
- Un solo libro compartido: exactamente 2 usuarios (sembrados de `AUTH_USERS`). Las lecturas **no** filtran por usuario.
- `fx_source` persistido en `Movement`: `frankfurter` cuando FX vino de API/cache (`source ∈ {frankfurter,cache,direct}`), `fallback` cuando cayó al fallback, `manual` cuando el usuario fija la tasa.
- Sin estado en proceso salvo el rate-limit de login (aceptable; se puede perder en serverless).

**Referencia de reutilización:** `~/Desktop/Expenses/backend/app/api/auth.py` (auth completa), `app/api/expenses.py` (CRUD), `app/api/expenses_analytics.py` (agregados), `app/main.py` (lifespan/seed), `app/db/engine.py` (`get_session`).

---

## Estructura de archivos (Plan 2)

- Modify: `backend/app/config.py` — agregar `secret_key`, `jwt_expire_days`, `bot_api_key`, `cors_origins`, `auth_users`, `trip_shared_api_key`, `andiamo_url`, campos WhatsApp/Anthropic (placeholders para plans 3/4).
- Modify: `backend/app/db/engine.py` — agregar `async def get_session()` (dependency).
- Create: `backend/app/main.py` — FastAPI app, CORS, lifespan (seed categorías + usuarios), `/health`.
- Create: `backend/app/api/__init__.py`, `backend/app/api/router.py`, `backend/app/api/schemas.py`.
- Create: `backend/app/api/auth.py` — login + `get_current_user`.
- Create: `backend/app/users.py` — `get_trip_users(session)`.
- Create: `backend/app/api/movements.py` — CRUD.
- Create: `backend/app/api/balance.py` — GET balance.
- Create: `backend/app/api/categories.py` — GET categorías.
- Create: `backend/app/api/dashboard.py` — summary / by-city / by-category / timeseries.
- Test: `backend/tests/conftest.py` (extender con `app_client` fixture), `test_health.py`, `test_auth.py`, `test_movements_api.py`, `test_balance_api.py`, `test_dashboard_api.py`.

---

### Task 1: App, config, session dependency, health

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/db/engine.py`
- Create: `backend/app/main.py`, `backend/app/api/__init__.py`, `backend/app/api/router.py`
- Test: `backend/tests/conftest.py` (extender), `backend/tests/test_health.py`

**Interfaces:**
- Produces:
  - `app.config.Settings` con: `secret_key: str`, `jwt_expire_days: int = 30`, `bot_api_key: str`, `cors_origins: str`, `auth_users: str`, `trip_shared_api_key: str`, `andiamo_url: str`, `openai_api_key: str`, `openai_model: str`, y campos WhatsApp (`whatsapp_*`).
  - `app.db.engine.get_session()` — async generator dependency que yield-ea `AsyncSession`.
  - `app.main.app` (FastAPI) con `GET /health` → `{"status":"ok"}` y router en `/api/v1`.
  - Fixture `app_client` (httpx.AsyncClient sobre ASGI con DB sqlite en memoria y `get_session` overrideado).

- [x] **Step 1: Escribir el test que falla**

`backend/tests/test_health.py`:
```python
async def test_health(app_client):
    r = await app_client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

Extender `backend/tests/conftest.py` (agregar debajo del fixture `db_session`):
```python
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base


@pytest_asyncio.fixture
async def app_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    from app.main import app
    from app.db.engine import get_session

    async def _override_get_session():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    # Seed base (categorías) para las pruebas que lo requieran.
    from app.categories.seed import seed_categories
    async with maker() as s:
        await seed_categories(s)
        await s.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client._maker = maker  # exponer para tests que necesiten sembrar datos
        yield client
    app.dependency_overrides.clear()
    await engine.dispose()
```

- [x] **Step 2: Correr y verificar fallo**

Run: `cd backend && pytest tests/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`.

- [x] **Step 3: Extender `config.py`**

Agregar a la clase `Settings` en `backend/app/config.py` (después de `environment`):
```python
    # Auth
    secret_key: str = "change-me-in-production-use-a-long-random-string"
    jwt_expire_days: int = 30
    bot_api_key: str = "change-me-bot-key"
    auth_users: str = ""  # "user:pass:wa_id,user2:pass2:wa_id2"
    cors_origins: str = Field(default="", alias="CORS_ORIGINS")

    # Integración Andiamo
    trip_shared_api_key: str = "change-me-shared-key"
    andiamo_url: str = ""  # ej. https://andiamo-production.up.railway.app

    # LLM (parse, Claude Haiku 4.5) — usado en Plan 3
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5"
    anthropic_timeout_seconds: float = 20.0

    # WhatsApp Cloud — usado en Plan 3
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_graph_version: str = "v21.0"
    whatsapp_auto_register: bool = False
```

Y agregar helper de CORS al final del archivo (antes de `get_settings`):
```python
_DEFAULT_CORS = ["http://localhost:5173", "http://localhost:3000"]


def parse_cors(v: str) -> list[str]:
    if not v or not v.strip():
        return _DEFAULT_CORS
    v = v.strip()
    if v.startswith("["):
        import json
        return json.loads(v)
    return [o.strip() for o in v.split(",") if o.strip()]
```

- [x] **Step 4: Agregar `get_session` a `engine.py`**

Agregar al final de `backend/app/db/engine.py`:
```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    maker = get_sessionmaker()
    async with maker() as session:
        yield session
```

- [x] **Step 5: Crear router y main**

`backend/app/api/__init__.py`: (vacío)

`backend/app/api/router.py`:
```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")
```

`backend/app/main.py`:
```python
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings, parse_cors

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Botardo Viaje")

app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors(get_settings().cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


from app.api.router import router as api_router  # noqa: E402

app.include_router(api_router)
```

- [x] **Step 6: Correr el test**

Run: `cd backend && pytest tests/test_health.py -v`
Expected: PASS.

- [x] **Step 7: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/app/config.py backend/app/db/engine.py backend/app/main.py backend/app/api backend/tests/conftest.py backend/tests/test_health.py
git commit -m "feat(backend): app FastAPI + CORS + get_session + health"
```

---

### Task 2: Auth JWT + usuarios del viaje

**Files:**
- Create: `backend/app/api/auth.py`, `backend/app/api/schemas.py`, `backend/app/users.py`
- Modify: `backend/app/main.py` (seed usuarios en lifespan), `backend/app/api/router.py` (incluir auth)
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `app.db.models.User`, `app.config`, `get_session`.
- Produces:
  - `app.api.auth.hash_password(p)->str`, `verify_password(p,h)->bool`, `create_jwt(username)->str`.
  - `app.api.auth.get_current_user(...)` dependency → `User` (401 si token inválido).
  - `POST /api/v1/auth/login` (form `username`,`password`) → `{"access_token","token_type":"bearer"}`.
  - `GET /api/v1/users` (JWT) → `[{id, username}]` de los 2 usuarios (orden `id` asc). **Lo necesitan `BalanceHero` ("X le debe a Y") y `SettleDialog` (elegir pagador) del Plan 5 — no es opcional.**
  - `app.users.get_trip_users(session) -> tuple[User, User]` — los 2 usuarios del libro (por `id` asc). Lanza `HTTPException(500)` si no hay exactamente 2.
  - `app.users.seed_users_from_env(session)` — crea usuarios de `AUTH_USERS` (idempotente, vincula wa_id).

- [x] **Step 1: Escribir el test que falla**

`backend/tests/test_auth.py`:
```python
import pytest

from app.api.auth import create_jwt, hash_password, verify_password


def test_password_roundtrip():
    h = hash_password("secreto")
    assert verify_password("secreto", h)
    assert not verify_password("malo", h)


async def test_login_and_protected_route(app_client):
    # Sembrar un usuario directo en la DB del cliente.
    from app.db.models import User
    async with app_client._maker() as s:
        s.add(User(username="bruno", password_hash=hash_password("pw")))
        await s.commit()

    r = await app_client.post("/api/v1/auth/login", data={"username": "bruno", "password": "pw"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    r2 = await app_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["username"] == "bruno"

    r3 = await app_client.get("/api/v1/auth/me")
    assert r3.status_code == 401


async def test_users_endpoint(app_client):
    from app.db.models import User
    async with app_client._maker() as s:
        s.add_all([User(username="bruno", password_hash=hash_password("pw")),
                   User(username="katia", password_hash=hash_password("pw"))])
        await s.commit()
    r = await app_client.post("/api/v1/auth/login", data={"username": "bruno", "password": "pw"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    users = await app_client.get("/api/v1/users", headers=h)
    assert users.status_code == 200
    assert [u["username"] for u in users.json()] == ["bruno", "katia"]
```

- [x] **Step 2: Correr y verificar fallo**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: FAIL — import error de `app.api.auth`.

- [x] **Step 3: Crear `schemas.py`**

`backend/app/api/schemas.py`:
```python
from datetime import date
from pydantic import BaseModel, ConfigDict, field_serializer
from decimal import Decimal


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str


class MovementIn(BaseModel):
    type: str = "expense"
    amount: Decimal
    currency: str = "USD"
    split: str = "shared"
    paid_by: int | None = None  # default: usuario actual
    description: str | None = None
    category_id: int | None = None
    stop_slug: str | None = None
    city_name: str | None = None
    movement_date: date | None = None
    fx_rate: Decimal | None = None  # override manual


class MovementUpdate(BaseModel):
    """PATCH parcial: todos opcionales; solo se aplica lo que vino en el body
    (via model_fields_set). Nunca usar MovementIn acá: sus campos obligatorios
    romperían las ediciones parciales."""

    type: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    split: str | None = None
    paid_by: int | None = None
    description: str | None = None
    category_id: int | None = None
    stop_slug: str | None = None
    city_name: str | None = None
    movement_date: date | None = None
    fx_rate: Decimal | None = None  # setearlo => fx_source='manual'


class MovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: str
    amount: Decimal
    currency: str
    amount_usd: Decimal
    fx_rate: Decimal
    fx_source: str
    paid_by: int
    split: str
    description: str | None
    category_id: int | None
    stop_slug: str | None
    city_name: str | None
    movement_date: date

    @field_serializer("amount", "amount_usd", "fx_rate")
    def _ser_decimal(self, v: Decimal) -> str:
        return str(v)


class BalanceOut(BaseModel):
    debtor_id: int | None
    creditor_id: int | None
    amount_usd: str
```

- [x] **Step 4: Crear `auth.py`** (adaptado de Expenses `app/api/auth.py`, sin auto-registro)

`backend/app/api/auth.py`:
```python
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import TokenResponse, UserOut
from app.config import get_settings
from app.db.engine import get_session
from app.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_jwt(username: str) -> str:
    s = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=s.jwt_expire_days)
    return jwt.encode({"sub": username, "exp": expire}, s.secret_key, algorithm="HS256")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    cred_exc = HTTPException(status_code=401, detail="No autenticado")
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
        username = payload.get("sub")
    except JWTError:
        raise cred_exc
    if not username:
        raise cred_exc
    user = (
        await session.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()
    if user is None:
        raise cred_exc
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    username = form.username.strip().lower()
    user = (
        await session.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()
    if user is None or not user.password_hash or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Usuario o contraseña inválidos")
    return TokenResponse(access_token=create_jwt(username))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
```

Y agregar el endpoint de usuarios (mismo archivo o `app/api/users.py`; acá en `auth.py` por simplicidad, registrado bajo `/api/v1`):

```python
users_router = APIRouter(tags=["users"])


@users_router.get("/users", response_model=list[UserOut])
async def list_users(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[User]:
    return list((await session.execute(select(User).order_by(User.id))).scalars().all())
```

(En el Step 6, incluir también `users_router` en `app/api/router.py`.)

- [x] **Step 5: Crear `users.py`**

`backend/app/users.py`:
```python
import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import User

logger = logging.getLogger(__name__)


async def get_trip_users(session: AsyncSession) -> tuple[User, User]:
    users = (await session.execute(select(User).order_by(User.id))).scalars().all()
    if len(users) != 2:
        raise HTTPException(status_code=500, detail="El libro requiere exactamente 2 usuarios")
    return users[0], users[1]


async def seed_users_from_env(session: AsyncSession) -> None:
    from app.api.auth import hash_password

    raw = get_settings().auth_users
    if not raw:
        return
    for entry in raw.split(","):
        entry = entry.strip()
        if ":" not in entry:
            continue
        parts = entry.split(":", 2)
        username, password = parts[0].strip().lower(), parts[1].strip()
        wa_id = parts[2].strip() if len(parts) == 3 else None
        user = (
            await session.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if user is None:
            user = User(username=username, password_hash=hash_password(password))
            session.add(user)
        if wa_id and user.whatsapp_wa_id != wa_id:
            user.whatsapp_wa_id = wa_id
    await session.commit()
```

- [x] **Step 6: Cablear router + lifespan seed**

En `backend/app/api/router.py`, agregar:
```python
from app.api.auth import router as auth_router, users_router

router.include_router(auth_router)
router.include_router(users_router)
```

En `backend/app/main.py`, agregar lifespan (reemplazar la creación `app = FastAPI(...)`):
```python
from contextlib import asynccontextmanager

from app.categories.seed import seed_categories
from app.db.engine import get_sessionmaker
from app.users import seed_users_from_env


@asynccontextmanager
async def lifespan(app: FastAPI):
    maker = get_sessionmaker()
    async with maker() as session:
        await seed_categories(session)
        await session.commit()
        await seed_users_from_env(session)
    yield


app = FastAPI(title="Botardo Viaje", lifespan=lifespan)
```

- [x] **Step 7: Correr los tests**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: PASS (3 tests).

- [x] **Step 8: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/app/api/auth.py backend/app/api/schemas.py backend/app/users.py backend/app/api/router.py backend/app/main.py backend/tests/test_auth.py
git commit -m "feat(backend): auth JWT + seed de 2 usuarios del viaje"
```

---

### Task 3: CRUD de movimientos (con FX)

**Files:**
- Create: `backend/app/api/movements.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/test_movements_api.py`

**Interfaces:**
- Consumes: `MovementIn`/`MovementUpdate`/`MovementOut`, `get_current_user`, `app.fx.convert_to_usd`, `app.trip_time.today_in_tz` (default de `movement_date`; la tz real de la parada activa se cablea en Plan 4).
- Produces:
  - `POST /api/v1/movements` → crea; si no hay `fx_rate` override, llama `convert_to_usd`. `paid_by` default = usuario actual. `fx_source` mapeado con `_map_source(src, currency)`. → `MovementOut`.
  - `GET /api/v1/movements` → lista (orden `movement_date desc, id desc`).
  - `PATCH /api/v1/movements/{id}` → **parcial** (`MovementUpdate`, solo campos presentes en el body):
    - Si mandan `fx_rate` → `fx_source='manual'`, recalcula `amount_usd`.
    - Si cambia `amount`/`currency`/`movement_date` y **no** hay tasa manual vigente (`fx_source != 'manual'`) → recalcula FX. Con tasa manual, recalcula `amount_usd` con la tasa manual existente.
    - Editar solo `description`/`category`/`split`/etc. **no toca** FX (bug del diseño original: pisaba correcciones manuales).
  - `DELETE /api/v1/movements/{id}` → 204.

- [x] **Step 1: Escribir el test que falla**

`backend/tests/test_movements_api.py`:
```python
import httpx
import pytest

from app.api.auth import hash_password


async def _auth(app_client):
    from app.db.models import User
    async with app_client._maker() as s:
        s.add_all([User(username="bruno", password_hash=hash_password("pw")),
                   User(username="katia", password_hash=hash_password("pw"))])
        await s.commit()
    r = await app_client.post("/api/v1/auth/login", data={"username": "bruno", "password": "pw"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_create_usd_movement(app_client):
    h = await _auth(app_client)
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "30.00", "currency": "USD", "description": "taxi", "split": "shared",
        "movement_date": "2026-08-06",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["amount_usd"] == "30.00"
    assert body["fx_source"] == "frankfurter"  # USD -> direct -> mapea a frankfurter
    assert body["paid_by"] >= 1


async def test_manual_fx_override(app_client):
    h = await _auth(app_client)
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "100.00", "currency": "GBP", "fx_rate": "1.30", "movement_date": "2026-08-06",
    })
    assert r.status_code == 201
    assert r.json()["amount_usd"] == "130.00"
    assert r.json()["fx_source"] == "manual"


async def test_list_and_delete(app_client):
    h = await _auth(app_client)
    await app_client.post("/api/v1/movements", headers=h, json={"amount": "10", "currency": "USD", "movement_date": "2026-08-06"})
    lst = await app_client.get("/api/v1/movements", headers=h)
    assert len(lst.json()) == 1
    mid = lst.json()[0]["id"]
    d = await app_client.delete(f"/api/v1/movements/{mid}", headers=h)
    assert d.status_code == 204
    assert (await app_client.get("/api/v1/movements", headers=h)).json() == []


async def test_partial_patch_keeps_manual_fx(app_client):
    # Regresión del bug de diseño: editar la descripción NO debe pisar una tasa manual.
    h = await _auth(app_client)
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "100.00", "currency": "GBP", "fx_rate": "1.30", "movement_date": "2026-08-06",
    })
    mid = r.json()["id"]
    p = await app_client.patch(f"/api/v1/movements/{mid}", headers=h, json={"description": "cena rica"})
    assert p.status_code == 200
    body = p.json()
    assert body["description"] == "cena rica"
    assert body["fx_source"] == "manual"
    # Comparar como Decimal: la DB devuelve la tasa con scale 6 ("1.300000").
    assert Decimal(body["fx_rate"]) == Decimal("1.30")
    assert body["amount_usd"] == "130.00"
    # PATCH parcial sin amount no debe fallar por validación (MovementUpdate, no MovementIn).
    p2 = await app_client.patch(f"/api/v1/movements/{mid}", headers=h, json={"amount": "50.00"})
    assert p2.status_code == 200
    assert p2.json()["amount_usd"] == "65.00"  # recalcula con la tasa manual 1.30
```

- [x] **Step 2: Correr y verificar fallo**

Run: `cd backend && pytest tests/test_movements_api.py -v`
Expected: FAIL — import error de `app.api.movements`.

- [x] **Step 3: Implementar `movements.py`**

`backend/app/api/movements.py`:
```python
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.schemas import MovementIn, MovementOut, MovementUpdate
from app.db.engine import get_session
from app.db.models import Movement, User
from app.fx import convert_to_usd
from app.trip_time import today_in_tz

router = APIRouter(prefix="/movements", tags=["movements"])
_TWO = Decimal("0.01")


def _map_source(fx_source: str, currency: str) -> str:
    # FX devuelve frankfurter|dolarapi|cache|direct|fallback.
    if fx_source == "fallback":
        return "fallback"
    if currency.upper() == "ARS":
        return "dolarapi"
    return "frankfurter"


@router.post("", response_model=MovementOut, status_code=status.HTTP_201_CREATED)
async def create_movement(
    body: MovementIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Movement:
    # Plan 4 reemplaza el None por la timezone de la parada activa.
    mdate = body.movement_date or today_in_tz(None)
    if body.fx_rate is not None:
        rate = body.fx_rate
        amount_usd = (body.amount * rate).quantize(_TWO, rounding=ROUND_HALF_UP)
        fx_source = "manual"
    else:
        amount_usd, rate, src = await convert_to_usd(session, body.amount, body.currency, mdate)
        fx_source = _map_source(src, body.currency)
    mv = Movement(
        type=body.type,
        amount=body.amount,
        currency=body.currency.upper(),
        amount_usd=amount_usd,
        fx_rate=rate,
        fx_source=fx_source,
        paid_by=body.paid_by or user.id,
        split=body.split,
        description=body.description,
        category_id=body.category_id,
        stop_slug=body.stop_slug,
        city_name=body.city_name,
        movement_date=mdate,
        created_by=user.id,
    )
    session.add(mv)
    await session.commit()
    await session.refresh(mv)
    return mv


@router.get("", response_model=list[MovementOut])
async def list_movements(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Movement]:
    rows = (
        await session.execute(
            select(Movement).order_by(Movement.movement_date.desc(), Movement.id.desc())
        )
    ).scalars().all()
    return list(rows)


@router.patch("/{movement_id}", response_model=MovementOut)
async def update_movement(
    movement_id: int,
    body: MovementUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Movement:
    mv = (await session.execute(select(Movement).where(Movement.id == movement_id))).scalar_one_or_none()
    if mv is None:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    sent = body.model_fields_set  # solo lo que vino en el body
    for field in ("type", "split", "paid_by", "description", "category_id",
                  "stop_slug", "city_name", "movement_date"):
        if field in sent:
            setattr(mv, field, getattr(body, field))
    if "amount" in sent:
        mv.amount = body.amount
    if "currency" in sent:
        mv.currency = body.currency.upper()

    fx_inputs_changed = sent & {"amount", "currency", "movement_date"}
    if "fx_rate" in sent:
        # Override explícito -> manual.
        mv.fx_rate = body.fx_rate
        mv.fx_source = "manual"
        mv.amount_usd = (mv.amount * mv.fx_rate).quantize(_TWO, rounding=ROUND_HALF_UP)
    elif fx_inputs_changed:
        if mv.fx_source == "manual":
            # Respetar la tasa manual vigente; solo recalcular el monto.
            mv.amount_usd = (mv.amount * mv.fx_rate).quantize(_TWO, rounding=ROUND_HALF_UP)
        else:
            amount_usd, rate, src = await convert_to_usd(session, mv.amount, mv.currency, mv.movement_date)
            mv.amount_usd = amount_usd
            mv.fx_rate = rate
            mv.fx_source = _map_source(src, mv.currency)
    # Si no cambió nada relevante al FX, no se toca (no pisar correcciones).

    await session.commit()
    await session.refresh(mv)
    return mv


@router.delete("/{movement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_movement(
    movement_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    mv = (await session.execute(select(Movement).where(Movement.id == movement_id))).scalar_one_or_none()
    if mv is not None:
        await session.delete(mv)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [x] **Step 4: Registrar router**

En `backend/app/api/router.py`, agregar:
```python
from app.api.movements import router as movements_router

router.include_router(movements_router)
```

- [x] **Step 5: Correr los tests**

Run: `cd backend && pytest tests/test_movements_api.py -v`
Expected: PASS (4 tests).

- [x] **Step 6: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/app/api/movements.py backend/app/api/router.py backend/tests/test_movements_api.py
git commit -m "feat(backend): CRUD de movimientos con conversión FX"
```

---

### Task 4: Endpoint de balance (neto)

**Files:**
- Create: `backend/app/api/balance.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/test_balance_api.py`

**Interfaces:**
- Consumes: `app.balance.compute_balance`, `app.users.get_trip_users`, `Movement`, `get_current_user`.
- Produces: `GET /api/v1/balance` → `BalanceOut` (`amount_usd` string).

- [x] **Step 1: Escribir el test que falla**

`backend/tests/test_balance_api.py`:
```python
from app.api.auth import hash_password


async def test_balance_endpoint(app_client):
    from app.db.models import Movement, User
    async with app_client._maker() as s:
        u1 = User(username="bruno", password_hash=hash_password("pw"))
        u2 = User(username="katia", password_hash=hash_password("pw"))
        s.add_all([u1, u2])
        await s.flush()
        from decimal import Decimal
        from datetime import date
        s.add(Movement(type="expense", amount=Decimal("100"), currency="USD",
                       amount_usd=Decimal("100"), fx_rate=Decimal("1"), fx_source="frankfurter",
                       paid_by=u1.id, split="shared", movement_date=date(2026, 8, 6), created_by=u1.id))
        await s.commit()
    r = await app_client.post("/api/v1/auth/login", data={"username": "bruno", "password": "pw"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    b = await app_client.get("/api/v1/balance", headers=h)
    assert b.status_code == 200
    # katia (u2) le debe 50 a bruno (u1) — Decimal conserva el exponente ideal (100.00/2 = 50.00)
    body = b.json()
    assert body["amount_usd"] == "50.00"
```

- [x] **Step 2: Correr y verificar fallo**

Run: `cd backend && pytest tests/test_balance_api.py -v`
Expected: FAIL — import error `app.api.balance`.

- [x] **Step 3: Implementar `balance.py`**

`backend/app/api/balance.py`:
```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.schemas import BalanceOut
from app.balance import compute_balance
from app.db.engine import get_session
from app.db.models import Movement, User
from app.users import get_trip_users

router = APIRouter(tags=["balance"])


@router.get("/balance", response_model=BalanceOut)
async def get_balance(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BalanceOut:
    a, b = await get_trip_users(session)
    rows = (await session.execute(select(Movement))).scalars().all()
    bal = compute_balance(rows, a.id, b.id)
    return BalanceOut(
        debtor_id=bal.debtor_id,
        creditor_id=bal.creditor_id,
        amount_usd=str(bal.amount_usd),
    )
```

En `backend/app/api/router.py`:
```python
from app.api.balance import router as balance_router

router.include_router(balance_router)
```

- [x] **Step 4: Correr los tests**

Run: `cd backend && pytest tests/test_balance_api.py -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/app/api/balance.py backend/app/api/router.py backend/tests/test_balance_api.py
git commit -m "feat(backend): endpoint de balance (neto splitwise)"
```

---

### Task 5: Categorías + agregados del dashboard

**Files:**
- Create: `backend/app/api/categories.py`, `backend/app/api/dashboard.py`
- Modify: `backend/app/api/router.py`, `backend/app/api/schemas.py`
- Test: `backend/tests/test_dashboard_api.py`

**Interfaces:**
- Produces:
  - `GET /api/v1/categories` → `[{id,name,icon,sort_order}]` (orden `sort_order`).
  - `GET /api/v1/dashboard/summary` → `{"total_usd": str, "movement_count": int}` (solo `type='expense'`).
  - `GET /api/v1/dashboard/by-city` → `[{"stop_slug","city_name","total_usd"}]` desc por total.
  - `GET /api/v1/dashboard/by-category` → `[{"category_id","name","icon","total_usd"}]`.
  - `GET /api/v1/dashboard/timeseries` → `[{"date","cumulative_usd"}]` acumulado por fecha.
- Schemas nuevos: `CategoryOut`, `SummaryOut`, `CitySpendOut`, `CategorySpendOut`, `TimePointOut`.

- [x] **Step 1: Escribir el test que falla**

`backend/tests/test_dashboard_api.py`:
```python
from datetime import date
from decimal import Decimal

from app.api.auth import hash_password


async def _seed_and_auth(app_client):
    from app.db.models import Category, Movement, User
    async with app_client._maker() as s:
        u1 = User(username="bruno", password_hash=hash_password("pw"))
        u2 = User(username="katia", password_hash=hash_password("pw"))
        s.add_all([u1, u2])
        await s.flush()
        cat = (await s.execute(__import__("sqlalchemy").select(Category))).scalars().first()
        s.add_all([
            Movement(type="expense", amount=Decimal("50"), currency="USD", amount_usd=Decimal("50"),
                     fx_rate=Decimal("1"), fx_source="frankfurter", paid_by=u1.id, split="shared",
                     category_id=cat.id, stop_slug="londres", city_name="Londres",
                     movement_date=date(2026, 8, 6), created_by=u1.id),
            Movement(type="expense", amount=Decimal("30"), currency="USD", amount_usd=Decimal("30"),
                     fx_rate=Decimal("1"), fx_source="frankfurter", paid_by=u2.id, split="shared",
                     category_id=cat.id, stop_slug="paris", city_name="París",
                     movement_date=date(2026, 8, 30), created_by=u2.id),
        ])
        await s.commit()
    r = await app_client.post("/api/v1/auth/login", data={"username": "bruno", "password": "pw"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_categories_endpoint(app_client):
    h = await _seed_and_auth(app_client)
    r = await app_client.get("/api/v1/categories", headers=h)
    assert [c["name"] for c in r.json()][0] == "Alojamiento"


async def test_summary_and_by_city(app_client):
    h = await _seed_and_auth(app_client)
    summ = await app_client.get("/api/v1/dashboard/summary", headers=h)
    assert summ.json()["total_usd"] == "80.00"
    by_city = await app_client.get("/api/v1/dashboard/by-city", headers=h)
    cities = {c["city_name"]: c["total_usd"] for c in by_city.json()}
    assert cities["Londres"] == "50.00"
    assert cities["París"] == "30.00"


async def test_timeseries(app_client):
    h = await _seed_and_auth(app_client)
    ts = await app_client.get("/api/v1/dashboard/timeseries", headers=h)
    pts = ts.json()
    assert pts[-1]["cumulative_usd"] == "80.00"
```

- [x] **Step 2: Correr y verificar fallo**

Run: `cd backend && pytest tests/test_dashboard_api.py -v`
Expected: FAIL — import error.

- [x] **Step 3: Agregar schemas**

Agregar a `backend/app/api/schemas.py`:
```python
class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    icon: str | None
    sort_order: int


class SummaryOut(BaseModel):
    total_usd: str
    movement_count: int


class CitySpendOut(BaseModel):
    stop_slug: str | None
    city_name: str | None
    total_usd: str


class CategorySpendOut(BaseModel):
    category_id: int | None
    name: str | None
    icon: str | None
    total_usd: str


class TimePointOut(BaseModel):
    date: date
    cumulative_usd: str
```

- [x] **Step 4: Crear `categories.py`**

`backend/app/api/categories.py`:
```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.schemas import CategoryOut
from app.db.engine import get_session
from app.db.models import Category, User

router = APIRouter(tags=["categories"])


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Category]:
    return list(
        (await session.execute(select(Category).order_by(Category.sort_order))).scalars().all()
    )
```

- [x] **Step 5: Crear `dashboard.py`**

`backend/app/api/dashboard.py`:
```python
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.schemas import CategorySpendOut, CitySpendOut, SummaryOut, TimePointOut
from app.db.engine import get_session
from app.db.models import Category, Movement, User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
_EXPENSE = Movement.type == "expense"


@router.get("/summary", response_model=SummaryOut)
async def summary(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SummaryOut:
    total = (await session.execute(
        select(func.coalesce(func.sum(Movement.amount_usd), 0)).where(_EXPENSE)
    )).scalar_one()
    count = (await session.execute(
        select(func.count()).select_from(Movement).where(_EXPENSE)
    )).scalar_one()
    return SummaryOut(total_usd=str(Decimal(str(total)).normalize()), movement_count=count)


@router.get("/by-city", response_model=list[CitySpendOut])
async def by_city(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CitySpendOut]:
    rows = (await session.execute(
        select(Movement.stop_slug, Movement.city_name, func.sum(Movement.amount_usd))
        .where(_EXPENSE)
        .group_by(Movement.stop_slug, Movement.city_name)
        .order_by(func.sum(Movement.amount_usd).desc())
    )).all()
    return [CitySpendOut(stop_slug=s, city_name=c, total_usd=str(Decimal(str(t)).normalize())) for s, c, t in rows]


@router.get("/by-category", response_model=list[CategorySpendOut])
async def by_category(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CategorySpendOut]:
    rows = (await session.execute(
        select(Category.id, Category.name, Category.icon, func.sum(Movement.amount_usd))
        .join(Movement, Movement.category_id == Category.id)
        .where(_EXPENSE)
        .group_by(Category.id, Category.name, Category.icon)
        .order_by(func.sum(Movement.amount_usd).desc())
    )).all()
    return [CategorySpendOut(category_id=i, name=n, icon=ic, total_usd=str(Decimal(str(t)).normalize())) for i, n, ic, t in rows]


@router.get("/timeseries", response_model=list[TimePointOut])
async def timeseries(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[TimePointOut]:
    rows = (await session.execute(
        select(Movement.movement_date, func.sum(Movement.amount_usd))
        .where(_EXPENSE)
        .group_by(Movement.movement_date)
        .order_by(Movement.movement_date)
    )).all()
    out: list[TimePointOut] = []
    cum = Decimal("0")
    for d, t in rows:
        cum += Decimal(str(t))
        out.append(TimePointOut(date=d, cumulative_usd=str(cum.normalize())))
    return out
```

En `backend/app/api/router.py`:
```python
from app.api.categories import router as categories_router
from app.api.dashboard import router as dashboard_router

router.include_router(categories_router)
router.include_router(dashboard_router)
```

- [x] **Step 6: Correr toda la suite**

Run: `cd backend && pytest -v`
Expected: PASS (todos los tests de Plans 1 y 2).

Nota: los montos del dashboard se formatean con `def _money(v) -> str: return f"{Decimal(str(v)):.2f}"` (evita el `"8E+1"` de `.normalize()`); los asserts usan `"80.00"`, `"50.00"`, `"30.00"`.

- [x] **Step 7: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/app/api/categories.py backend/app/api/dashboard.py backend/app/api/router.py backend/app/api/schemas.py backend/tests/test_dashboard_api.py
git commit -m "feat(backend): categorías + agregados del dashboard (total/ciudad/categoría/timeseries)"
```

---

## Self-review (Plan 2)

- **Cobertura de spec:** §9 dashboard (summary/by-city/by-category/timeseries) → Task 5. §5 balance → Task 4. §4 movements CRUD (PATCH parcial que respeta tasas manuales) → Task 3. Auth/login (web) + `GET /users` (nombres para Plan 5) → Task 2. App/CORS/health → Task 1. FX se integra en Task 3 mapeando `_map_source(src, currency)`→`fx_source` (incluye `dolarapi` para ARS).
- **Placeholders:** ninguno. La nota de formato de dinero en Task 5/Step 6 da una alternativa concreta (no es placeholder).
- **Consistencia de tipos:** `MovementIn` (POST, campos obligatorios) vs `MovementUpdate` (PATCH, todo opcional + `model_fields_set`) — nunca compartir el schema. `compute_balance` (Plan 1) consumido en Task 4 con `Movement` real. `convert_to_usd` y `today_in_tz` (Plan 1) consumidos en Task 3. `get_current_user`/`get_trip_users` consistentes.
- **Deuda para Plan 3/4:** `stop_slug`/`city_name` hoy los manda el cliente; `today_in_tz(None)` usa Europe/Madrid — en Plan 4 el bot/deriva-de-Andiamo completa parada activa y su timezone.
