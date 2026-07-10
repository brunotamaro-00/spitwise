# Botardo Viaje — Plan 1: Fundamentos del backend

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Levantar el esqueleto del backend de Botardo (repo nuevo) con la persistencia, el catálogo de categorías, la conversión de moneda a USD y el cálculo del neto splitwise — todo unit-testeable con `pytest`, sin HTTP ni bot ni frontend todavía.

**Architecture:** FastAPI + SQLAlchemy 2.0 async (asyncpg contra Railway Postgres en prod, aiosqlite en tests) + Alembic. Un solo libro compartido: los movimientos referencian `paid_by` entre 2 usuarios. FX vía Frankfurter (ECB) con cache en Postgres, **dólar MEP (dolarapi.com) para ARS**, y fallback estático. El neto se computa on-the-fly con una función pura. Las fechas "hoy" se derivan de una timezone del viaje (`app/trip_time.py`), nunca del UTC del servidor.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy[asyncio] 2.0, asyncpg, alembic, httpx, pydantic-settings, anthropic (SDK, se usa en Plan 3), pytest + pytest-asyncio + aiosqlite.

## Global Constraints

- Python `>=3.11`. SQLAlchemy `>=2.0` estilo async (`AsyncSession`, `Mapped`/`mapped_column`).
- **Sin Redis, sin embeddings, sin llamadas LLM en este plan.** No portar `scheduled_expenses`, `recurring_movements`, `user_category_examples`, `merchant_aliases`, **ni `bot_pending_confirmations`** (con `bot_pending_actions` alcanza).
- Moneda base del neto = **USD** (constante). Montos como `Decimal` (`Numeric(12,2)`; FX `Numeric(14,6)`).
- Enum `split`: exactamente `shared` | `payer_only` | `other_only`. Enum `type` de movimiento: `expense` | `settlement`. Guardados como `String`, no como tipos enum nativos de PG (portabilidad sqlite).
- Valores de `fx_source`: `frankfurter` | `dolarapi` | `manual` | `fallback`.
- Categorías: exactamente 7 fijas — `Alojamiento`, `Comida`, `Transporte`, `Actividades`, `Compras`, `Bebidas/Salidas`, `Otros`.
- Tests deben correr sobre sqlite (aiosqlite) sin Postgres. Nada específico de PG (no `JSONB`, no `server_default` que sqlite no soporte de forma incompatible).
- Deploy = Railway (proceso siempre vivo): pool normal de SQLAlchemy, sin hacks serverless.
- Fechas: nunca `date.today()` pelado en lógica de negocio — usar `app.trip_time.today_in_tz()` (Task 6).

**Referencia de reutilización:** el repo `~/Desktop/Expenses/backend` tiene los patrones originales (`app/config.py`, `app/db/engine.py`, `app/db/models.py`, `app/services/exchange_rate.py`). Se adaptan, no se copian tal cual.

---

## Estructura de archivos (Plan 1)

- Create: `backend/pyproject.toml` — deps + config de pytest/ruff.
- Create: `backend/.gitignore`, `backend/.env.example`.
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py` — `Settings` (pydantic-settings).
- Create: `backend/app/db/__init__.py`, `backend/app/db/engine.py` — engine async + `async_session`.
- Create: `backend/app/db/models.py` — todas las tablas del esquema (sección 4 del spec).
- Create: `backend/app/categories/__init__.py`, `backend/app/categories/catalog.py`, `backend/app/categories/seed.py`.
- Create: `backend/app/fx.py` — conversión a USD (Frankfurter + dolarapi MEP para ARS + cache + fallback).
- Create: `backend/app/balance.py` — cálculo del neto (función pura).
- Create: `backend/app/trip_time.py` — "hoy" en una timezone dada (fallback Europe/Madrid).
- Create: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/alembic/versions/0001_initial.py`.
- Create (tests): `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_models.py`, `backend/tests/test_categories_seed.py`, `backend/tests/test_fx.py`, `backend/tests/test_balance.py`, `backend/tests/test_trip_time.py`.

---

### Task 1: Scaffold del repo backend

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.gitignore`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Test: `backend/tests/__init__.py`, `backend/tests/test_config_smoke.py`

**Interfaces:**
- Produces: `app.config.Settings` con atributos `database_url: str`, `frankfurter_url: str`, `fx_fallback_rates: dict[str, str]`, `environment: str`. `app.config.get_settings() -> Settings` (cacheada con `functools.lru_cache`).

- [ ] **Step 1: Escribir el test que falla**

`backend/tests/test_config_smoke.py`:
```python
from app.config import get_settings


