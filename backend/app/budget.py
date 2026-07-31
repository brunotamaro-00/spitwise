"""Presupuesto de "vivir": target por parada contra el gasto diario real.

Funciones puras (sin I/O), estilo balance.py/spend.py/analytics.py. El modelo:

- **"Vivir" no es un campo, es `other_usd`.** Es todo menos alojamiento y
  generales, y `analytics.build_trip_pace` ya lo calcula por ciudad: el
  alojamiento sale prorrateado por noches y los vuelos/pases/seguros no entran
  porque no tienen `stop_slug`. Todo en `user_share` (la parte del usuario).
- Por eso este módulo **consume la lista `cities` de `build_trip_pace`** y nunca
  re-agrega movimientos. Duplicar el prorrateo o `user_share` acá es la forma
  garantizada de que /ciudades y /presupuesto terminen diciendo cosas distintas.
- El **target** (`StopBudget.daily_usd`) es USD/día **por persona**, cargado a
  mano. Una parada sin target no se compara ni se extrapola: baja la cobertura.
- **Regla de honestidad:** con cobertura parcial, el presupuesto del viaje es
  parcial, y compararlo contra una proyección de noches completas es mentir.
  `coverage_pct` y `uncovered_slugs` viajan siempre junto a la varianza para
  que no se pueda renderizar una sin la otra.

No recibe `today`: `build_trip_pace` ya resolvió `status`, `nights` y
`elapsed_nights` contra el hoy del viaje, y pedirlo de nuevo abriría la puerta
a dos "hoy" distintos en la misma respuesta.

Devuelve Decimals/None crudos; el endpoint serializa.
"""

from decimal import Decimal
from typing import Mapping

_ZERO = Decimal("0")

Targets = Mapping[str, Decimal]
Notes = Mapping[str, str]


def _target(targets: Targets, slug: str) -> Decimal | None:
    """Target usable de una parada, o None.

    Un target <= 0 se trata como ausente. La API ya lo impide (`Field(gt=0)`),
    pero el módulo puro no confía en el borde: una fila vieja o un seed torcido
    no tienen que producir una división rara ni un delta infinito.
    """
    raw = targets.get(slug)
    if raw is None:
        return None
    value = Decimal(raw)
    return value if value > 0 else None


def _delta_pct(per_day: Decimal | None, target: Decimal | None) -> float | None:
    """Desvío % del ritmo real contra el target. El veredicto lo pinta
    DeltaBadge en el frontend con sus umbrales (±10% = ruido)."""
    if per_day is None or target is None:
        return None
    return float((per_day / target - 1) * 100)


def _eligible(cities: list[dict]) -> list[dict]:
    """Paradas que cuentan para el presupuesto del viaje.

    `in_itinerary` es la frontera: una parada del otro (Pititas) puede aparecer
    como fila —el usuario gastó ahí— pero sus noches no son suyas, y sumarlas
    le inventaría presupuesto de un tramo que no viaja. Las archivadas y las de
    0 noches tampoco: su plata existe y se muestra, pero no tienen noches que
    presupuestar.
    """
    return [
        c
        for c in cities
        if c["in_itinerary"] and not c["is_archived"] and c["nights"] > 0
    ]


def _coverage(eligible: list[dict], targets: Targets) -> dict:
    """Cuánto del itinerario tiene target, y el presupuesto de lo cubierto."""
    budget_nights = 0
    covered_nights = 0
    uncovered: list[str] = []
    living_budget = _ZERO
    for c in eligible:
        nights = c["nights"]
        budget_nights += nights
        target = _target(targets, c["stop_slug"])
        if target is None:
            uncovered.append(c["stop_slug"])
            continue
        covered_nights += nights
        living_budget += target * nights
    return {
        "budget_nights": budget_nights,
        "covered_nights": covered_nights,
        "coverage_pct": (
            float(covered_nights * 100 / budget_nights) if budget_nights else None
        ),
        "uncovered_slugs": uncovered,
        # Nunca extrapolar un target a una parada que no lo tiene: el
        # presupuesto es el de lo cubierto, y la cobertura lo dice al lado.
        "living_budget_usd": living_budget if covered_nights else None,
    }


