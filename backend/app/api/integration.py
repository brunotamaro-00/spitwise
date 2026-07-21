from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
import secrets
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel

from app.andiamo import force_sync_soon, sync_stops
from app.andiamo_content import force_content_sync_soon
from app.api.auth import get_current_user
from app.api.schemas import (
    CitySpendPublicOut,
    SpendDetailCategoryOut,
    SpendDetailMovementOut,
    SpendDetailOut,
    TripSpendOut,
)
from app.config import get_settings
from app.db.engine import get_session
from app.db.models import Category, Movement, Stop, User
from app.spend import user_share
from app.trip_time import day_in_tz, today_in_tz

router = APIRouter(tags=["integration"])

_EXPENSE = Movement.type == "expense"


def _money(v) -> str:
    return f"{Decimal(str(v)):.2f}"


async def require_api_key(x_api_key: str = Header(...)) -> None:
    if not secrets.compare_digest(x_api_key, get_settings().trip_shared_api_key):
        raise HTTPException(status_code=401, detail="API key inválida")


async def _resolve_user(session: AsyncSession, username: str | None) -> User | None:
    """`?user=` opcional: sin él, totales gross del hogar (contrato original).
    Un username desconocido es 400, nunca un fallback silencioso a gross —
    si Andiamo manda basura tiene que romper, no mostrarle a uno los gastos
    privados del otro."""
    if username is None:
        return None
    found = (
        await session.execute(select(User).where(User.username == username.strip().lower()))
    ).scalar_one_or_none()
    if found is None:
        raise HTTPException(status_code=400, detail="Usuario desconocido")
    return found


def _shares(movements: list[Movement], user: User | None) -> list[tuple[Movement, Decimal]]:
    """Empareja cada movimiento con el monto que le corresponde al usuario.
    Sin usuario => monto gross. Los que no lo tocan (share 0) se descartan:
    un payer_only del otro no debe aparecer ni siquiera con importe 0."""
    if user is None:
        return [(m, m.amount_usd) for m in movements]
    return [(m, s) for m in movements if (s := user_share(m, user.id)) > 0]


async def _local_slugs(session: AsyncSession) -> list[str]:
    """Slugs que solo existen en Spitwise. Andiamo no los conoce, así que nunca
    se le exponen como ciudad (su itinerario no tiene dónde renderizarlos)."""
    return list(
        (await session.execute(select(Stop.slug).where(Stop.is_local.is_(True)))).scalars().all()
    )