def test_settings_defaults():
    s = get_settings()
    assert s.frankfurter_url.startswith("https://")
    # Fallback USD siempre presente y = 1.
    assert s.fx_fallback_rates["USD"] == "1.0"
    assert "GBP" in s.fx_fallback_rates
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd backend && pytest tests/test_config_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.config'` (o import error).

- [ ] **Step 3: Crear `pyproject.toml`**

`backend/pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "botardo-api"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "httpx>=0.27",
    "pydantic",
    "pydantic-settings>=2.6",
    "python-dotenv>=1.0",
    "python-jose[cryptography]>=3.3",
    "python-multipart>=0.0.9",
    "bcrypt>=4.0",
    "anthropic>=0.69",
]

[project.optional-dependencies]
dev = [
    "aiosqlite>=0.20",
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-mock>=3.12",
    "ruff",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"

[tool.setuptools.packages.find]
where = ["."]
include = ["app*"]

[tool.ruff]
line-length = 100
```

- [ ] **Step 4: Crear `.gitignore` y `.env.example`**

`backend/.gitignore`:
```
.venv/
__pycache__/
*.pyc
.env
.pytest_cache/
*.egg-info/
```

`backend/.env.example`:
```
# DB (Railway Postgres en prod; local docker en dev)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/botardo
# FX
FRANKFURTER_URL=https://api.frankfurter.dev/v1
DOLARAPI_URL=https://dolarapi.com/v1
ENVIRONMENT=dev
```

- [ ] **Step 5: Crear `app/__init__.py` (vacío) y `app/config.py`**

`backend/app/__init__.py`: (archivo vacío)

`backend/app/config.py`:
```python
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Tasas fallback aproximadas currency -> USD (se usan solo si Frankfurter falla).
# Valores de referencia; se corrigen a mano en el dashboard cuando aplique.
_FX_FALLBACK: dict[str, str] = {
    "USD": "1.0",
    "EUR": "1.08",
    "GBP": "1.27",
    "CHF": "1.12",
    "CZK": "0.043",
    "PLN": "0.25",
    "HUF": "0.0027",
    "ARS": "0.0011",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/botardo"
    frankfurter_url: str = Field(default="https://api.frankfurter.dev/v1", alias="FRANKFURTER_URL")
    dolarapi_url: str = Field(default="https://dolarapi.com/v1", alias="DOLARAPI_URL")
    environment: str = "dev"
    trip_default_timezone: str = "Europe/Madrid"

    # No es env: se expone como propiedad para tests/servicios.
    @property
    def fx_fallback_rates(self) -> dict[str, str]:
        return dict(_FX_FALLBACK)


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 6: Crear `tests/__init__.py` y correr el test**

`backend/tests/__init__.py`: (archivo vacío)

Run: `cd backend && pip install -e ".[dev]" && pytest tests/test_config_smoke.py -v`
Expected: PASS (2 asserts).

- [ ] **Step 7: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/pyproject.toml backend/.gitignore backend/.env.example backend/app backend/tests
git commit -m "feat(backend): scaffold repo + Settings"
```

---

### Task 2: Engine async + modelos + migración inicial

**Files:**
- Create: `backend/app/db/__init__.py`, `backend/app/db/engine.py`
- Create: `backend/app/db/models.py`
- Create: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/alembic/versions/0001_initial.py`
- Test: `backend/tests/conftest.py`, `backend/tests/test_models.py`

**Interfaces:**
- Produces:
  - `app.db.engine.make_engine(url: str)`, `app.db.engine.async_session_factory(engine)`, `app.db.engine.get_engine()`, `app.db.engine.get_sessionmaker()`.
  - `app.db.models.Base` (DeclarativeBase) y modelos: `User`, `Category`, `Movement`, `Stop`, `FxRate`, `WhatsAppDedupe`, `BotPendingAction`, `WhatsAppSessionState`.
  - `Movement` campos: `id, type, amount, currency, amount_usd, fx_rate, fx_source, paid_by(FK users.id), split, description, category_id(FK categories.id), stop_slug, city_name, movement_date, raw_message, created_by(FK users.id), created_at, updated_at`.
  - Test fixture `db_session` (AsyncSession sobre sqlite en memoria con tablas creadas por `Base.metadata.create_all`).

- [ ] **Step 1: Escribir el test que falla**

`backend/tests/conftest.py`:
```python
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()
```

`backend/tests/test_models.py`:
```python
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.db.models import Category, Movement, User


