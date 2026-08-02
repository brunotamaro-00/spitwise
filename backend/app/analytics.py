"""Ritmo del viaje: $/día con alojamiento prorrateado por noches.

Funciones puras (sin I/O), estilo balance.py/spend.py. El modelo:

- El alojamiento de una parada se prorratea entre sus noches (departure
  exclusivo), así el $/día es "all-in" y no pica el día que se paga.
- El ritmo (global y por ciudad) es *sin generales*: los vuelos, pases y
  seguros no pasan por ninguna ciudad, así que meterlos en la media dejaba a
  todas las ciudades debajo de la línea por construcción. Van aparte, en
  `general_usd` / `general_per_day_usd`, y solo entran en la proyección.
- Todo es personal (`user_share`): la parte del usuario, no el gross.
- `living_by_category` (por ciudad y del viaje) es el desglose de ese mismo
  "vivir" por categoría. Se agrega en este módulo, y no en `app/budget.py`,
  porque acá está el único loop que ya sabe qué movimiento es alojamiento y
  cuál es general: la suma del dict da `other_usd` por construcción, no por
  disciplina.
"""

from datetime import date, timedelta
from decimal import Decimal

from app.spend import user_share
from app.trip_time import day_in_tz

_ZERO = Decimal("0")


def stop_nights(stop) -> int:
    """Noches de la parada (departure exclusivo). Sin fechas => 0."""
    if not (stop.arrival_date and stop.departure_date):
        return 0
    return max((stop.departure_date - stop.arrival_date).days, 0)


def stop_status(stop, today: date) -> str:
    """past | current | future. Archivadas o sin fechas => past (la plata ya
    existe y no juega en proyecciones)."""
    if stop.is_archived or not stop.arrival_date:
        return "past"
    if today < stop.arrival_date:
        return "future"
    if stop.departure_date and today >= stop.departure_date:
        return "past"
    if not stop.departure_date:
        # Sin departure (candidatas con fechas raras): pasada una vez arribada.
        return "past"
    return "current"


def lived_days(stop, today: date) -> int:
    """Noches ya vividas de la parada (el día de llegada cuenta como día 1)."""
    status = stop_status(stop, today)
    nights = stop_nights(stop)
    if status == "future":
        return 0
    if status == "past":
        return nights
    return min((today - stop.arrival_date).days + 1, nights)


def itinerary_dates(stops) -> set[date]:
    """Fechas (noches) del itinerario, deduplicadas: paradas que solapan
    (Katia en Pititas mientras Bruno está en Portugal) no duplican días."""
    days: set[date] = set()
    for s in stops:
        if not (s.arrival_date and s.departure_date):
            continue
        d = s.arrival_date
        while d < s.departure_date:  # departure exclusivo: noches, no fechas
            days.add(d)
            d += timedelta(days=1)
    return days


def _visible(stops, username: str | None):
    u = (username or "").strip().lower() or None
    return [s for s in stops if s.owner_username is None or s.owner_username == u]


def _project(cities, total_nights: int, general: Decimal) -> Decimal | None:
    """Proyección del viaje entero = generales + noches × ritmo de lo cerrado.

    Solo se miran las ciudades ya terminadas: la que está en curso todavía no tiene
    todos sus gastos cargados y las futuras solo tienen reservas adelantadas, así
    que incluirlas mezclaba plata comprometida con ritmo real y hundía el número.
    Sin ninguna ciudad cerrada (primeros días) no hay proyección: None.
    """
    spent = _ZERO
    nights = 0
    for c in cities:
        if c["status"] != "past" or c["is_archived"] or c["nights"] <= 0:
            continue
        spent += c["total_usd"]
        nights += c["nights"]
    if not nights or not total_nights:
        return None
    return general + (spent / nights) * total_nights


