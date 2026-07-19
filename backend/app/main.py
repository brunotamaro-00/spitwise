import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.andiamo import sync_stops
from app.categories.seed import seed_categories
from app.config import get_settings, parse_cors
from app.db.engine import get_sessionmaker
from app.due import ensure_due_settled
from app.stops_local import seed_local_stops
from app.users import seed_users_from_env

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Solo secretos que la app usa de verdad. bot_api_key existe en config pero no se lee
# en ningún endpoint — no debe tumbar el deploy.
_DEFAULT_SECRETS = {
    "secret_key": "change-me-in-production-use-a-long-random-string",
    "trip_shared_api_key": "change-me-shared-key",
}


def _assert_prod_secrets() -> None:
    s = get_settings()
    if s.environment in ("dev", "test"):
        return
    bad = [name for name, default in _DEFAULT_SECRETS.items() if getattr(s, name) == default]
    if bad:
        raise RuntimeError(
            f"Secrets con valor default en environment={s.environment!r}: {', '.join(bad)}. "
            "Configurá SECRET_KEY / TRIP_SHARED_API_KEY antes de arrancar."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _assert_prod_secrets()
    maker = get_sessionmaker()
    async with maker() as session:
        await seed_categories(session)
        await session.commit()
        await seed_users_from_env(session)
        if get_settings().andiamo_url:
            await sync_stops(session)  # primer sync; tolerante a fallo
        # Después del sync: el orden de Pititas se deriva del snapshot.
        await seed_local_stops(session)
        # Pendings vencidos durante un deploy sin tráfico: una pasada al boot.
        await ensure_due_settled(session)
    yield


app = FastAPI(title="Spitwise Viaje", lifespan=lifespan)

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
from app.api.webhook import router as webhook_router  # noqa: E402

app.include_router(api_router)
app.include_router(webhook_router)


def mount_frontend(app: FastAPI, dist: Path) -> None:
    """Sirve el build de Vite con SPA fallback. Los routers ya registrados
    (/api/v1, /webhooks, /health) ganan porque el catch-all se agrega último."""
    if not dist.exists():
        logger.warning("frontend_dist_missing path=%s (solo API)", dist)
        return
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    root = dist.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        candidate = (dist / full_path).resolve()
        # resolve + is_relative_to: un full_path con ".." no puede escapar de dist.
        if full_path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")


mount_frontend(app, Path(os.environ.get("FRONTEND_DIST", "../frontend/dist")))