async def test_insert_movement_roundtrip(db_session):
    u1 = User(username="bruno")
    u2 = User(username="novia")
    cat = Category(name="Comida", icon="🍽️")
    db_session.add_all([u1, u2, cat])
    await db_session.flush()

    mv = Movement(
        type="expense",
        amount=Decimal("45.00"),
        currency="GBP",
        amount_usd=Decimal("57.15"),
        fx_rate=Decimal("1.27"),
        fx_source="frankfurter",
        paid_by=u1.id,
        split="shared",
        description="cena",
        category_id=cat.id,
        stop_slug="londres",
        city_name="Londres",
        movement_date=date(2026, 8, 6),
        created_by=u1.id,
    )
    db_session.add(mv)
    await db_session.flush()

    got = (await db_session.execute(select(Movement))).scalar_one()
    assert got.amount_usd == Decimal("57.15")
    assert got.split == "shared"
    assert got.stop_slug == "londres"
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd backend && pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.db.models'`.

- [ ] **Step 3: Crear engine**

`backend/app/db/__init__.py`: (vacío)

`backend/app/db/engine.py`:
```python
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.config import get_settings


def make_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True)


def async_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


@lru_cache
def get_engine() -> AsyncEngine:
    return make_engine(get_settings().database_url)


@lru_cache
def get_sessionmaker() -> async_sessionmaker:
    return async_session_factory(get_engine())
```

- [ ] **Step 4: Crear modelos**

`backend/app/db/models.py`:
```python
from datetime import date, datetime
from decimal import Decimal
import secrets

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    whatsapp_wa_id: Mapped[str | None] = mapped_column(String(50), unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    icon: Mapped[str | None] = mapped_column(String(10))
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Movement(Base):
    __tablename__ = "movements"
    __table_args__ = (
        Index("ix_movements_date", "movement_date"),
        Index("ix_movements_stop_slug", "stop_slug"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # expense (default) | settlement
    type: Mapped[str] = mapped_column(String(12), server_default=text("'expense'"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), server_default=text("'USD'"))
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fx_rate: Mapped[Decimal] = mapped_column(Numeric(14, 6), server_default=text("'1.0'"))
    # frankfurter | manual | fallback
    fx_source: Mapped[str] = mapped_column(String(16), server_default=text("'manual'"))
    paid_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # shared | payer_only | other_only  (ignorado para settlement)
    split: Mapped[str] = mapped_column(String(12), server_default=text("'shared'"))
    description: Mapped[str | None] = mapped_column(String(255))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    stop_slug: Mapped[str | None] = mapped_column(String(80))
    city_name: Mapped[str | None] = mapped_column(String(120))
    movement_date: Mapped[date] = mapped_column(Date, nullable=False)
    raw_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    category: Mapped["Category | None"] = relationship()


class Stop(Base):
    """Snapshot local del itinerario (fuente de verdad = Andiamo)."""

    __tablename__ = "stops"

    slug: Mapped[str] = mapped_column(String(80), primary_key=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str | None] = mapped_column(String(80))
    country_flag: Mapped[str | None] = mapped_column(String(16))
    arrival_date: Mapped[date | None] = mapped_column(Date)
    departure_date: Mapped[date | None] = mapped_column(Date)
    currency_code: Mapped[str | None] = mapped_column(String(3))
    timezone: Mapped[str | None] = mapped_column(String(64))
    is_transit: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    is_candidate: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    is_flex_margin: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    synced_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class FxRate(Base):
    __tablename__ = "fx_rates"
    __table_args__ = (UniqueConstraint("currency", "rate_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    rate_to_usd: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(server_default=func.now())


class WhatsAppDedupe(Base):
    __tablename__ = "whatsapp_dedupe"

    wamid: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)


class BotPendingAction(Base):
    __tablename__ = "bot_pending_actions"
    __table_args__ = (UniqueConstraint("channel", "external_message_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, default=lambda: secrets.token_urlsafe(24)
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    owner: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    external_message_id: Mapped[str | None] = mapped_column(String(128))
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    processing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class WhatsAppSessionState(Base):
    __tablename__ = "whatsapp_session_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    wa_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    owner: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'{}'"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 5: Correr el test de modelos**

Run: `cd backend && pytest tests/test_models.py -v`
Expected: PASS.

- [ ] **Step 6: Inicializar Alembic y escribir la migración inicial**

Crear `backend/alembic.ini` (mínimo):
```ini
[alembic]
script_location = alembic
sqlalchemy.url = driver://user:pass@localhost/dbname

