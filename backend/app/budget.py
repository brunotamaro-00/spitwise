"""Presupuesto de "vivir": una banda por parada contra el gasto diario real.

Funciones puras (sin I/O), estilo balance.py/spend.py/analytics.py. El modelo:

- **"Vivir" no es un campo, es `other_usd`.** Es todo menos alojamiento y
  generales, y `analytics.build_trip_pace` ya lo calcula por ciudad: el
  alojamiento sale prorrateado por noches y los vuelos/pases/seguros no entran
  porque no tienen `stop_slug`. Todo en `user_share` (la parte del usuario).
- Por eso este módulo **consume la lista `cities` de `build_trip_pace`** y nunca
  re-agrega movimientos. Duplicar el prorrateo o `user_share` acá es la forma
  garantizada de que /ciudades y /presupuesto terminen diciendo cosas distintas.
- El **plan** (`StopBudget`) es un **rango** USD/día por persona, cargado a mano:
  `PRESUPUESTO.md` da bandas y colapsarlas a un punto era precisión falsa.
  - el **techo es el límite**: recién arriba de `max` se pasaron;
  - el **centro es el objetivo**: todos los agregados (devengado, varianza,
    colchón, proyección, `remaining_daily`) se miden contra `band.center`.
  Una banda de ancho cero (`min == max`) se comporta igual que el target de un
  solo número, y ese es el test de no-regresión de este módulo.
- Una parada sin banda no se compara ni se extrapola: baja la cobertura.
- **El costo del viaje entero (`trip_cost`) se compone, no se juzga.** Vivir
  proyectado + alojamiento (lo reservado más una estimación de las noches que
  faltan) + generales comprometidos. El veredicto contra la banda sigue midiendo
  **solo** vivir: dormir y los generales no se "gastan bien o mal".
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
from typing import Mapping, NamedTuple

_ZERO = Decimal("0")
_TWO = Decimal("2")


class Band(NamedTuple):
    """Plan diario de una parada: piso y techo, en USD por persona."""

    min: Decimal
    max: Decimal

    @property
    def center(self) -> Decimal:
        """El objetivo. Derivado y nunca persistido: guardarlo sería un tercer
        estado que puede quedar desincronizado de los bordes."""
        return (self.min + self.max) / _TWO


Bands = Mapping[str, Band]
Notes = Mapping[str, str]


def _band(bands: Bands, slug: str) -> Band | None:
    """Banda usable de una parada, o None.

    Una banda con piso <= 0 o con el techo debajo del piso se trata como
    ausente. La API ya lo impide (`Field(gt=0)` + validador), pero el módulo
    puro no confía en el borde: una fila vieja o un seed torcido no tienen que
    producir una división rara ni un delta infinito.
    """
    raw = bands.get(slug)
    if raw is None:
        return None
    lo, hi = Decimal(raw.min), Decimal(raw.max)
    return Band(lo, hi) if lo > 0 and hi >= lo else None


def band_position(per_day: Decimal | None, band: Band | None) -> str | None:
    """`under` (ahorrando) | `in` (en plan) | `over` (pasados). None sin datos."""
    if per_day is None or band is None:
        return None
    if per_day < band.min:
        return "under"
    if per_day > band.max:
        return "over"
    return "in"


def edge_delta_pct(per_day: Decimal | None, band: Band | None) -> float | None:
    """Desvío % contra el borde que se violó; None adentro de la banda.

    Adentro del rango no hay desvío que reportar — ese es el punto de tener un
    rango. Afuera, el % se mide contra el borde más cercano y no contra el
    centro: "te pasaste 9% del techo" es accionable, "estás 20% arriba del
    centro estando adentro del plan" es ruido.
    """
    pos = band_position(per_day, band)
    if pos == "over":
        return float((per_day / band.max - 1) * 100)
    if pos == "under":
        return float((per_day / band.min - 1) * 100)
    return None


def _delta_pct(per_day: Decimal | None, target: Decimal | None) -> float | None:
    """Desvío % del ritmo real contra el centro de la banda. Es la magnitud
    continua que consumen el bot y los agregados; el veredicto visual lo da
    `band_position`."""
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


def _covered(cities: list[dict], bands: Bands) -> list[tuple[dict, Band]]:
    """Elegibles que además tienen banda cargada."""
    out: list[tuple[dict, Band]] = []
    for c in _eligible(cities):
        band = _band(bands, c["stop_slug"])
        if band is not None:
            out.append((c, band))
    return out


def _coverage(eligible: list[dict], bands: Bands) -> dict:
    """Cuánto del itinerario tiene banda, y el presupuesto de lo cubierto."""
    budget_nights = 0
    covered_nights = 0
    uncovered: list[str] = []
    lo_total = hi_total = _ZERO
    for c in eligible:
        nights = c["nights"]
        budget_nights += nights
        band = _band(bands, c["stop_slug"])
        if band is None:
            uncovered.append(c["stop_slug"])
            continue
        covered_nights += nights
        lo_total += band.min * nights
        hi_total += band.max * nights
    return {
        "budget_nights": budget_nights,
        "covered_nights": covered_nights,
        "coverage_pct": (
            float(covered_nights * 100 / budget_nights) if budget_nights else None
        ),
        "uncovered_slugs": uncovered,
        # Nunca extrapolar una banda a una parada que no la tiene: el
        # presupuesto es el de lo cubierto, y la cobertura lo dice al lado.
        "living_budget_min_usd": lo_total if covered_nights else None,
        "living_budget_max_usd": hi_total if covered_nights else None,
        "living_budget_usd": (lo_total + hi_total) / _TWO if covered_nights else None,
    }


def category_mix(city: dict, trip: dict) -> list[dict]:
    """En qué se va el "vivir" de una parada, en proporción y en plata por día.

    **Dos lecturas, y las dos hacen falta.**

    - `share_pct` / `ratio` comparan **proporciones**: que en Viena hayas gastado
      más en café que en Praga puede ser solo que estuviste más días. Lo que dice
      algo es que el café sea el 22% de lo que gastás acá cuando en el viaje es
      el 9%. `ratio = share de la parada / share del viaje`.
    - `per_day_usd` / `delta_per_day_usd` dan la magnitud: "×1,7 de lo normal" no
      dice si son USD 3 o USD 30 por día, que es lo único accionable.

    **Las dos bases son distintas a propósito** (no unificarlas):
    el share va sobre lo **comprometido** (`living_by_category`, que incluye lo
    ya cargado a paradas futuras: es parte de la mezcla del viaje), y el $/día
    sobre lo **devengado** (`living_by_category_accrued`, sin paradas futuras),
    porque dividir plata de noches no vividas por las noches vividas infla el
    promedio. Ver el comentario de `analytics.build_trip_pace`.

    None en cualquier campo cuando falta la base contra la que comparar
    (categoría nueva, viaje sin gasto, o parada sin noches vividas).
    """
    living = city["other_usd"]
    trip_by_cat = trip.get("living_by_category") or {}
    trip_living = sum(trip_by_cat.values(), _ZERO)

    # Mismo divisor que `other_per_day_usd` de una parada en curso
    # (`analytics.build_trip_pace`), así la suma de los `per_day_usd` da el
    # $/día de vivir de la ciudad en vez de un número parecido pero distinto.
    lived = city.get("elapsed_nights") or 0
    trip_elapsed = trip.get("elapsed_nights") or 0
    trip_by_cat_day = trip.get("living_by_category_accrued") or {}

    rows: list[dict] = []
    for cat_id, amount in (city.get("living_by_category") or {}).items():
        if amount <= 0:
            continue
        share = float(amount * 100 / living) if living > 0 else None
        trip_amount = trip_by_cat.get(cat_id, _ZERO)
        trip_share = float(trip_amount * 100 / trip_living) if trip_living > 0 else None
        per_day = amount / lived if lived else None
        trip_per_day = (
            trip_by_cat_day.get(cat_id, _ZERO) / trip_elapsed if trip_elapsed else None
        )
        rows.append(
            {
                "category_id": cat_id,
                "living_usd": amount,
                "share_pct": share,
                "trip_share_pct": trip_share,
                "ratio": (
                    share / trip_share
                    if share is not None and trip_share
                    else None
                ),
                "per_day_usd": per_day,
                "trip_per_day_usd": trip_per_day,
                # Signo sin clampear: gastar menos que tu promedio es tan
                # informativo como gastar más.
                "delta_per_day_usd": (
                    per_day - trip_per_day
                    if per_day is not None and trip_per_day is not None
                    else None
                ),
            }
        )
    rows.sort(key=lambda r: r["living_usd"], reverse=True)
    return rows


def city_budget_rows(
    cities: list[dict], bands: Bands, notes: Notes | None = None
) -> list[dict]:
    """Una fila por ciudad: banda, gasto de vivir y posición contra el plan.

    El orden viene de `build_trip_pace` (archivadas al final, después por
    `order`), así que no se re-ordena.
    """
    notes = notes or {}
    rows: list[dict] = []
    for c in cities:
        slug = c["stop_slug"]
        band = _band(bands, slug)
        per_day = c["other_per_day_usd"]
        living = c["other_usd"]

        # Una futura solo tiene prepago imputado: no hay ritmo que comparar, y
        # gritar un +400% sobre una reserva es ruido. Espeja analytics.py.
        comparable = band is not None and c["status"] != "future"
        center = band.center if band is not None else None
        budget_accrued = center * c["elapsed_nights"] if comparable else None

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
                "target_min_usd": band.min if band else None,
                "target_max_usd": band.max if band else None,
                "target_daily_usd": center,
                "note": notes.get(slug),
                "living_usd": living,
                "living_per_day_usd": per_day,
                "budget_accrued_usd": budget_accrued,
                "variance_usd": (
                    living - budget_accrued if budget_accrued is not None else None
                ),
                "band_position": band_position(per_day, band) if comparable else None,
                "edge_delta_pct": edge_delta_pct(per_day, band) if comparable else None,
                "delta_pct": _delta_pct(per_day, center) if comparable else None,
            }
        )
    return rows


def current_city_budget(cities: list[dict], bands: Bands, *, trip: dict) -> dict | None:
    """Bloque focal: el **pote** de la parada en curso y cómo va el día de hoy.

    El hero de la página es `remaining_budget_usd`: lo que queda del pote de esta
    ciudad (`envelope_usd` = centro de la banda × noches). Es plata total, no una
    tasa, y por eso no salta con un almuerzo caro — la tasa por día
    (`remaining_daily_usd`) baja a ser su lectura secundaria.

    **El pote se arma contra el centro**, no contra el techo: el colchón, la
    proyección y la varianza ya se miden contra el centro (invariante 11), y un
    hero calculado con otro borde haría que la misma página se contradiga.
    `envelope_max_usd` viaja al lado solo como marca visual del margen que queda
    antes de pasarse.

    **Una sola tasa alimenta las dos lecturas**: `remaining_budget_usd`
    (= tasa × días restantes) y la sub-línea por día. Consecuencia deliberada:
    gastar hoy baja un poco la tasa de los días que quedan. El pote es finito y
    esconderlo sería el mismo error que tenía el hero anterior.

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
    band = _band(bands, row["stop_slug"])
    remaining_days = max(nights - lived + 1, 1)

    if band is None or nights <= 0:
        budget_to_date = variance = remaining_budget = remaining_daily = None
        envelope = envelope_max = None
    else:
        budget_to_date = band.center * lived
        variance = living - budget_to_date
        envelope = band.center * nights
        envelope_max = band.max * nights
        remaining_budget = envelope - living
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
        "target_min_usd": band.min if band else None,
        "target_max_usd": band.max if band else None,
        "target_daily_usd": band.center if band else None,
        "living_usd": living,
        "living_per_day_usd": per_day,
        "budget_to_date_usd": budget_to_date,
        "variance_usd": variance,
        # El pote de la parada y su techo: el hero es `remaining_budget_usd`
        # contra `envelope_usd`, y `envelope_max_usd` solo se marca en la barra.
        "envelope_usd": envelope,
        "envelope_max_usd": envelope_max,
        "remaining_budget_usd": remaining_budget,
        "remaining_daily_usd": remaining_daily,
        "band_position": band_position(per_day, band),
        "edge_delta_pct": edge_delta_pct(per_day, band),
        "delta_pct": _delta_pct(per_day, band.center if band else None),
        "by_category": category_mix(row, trip),
    }


