from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.schemas import MovementConfirm, MovementIn, MovementOut, MovementUpdate
from app.balance import UNSETTLED
from app.bot.active_stop import place_for_date, resolve_trip_timezone
from app.bot.capture import owner_split
from app.cashback import net_amount, validate_cashback
from app.db.engine import get_session
from app.db.models import Movement, Stop, User
from app.due import ensure_due_settled, next_status_for_date
from app.fx import convert_to_usd, fx_reference_date, map_fx_source, reprice_movement
from app.textnorm import load_proper_nouns, normalize_description
from app.trip_time import today_in_tz

router = APIRouter(prefix="/movements", tags=["movements"])
_TWO = Decimal("0.01")


# Alias histórico: la política vive en app/fx.py, único dueño del mapeo.
_map_source = map_fx_source


async def _load_today(session: AsyncSession, username: str | None = None):
    tz = await resolve_trip_timezone(session, username)
    return today_in_tz(tz)


async def _stop_by_slug(session: AsyncSession, slug: str) -> Stop:
    """La ciudad siempre sale de una parada real del itinerario: nunca texto libre."""
    stop = (
        await session.execute(
            select(Stop).where(
                Stop.slug == slug, Stop.is_candidate.is_(False), Stop.is_archived.is_(False)
            )
        )
    ).scalar_one_or_none()
    if stop is None:
        raise HTTPException(status_code=422, detail=f"Parada desconocida: {slug!r}")
    return stop


async def _derive_place(session: AsyncSession, body, username: str, today) -> tuple[str | None, str | None]:
    """(stop_slug, city_name) según las reglas: slug explícito validado, o parada de hoy."""
    if body.stop_slug is not None:
        stop = await _stop_by_slug(session, body.stop_slug)
        return stop.slug, stop.name
    stop = await place_for_date(session, today, username)
    return (stop.slug, stop.name) if stop is not None else (None, None)