[loggers]
keys = root

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

Crear `backend/alembic/script.py.mako`:
```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

Crear `backend/alembic/env.py`:
```python
import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.config import get_settings
from app.db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

Generar la migración autogenerada contra una DB Postgres local:
Run: `cd backend && docker run -d --name botardo-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16 && sleep 5 && DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/postgres alembic revision --autogenerate -m "initial" `
Renombrar el archivo generado en `alembic/versions/` a `0001_initial.py` y fijar `revision = "0001"`, `down_revision = None`.

- [ ] **Step 7: Verificar que la migración aplica**

Run: `cd backend && DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/postgres alembic upgrade head && echo MIGRATION_OK`
Expected: imprime `MIGRATION_OK` sin error.
Cleanup: `docker rm -f botardo-pg`

- [ ] **Step 8: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/app/db backend/alembic.ini backend/alembic backend/tests
git commit -m "feat(backend): esquema async + migración inicial"
```

---

### Task 3: Catálogo y seed de categorías

**Files:**
- Create: `backend/app/categories/__init__.py`, `backend/app/categories/catalog.py`, `backend/app/categories/seed.py`
- Test: `backend/tests/test_categories_seed.py`

**Interfaces:**
- Consumes: `app.db.models.Category`, fixture `db_session`.
- Produces:
  - `app.categories.catalog.CATEGORIES: list[tuple[str, str]]` — 7 `(name, icon)` en orden.
  - `app.categories.seed.seed_categories(session) -> None` — idempotente (upsert por `name`, setea `sort_order`).

- [ ] **Step 1: Escribir el test que falla**

`backend/tests/test_categories_seed.py`:
```python
from sqlalchemy import select

from app.categories.catalog import CATEGORIES
from app.categories.seed import seed_categories
from app.db.models import Category


def test_catalog_has_seven():
    names = [c[0] for c in CATEGORIES]
    assert names == [
        "Alojamiento",
        "Comida",
        "Transporte",
        "Actividades",
        "Compras",
        "Bebidas/Salidas",
        "Otros",
    ]


async def test_seed_is_idempotent(db_session):
    await seed_categories(db_session)
    await seed_categories(db_session)
    rows = (await db_session.execute(select(Category).order_by(Category.sort_order))).scalars().all()
    assert len(rows) == 7
    assert rows[0].name == "Alojamiento"
    assert rows[0].sort_order == 0
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd backend && pytest tests/test_categories_seed.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.categories.catalog'`.

- [ ] **Step 3: Crear catálogo**

`backend/app/categories/__init__.py`: (vacío)

`backend/app/categories/catalog.py`:
```python
# 7 categorías fijas del viaje (orden estable = sort_order).
CATEGORIES: list[tuple[str, str]] = [
    ("Alojamiento", "🏨"),
    ("Comida", "🍽️"),
    ("Transporte", "🚆"),
    ("Actividades", "🎟️"),
    ("Compras", "🛍️"),
    ("Bebidas/Salidas", "🍷"),
    ("Otros", "📦"),
]
```

- [ ] **Step 4: Crear seed idempotente**

`backend/app/categories/seed.py`:
```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.categories.catalog import CATEGORIES
from app.db.models import Category


async def seed_categories(session: AsyncSession) -> None:
    existing = {
        c.name: c
        for c in (await session.execute(select(Category))).scalars().all()
    }
    for order, (name, icon) in enumerate(CATEGORIES):
        cat = existing.get(name)
        if cat is None:
            session.add(Category(name=name, icon=icon, sort_order=order))
        else:
            cat.icon = icon
            cat.sort_order = order
    await session.flush()
```

- [ ] **Step 5: Correr los tests**

Run: `cd backend && pytest tests/test_categories_seed.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/app/categories backend/tests/test_categories_seed.py
git commit -m "feat(backend): catálogo y seed de 7 categorías del viaje"
```

---

### Task 4: Conversión de moneda a USD (FX)

**Files:**
- Create: `backend/app/fx.py`
- Test: `backend/tests/test_fx.py`