def trip_cushion(cities: list[dict], bands: Bands) -> dict:
    """Colchón acumulado y ritmo necesario: la palanca de control del viaje.

    `cushion_usd` = lo que el plan devengó hasta hoy menos lo que se gastó de
    verdad. Positivo = ahorrado. El signo **no se clampea**: ir arriba del plan
    es información, no un error que haya que esconder.

    `needed_daily_usd` = a cuánto por día hay que ir en lo que queda para
    cerrar en plan. Es lo que responde "en la próxima ciudad nos ajustamos":
    sube solo si vienen ahorrando y baja si se pasaron.

    `remaining_nights` espeja la intención de `current_city_budget` (**hoy
    cuenta**), pero el "+1" solo se suma si hoy cae **dentro** de una parada
    cubierta: `covered_nights - covered_elapsed` ya son las noches que no se
    vivieron, y en un día de traslado entre dos paradas hoy no es ninguna de
    ellas — sumarlo igual inventaba una noche. Lo gastado hoy ya está adentro
    de `living_committed`, así que no hay doble conteo. Terminado el viaje no
    hay ritmo que pedir: None.
    """
    covered = _covered(cities, bands)

    started = [(c, b) for c, b in covered if c["status"] != "future"]
    budget_to_date = sum((b.center * c["elapsed_nights"] for c, b in started), _ZERO)
    living_to_date = sum((c["other_usd"] for c, _ in started), _ZERO)

    covered_nights = sum(c["nights"] for c, _ in covered)
    covered_elapsed = sum(c["elapsed_nights"] for c, _ in covered)
    budget_total = sum((b.center * c["nights"] for c, b in covered), _ZERO)
    # Todas las cubiertas, incluidas las futuras: una reserva de actividad ya
    # cargada consume presupuesto de vivir aunque la parada no haya empezado.
    living_committed = sum((c["other_usd"] for c, _ in covered), _ZERO)

    in_stop = any(c["status"] == "current" for c, _ in covered)
    ahead = in_stop or any(c["status"] == "future" for c, _ in covered)
    if not covered or not ahead:
        remaining_nights = 0
        needed_daily = None
    else:
        remaining_nights = max(
            covered_nights - covered_elapsed + (1 if in_stop else 0), 1
        )
        needed_daily = (budget_total - living_committed) / remaining_nights

    avg_target = budget_total / covered_nights if covered_nights else None

    return {
        "covered_nights": covered_nights,
        "budget_to_date_usd": budget_to_date if covered else None,
        "living_to_date_usd": living_to_date,
        "cushion_usd": (budget_to_date - living_to_date) if covered else None,
        "remaining_nights": remaining_nights,
        "needed_daily_usd": needed_daily,
        "avg_target_daily_usd": avg_target,
        "needed_delta_pct": _delta_pct(needed_daily, avg_target),
    }


