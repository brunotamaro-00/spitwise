import asyncio
import hmac
import time
from typing import Annotated
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import SwitchUserIn, TokenResponse, UserOut
from app.config import get_settings
from app.db.engine import get_session
from app.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Con quién entrás cuando no hay a quién recordar (y siempre, en la demo pública).
# Constante y no setting: los dos usuarios los crea el seed con estos nombres, y
# una env var más sería una que puede quedar apuntando a un usuario inexistente.
DEFAULT_USERNAME = "bruno"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def login_passwords() -> list[str]:
    """Contraseñas válidas del login web (env LOGIN_PASSWORDS, separadas por comas).

    Se trimea y se descartan vacías: una coma de más en la UI de Railway no puede
    crear una contraseña vacía que matchearía un campo sin completar.
    """
    return [p.strip() for p in get_settings().login_passwords.split(",") if p.strip()]


def is_valid_login_password(candidate: str) -> bool:
    """Falla cerrado: sin contraseñas configuradas no entra nadie, no entran todos.

    Compara contra TODAS las entradas sin cortar en la primera: salir antes filtra
    por tiempo cuál matcheó y cuántas hay.
    """
    if not candidate:
        return False
    matched = False
    for password in login_passwords():
        if hmac.compare_digest(candidate, password):
            matched = True
    return matched


# Freno a la fuerza bruta. El servicio corre en UN solo proceso (los locks del bot
# lo exigen, ver DEPLOY.md), así que un dict de módulo lo comparten todos los
# requests — mismo patrón que el throttle de app/due.py. Se pierde en cada deploy,
# que es aceptable con una ventana de 10 minutos.
_MAX_FAILURES = 8
_WINDOW_SECONDS = 600
_FAILURE_DELAY_SECONDS = 0.3
_failures: dict[str, list[float]] = {}


def _recent_failures(key: str, now: float) -> list[float]:
    hits = [t for t in _failures.get(key, []) if now - t < _WINDOW_SECONDS]
    if hits:
        _failures[key] = hits
    else:
        _failures.pop(key, None)
    return hits


def _client_key(request: Request) -> str:
    # Railway está detrás de un proxy: la IP del socket es siempre la del proxy.
    # Un header spoofeable alcanza — esto es un badén encima de una contraseña
    # real, no la decisión de autorización.
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


async def _resolve_user(session: AsyncSession, username: str) -> User | None:
    return (
        await session.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()


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
    request: Request,
    password: Annotated[str, Form()] = "",
    username: Annotated[str, Form()] = "",
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Login: la contraseña compartida (LOGIN_PASSWORDS) es el único gate.

    ``spitwise.lat`` está impreso en un CV, así que /login es una puerta pública
    con gastos reales detrás. La contraseña es del deploy, no del usuario: el
    login solo abre la puerta y *quién* sos se decide adentro (``/auth/switch``).

    ``username`` sobrevive como **pista**, no como identidad: el frontend manda
    la última persona con la que se entró desde ese dispositivo, para que Katia
    no tenga que cambiarse en cada sesión. Si viene vacía o no existe, se entra
    como ``DEFAULT_USERNAME``. Que sea el cliente el que la elige no agrega
    superficie: pasar de una persona a la otra ya es libre para cualquiera que
    tenga la contraseña, y eso es deliberado (es un ledger de pareja, no un
    sistema multi-tenant).

    Los dos campos van como ``Form`` opcionales en vez de
    ``OAuth2PasswordRequestForm``: ese dependency los declara obligatorios y
    FastAPI trata un campo vacío como ausente, así que un login sin pista —el
    caso normal ahora— contestaba 422 en vez de entrar. El flujo "Authorize" de
    /docs sigue andando: manda los mismos dos nombres de campo.

    En ``demo_mode`` no hay gate ni pista: entrada libre y siempre como
    ``DEFAULT_USERNAME`` — quien llega desde el CV no sabe quiénes somos.
    """
    demo = get_settings().demo_mode

    if not demo:
        key = _client_key(request)
        now = time.time()
        if len(_recent_failures(key, now)) >= _MAX_FAILURES:
            raise HTTPException(
                status_code=429, detail="Demasiados intentos. Probá de nuevo en un minuto."
            )
        if not is_valid_login_password(password):
            _failures.setdefault(key, []).append(now)
            # asyncio.sleep, no time.sleep: un solo worker => bloquear el event
            # loop 300 ms congelaría también el webhook del bot.
            await asyncio.sleep(_FAILURE_DELAY_SECONDS)
            raise HTTPException(status_code=401, detail="Contraseña incorrecta")
        _failures.pop(key, None)

    hint = "" if demo else username.strip().lower()
    user = await _resolve_user(session, hint) if hint else None
    if user is None:
        user = await _resolve_user(session, DEFAULT_USERNAME)
    if user is None:
        # Base sin sembrar: no hay ninguna identidad que emitir.
        raise HTTPException(status_code=503, detail="No hay usuarios configurados")

    return TokenResponse(access_token=create_jwt(user.username))


@router.post("/switch", response_model=TokenResponse)
async def switch_user(
    payload: SwitchUserIn,
    _current: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Cambiar de persona ya adentro: emite un JWT nuevo para ``username``.

    Sin contraseña a propósito. La identidad nunca fue el límite de seguridad acá
    —el login ya dejaba elegir Bruno o Katia con la misma contraseña—; lo único
    que separa lo público de lo privado es ``LOGIN_PASSWORDS``, y para llegar a
    este endpoint ya hay que haberla pasado.
    """
    target = await _resolve_user(session, payload.username.strip().lower())
    if target is None:
        raise HTTPException(status_code=404, detail="Usuario inexistente")
    return TokenResponse(access_token=create_jwt(target.username))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


users_router = APIRouter(tags=["users"])


@users_router.get("/users", response_model=list[UserOut])
async def list_users(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[User]:
    return list((await session.execute(select(User).order_by(User.id))).scalars().all())