**Interfaces:**
- Consumes: `app.db.models.FxRate`, `app.config.get_settings`, fixture `db_session`.
- Produces:
  - `async app.fx.get_rate_to_usd(session, currency: str, on_date: date, *, client: httpx.AsyncClient | None = None) -> tuple[Decimal, str]` → `(rate, source)` con `source ∈ {"frankfurter","dolarapi","fallback","cache","direct"}`. Para `USD` devuelve `(Decimal("1"), "direct")`. Para `ARS` (Frankfurter no lo soporta) usa dolarapi MEP: `GET {dolarapi_url}/dolares/bolsa` → `rate = 1 / venta` (cuantizado a 6 decimales), `source="dolarapi"`.
  - `async app.fx.convert_to_usd(session, amount: Decimal, currency: str, on_date: date, *, client=None) -> tuple[Decimal, Decimal, str]` → `(amount_usd, rate, source)`. `amount_usd` redondeado a 2 decimales.

- [ ] **Step 1: Escribir el test que falla**

`backend/tests/test_fx.py`:
```python
from datetime import date
from decimal import Decimal

import httpx
import pytest

from app.db.models import FxRate
from app.fx import convert_to_usd, get_rate_to_usd


def _mock_client(rate: float | None):
    def handler(request: httpx.Request) -> httpx.Response:
        if rate is None:
            return httpx.Response(500)
        return httpx.Response(200, json={"rates": {"USD": rate}})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_usd_is_identity(db_session):
    rate, source = await get_rate_to_usd(db_session, "USD", date(2026, 8, 6))
    assert rate == Decimal("1")
    assert source == "direct"


async def test_frankfurter_hit_and_cache(db_session):
    async with _mock_client(1.27) as client:
        rate, source = await get_rate_to_usd(db_session, "GBP", date(2026, 8, 6), client=client)
    assert rate == Decimal("1.27")
    assert source == "frankfurter"
    # Segunda llamada: viene de cache (sin cliente => no red).
    rate2, source2 = await get_rate_to_usd(db_session, "GBP", date(2026, 8, 6))
    assert rate2 == Decimal("1.27")
    assert source2 == "cache"


async def test_fallback_on_api_error(db_session):
    async with _mock_client(None) as client:
        rate, source = await get_rate_to_usd(db_session, "EUR", date(2026, 8, 6), client=client)
    assert source == "fallback"
    assert rate == Decimal("1.08")


def _mock_mep_client(venta: float | None):
    def handler(request: httpx.Request) -> httpx.Response:
        if venta is None:
            return httpx.Response(500)
        assert "dolares/bolsa" in str(request.url)
        return httpx.Response(200, json={
            "moneda": "USD", "casa": "bolsa", "compra": venta - 20, "venta": venta,
        })

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_ars_uses_dolarapi_mep(db_session):
    # ARS no está en Frankfurter: va directo a dolarapi (MEP) -> 1/venta.
    async with _mock_mep_client(1600.0) as client:
        rate, source = await get_rate_to_usd(db_session, "ARS", date(2026, 8, 6), client=client)
    assert source == "dolarapi"
    assert rate == Decimal("0.000625")  # 1/1600
    # Segunda llamada: cache.
    rate2, source2 = await get_rate_to_usd(db_session, "ARS", date(2026, 8, 6))
    assert (rate2, source2) == (Decimal("0.000625"), "cache")


async def test_ars_fallback_on_dolarapi_error(db_session):
    async with _mock_mep_client(None) as client:
        rate, source = await get_rate_to_usd(db_session, "ARS", date(2026, 8, 6), client=client)
    assert source == "fallback"


async def test_convert_rounds_to_2dp(db_session):
    async with _mock_client(1.27) as client:
        amount_usd, rate, source = await convert_to_usd(
            db_session, Decimal("45.00"), "GBP", date(2026, 8, 6), client=client
        )
    assert amount_usd == Decimal("57.15")
    assert rate == Decimal("1.27")
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd backend && pytest tests/test_fx.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.fx'`.

- [ ] **Step 3: Implementar `app/fx.py`**

