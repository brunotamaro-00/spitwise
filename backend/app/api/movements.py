from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.schemas import MovementIn, MovementOut, MovementUpdate
from app.bot.active_stop import place_for_date, resolve_trip_timezone
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
    if fx_source == "direct" or currency.upper() == "USD":
        return "direct" if currency.upper() == "USD" else fx_source
    if currency.upper() == "ARS":
        return "dolarapi"
    return "frankfurter"


async def _load_today(session: AsyncSession):
    tz = await resolve_trip_timezone(session)
    return today_in_tz(tz)


@router.post("", response_model=MovementOut, status_code=status.HTTP_201_CREATED)
async def create_movement(
    body: MovementIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Movement:
    today = await _load_today(session)
    mdate = body.movement_date or today
    stop_slug, city_name = body.stop_slug, body.city_name
    # `general` (o un saldo) => sin ciudad; no derivar la parada activa por fecha.
    is_general = body.general or body.type == "settlement"
    if not is_general and stop_slug is None and city_name is None:
        stop = await place_for_date(session, mdate)
        if stop is not None:
            stop_slug, city_name = stop.slug, stop.name
    if body.type == "settlement":
        stop_slug, city_name = None, None
    if body.fx_rate is not None:
        rate = body.fx_rate
        # ARS system rate is ~1/venta (<1). Users often type pesos-per-USD (>1).
        if body.currency.upper() == "ARS" and rate >= 1:
            raise HTTPException(
                status_code=422,
                detail="fx_rate para ARS debe ser el multiplicador a USD (ej. 0.000625), no pesos por dólar",
            )
        amount_usd = (body.amount * rate).quantize(_TWO, rounding=ROUND_HALF_UP)
        fx_source = "manual"
    else:
        # Regla: el TC es siempre el de la fecha de CARGA, no la del gasto.
        amount_usd, rate, src = await convert_to_usd(session, body.amount, body.currency, today)
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
        category_id=None if body.type == "settlement" else body.category_id,
        stop_slug=stop_slug,
        city_name=city_name,
        movement_date=mdate,
        created_by=user.id,
    )
    session.add(mv)
    await session.commit()
    await session.refresh(mv)
    return mv


@router.get("", response_model=list[MovementOut])
async def list_movements(
    sort: str = "date",  # "date" = fecha imputada; "created" = fecha de carga
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Movement]:
    order = (
        (Movement.created_at.desc(), Movement.id.desc())
        if sort == "created"
        else (Movement.movement_date.desc(), Movement.id.desc())
    )
    rows = (
        await session.execute(select(Movement).order_by(*order))
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

    # general=True => forzar sin ciudad.
    if "general" in sent and body.general:
        mv.stop_slug, mv.city_name = None, None

    # Si cambió la fecha y no vino override de ciudad / general, re-derivar (o limpiar).
    if "movement_date" in sent and not ({"stop_slug", "city_name"} & sent) and not (
        "general" in sent and body.general
    ):
        if mv.type != "settlement":
            stop = await place_for_date(session, mv.movement_date)
            if stop is not None:
                mv.stop_slug, mv.city_name = stop.slug, stop.name
            else:
                mv.stop_slug, mv.city_name = None, None

    # Settlement nunca lleva ciudad.
    if mv.type == "settlement":
        mv.stop_slug, mv.city_name = None, None
        mv.category_id = None

    fx_inputs_changed = sent & {"amount", "currency"}
    if "fx_rate" in sent:
        if body.fx_rate is None:
            raise HTTPException(status_code=422, detail="fx_rate no puede ser null")
        if mv.currency == "ARS" and body.fx_rate >= 1:
            raise HTTPException(
                status_code=422,
                detail="fx_rate para ARS debe ser el multiplicador a USD (ej. 0.000625), no pesos por dólar",
            )
        mv.fx_rate = body.fx_rate
        mv.fx_source = "manual"
        mv.amount_usd = (mv.amount * mv.fx_rate).quantize(_TWO, rounding=ROUND_HALF_UP)
    elif fx_inputs_changed:
        if mv.fx_source == "manual":
            # Respetar la tasa manual vigente; solo recalcular el monto.
            mv.amount_usd = (mv.amount * mv.fx_rate).quantize(_TWO, rounding=ROUND_HALF_UP)
        else:
            today = await _load_today(session)
            # Regla: el TC es siempre el de la fecha de CARGA/edición, no la del gasto.
            amount_usd, rate, src = await convert_to_usd(session, mv.amount, mv.currency, today)
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
    if mv is None:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    await session.delete(mv)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
