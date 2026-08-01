"""Presupuesto de "vivir": lectura del análisis y ABM de los targets.

Router propio y no parte de `dashboard.py` a propósito: ese es read-only y
personal por definición, mientras que acá hay escrituras sobre datos
**autorales y compartidos** — el target de Viena es el mismo para los dos, el
número ya es por persona.

La lectura sale de `app/budget.py` sobre las mismas filas de ciudad que
`/dashboard/pace` (vía `dashboard.load_trip_pace`): el presupuesto nunca
re-agrega movimientos por su cuenta.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.dashboard import _money, _money_opt, load_trip_pace
from app.api.movements import _stop_by_slug
from app.api.schemas import (
    BudgetOut,
    BudgetProjectionOut,
    CategoryMixOut,
    CityBudgetOut,
    CurrentCityBudgetOut,
    FixedBlockOut,
    NextStopBudgetOut,
    StopBudgetIn,
    StopBudgetOut,
    TripCushionOut,
    TripPlanOut,
)
from app.budget import Band, build_budget
from app.db.engine import get_session
from app.db.models import StopBudget, User

router = APIRouter(prefix="/budget", tags=["budget"])


async def _load_bands(
    session: AsyncSession,
) -> tuple[dict[str, Band], dict[str, str]]:
    rows = list((await session.execute(select(StopBudget))).scalars().all())
    bands = {r.stop_slug: Band(r.daily_min_usd, r.daily_max_usd) for r in rows}
    notes = {r.stop_slug: r.note for r in rows if r.note}
    return bands, notes


@router.get("", response_model=BudgetOut)
async def get_budget(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BudgetOut:
    """Análisis completo: ciudad en curso, colchón, filas por ciudad, proyección y fijos."""
    pace, today = await load_trip_pace(session, user)
    bands, notes = await _load_bands(session)
    data = build_budget(pace, bands, notes)

    cur, cush, plan, proj, fixed = (
        data["current"],
        data["cushion"],
        data["plan"],
        data["projection"],
        data["fixed"],
    )
    nxt = plan["next_stop"]

    return BudgetOut(
        as_of=today,
        trip_status=data["trip_status"],
        current=(
            None
            if cur is None
            else CurrentCityBudgetOut(
                stop_slug=cur["stop_slug"],
                city_name=cur["city_name"],
                country_flag=cur["country_flag"],
                arrival_date=cur["arrival_date"],
                departure_date=cur["departure_date"],
                lived_nights=cur["lived_nights"],
                total_nights=cur["total_nights"],
                remaining_days=cur["remaining_days"],
                target_min_usd=_money_opt(cur["target_min_usd"]),
                target_max_usd=_money_opt(cur["target_max_usd"]),
                target_daily_usd=_money_opt(cur["target_daily_usd"]),
                living_usd=_money(cur["living_usd"]),
                living_per_day_usd=_money_opt(cur["living_per_day_usd"]),
                budget_to_date_usd=_money_opt(cur["budget_to_date_usd"]),
                variance_usd=_money_opt(cur["variance_usd"]),
                remaining_budget_usd=_money_opt(cur["remaining_budget_usd"]),
                remaining_daily_usd=_money_opt(cur["remaining_daily_usd"]),
                band_position=cur["band_position"],
                edge_delta_pct=cur["edge_delta_pct"],
                delta_pct=cur["delta_pct"],
                by_category=[
                    CategoryMixOut(
                        category_id=m["category_id"],
                        living_usd=_money(m["living_usd"]),
                        share_pct=m["share_pct"],
                        trip_share_pct=m["trip_share_pct"],
                        ratio=m["ratio"],
                    )
                    for m in cur["by_category"]
                ],
            )
        ),
        cushion=TripCushionOut(
            covered_nights=cush["covered_nights"],
            budget_to_date_usd=_money_opt(cush["budget_to_date_usd"]),
            living_to_date_usd=_money(cush["living_to_date_usd"]),
            cushion_usd=_money_opt(cush["cushion_usd"]),
            remaining_nights=cush["remaining_nights"],
            needed_daily_usd=_money_opt(cush["needed_daily_usd"]),
            avg_target_daily_usd=_money_opt(cush["avg_target_daily_usd"]),
            needed_delta_pct=cush["needed_delta_pct"],
        ),
        plan=TripPlanOut(
            budget_nights=plan["budget_nights"],
            covered_nights=plan["covered_nights"],
            coverage_pct=plan["coverage_pct"],
            uncovered_slugs=plan["uncovered_slugs"],
            living_budget_min_usd=_money_opt(plan["living_budget_min_usd"]),
            living_budget_max_usd=_money_opt(plan["living_budget_max_usd"]),
            living_budget_usd=_money_opt(plan["living_budget_usd"]),
            avg_target_daily_usd=_money_opt(plan["avg_target_daily_usd"]),
            next_stop=(
                None
                if nxt is None
                else NextStopBudgetOut(
                    stop_slug=nxt["stop_slug"],
                    city_name=nxt["city_name"],
                    country_flag=nxt["country_flag"],
                    arrival_date=nxt["arrival_date"],
                    nights=nxt["nights"],
                    target_min_usd=_money_opt(nxt["target_min_usd"]),
                    target_max_usd=_money_opt(nxt["target_max_usd"]),
                    target_daily_usd=_money_opt(nxt["target_daily_usd"]),
                )
            ),
        ),
        cities=[
            CityBudgetOut(
                stop_slug=c["stop_slug"],
                city_name=c["city_name"],
                country_flag=c["country_flag"],
                order=c["order"],
                status=c["status"],
                is_archived=c["is_archived"],
                in_itinerary=c["in_itinerary"],
                nights=c["nights"],
                elapsed_nights=c["elapsed_nights"],
                movement_count=c["movement_count"],
                target_min_usd=_money_opt(c["target_min_usd"]),
                target_max_usd=_money_opt(c["target_max_usd"]),
                target_daily_usd=_money_opt(c["target_daily_usd"]),
                note=c["note"],
                living_usd=_money(c["living_usd"]),
                living_per_day_usd=_money_opt(c["living_per_day_usd"]),
                budget_accrued_usd=_money_opt(c["budget_accrued_usd"]),
                variance_usd=_money_opt(c["variance_usd"]),
                band_position=c["band_position"],
                edge_delta_pct=c["edge_delta_pct"],
                delta_pct=c["delta_pct"],
            )
            for c in data["cities"]
        ],
        projection=BudgetProjectionOut(
            budget_nights=proj["budget_nights"],
            covered_nights=proj["covered_nights"],
            coverage_pct=proj["coverage_pct"],
            uncovered_slugs=proj["uncovered_slugs"],
            living_budget_min_usd=_money_opt(proj["living_budget_min_usd"]),
            living_budget_max_usd=_money_opt(proj["living_budget_max_usd"]),
            living_budget_usd=_money_opt(proj["living_budget_usd"]),
            living_to_date_usd=_money(proj["living_to_date_usd"]),
            living_run_rate_usd=_money_opt(proj["living_run_rate_usd"]),
            projected_living_usd=_money_opt(proj["projected_living_usd"]),
            variance_usd=_money_opt(proj["variance_usd"]),
        ),
        fixed=FixedBlockOut(
            lodging_usd=_money(fixed["lodging_usd"]),
            general_usd=_money(fixed["general_usd"]),
            total_usd=_money(fixed["total_usd"]),
            per_night_usd=_money_opt(fixed["per_night_usd"]),
        ),
    )


@router.put("/{stop_slug}", response_model=StopBudgetOut)
async def upsert_stop_budget(
    stop_slug: str,
    body: StopBudgetIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StopBudget:
    """Fija la banda de una parada. Bordes <= 0 o invertidos mueren en el schema."""
    # Misma política que POST /movements: el slug se valida contra una parada
    # real del itinerario, nunca texto libre.
    await _stop_by_slug(session, stop_slug)

    row = await session.get(StopBudget, stop_slug)
    if row is None:
        row = StopBudget(stop_slug=stop_slug)
        session.add(row)
    row.daily_min_usd = body.daily_min_usd
    row.daily_max_usd = body.daily_max_usd
    row.note = body.note
    await session.commit()
    await session.refresh(row)
    return row


@router.delete("/{stop_slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stop_budget(
    stop_slug: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Borra el target. Baja la cobertura, y eso es información, no un error."""
    row = await session.get(StopBudget, stop_slug)
    if row is None:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    await session.delete(row)
    await session.commit()