def trip_plan(cities: list[dict], bands: Bands) -> dict:
    """El plan de vivir del viaje entero: lo que se ve antes de arrancar.

    Es también la pantalla donde se revisan las bandas cargadas mientras
    todavía se pueden ajustar. `next_stop` es la primera parada por venir.
    """
    eligible = _eligible(cities)
    cov = _coverage(eligible, bands)
    covered = cov["covered_nights"]
    budget = cov["living_budget_usd"]

    nxt = next((c for c in eligible if c["status"] == "future"), None)
    nxt_band = _band(bands, nxt["stop_slug"]) if nxt is not None else None
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
                "target_min_usd": nxt_band.min if nxt_band else None,
                "target_max_usd": nxt_band.max if nxt_band else None,
                "target_daily_usd": nxt_band.center if nxt_band else None,
            }
        ),
    }


def trip_budget_projection(cities: list[dict], bands: Bands, *, trip: dict) -> dict:
    """Presupuesto de vivir del viaje contra la proyección del ritmo real.

    El ritmo sale **solo de las ciudades cerradas**, igual que
    `analytics._project`: la que está en curso todavía no tiene todos sus
    gastos cargados y las futuras solo tienen reservas adelantadas, así que
    incluirlas mezcla plata comprometida con ritmo real y hunde el número.

    La varianza se mide contra el centro de las bandas; los bordes viajan al
    lado para que la página pueda mostrar el presupuesto como el rango que es.
    """
    eligible = _eligible(cities)
    cov = _coverage(eligible, bands)

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