@router.get("/cities/spend", response_model=list[CitySpendPublicOut])
async def cities_spend(
    slug: str | None = Query(default=None),
    _: None = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> list[CitySpendPublicOut]:
    """Total del hogar (gross amount_usd de expenses), no share personal.
    Excluye stops locales: son ciudades que no existen en el itinerario de Andiamo."""
    stmt = (
        select(Movement.stop_slug, Movement.city_name,
               func.sum(Movement.amount_usd), func.count())
        .where(_EXPENSE)
        .group_by(Movement.stop_slug, Movement.city_name)
    )
    local = await _local_slugs(session)
    if local:
        stmt = stmt.where(
            func.coalesce(Movement.stop_slug, "").not_in(local)
        )
    if slug:
        stmt = stmt.where(Movement.stop_slug == slug)
    rows = (await session.execute(stmt)).all()
    return [
        CitySpendPublicOut(slug=s, name=c, total_usd=_money(t), movement_count=cnt)
        for s, c, t, cnt in rows
    ]


@router.get("/cities/spend-detail", response_model=SpendDetailOut)
async def cities_spend_detail(
    slug: str = Query(...),
    limit: int = Query(default=5, ge=1, le=10),
    user: str | None = Query(default=None),
    _: None = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> SpendDetailOut:
    """Detalle de gasto de una ciudad para Andiamo. Sin `?user=`, totales gross
    del hogar; con él, la parte de esa persona (`user_share`: mitad de un
    compartido, entero de un payer_only/other_only suyo) y los gastos privados
    del otro quedan afuera.
    Siempre 200: slug desconocido => ceros y arrays vacíos (nunca 404).
    Un stop local se trata como desconocido: para Andiamo no existe."""
    who = await _resolve_user(session, user)
    is_local = slug in await _local_slugs(session)
    movements: list[Movement] = []
    if not is_local:
        base = select(Movement).where(_EXPENSE, Movement.stop_slug == slug)
        movements = list((await session.execute(base)).scalars().all())

    shares = _shares(movements, who)
    total = sum((s for _m, s in shares), Decimal("0"))
    city_name = shares[0][0].city_name if shares else None

    stop = None if is_local else (
        await session.execute(select(Stop).where(Stop.slug == slug))
    ).scalar_one_or_none()
    days = 0
    if stop and stop.arrival_date and stop.departure_date:
        days = max((stop.departure_date - stop.arrival_date).days, 0)
    if stop and not city_name:
        city_name = stop.name
    avg = total / days if days else Decimal("0")

    cats = {c.id: c for c in (await session.execute(select(Category))).scalars().all()}
    agg: dict[int | None, Decimal] = {}
    for m, share in shares:
        agg[m.category_id] = agg.get(m.category_id, Decimal("0")) + share
    by_category = [
        SpendDetailCategoryOut(
            category_id=cid,
            name=cats[cid].name if cid in cats else "Otros",
            icon=cats[cid].icon if cid in cats else None,
            total_usd=_money(v),
        )
        for cid, v in sorted(agg.items(), key=lambda kv: kv[1], reverse=True)
        if v > 0
    ]

    users = {u.id: u.username for u in (await session.execute(select(User))).scalars().all()}
    recent = sorted(shares, key=lambda t: (t[0].created_at, t[0].id), reverse=True)[:limit]
    last_movements = [
        SpendDetailMovementOut(
            description=m.description,
            # `amount` se escala en la misma proporción que el share: mostrar el
            # importe original en moneda local al lado de medio importe en USD
            # no cerraría por ningún lado.
            amount=_money(m.amount * share / m.amount_usd if m.amount_usd else 0),
            currency=m.currency,
            amount_usd=_money(share),
            date=day_in_tz(m.created_at, None),
            category_id=m.category_id,
            paid_by_name=users.get(m.paid_by),
        )
        for m, share in recent
    ]

    return SpendDetailOut(
        slug=slug,
        city_name=city_name,
        total_usd=_money(total),
        movement_count=len(shares),
        itinerary_days=days,
        avg_per_day_usd=_money(avg),
        by_category=by_category,
        last_movements=last_movements,
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/trip/spend", response_model=TripSpendOut)
async def trip_spend(
    user: str | None = Query(default=None),
    _: None = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> TripSpendOut:
    """Totales del viaje para el strip de /hoy en Andiamo. Sin `?user=`, gross
    del hogar; con él, la parte de esa persona."""
    who = await _resolve_user(session, user)
    # user_share() vive en Python (mira split y paid_by), así que todo se agrega
    # acá. Son dos personas y un viaje: el volumen no justifica SQL.
    shares = _shares(
        list((await session.execute(select(Movement).where(_EXPENSE))).scalars().all()), who
    )
    total = sum((s for _m, s in shares), Decimal("0"))
    count = len(shares)
    # "Hoy" = fecha de carga (created_at) en la tz default del viaje.
    today = today_in_tz(None)
    today_total = sum(
        (s for m, s in shares if day_in_tz(m.created_at, None) == today), Decimal("0")
    )
    return TripSpendOut(
        total_usd=_money(total), today_usd=_money(today_total), movement_count=count
    )


class SyncHookIn(BaseModel):
    event: str = ""
    source: str = ""
    ts: str = ""


@router.post("/andiamo/sync-hook", status_code=202)
async def sync_hook(body: SyncHookIn | None = None, _: None = Depends(require_api_key)) -> dict:
    """Webhook de Andiamo: agenda un re-pull inmediato según el evento.
    Responde 202 al instante; el sync corre como task. Sin body o con
    evento desconocido → stops (compat con el ping original)."""
    event = (body.event if body else "") or "stops.changed"
    if event == "notes.changed":
        force_content_sync_soon(notes_only=True)
    elif event == "guides.changed":
        force_content_sync_soon()
    else:
        force_sync_soon()
    return {"status": "scheduled", "event": event}


@router.post("/andiamo/sync")
async def trigger_sync(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await sync_stops(session)
