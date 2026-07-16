from fastapi import APIRouter, Depends

from app.api.auth import get_current_user
from app.api.schemas import ConfigOut
from app.config import get_settings
from app.db.models import User

router = APIRouter(tags=["config"])


@router.get("/config", response_model=ConfigOut)
async def get_config(user: User = Depends(get_current_user)) -> ConfigOut:
    """Config pública para el frontend (deep links a Andiamo)."""
    return ConfigOut(andiamo_url=get_settings().andiamo_url or None)