@router.post("", response_model=MovementOut, status_code=status.HTTP_201_CREATED)
async def create_movement(
    body: MovementIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Movement:
    today = await _load_today(session, user.username)
    # `general` (o un saldo) => sin ciudad; si no, parada explícita validada o la de hoy.
    if body.general or body.type == "settlement":
        stop_slug, city_name = None, None
    else:
        stop_slug, city_name = await _derive_place(session, body, user.username, today)
    # Saldos: siempre de hoy. status lo deriva el server, nunca el cliente.
    payment_date = None if body.type == "settlement" else body.payment_date
    mv_status = "pending" if payment_date is not None and payment_date > today else "confirmed"
    # Cashback solo en gastos. amount es el bruto; el neto (bruto - cashback)
    # es el que se convierte a USD (app/cashback.py).
    cb_kind = body.cashback_kind if body.type == "expense" else None
    cb_value = body.cashback_value if body.type == "expense" else None
    if (err := validate_cashback(cb_kind, cb_value, body.amount)) is not None:
        raise HTTPException(status_code=422, detail=err)
    net = net_amount(body.amount, cb_kind, cb_value)
    if body.fx_rate is not None:
        rate = body.fx_rate
        # ARS system rate is ~1/venta (<1). Users often type pesos-per-USD (>1).
        if body.currency.upper() == "ARS" and rate >= 1:
            raise HTTPException(
                status_code=422,
                detail="fx_rate para ARS debe ser el multiplicador a USD (ej. 0.000625), no pesos por dólar",
            )
        amount_usd = (net * rate).quantize(_TWO, rounding=ROUND_HALF_UP)
        fx_source = "manual"
    else:
        # Regla: TC de la fecha de pago, capeada a hoy (histórico si es pasada,
        # proxy de hoy si es futura — se ajusta al liquidar, app/due.py).
        amount_usd, rate, src = await convert_to_usd(
            session, net, body.currency, fx_reference_date(payment_date, today)
        )
        fx_source = _map_source(src, body.currency)

    # Paradas con dueño (Pititas/Portugal): el gasto es de esa persona por
    # default, igual que por el bot. Estaba solo en el camino de WhatsApp, así
    # que el mismo gasto se repartía distinto según por dónde se cargara.
    payer_id = body.paid_by or user.id
    split = body.split
    if body.type == "expense":
        payer = (await session.execute(select(User).where(User.id == payer_id))).scalar_one_or_none()
        if payer is not None:
            split = await owner_split(session, stop_slug, payer, split)

    mv = Movement(
        type=body.type,
        amount=body.amount,
        currency=body.currency.upper(),
        amount_usd=amount_usd,
        fx_rate=rate,
        fx_source=fx_source,
        paid_by=payer_id,
        split=split,
        description=normalize_description(body.description, await load_proper_nouns(session)),
        category_id=None if body.type == "settlement" else body.category_id,
        stop_slug=stop_slug,
        city_name=city_name,
        payment_date=payment_date,
        status=mv_status,
        cashback_kind=cb_kind,
        cashback_value=cb_value,
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
    await ensure_due_settled(session)
    rows = (
        await session.execute(
            select(Movement).order_by(Movement.created_at.desc(), Movement.id.desc())
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
    for field in ("type", "split", "paid_by", "category_id"):
        if field in sent:
            setattr(mv, field, getattr(body, field))
    if "description" in sent:
        mv.description = normalize_description(
            body.description, await load_proper_nouns(session)
        )
    # Se comparan valores, no presencia: un cliente que re-manda el body entero
    # no debe gatillar un re-precio del FX (ver `fx_inputs_changed`).
    money_changed = False
    if "amount" in sent and body.amount != mv.amount:
        mv.amount = body.amount
        money_changed = True
    if "currency" in sent and body.currency.upper() != mv.currency:
        mv.currency = body.currency.upper()
        money_changed = True

    # Cashback: cada campo se pisa solo si vino en el body. Pisar los dos cuando
    # llega uno solo hacía imposible corregir nada más que el % (el otro campo
    # viajaba como el None default de Pydantic y `validate_cashback` tiraba 422).
    cashback_changed = False
    if "cashback_kind" in sent and body.cashback_kind != mv.cashback_kind:
        mv.cashback_kind = body.cashback_kind
        cashback_changed = True
    if "cashback_value" in sent and body.cashback_value != mv.cashback_value:
        mv.cashback_value = body.cashback_value
        cashback_changed = True

    # Ciudad: slug explícito validado (deriva city_name), null explícito => parada de hoy.
    if "stop_slug" in sent and mv.type != "settlement":
        today = await _load_today(session, user.username)
        mv.stop_slug, mv.city_name = await _derive_place(session, body, user.username, today)

    # general=True => forzar sin ciudad.
    if "general" in sent and body.general:
        mv.stop_slug, mv.city_name = None, None

    # Settlement nunca lleva ciudad, fecha diferida ni cashback.
    if mv.type == "settlement":
        mv.stop_slug, mv.city_name = None, None
        mv.category_id = None
        mv.payment_date = None
        mv.status = "confirmed"
        mv.cashback_kind = None
        mv.cashback_value = None

    if (err := validate_cashback(mv.cashback_kind, mv.cashback_value, mv.amount)) is not None:
        raise HTTPException(status_code=422, detail=err)

    # Fecha de pago: recalcula status (siempre derivado server-side) y el TC.
    pay_changed = (
        "payment_date" in sent
        and mv.type != "settlement"
        and body.payment_date != mv.payment_date
    )
    if pay_changed:
        today = await _load_today(session, user.username)
        mv.payment_date = body.payment_date
        # Un awaiting conserva su estado: solo POST /confirm lo mete al balance.
        mv.status = next_status_for_date(mv.status, body.payment_date, today)

    # amount_usd = neto (bruto - cashback) × TC. El cashback también gatilla recálculo.
    net = net_amount(mv.amount, mv.cashback_kind, mv.cashback_value)
    fx_inputs_changed = money_changed or pay_changed or cashback_changed
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
        mv.amount_usd = (net * mv.fx_rate).quantize(_TWO, rounding=ROUND_HALF_UP)
    elif fx_inputs_changed:
        today = await _load_today(session, user.username)
        # Regla: TC de la fecha de pago, capeada a hoy. `reprice_movement` respeta
        # las tasas lockeadas (manual / awaiting) y no pisa una tasa buena con el
        # fallback de un proveedor caído.
        mv.amount_usd, mv.fx_rate, mv.fx_source = await reprice_movement(
            session, mv, net, fx_reference_date(mv.payment_date, today)
        )
    # Si no cambió nada relevante al FX, no se toca (no pisar correcciones).

    await session.commit()
    await session.refresh(mv)
    return mv


@router.post("/{movement_id}/confirm", response_model=MovementOut)
async def confirm_movement(
    movement_id: int,
    body: MovementConfirm,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Movement:
    """Confirma manualmente un gasto vencido (pending/awaiting): opcionalmente
    corrige el pagador y lo pasa a confirmed, recién ahí entra al balance.
    No recalcula el FX (ya quedó lockeado al vencer; un confirm 1 día antes
    acepta el TC proxy). Única vía de confirmación — el cliente nunca escribe
    `status` directo (invariante 4)."""
    mv = (await session.execute(select(Movement).where(Movement.id == movement_id))).scalar_one_or_none()
    if mv is None:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    if mv.status not in UNSETTLED:
        raise HTTPException(status_code=409, detail="El movimiento ya está confirmado")

    # Solo se confirma lo que ya venció (o vence mañana, igual que el banner de
    # la web). Confirmar un pending lejano lo dejaría clavado al TC proxy del día
    # de carga: `settle_due_movements` filtra por status='pending' y nunca lo
    # volvería a mirar, así que el TC real de la fecha de pago se perdería.
    if mv.payment_date is not None:
        today = await _load_today(session, user.username)
        if mv.payment_date > today + timedelta(days=1):
            raise HTTPException(
                status_code=409,
                detail="El gasto todavía no llegó a su fecha de pago",
            )

    if body.paid_by is not None:
        from app.users import get_trip_users

        valid_ids = {u.id for u in await get_trip_users(session)}
        if body.paid_by not in valid_ids:
            raise HTTPException(status_code=422, detail="paid_by no es un usuario del viaje")
        mv.paid_by = body.paid_by

    mv.status = "confirmed"
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
