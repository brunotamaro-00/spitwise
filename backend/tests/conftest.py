import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.models import Base


@pytest.fixture(autouse=True)
def login_password(monkeypatch):
    """`pw` es la contraseña del login en toda la suite.

    /auth/login falla cerrado sin LOGIN_PASSWORDS, así que sin esto cualquier
    test que pida un token daría 401. Los tests que ejercitan el gate en sí
    (test_auth.py) pisan la env var con su propio monkeypatch.
    """
    monkeypatch.setenv("LOGIN_PASSWORDS", "pw")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


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
