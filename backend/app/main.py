import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.categories.seed import seed_categories
from app.config import get_settings, parse_cors
from app.db.engine import get_sessionmaker
from app.users import seed_users_from_env

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    maker = get_sessionmaker()
    async with maker() as session:
        await seed_categories(session)
        await session.commit()
        await seed_users_from_env(session)
    yield


app = FastAPI(title="Botardo Viaje", lifespan=lifespan)

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