`backend/app/fx.py`:
```python
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import FxRate

_TWO = Decimal("0.01")


async def _cached_rate(session: AsyncSession, currency: str, on_date: date) -> Decimal | None:
    row = (
        await session.execute(
            select(FxRate).where(FxRate.currency == currency, FxRate.rate_date == on_date)
        )
    ).scalar_one_or_none()
    return row.rate_to_usd if row else None


async def _store_rate(session: AsyncSession, currency: str, on_date: date, rate: Decimal) -> None:
    session.add(FxRate(currency=currency, rate_date=on_date, rate_to_usd=rate))
    await session.flush()


def _fallback_rate(currency: str) -> Decimal:
    rates = get_settings().fx_fallback_rates
    return Decimal(rates.get(currency, "1.0"))


async def get_rate_to_usd(
    session: AsyncSession,
    currency: str,
    on_date: date,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[Decimal, str]:
    currency = currency.upper()
    if currency == "USD":
        return Decimal("1"), "direct"

    cached = await _cached_rate(session, currency, on_date)
    if cached is not None:
        return cached, "cache"

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=10.0)
    try:
        if currency == "ARS":
            # Frankfurter (ECB) no publica ARS: usamos dólar MEP (dolarapi).
            resp = await client.get(f"{get_settings().dolarapi_url}/dolares/bolsa")
            resp.raise_for_status()
            venta = Decimal(str(resp.json()["venta"]))
            rate = (Decimal("1") / venta).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            source = "dolarapi"
        else:
            url = f"{get_settings().frankfurter_url}/{on_date.isoformat()}"
            resp = await client.get(url, params={"base": currency, "symbols": "USD"})
            resp.raise_for_status()
            rate = Decimal(str(resp.json()["rates"]["USD"]))
            source = "frankfurter"
        await _store_rate(session, currency, on_date, rate)
        return rate, source
    except Exception:
        return _fallback_rate(currency), "fallback"
    finally:
        if owns_client:
            await client.aclose()


async def convert_to_usd(
    session: AsyncSession,
    amount: Decimal,
    currency: str,
    on_date: date,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[Decimal, Decimal, str]:
    rate, source = await get_rate_to_usd(session, currency, on_date, client=client)
    amount_usd = (amount * rate).quantize(_TWO, rounding=ROUND_HALF_UP)
    return amount_usd, rate, source
```

- [ ] **Step 4: Correr los tests de FX**

Run: `cd backend && pytest tests/test_fx.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/app/fx.py backend/tests/test_fx.py
git commit -m "feat(backend): conversión a USD vía Frankfurter con cache y fallback"
```

---

### Task 5: Cálculo del neto splitwise

**Files:**
- Create: `backend/app/balance.py`
- Test: `backend/tests/test_balance.py`

**Interfaces:**
- Consumes: nada de DB (función pura sobre objetos con atributos `type, split, paid_by, amount_usd`).
- Produces:
  - `@dataclass app.balance.MovementLike` con `type: str`, `split: str`, `paid_by: int`, `amount_usd: Decimal` (para tipar/testear; en runtime sirve cualquier objeto con esos atributos).
  - `@dataclass app.balance.Balance` con `debtor_id: int | None`, `creditor_id: int | None`, `amount_usd: Decimal` (amount siempre ≥ 0; si 0 → ambos ids None).
  - `app.balance.compute_balance(movements, user_a: int, user_b: int) -> Balance`.
  - Semántica (todo en USD):
    - `expense`+`shared`: el que NO pagó le debe al que pagó `amount_usd / 2`.
    - `expense`+`other_only`: el que NO pagó le debe al que pagó `amount_usd`.
    - `expense`+`payer_only`: no mueve el neto.
    - `settlement`: `paid_by` le paga al otro → reduce lo que `paid_by` le debe (o le genera crédito) por `amount_usd`.

- [ ] **Step 1: Escribir el test que falla**

`backend/tests/test_balance.py`:
```python
from decimal import Decimal

from app.balance import Balance, MovementLike, compute_balance

A, B = 1, 2


def mv(type_, split, paid_by, amount):
    return MovementLike(type=type_, split=split, paid_by=paid_by, amount_usd=Decimal(amount))


def test_no_movements_is_settled():
    bal = compute_balance([], A, B)
    assert bal == Balance(debtor_id=None, creditor_id=None, amount_usd=Decimal("0"))


def test_shared_expense_paid_by_a():
    # A paga 100 compartido -> B le debe 50 a A.
    bal = compute_balance([mv("expense", "shared", A, "100")], A, B)
    assert bal.debtor_id == B
    assert bal.creditor_id == A
    assert bal.amount_usd == Decimal("50")


def test_other_only_paid_by_a():
    # A paga 80 pero es todo de B -> B le debe 80 a A.
    bal = compute_balance([mv("expense", "other_only", A, "80")], A, B)
    assert (bal.debtor_id, bal.creditor_id, bal.amount_usd) == (B, A, Decimal("80"))


def test_payer_only_moves_nothing():
    bal = compute_balance([mv("expense", "payer_only", A, "80")], A, B)
    assert bal.amount_usd == Decimal("0")


def test_settlement_reduces_debt():
    # B le debe 50 a A; luego B le paga 50 a A -> saldados.
    movements = [
        mv("expense", "shared", A, "100"),   # B debe 50 a A
        mv("settlement", "shared", B, "50"),  # B paga 50 a A
    ]
    bal = compute_balance(movements, A, B)
    assert bal.amount_usd == Decimal("0")


def test_mixed_nets_out():
    movements = [
        mv("expense", "shared", A, "100"),    # B debe 50 a A
        mv("expense", "shared", B, "40"),     # A debe 20 a B
        mv("expense", "other_only", A, "10"),  # B debe 10 a A
    ]
    # Neto: B debe 50 - 20 + 10 = 40 a A
    bal = compute_balance(movements, A, B)
    assert (bal.debtor_id, bal.creditor_id, bal.amount_usd) == (B, A, Decimal("40"))
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd backend && pytest tests/test_balance.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.balance'`.