def build_trip_pace(
    stops,
    movements,
    *,
    lodging_category_id: int | None,
    user_id: int,
    username: str | None,
    today: date,
    tz_name: str | None = None,
) -> dict:
    """Arma el bloque de ritmo del viaje + una fila por ciudad.

    `stops` = todas las filas Stop; acá se filtra visibilidad (paradas con
    owner ajeno solo aparecen si el usuario tiene gastos imputados ahí).
    Devuelve Decimals/None crudos; el endpoint serializa.

    `tz_name` es la misma tz con la que el caller resolvió `today`: se usa solo
    para `other_today_usd` (el gasto de vivir cargado hoy), que alimenta la fila
    HOY del hero de /presupuesto. Se agrega en este loop y no en `budget.py`
    porque este es el único lugar que ya separó alojamiento de vivir; abrir un
    segundo recorrido de movimientos allá es la forma garantizada de que las dos
    páginas empiecen a discrepar.
    """
    visible = _visible(stops, username)
    by_slug = {s.slug: s for s in stops}

    # Itinerario del usuario: base del promedio y del devengado global.
    itinerary = [s for s in visible if not s.is_candidate and not s.is_archived]
    # Qué paradas cuentan en `total_nights`. Se expone por fila (`in_itinerary`)
    # porque `app/budget.py` consume estas filas y necesita la misma frontera:
    # Pititas le aparece a Bruno si gastó ahí, pero sus noches no son suyas, y
    # sumarlas al presupuesto del viaje le inventaría 8 noches que no viaja.
    itin_slugs = {s.slug for s in itinerary}
    trip_days = itinerary_dates(itinerary)
    total_nights = len(trip_days)
    elapsed_nights = sum(1 for d in trip_days if d <= today)
    trip_start = min(trip_days) if trip_days else None
    trip_end = (max(trip_days) + timedelta(days=1)) if trip_days else None

    # Agregación de gastos por parada; sin parada (o slug huérfano) => general.
    per_stop: dict[str, dict] = {}
    general = _ZERO
    total = _ZERO
    for m in movements:
        share = user_share(m, user_id)
        if share <= 0:
            continue
        total += share
        if m.stop_slug is None or m.stop_slug not in by_slug:
            general += share
            continue
        row = per_stop.setdefault(
            m.stop_slug,
            {"lodging": _ZERO, "other": _ZERO, "today": _ZERO, "count": 0, "by_cat": {}},
        )
        if lodging_category_id is not None and m.category_id == lodging_category_id:
            row["lodging"] += share
        else:
            row["other"] += share
            # Eje temporal `created_at` (el día de carga), igual que la lista y
            # el agrupamiento por día del resto de la app — nunca `payment_date`.
            if day_in_tz(m.created_at, tz_name) == today:
                row["today"] += share
            # Desglose de "vivir" por categoría, agregado acá y no en budget.py:
            # este es el único loop que ya sabe qué es alojamiento y qué es
            # general, así que la suma del dict da `other_usd` por construcción.
            row["by_cat"][m.category_id] = (
                row["by_cat"].get(m.category_id, _ZERO) + share
            )
        row["count"] += 1

    # Filas: itinerario visible (sin candidatas) + cualquier parada ajena
    # donde el usuario tenga gastos (Bruno sigue viendo Pititas).
    row_slugs = {s.slug for s in visible if not s.is_candidate}
    row_slugs |= set(per_stop)
    row_stops = sorted(
        (by_slug[slug] for slug in row_slugs),
        key=lambda s: (s.is_archived, s.order),
    )

    cities: list[dict] = []
    accrued = _ZERO
    trip_by_cat: dict[int | None, Decimal] = {}
    trip_by_cat_accrued: dict[int | None, Decimal] = {}
    for s in row_stops:
        agg = per_stop.get(
            s.slug,
            {"lodging": _ZERO, "other": _ZERO, "today": _ZERO, "count": 0, "by_cat": {}},
        )
        lodging, other = agg["lodging"], agg["other"]
        nights = stop_nights(s)
        status = stop_status(s, today)
        lived = lived_days(s, today)

        lodging_per_night = lodging / nights if nights else None
        if nights == 0:
            other_per_day = per_day = None
        elif status == "current":
            other_per_day = other / lived
            per_day = (lodging_per_night * lived + other) / lived
        else:
            other_per_day = other / nights
            per_day = (lodging + other) / nights

        # Devengado: alojamiento prorrateado hasta hoy + el resto una vez
        # arrancada la parada. Paradas sin noches devengan todo al llegar.
        if nights:
            accrued += lodging_per_night * lived
            if status != "future":
                accrued += other
        elif status != "future":
            accrued += lodging + other

        cities.append(
            {
                "stop_slug": s.slug,
                "city_name": s.name,
                "country_flag": s.country_flag,
                "order": s.order,
                "status": status,
                "is_archived": s.is_archived,
                "is_transit": s.is_transit,
                "in_itinerary": s.slug in itin_slugs,
                "arrival_date": s.arrival_date,
                "departure_date": s.departure_date,
                "nights": nights,
                "elapsed_nights": lived,
                "movement_count": agg["count"],
                "total_usd": lodging + other,
                "lodging_usd": lodging,
                "other_usd": other,
                # Vivir cargado hoy en esta parada: un hecho del día, sin
                # comparación contra el plan (eso lo hace `budget.py`).
                "other_today_usd": agg["today"],
                "per_day_usd": per_day,
                "lodging_per_night_usd": lodging_per_night,
                "other_per_day_usd": other_per_day,
                "living_by_category": dict(agg["by_cat"]),
            }
        )
        for cat_id, amount in agg["by_cat"].items():
            trip_by_cat[cat_id] = trip_by_cat.get(cat_id, _ZERO) + amount
            # Base **devengada** de la mezcla: misma frontera que `accrued_cities`
            # (de donde sale `run_rate_usd`), o sea sin el `other` de las paradas
            # futuras. Existe aparte de `trip_by_cat` porque las dos preguntas
            # son distintas: el *share* se calcula sobre lo comprometido (una
            # entrada ya pagada de la próxima ciudad es parte de la mezcla),
            # pero un **$/día** dividido por las noches vividas no puede incluir
            # plata de noches que todavía no se vivieron.
            if status != "future":
                trip_by_cat_accrued[cat_id] = (
                    trip_by_cat_accrued.get(cat_id, _ZERO) + amount
                )

    general_per_day = general / total_nights if total_nights else None
    # `accrued` venía solo de ciudades: ese es el ritmo que se compara contra
    # las barras. El devengado total suma aparte los generales prorrateados.
    accrued_cities = accrued
    if total_nights and elapsed_nights:
        accrued += general * elapsed_nights / total_nights

    if trip_start is None:
        trip_status = "not_started"
    elif today < trip_start:
        trip_status = "not_started"
    elif today >= trip_end:
        trip_status = "finished"
    else:
        trip_status = "in_progress"

    # Ritmo y baseline: siempre sin generales, para que sea la misma unidad que
    # el $/día de cada ciudad. Con generales adentro, ninguna ciudad podía
    # llegar a la media y todas las comparaciones daban negativas.
    run_rate = accrued_cities / elapsed_nights if elapsed_nights else None
    if run_rate is not None:
        avg_per_day = run_rate
    else:
        # Pre-viaje: lo comprometido en ciudades repartido en las noches.
        avg_per_day = (total - general) / total_nights if total_nights else None

    projected = _project(cities, total_nights, general)

    for c in cities:
        if c["status"] == "future" or c["per_day_usd"] is None or not avg_per_day:
            c["delta_vs_trip_pct"] = None
        else:
            c["delta_vs_trip_pct"] = float((c["per_day_usd"] / avg_per_day - 1) * 100)

    return {
        "trip": {
            "status": trip_status,
            "start": trip_start,
            "end": trip_end,
            "total_nights": total_nights,
            "elapsed_nights": elapsed_nights,
            "total_usd": total,
            "general_usd": general,
            "general_per_day_usd": general_per_day,
            "avg_per_day_usd": avg_per_day,
            "run_rate_usd": run_rate,
            "accrued_usd": accrued,
            "projected_total_usd": projected,
            # Mezcla de "vivir" de todo el viaje: la baseline contra la que se
            # compara la de una parada. Suma de las ciudades ⇒ sin generales.
            "living_by_category": trip_by_cat,
            # La misma mezcla pero solo de lo ya devengado. Su suma es el
            # "vivir" acumulado del viaje (sin alojamiento, a diferencia de
            # `run_rate_usd`), así que dividida por `elapsed_nights` da el
            # $/día de vivir: la baseline honesta del desglose por categoría.
            "living_by_category_accrued": trip_by_cat_accrued,
        },
        "cities": cities,
    }