def city_budget_rows(
    cities: list[dict], targets: Targets, notes: Notes | None = None
) -> list[dict]:
    """Una fila por ciudad: target, gasto de vivir y desvío.

    El orden viene de `build_trip_pace` (archivadas al final, después por
    `order`), así que no se re-ordena.
    """
    notes = notes or {}
    rows: list[dict] = []
    for c in cities:
        slug = c["stop_slug"]
        target = _target(targets, slug)
        per_day = c["other_per_day_usd"]
        living = c["other_usd"]

        # Una futura solo tiene prepago imputado: no hay ritmo que comparar, y
        # gritar un +400% sobre una reserva es ruido. Espeja analytics.py.
        comparable = target is not None and c["status"] != "future"
        budget_accrued = target * c["elapsed_nights"] if comparable else None

        rows.append(
            {
                "stop_slug": slug,
                "city_name": c["city_name"],
                "country_flag": c["country_flag"],
                "order": c["order"],
                "status": c["status"],
                "is_archived": c["is_archived"],
                "in_itinerary": c["in_itinerary"],
                "nights": c["nights"],
                "elapsed_nights": c["elapsed_nights"],
                "movement_count": c["movement_count"],
                "target_daily_usd": target,
                "note": notes.get(slug),
                "living_usd": living,
                "living_per_day_usd": per_day,
                "budget_accrued_usd": budget_accrued,
                "variance_usd": (
                    living - budget_accrued if budget_accrued is not None else None
                ),
                "delta_pct": _delta_pct(per_day, target) if comparable else None,
            }
        )
    return rows


def current_city_budget(cities: list[dict], targets: Targets) -> dict | None:
    """Bloque focal: la parada en curso y cuánto queda por día hasta el check-out.

    `remaining_daily_usd` es la métrica que responde "¿salimos a comer hoy?":
    lo que sobra del presupuesto de la parada repartido en los días que faltan.
    Si vinieron gastando poco, sube.

    **Hoy cuenta** en los días restantes (`nights - lived + 1`): el último día
    `nights - lived` es 0 y la división explota justo cuando más se mira la
    página. Lo gastado hoy ya está adentro de `living_usd`, así que no hay
    doble conteo.

    El signo **no se clampea**: negativo significa que ya se pasaron del
    presupuesto de la ciudad, y eso hay que decirlo, no esconderlo en un cero.

    None si no hay parada en curso (viaje no empezado, terminado, o un día
    suelto fuera de rango).
    """
    row = next(
        (c for c in cities if c["status"] == "current" and c["in_itinerary"]), None
    )
    if row is None:
        return None

    nights = row["nights"]
    lived = row["elapsed_nights"]
    living = row["other_usd"]
    per_day = row["other_per_day_usd"]
    target = _target(targets, row["stop_slug"])
    remaining_days = max(nights - lived + 1, 1)

    if target is None or nights <= 0:
        budget_to_date = variance = remaining_budget = remaining_daily = None
    else:
        budget_to_date = target * lived
        variance = living - budget_to_date
        remaining_budget = target * nights - living
        remaining_daily = remaining_budget / remaining_days

    return {
        "stop_slug": row["stop_slug"],
        "city_name": row["city_name"],
        "country_flag": row["country_flag"],
        "arrival_date": row["arrival_date"],
        "departure_date": row["departure_date"],
        "lived_nights": lived,
        "total_nights": nights,
        "remaining_days": remaining_days,
        "target_daily_usd": target,
        "living_usd": living,
        "living_per_day_usd": per_day,
        "budget_to_date_usd": budget_to_date,
        "variance_usd": variance,
        "remaining_budget_usd": remaining_budget,
        "remaining_daily_usd": remaining_daily,
        "delta_pct": _delta_pct(per_day, target),
    }


