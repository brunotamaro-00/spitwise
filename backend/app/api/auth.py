import asyncio
import hmac
import time
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request
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
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Login: contraseña compartida (LOGIN_PASSWORDS) + picker de persona.

    ``spitwise.lat`` está impreso en un CV, así que /login es una puerta pública
    con gastos reales detrás. La contraseña es del deploy, no del usuario: el
    ``username`` sigue eligiendo *quién* sos (una preferencia de vista, mismos
    datos para los dos), y ``password_hash``/``AUTH_USERS`` siguen siendo solo el
    mapeo de ``wa_id``.

    En ``demo_mode`` no hay gate: el picker pasa sin contraseña, que es todo el
    punto del deploy público.
    """
    username = form.username.strip().lower()
    user = (
        await session.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Usuario inválido")

    if not get_settings().demo_mode:
        key = _client_key(request)
        now = time.time()
        if len(_recent_failures(key, now)) >= _MAX_FAILURES:
            raise HTTPException(
                status_code=429, detail="Demasiados intentos. Probá de nuevo en un minuto."
            )
        if not is_valid_login_password(form.password):
            _failures.setdefault(key, []).append(now)
            # asyncio.sleep, no time.sleep: un solo worker => bloquear el event
            # loop 300 ms congelaría también el webhook del bot.
            await asyncio.sleep(_FAILURE_DELAY_SECONDS)
            raise HTTPException(status_code=401, detail="Contraseña incorrecta")
        _failures.pop(key, None)

    return TokenResponse(access_token=create_jwt(username))


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