def fixed_block(cities: list[dict], *, general_usd: Decimal, total_nights: int) -> dict:
    """Alojamiento + generales: lo fijo, mostrado aparte y sin veredicto.

    Son plata ya comprometida, no algo que se "gaste bien". El alojamiento suma
    **todas** las filas, archivadas incluidas: esa plata existió.

    El `per_night_usd` divide por las **noches efectivamente reservadas** (las
    de las paradas que tienen alojamiento cargado), no por `total_nights`: con
    el itinerario a medio reservar, dividir por el viaje entero mezcla plata ya
    comprometida con noches todavía sin pagar y sale un precio por noche que no
    es el de ningún hostel. Las noches salen de las paradas de Andiamo.
    """
    lodging = sum((c["lodging_usd"] for c in cities), _ZERO)
    booked_nights = sum(c["nights"] for c in cities if c["lodging_usd"] > 0)
    return {
        "lodging_usd": lodging,
        "general_usd": general_usd,
        "total_usd": lodging + general_usd,
        "booked_nights": booked_nights,
        "total_nights": total_nights,
        "per_night_usd": lodging / booked_nights if booked_nights else None,
    }


def trip_cost(projection: dict, fixed: dict) -> dict:
    """Cuánto sale el viaje entero: la suma de lo que la página muestra separado.

    Se arma con los dicts que ya construyeron `trip_budget_projection` y
    `fixed_block` — no re-agrega movimientos, igual que el resto del módulo.

    - **`basis` es el interruptor del copy**, no un detalle interno. Con al menos
      una ciudad cerrada hay run-rate y el total es una **proyección**; sin
      ninguna, el total es solo **lo comprometido hasta hoy** y presentarlo como
      proyección sería mentir. Viaja explícito para que el frontend no lo tenga
      que deducir de un `None` suelto.
    - **Los generales no se proyectan.** Los vuelos y pases del tramo que falta
      ya suelen estar comprados; extrapolar un $/día de generales inventaría
      plata. Misma decisión que `analytics._project`.
    - **La estimación de alojamiento usa `per_night_usd`**, que divide por las
      noches efectivamente reservadas (ver `fixed_block`): es el precio real que
      vienen pagando, no un promedio diluido sobre el viaje entero. Sin nada
      reservado no hay base para estimar y `lodging_estimated_usd` es None: no
      se inventa un precio por noche.
    - Las noches sin reservar salen de `fixed.total_nights` (días del itinerario)
      y **no** de `projection.budget_nights` (las elegibles, que excluyen las
      paradas del otro y las de 0 noches): el denominador de `booked_nights` es
      el universo de `fixed_block`, y cruzar los dos daría noches faltantes
      negativas o infladas. No "arreglarlo" unificándolos.

    Nota de coherencia: este es **el** total del viaje de la app (Dashboard y
    `/presupuesto` muestran el mismo bloque). `analytics._project`
    (`trip.projected_total_usd`: generales + noches × ritmo all-in de las
    cerradas) sigue en el payload de `/dashboard/pace` pero ya no se renderiza:
    ignora las reservas futuras ya cargadas, y tener dos totales distintos en
    dos pantallas era la forma garantizada de contradecirse.
    """
    total_nights = fixed["total_nights"]
    booked_nights = fixed["booked_nights"]
    per_night = fixed["per_night_usd"]

    unbooked = max(total_nights - booked_nights, 0)
    estimated = per_night * unbooked if per_night is not None else None
    lodging_projected = fixed["lodging_usd"] + (estimated or _ZERO)

    projected_living = projection["projected_living_usd"]
    living = (
        projected_living
        if projected_living is not None
        else projection["living_to_date_usd"]
    )
    general = fixed["general_usd"]

    return {
        "unbooked_nights": unbooked,
        "lodging_estimated_usd": estimated,
        "lodging_projected_usd": lodging_projected,
        "living_usd": living,
        "general_usd": general,
        "total_usd": living + lodging_projected + general,
        "basis": "projected" if projected_living is not None else "committed",
        "lodging_is_estimated": unbooked > 0 and estimated is not None,
    }


def build_budget(pace: dict, bands: Bands, notes: Notes | None = None) -> dict:
    """Análisis completo. Único punto de entrada de la API y de la tool del bot.

    `pace` es el dict que devuelve `analytics.build_trip_pace`.
    """
    cities, trip = pace["cities"], pace["trip"]
    projection = trip_budget_projection(cities, bands, trip=trip)
    fixed = fixed_block(
        cities,
        general_usd=trip["general_usd"],
        total_nights=trip["total_nights"],
    )
    return {
        # El estado del viaje viaja explícito: el frontend lo necesita para
        # elegir el copy del bloque focal cuando no hay ciudad en curso, y
        # deducirlo de "no hay próxima parada" miente con un itinerario vacío.
        "trip_status": trip["status"],
        "current": current_city_budget(cities, bands, trip=trip),
        "cushion": trip_cushion(cities, bands),
        "plan": trip_plan(cities, bands),
        "cities": city_budget_rows(cities, bands, notes),
        "projection": projection,
        "fixed": fixed,
        # El cierre: lo que la página muestra separado, sumado una sola vez.
        "cost": trip_cost(projection, fixed),
    }