- [ ] **Step 3: Implementar `app/balance.py`**

`backend/app/balance.py`:
```python
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class MovementLike:
    type: str
    split: str
    paid_by: int
    amount_usd: Decimal


@dataclass
class Balance:
    debtor_id: int | None
    creditor_id: int | None
    amount_usd: Decimal


def compute_balance(movements, user_a: int, user_b: int) -> Balance:
    """Neto en USD entre dos usuarios.

    `net` positivo => user_a le debe a user_b; negativo => user_b le debe a user_a.
    """
    net = Decimal("0")
    for m in movements:
        payer = m.paid_by
        amt = m.amount_usd
        if m.type == "settlement":
            # payer le paga al otro => reduce lo que payer debe.
            if payer == user_a:
                net -= amt
            else:
                net += amt
            continue
        if m.split == "payer_only":
            continue
        share = amt if m.split == "other_only" else amt / Decimal("2")
        # El que NO pagó le debe `share` al que pagó.
        if payer == user_a:
            # user_b le debe a user_a => net (a debe a b) baja.
            net -= share
        else:
            net += share

    if net > 0:
        return Balance(debtor_id=user_a, creditor_id=user_b, amount_usd=net)
    if net < 0:
        return Balance(debtor_id=user_b, creditor_id=user_a, amount_usd=-net)
    return Balance(debtor_id=None, creditor_id=None, amount_usd=Decimal("0"))
```

- [ ] **Step 4: Correr los tests de balance**

Run: `cd backend && pytest tests/test_balance.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Correr toda la suite**

Run: `cd backend && pytest -v`
Expected: PASS (todos los tests de los 5 tasks).

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/app/balance.py backend/tests/test_balance.py
git commit -m "feat(backend): cálculo del neto splitwise en USD"
```

---

### Task 6: Fecha del viaje por timezone (`trip_time`)

**Files:**
- Create: `backend/app/trip_time.py`
- Test: `backend/tests/test_trip_time.py`

**Interfaces:**
- Produces: `app.trip_time.today_in_tz(tz_name: str | None, *, now: datetime | None = None) -> date` — "hoy" en la timezone dada (`zoneinfo`); si `tz_name` es `None` o inválida, usa `get_settings().trip_default_timezone` (Europe/Madrid). `now` (aware, UTC) es inyectable para tests. **Motivo:** con `date.today()` (UTC del servidor) un gasto cargado a las 00:30 en Praga cae en el día anterior y puede resolver mal la parada activa/moneda.
- Consumers futuros: Plan 2 (default de `movement_date`), Plan 3 (dispatcher/webhook), Plan 4 (la timezone real viene de la parada activa sincronizada de Andiamo).

- [ ] **Step 1: Escribir el test que falla**

`backend/tests/test_trip_time.py`:
```python
from datetime import datetime, timezone

from app.trip_time import today_in_tz

# 2026-08-05 23:30 UTC == 2026-08-06 01:30 en Madrid (CEST, UTC+2)
_NOW = datetime(2026, 8, 5, 23, 30, tzinfo=timezone.utc)


def test_today_crosses_midnight_in_local_tz():
    assert today_in_tz("Europe/Madrid", now=_NOW).isoformat() == "2026-08-06"
    # Londres (UTC+1 en agosto) sigue en el día 5.
    assert today_in_tz("Europe/London", now=_NOW).isoformat() == "2026-08-05"


def test_invalid_or_missing_tz_falls_back_to_default():
    assert today_in_tz(None, now=_NOW).isoformat() == "2026-08-06"      # Madrid
    assert today_in_tz("No/Existe", now=_NOW).isoformat() == "2026-08-06"
```