def trip_plan(cities: list[dict], targets: Targets) -> dict:
    """El plan de vivir del viaje entero: lo que se ve antes de arrancar.

    Es también la pantalla donde se revisan los targets cargados mientras
    todavía se pueden ajustar. `next_stop` es la primera parada por venir.
    """
    eligible = _eligible(cities)
    cov = _coverage(eligible, targets)
    covered = cov["covered_nights"]
    budget = cov["living_budget_usd"]

    nxt = next((c for c in eligible if c["status"] == "future"), None)
    return {
        **cov,
        "avg_target_daily_usd": (budget / covered if budget is not None else None),
        "next_stop": (
            None
            if nxt is None
            else {
                "stop_slug": nxt["stop_slug"],
                "city_name": nxt["city_name"],
                "country_flag": nxt["country_flag"],
                "arrival_date": nxt["arrival_date"],
                "nights": nxt["nights"],
                "target_daily_usd": _target(targets, nxt["stop_slug"]),
            }
        ),
    }


def trip_budget_projection(
    cities: list[dict], targets: Targets, *, trip: dict
) -> dict:
    """Presupuesto de vivir del viaje contra la proyección del ritmo real.

    El ritmo sale **solo de las ciudades cerradas**, igual que
    `analytics._project`: la que está en curso todavía no tiene todos sus
    gastos cargados y las futuras solo tienen reservas adelantadas, así que
    incluirlas mezcla plata comprometida con ritmo real y hunde el número.
    """
    eligible = _eligible(cities)
    cov = _coverage(eligible, targets)

    living_to_date = sum(
        (c["other_usd"] for c in eligible if c["status"] != "future"), _ZERO
    )

    closed = [c for c in eligible if c["status"] == "past"]
    closed_nights = sum(c["nights"] for c in closed)
    run_rate = (
        sum((c["other_usd"] for c in closed), _ZERO) / closed_nights
        if closed_nights
        else None
    )
    projected = (
        run_rate * cov["budget_nights"]
        if run_rate is not None and cov["budget_nights"]
        else None
    )
    budget = cov["living_budget_usd"]

    return {
        **cov,
        "living_to_date_usd": living_to_date,
        "living_run_rate_usd": run_rate,
        "projected_living_usd": projected,
        "variance_usd": (
            projected - budget if projected is not None and budget is not None else None
        ),
    }


def fixed_block(
    cities: list[dict], *, general_usd: Decimal, total_nights: int
) -> dict:
    """Alojamiento + generales: lo fijo, mostrado aparte y sin veredicto.

    Son plata ya comprometida, no algo que se "gaste bien". El alojamiento suma
    **todas** las filas, archivadas incluidas: esa plata existió.
    """
    lodging = sum((c["lodging_usd"] for c in cities), _ZERO)
    return {
        "lodging_usd": lodging,
        "general_usd": general_usd,
        "total_usd": lodging + general_usd,
        "per_night_usd": lodging / total_nights if total_nights else None,
    }


def build_budget(pace: dict, targets: Targets, notes: Notes | None = None) -> dict:
    """Análisis completo. Único punto de entrada de la API y de la tool del bot.

    `pace` es el dict que devuelve `analytics.build_trip_pace`.
    """
    cities, trip = pace["cities"], pace["trip"]
    return {
        # El estado del viaje viaja explícito: el frontend lo necesita para
        # elegir el copy del bloque focal cuando no hay ciudad en curso, y
        # deducirlo de "no hay próxima parada" miente con un itinerario vacío.
        "trip_status": trip["status"],
        "current": current_city_budget(cities, targets),
        "plan": trip_plan(cities, targets),
        "cities": city_budget_rows(cities, targets, notes),
        "projection": trip_budget_projection(cities, targets, trip=trip),
        "fixed": fixed_block(
            cities,
            general_usd=trip["general_usd"],
            total_nights=trip["total_nights"],
        ),
    }
