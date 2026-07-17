"""Ritmo del viaje: $/día con alojamiento prorrateado por noches.

Funciones puras (sin I/O), estilo balance.py/spend.py. El modelo:

- El alojamiento de una parada se prorratea entre sus noches (departure
  exclusivo), así el $/día es "all-in" y no pica el día que se paga.
- Los gastos generales (sin parada) se prorratean entre todas las noches
  del viaje: suman al ritmo global, nunca a una ciudad.
- Todo es personal (`user_share`): la parte del usuario, no el gross.
"""

from datetime import date, timedelta
from decimal import Decimal

from app.spend import user_share

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


def build_trip_pace(
    stops,
    movements,
    *,
    lodging_category_id: int | None,
    user_id: int,
    username: str | None,
    today: date,
) -> dict:
    """Arma el bloque de ritmo del viaje + una fila por ciudad.

    `stops` = todas las filas Stop; acá se filtra visibilidad (paradas con
    owner ajeno solo aparecen si el usuario tiene gastos imputados ahí).
    Devuelve Decimals/None crudos; el endpoint serializa.
    """
    visible = _visible(stops, username)
    by_slug = {s.slug: s for s in stops}

    # Itinerario del usuario: base del promedio y del devengado global.
    itinerary = [s for s in visible if not s.is_candidate and not s.is_archived]
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
        row = per_stop.setdefault(m.stop_slug, {"lodging": _ZERO, "other": _ZERO, "count": 0})
        if lodging_category_id is not None and m.category_id == lodging_category_id:
            row["lodging"] += share
        else:
            row["other"] += share
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
    for s in row_stops:
        agg = per_stop.get(s.slug, {"lodging": _ZERO, "other": _ZERO, "count": 0})
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
                "arrival_date": s.arrival_date,
                "departure_date": s.departure_date,
                "nights": nights,
                "elapsed_nights": lived,
                "movement_count": agg["count"],
                "total_usd": lodging + other,
                "lodging_usd": lodging,
                "other_usd": other,
                "per_day_usd": per_day,
                "lodging_per_night_usd": lodging_per_night,
                "other_per_day_usd": other_per_day,
            }
        )

    general_per_day = general / total_nights if total_nights else None
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

    run_rate = accrued / elapsed_nights if elapsed_nights else None
    projected = run_rate * total_nights if run_rate is not None else None
    # Baseline de comparación: el ritmo real si el viaje arrancó; si no, el
    # "previsto" (todo lo comprometido repartido en las noches del viaje).
    if run_rate is not None:
        avg_per_day = run_rate
    else:
        avg_per_day = total / total_nights if total_nights else None

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
        },
        "cities": cities,
    }
