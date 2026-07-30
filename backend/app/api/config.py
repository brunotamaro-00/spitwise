from fastapi import APIRouter, Depends

from app.api.auth import get_current_user
from app.api.schemas import ConfigOut
from app.config import get_settings
from app.db.models import User

router = APIRouter(tags=["config"])


def _config() -> ConfigOut:
    s = get_settings()
    return ConfigOut(
        andiamo_url=s.andiamo_url or None,
        demo=s.demo_mode,
        demo_url=s.demo_url or None,
    )


@router.get("/config", response_model=ConfigOut)
async def get_config(user: User = Depends(get_current_user)) -> ConfigOut:
    """Config pública para el frontend (deep links a Andiamo)."""
    return _config()


@router.get("/public-config", response_model=ConfigOut)
async def get_public_config() -> ConfigOut:
    """Misma config, sin JWT.

    El banner de demo y el CTA "entrar a la demo" tienen que verse en /login —
    donde aterriza quien llega desde el CV — y ahí todavía no hay token. Va sin
    auth porque no revela nada: `andiamo_url` y `demo_url` ya son dominios
    públicos y `demo` es una constante del deploy.
    No alcanza con un `VITE_*`: el bundle se construye dentro del Dockerfile,
    así que una env var de runtime de Railway nunca llegaría al build.
    """
    return _config()