- [ ] **Step 2: Correr y verificar fallo**

Run: `cd backend && pytest tests/test_trip_time.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.trip_time'`.

- [ ] **Step 3: Implementar `trip_time.py`**

`backend/app/trip_time.py`:
```python
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import get_settings


def today_in_tz(tz_name: str | None, *, now: datetime | None = None) -> date:
    """'Hoy' en la timezone del viaje. Nunca usar date.today() (UTC del server)."""
    if now is None:
        now = datetime.now(timezone.utc)
    name = tz_name or get_settings().trip_default_timezone
    try:
        tz = ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        tz = ZoneInfo(get_settings().trip_default_timezone)
    return now.astimezone(tz).date()
```

- [ ] **Step 4: Correr los tests y toda la suite**

Run: `cd backend && pytest tests/test_trip_time.py -v && pytest -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add backend/app/trip_time.py backend/tests/test_trip_time.py
git commit -m "feat(backend): fecha del viaje por timezone (fallback Europe/Madrid)"
```

---

## Self-review (Plan 1)

- **Cobertura de spec (secciones aplicables):** §4 modelo de datos → Task 2 (todas las tablas: movements, users, categories, stops [con `timezone`], fx_rates, whatsapp_dedupe, bot_pending_actions, session states). §5 neto → Task 5. §8 FX (incl. ARS/MEP) → Task 4. Categorías (§3/§4) → Task 3. Timezone (§3) → Task 6. Scaffold → Task 1. Bot/HTTP/frontend/Andiamo quedan para plans posteriores (por diseño).
- **Placeholders:** ninguno; todo el código está completo.
- **Consistencia de tipos:** `Movement.split`/`type`/`fx_source` valores string consistentes entre modelo (Task 2), FX (`source` producido por Task 4: `frankfurter|dolarapi|fallback|cache|direct`) y balance (Task 5 consume `type`/`split`/`paid_by`/`amount_usd`). `convert_to_usd` devuelve `(amount_usd, rate, source)` — el mapeo a `fx_source` persistido lo hace el Plan 2 con `_map_source(src, currency)`: `fallback`→`fallback`; si `currency=="ARS"`→`dolarapi`; el resto (`frankfurter|cache|direct`)→`frankfurter`; override del usuario→`manual`.

---

## Roadmap del resto (plans siguientes)

- **Plan 2 — API HTTP + auth:** `app/main.py` (FastAPI, CORS dev, startup seed), auth JWT (reciclado de Expenses), `POST/GET/PATCH/DELETE /api/v1/movements` (crea con FX; PATCH parcial con `MovementUpdate` que no pisa tasas manuales), `GET /api/v1/balance`, `GET /api/v1/users` (para nombres en el frontend), `GET /api/v1/categories`, dashboard (`summary`/`by-city`/`by-category`/`timeseries`). Mapea `fx_source` de FX→persistido.
- **Plan 3 — Captura WhatsApp:** webhook fusionado con **ACK inmediato + background task** (verify HMAC, dedupe tabla, lock por chat), parser LLM con **Claude Haiku 4.5 structured outputs**, dispatcher determinista (devuelve `movement_id` para los botones de split — sin race), comando "borrar" con confirmación, settlement por comando, override de parada activa.
- **Plan 4 — Integración Andiamo:** `app/andiamo.py` (sync de `stops` con `timezone` incluida, refresh perezoso TTL 6h), parada activa por fecha + moneda + timezone, `GET /api/v1/cities/spend` (X-Api-Key). **Cambios en repo Andiamo:** endpoint `/api/stops` (X-Api-Key) + widget "Gastado: USD X" en `/stops/[slug]`.
- **Plan 5 — Frontend dashboard:** shell React 19 + Vite reciclado; balance destacado + botón saldar; gasto por ciudad/categoría; timeline; lista de movimientos (editar/borrar/corregir FX); login; nombres reales vía `GET /users`.
- **Plan 6 — Deploy:** Railway (backend FastAPI + Railway Postgres + frontend estático servido por FastAPI, un solo servicio), envs (`TRIP_SHARED_API_KEY`, `ANDIAMO_URL`, WhatsApp, `ANTHROPIC_API_KEY`), webhook Meta, verificación end-to-end.
