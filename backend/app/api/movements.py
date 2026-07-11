from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.schemas import MovementIn, MovementOut, MovementUpdate
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
    if currency.upper() == "ARS":
        return "dolarapi"
    return "frankfurter"


@router.post("", response_model=MovementOut, status_code=status.HTTP_201_CREATED)
async def create_movement(
    body: MovementIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Movement:
    # Plan 4 reemplaza el None por la timezone de la parada activa.
    mdate = body.movement_date or today_in_tz(None)
    if body.fx_rate is not None:
        rate = body.fx_rate
        amount_usd = (body.amount * rate).quantize(_TWO, rounding=ROUND_HALF_UP)
        fx_source = "manual"
    else:
        amount_usd, rate, src = await convert_to_usd(session, body.amount, body.currency, mdate)
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
        category_id=body.category_id,
        stop_slug=body.stop_slug,
        city_name=body.city_name,
        movement_date=mdate,
        created_by=user.id,
    )
    session.add(mv)
    await session.commit()
    await session.refresh(mv)
    return mv


@router.get("", response_model=list[MovementOut])
async def list_movements(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Movement]:
    rows = (
        await session.execute(
            select(Movement).order_by(Movement.movement_date.desc(), Movement.id.desc())
        )
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

    fx_inputs_changed = sent & {"amount", "currency", "movement_date"}
    if "fx_rate" in sent:
        # Override explícito -> manual.
        mv.fx_rate = body.fx_rate
        mv.fx_source = "manual"
        mv.amount_usd = (mv.amount * mv.fx_rate).quantize(_TWO, rounding=ROUND_HALF_UP)
    elif fx_inputs_changed:
        if mv.fx_source == "manual":
            # Respetar la tasa manual vigente; solo recalcular el monto.
            mv.amount_usd = (mv.amount * mv.fx_rate).quantize(_TWO, rounding=ROUND_HALF_UP)
        else:
            amount_usd, rate, src = await convert_to_usd(session, mv.amount, mv.currency, mv.movement_date)
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
    if mv is not None:
        await session.delete(mv)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
