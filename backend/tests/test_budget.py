"""build_budget: la banda de vivir por parada contra el gasto real.

Los helpers llaman `build_trip_pace` **real** y le pasan el resultado a
`build_budget`. Es a propósito: el riesgo de esta arquitectura no es la
aritmética del presupuesto, es que los dos módulos se desacoplen y /ciudades
termine diciendo un número y /presupuesto otro.

`plans` acepta un escalar o un par `(min, max)`. Un escalar arma una **banda de
ancho cero**, que se comporta exactamente como el target de un solo número que
había antes: por eso toda la batería vieja de tests sigue escrita con escalares
y funciona como el test de no-regresión del modelo de rango.
"""

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.analytics import build_trip_pace
from app.budget import Band, band_position, build_budget, edge_delta_pct

LODGING = 1  # category_id de Alojamiento en estos tests
OTHER = 2


def _stop(slug, order=1, arrival=None, departure=None, **kw):
    base = dict(
        slug=slug, order=order, name=slug.title(), country_flag=None,
        arrival_date=arrival, departure_date=departure,
        is_transit=False, is_candidate=False, is_archived=False,
        is_local=False, owner_username=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _mov(slug, usd, cat=OTHER, split="shared", paid_by=1, loaded=None):
    """`loaded` = día de carga (`created_at`). Default: una fecha vieja, así el
    gasto no cae "hoy" salvo en los tests de la fila HOY."""
    day = loaded or date(2000, 1, 1)
    return SimpleNamespace(
        type="expense", split=split, amount_usd=Decimal(usd),
        paid_by=paid_by, stop_slug=slug, category_id=cat,
        created_at=datetime(day.year, day.month, day.day, 12, 0),
    )


def _band(v) -> Band:
    """Escalar => banda de ancho cero (el target de un solo número de antes)."""
    if isinstance(v, (tuple, list)):
        return Band(Decimal(str(v[0])), Decimal(str(v[1])))
    return Band(Decimal(str(v)), Decimal(str(v)))


def _budget(stops, movements, today, targets=None, username="bruno", user_id=1):
    pace = build_trip_pace(
        stops, movements, lodging_category_id=LODGING,
        user_id=user_id, username=username, today=today,
    )
    return build_budget(pace, {k: _band(v) for k, v in (targets or {}).items()})


def _row(data, slug):
    return next(c for c in data["cities"] if c["stop_slug"] == slug)


ROMA = _stop("roma", arrival=date(2026, 8, 1), departure=date(2026, 8, 11))  # 10 noches


def test_delta_against_target():
    """10 noches, vivir 600 (share) => 60/día contra un target de 50 = +20%."""
    data = _budget([ROMA], [_mov("roma", "1200")], date(2026, 9, 1), {"roma": "50"})
    r = _row(data, "roma")
    assert r["living_usd"] == Decimal("600")
    assert r["living_per_day_usd"] == Decimal("60")
    assert r["target_daily_usd"] == Decimal("50")
    assert r["delta_pct"] == 20.0
    assert r["budget_accrued_usd"] == Decimal("500")
    assert r["variance_usd"] == Decimal("100")


def test_lodging_is_not_living():
    """El alojamiento no entra en vivir: sale por el bucket de fijos."""
    movs = [_mov("roma", "2000", cat=LODGING), _mov("roma", "200")]
    data = _budget([ROMA], movs, date(2026, 9, 1), {"roma": "50"})
    r = _row(data, "roma")
    assert r["living_usd"] == Decimal("100")      # solo la comida, no los 1000
    assert r["living_per_day_usd"] == Decimal("10")
    assert data["fixed"]["lodging_usd"] == Decimal("1000")
    assert data["fixed"]["per_night_usd"] == Decimal("100")
    assert data["fixed"]["booked_nights"] == 10


def test_per_night_divides_by_booked_nights_only():
    """El precio por noche es el de las noches reservadas, no las del viaje.

    Con media Europa sin reservar, dividir por `total_nights` daría un precio
    por noche que no es el de ningún hostel (la mitad, acá).
    """
    paris = _stop("paris", order=2, arrival=date(2026, 8, 11), departure=date(2026, 8, 21))
    movs = [_mov("roma", "2000", cat=LODGING)]  # 1000 de share, solo Roma reservada
    data = _budget([ROMA, paris], movs, date(2026, 9, 1))
    assert data["fixed"]["booked_nights"] == 10   # no las 20 del itinerario
    assert data["fixed"]["total_nights"] == 20
    assert data["fixed"]["per_night_usd"] == Decimal("100")


def test_generals_are_not_living():
    """Vuelos/pases/seguros (sin stop_slug) no tocan ninguna ciudad."""
    movs = [_mov(None, "600"), _mov("roma", "200")]
    data = _budget([ROMA], movs, date(2026, 9, 1), {"roma": "50"})
    assert _row(data, "roma")["living_usd"] == Decimal("100")
    assert data["fixed"]["general_usd"] == Decimal("300")
    assert data["projection"]["living_to_date_usd"] == Decimal("100")


def test_current_city_remaining_daily():
    """Día 4 de 10, target 50, llevan 300: sobran 200 para 7 días (hoy incluido)."""
    data = _budget([ROMA], [_mov("roma", "600")], date(2026, 8, 4), {"roma": "50"})
    cur = data["current"]
    assert cur["stop_slug"] == "roma"
    assert (cur["lived_nights"], cur["total_nights"]) == (4, 10)
    assert cur["living_usd"] == Decimal("300")
    assert cur["budget_to_date_usd"] == Decimal("200")
    assert cur["variance_usd"] == Decimal("100")
    assert cur["remaining_days"] == 7
    assert cur["remaining_budget_usd"] == Decimal("200")
    assert round(cur["remaining_daily_usd"], 2) == Decimal("28.57")


def test_envelope_is_the_center_times_the_nights():
    """El pote del hero va contra el centro; el techo solo viaja como marca."""
    data = _budget([ROMA], [_mov("roma", "600")], date(2026, 8, 4), {"roma": (40, 60)})
    cur = data["current"]
    assert cur["envelope_usd"] == Decimal("500")  # centro 50 x 10 noches
    assert cur["envelope_max_usd"] == Decimal("600")  # techo 60 x 10
    # El hero es el pote menos lo gastado, y la tasa lo reparte: los tres cierran.
    assert cur["remaining_budget_usd"] == cur["envelope_usd"] - cur["living_usd"]
    assert (
        cur["remaining_daily_usd"] * cur["remaining_days"]
        == cur["remaining_budget_usd"]
    )


def test_today_row_counts_only_living_loaded_today():
    """La fila HOY: vivir cargado hoy en la parada. El alojamiento de hoy y el
    gasto de ayer no entran."""
    hoy = date(2026, 8, 4)
    movs = [
        _mov("roma", "600"),                          # cargado hace años
        _mov("roma", "40", loaded=hoy),               # vivir de hoy
        _mov("roma", "1000", cat=LODGING, loaded=hoy),  # dormir no es vivir
        _mov("roma", "80", loaded=date(2026, 8, 3)),  # ayer
    ]
    cur = _budget([ROMA], movs, hoy, {"roma": "50"})["current"]
    assert cur["spent_today_usd"] == Decimal("20")  # share de los 40
    # Una sola tasa: el presupuesto del día es la misma que reparte el pote.
    assert cur["left_today_usd"] == cur["remaining_daily_usd"] - Decimal("20")


def test_today_row_exists_without_a_band():
    """El gasto de hoy es un hecho, no una comparación: se expone igual. Lo que
    no existe sin banda es el permiso del día."""
    hoy = date(2026, 8, 4)
    cur = _budget([ROMA], [_mov("roma", "40", loaded=hoy)], hoy)["current"]
    assert cur["spent_today_usd"] == Decimal("20")
    assert cur["left_today_usd"] is None
    assert cur["envelope_usd"] is None


def test_today_row_is_negative_when_the_day_is_blown():
    """Gastar hoy más que la tasa del día se dice con signo, no con un cero."""
    hoy = date(2026, 8, 4)
    # Pote 500, llevan 300 + 120 de hoy => quedan 80 para 7 días (11,43/día).
    movs = [_mov("roma", "600"), _mov("roma", "240", loaded=hoy)]
    cur = _budget([ROMA], movs, hoy, {"roma": "50"})["current"]
    assert cur["spent_today_usd"] == Decimal("120")
    assert cur["left_today_usd"] < 0


def test_no_daily_allowance_once_the_envelope_is_empty():
    """Pasados de pote, la fila HOY se queda con el hecho del día: restarle el
    gasto de hoy a una tasa negativa mezcla el exceso de toda la parada con el
    del día. El exceso ya lo cuenta el hero."""
    hoy = date(2026, 8, 4)
    movs = [_mov("roma", "1400"), _mov("roma", "80", loaded=hoy)]
    cur = _budget([ROMA], movs, hoy, {"roma": "50"})["current"]
    assert cur["remaining_daily_usd"] < 0
    assert cur["spent_today_usd"] == Decimal("40")
    assert cur["left_today_usd"] is None


def test_last_day_has_no_division_by_zero():
    """El último día quedan 0 noches por delante: hoy cuenta, así que da 1."""
    data = _budget([ROMA], [_mov("roma", "600")], date(2026, 8, 10), {"roma": "50"})
    cur = data["current"]
    assert cur["lived_nights"] == 10
    assert cur["remaining_days"] == 1
    assert cur["remaining_daily_usd"] == Decimal("200")  # 500 - 300


def test_over_budget_remaining_is_negative():
    """Pasarse se dice, no se esconde en un cero."""
    data = _budget([ROMA], [_mov("roma", "1400")], date(2026, 8, 4), {"roma": "50"})
    cur = data["current"]
    assert cur["living_usd"] == Decimal("700")
    assert cur["remaining_budget_usd"] == Decimal("-200")
    assert cur["remaining_daily_usd"] < 0
    assert cur["variance_usd"] == Decimal("500")  # 700 gastado vs 200 devengado


def test_stop_without_target():
    """La fila existe con su gasto, pero no se compara ni se extrapola."""
    data = _budget([ROMA], [_mov("roma", "600")], date(2026, 9, 1))
    r = _row(data, "roma")
    assert r["living_usd"] == Decimal("300")
    assert r["target_daily_usd"] is None
    assert r["delta_pct"] is None
    assert r["budget_accrued_usd"] is None
    assert r["variance_usd"] is None
    assert data["projection"]["uncovered_slugs"] == ["roma"]


def test_zero_night_stop_out_of_coverage():
    stops = [
        ROMA,
        _stop("transito", order=2, arrival=date(2026, 8, 11),
              departure=date(2026, 8, 11), is_transit=True),
    ]
    data = _budget(stops, [_mov("transito", "100")], date(2026, 9, 1),
                   {"roma": "50", "transito": "50"})
    r = _row(data, "transito")
    assert r["living_usd"] == Decimal("50")
    assert r["living_per_day_usd"] is None
    assert r["delta_pct"] is None
    assert data["projection"]["budget_nights"] == 10  # solo Roma


def test_future_city_has_no_delta():
    """Una futura solo tiene prepago: comparar su ritmo es ruido."""
    stops = [ROMA, _stop("paris", order=2, arrival=date(2026, 9, 1),
                         departure=date(2026, 9, 6))]
    movs = [_mov("roma", "200"), _mov("paris", "300")]
    data = _budget(stops, movs, date(2026, 8, 4), {"roma": "50", "paris": "50"})
    r = _row(data, "paris")
    assert r["status"] == "future"
    assert r["living_usd"] == Decimal("150")
    assert r["delta_pct"] is None
    assert r["budget_accrued_usd"] is None
    assert r["variance_usd"] is None
    assert _row(data, "roma")["delta_pct"] is not None


def test_trip_not_started_shows_the_plan():
    """Antes de arrancar no hay ciudad en curso ni proyección, pero sí plan."""
    stops = [ROMA, _stop("paris", order=2, arrival=date(2026, 8, 11),
                         departure=date(2026, 8, 16))]
    data = _budget(stops, [], date(2026, 7, 1), {"roma": "50", "paris": "80"})
    assert data["current"] is None
    assert data["projection"]["projected_living_usd"] is None
    plan = data["plan"]
    assert plan["living_budget_usd"] == Decimal("900")   # 50*10 + 80*5
    assert plan["avg_target_daily_usd"] == Decimal("60")  # 900 / 15 noches
    assert plan["coverage_pct"] == 100.0
    assert plan["next_stop"]["stop_slug"] == "roma"       # la primera por venir
    assert plan["next_stop"]["target_daily_usd"] == Decimal("50")


def test_archived_stop_out_of_coverage():
    """Su plata se ve, pero no tiene noches que presupuestar."""
    stops = [ROMA, _stop("vieja", order=2, arrival=date(2026, 7, 1),
                         departure=date(2026, 7, 3), is_archived=True)]
    data = _budget(stops, [_mov("vieja", "60")], date(2026, 9, 1),
                   {"roma": "50", "vieja": "50"})
    assert _row(data, "vieja")["living_usd"] == Decimal("30")
    assert data["projection"]["budget_nights"] == 10
    assert data["projection"]["covered_nights"] == 10


def test_foreign_owner_stop_out_of_projection():
    """Pititas le aparece a Bruno si gastó ahí, pero sus 8 noches no son suyas:
    sumarlas le inventaría presupuesto de un tramo que no viaja."""
    # Portugal lleva owner=bruno como en producción: se lo pone
    # stops_local._sync_counterpart_owner por estar contenida en la ventana de
    # Pititas. Sin eso las dos paradas se solapan y "la ciudad en curso" queda
    # decidida por `order`, que no es de nadie.
    stops = [
        _stop("portugal", order=1, arrival=date(2026, 9, 4), departure=date(2026, 9, 12),
              owner_username="bruno"),
        _stop("pititas", order=2, arrival=date(2026, 9, 4), departure=date(2026, 9, 12),
              is_local=True, owner_username="katia"),
    ]
    movs = [_mov("portugal", "160"), _mov("pititas", "80")]
    targets = {"portugal": "50", "pititas": "50"}
    bruno = _budget(stops, movs, date(2026, 9, 6), targets)

    assert _row(bruno, "pititas")["in_itinerary"] is False
    assert _row(bruno, "pititas")["living_usd"] == Decimal("40")  # la fila existe
    assert bruno["projection"]["budget_nights"] == 8              # NO 16
    assert bruno["projection"]["living_budget_usd"] == Decimal("400")
    assert bruno["current"]["stop_slug"] == "portugal"

    # Para Katia, Pititas sí es su itinerario (y Portugal no le aparece).
    katia = _budget(stops, movs, date(2026, 9, 6), targets,
                    username="katia", user_id=2)
    assert katia["current"]["stop_slug"] == "pititas"
    assert katia["projection"]["budget_nights"] == 8


def test_partial_coverage():
    """Con targets a medias, el presupuesto es el de lo cubierto y la
    cobertura lo dice al lado."""
    stops = [ROMA, _stop("paris", order=2, arrival=date(2026, 8, 11),
                         departure=date(2026, 8, 16))]
    data = _budget(stops, [], date(2026, 7, 1), {"roma": "50"})
    p = data["projection"]
    assert p["budget_nights"] == 15
    assert p["covered_nights"] == 10
    assert round(p["coverage_pct"], 1) == 66.7
    assert p["uncovered_slugs"] == ["paris"]
    assert p["living_budget_usd"] == Decimal("500")  # sin extrapolar a París


def test_zero_coverage_has_no_budget():
    data = _budget([ROMA], [_mov("roma", "600")], date(2026, 9, 1))
    p = data["projection"]
    assert p["coverage_pct"] == 0.0
    assert p["living_budget_usd"] is None
    assert p["variance_usd"] is None
    assert data["plan"]["avg_target_daily_usd"] is None


def test_projection_uses_closed_cities_only():
    """El ritmo sale de lo cerrado: la ciudad en curso no tiene todos sus
    gastos y las futuras solo tienen reservas."""
    stops = [
        ROMA,
        _stop("paris", order=2, arrival=date(2026, 8, 11), departure=date(2026, 8, 16)),
        _stop("niza", order=3, arrival=date(2026, 9, 1), departure=date(2026, 9, 6)),
    ]
    movs = [_mov("roma", "1000"), _mov("paris", "200"), _mov("niza", "600")]
    targets = {"roma": "50", "paris": "50", "niza": "50"}
    data = _budget(stops, movs, date(2026, 8, 13), targets)  # día 3 de París
    p = data["projection"]
    assert p["budget_nights"] == 20
    assert p["living_run_rate_usd"] == Decimal("50")       # 500 / 10 (solo Roma)
    assert p["projected_living_usd"] == Decimal("1000")    # 50 * 20
    assert p["living_budget_usd"] == Decimal("1000")
    assert p["variance_usd"] == Decimal("0")
    assert p["living_to_date_usd"] == Decimal("600")       # Niza es futura


def test_negative_target_treated_as_missing():
    """El módulo puro no confía en el borde aunque la API valide gt=0."""
    data = _budget([ROMA], [_mov("roma", "600")], date(2026, 9, 1), {"roma": "-5"})
    r = _row(data, "roma")
    assert r["target_daily_usd"] is None
    assert r["delta_pct"] is None
    assert data["projection"]["uncovered_slugs"] == ["roma"]


def test_shares_are_personal():
    """other_only pagado por bruno es consumo de katia: no es su vivir."""
    movs = [_mov("roma", "100", split="other_only", paid_by=1)]
    bruno = _budget([ROMA], movs, date(2026, 9, 1), {"roma": "50"})
    katia = _budget([ROMA], movs, date(2026, 9, 1), {"roma": "50"},
                    username="katia", user_id=2)
    assert _row(bruno, "roma")["living_usd"] == Decimal("0")
    assert _row(katia, "roma")["living_usd"] == Decimal("100")


# --------------------------------------------------------------- banda (rango)


def test_band_positions():
    """Las tres lecturas de una banda 40–60, sobre la misma parada de 10 noches."""
    def pos(usd):
        data = _budget([ROMA], [_mov("roma", usd)], date(2026, 9, 1),
                       {"roma": (40, 60)})
        return _row(data, "roma")

    ahorrando = pos("600")   # 300 share => 30/día, debajo del piso
    en_plan = pos("1000")    # 500 share => 50/día, justo en el centro
    pasados = pos("1400")    # 700 share => 70/día, arriba del techo

    assert ahorrando["band_position"] == "under"
    assert en_plan["band_position"] == "in"
    assert pasados["band_position"] == "over"

    assert ahorrando["target_min_usd"] == Decimal("40")
    assert ahorrando["target_max_usd"] == Decimal("60")
    assert ahorrando["target_daily_usd"] == Decimal("50")   # el centro


def test_edge_delta_is_measured_against_the_violated_edge():
    """Adentro de la banda no hay desvío que reportar: ese es el punto del rango.
    Afuera, el % se mide contra el borde violado, no contra el centro."""
    data = _budget([ROMA], [_mov("roma", "1320")], date(2026, 9, 1), {"roma": (40, 60)})
    r = _row(data, "roma")
    assert r["living_per_day_usd"] == Decimal("66")
    assert r["edge_delta_pct"] == 10.0          # 66 vs el techo de 60
    assert r["delta_pct"] == 32.0               # 66 vs el centro de 50

    dentro = _budget([ROMA], [_mov("roma", "1100")], date(2026, 9, 1), {"roma": (40, 60)})
    assert _row(dentro, "roma")["edge_delta_pct"] is None
    assert _row(dentro, "roma")["delta_pct"] == 10.0


def test_band_helpers_are_defensive():
    """El módulo puro no confía en la DB: banda invertida o con piso <= 0 se
    trata como ausente, igual que un target negativo."""
    assert band_position(Decimal("50"), None) is None
    assert edge_delta_pct(None, Band(Decimal("40"), Decimal("60"))) is None

    invertida = _budget([ROMA], [_mov("roma", "600")], date(2026, 9, 1),
                        {"roma": (60, 40)})
    assert _row(invertida, "roma")["target_daily_usd"] is None
    assert invertida["projection"]["uncovered_slugs"] == ["roma"]


def test_projection_carries_both_edges():
    """El total del viaje se muestra como rango; la varianza sigue contra el centro."""
    data = _budget([ROMA], [_mov("roma", "1000")], date(2026, 9, 1), {"roma": (40, 60)})
    p = data["projection"]
    assert p["living_budget_min_usd"] == Decimal("400")
    assert p["living_budget_max_usd"] == Decimal("600")
    assert p["living_budget_usd"] == Decimal("500")
    assert p["variance_usd"] == Decimal("0")     # ritmo 50/día = el centro


def test_next_stop_shows_the_band():
    stops = [ROMA, _stop("paris", order=2, arrival=date(2026, 9, 1),
                         departure=date(2026, 9, 6))]
    data = _budget(stops, [], date(2026, 8, 5), {"roma": 50, "paris": (30, 50)})
    nxt = data["plan"]["next_stop"]
    assert nxt["stop_slug"] == "paris"
    assert (nxt["target_min_usd"], nxt["target_max_usd"]) == (Decimal("30"), Decimal("50"))
    assert nxt["target_daily_usd"] == Decimal("40")


# ---------------------------------------------------------- colchón del viaje


def test_cushion_positive_raises_the_needed_rate():
    """Roma cerrada gastando la mitad del plan: el colchón es positivo y lo que
    queda por día sube por encima del promedio del plan."""
    stops = [ROMA, _stop("paris", order=2, arrival=date(2026, 8, 11),
                         departure=date(2026, 8, 21))]
    # Roma: 250 share en 10 noches = 25/día contra un centro de 50 => +250 de colchón.
    data = _budget(stops, [_mov("roma", "500")], date(2026, 8, 11),
                   {"roma": (40, 60), "paris": (40, 60)})
    c = data["cushion"]
    assert c["covered_nights"] == 20
    # 10 noches de Roma + el día 1 de París, que ya se vivió.
    assert c["budget_to_date_usd"] == Decimal("550")
    assert c["living_to_date_usd"] == Decimal("250")
    assert c["cushion_usd"] == Decimal("300")
    assert c["avg_target_daily_usd"] == Decimal("50")
    # Día 1 de París: quedan 10 noches (hoy cuenta) y 750 de presupuesto.
    assert c["remaining_nights"] == 10
    assert c["needed_daily_usd"] == Decimal("75")
    assert c["needed_delta_pct"] == 50.0


def test_cushion_negative_lowers_the_needed_rate():
    stops = [ROMA, _stop("paris", order=2, arrival=date(2026, 8, 11),
                         departure=date(2026, 8, 21))]
    # Roma: 750 share en 10 noches = 75/día contra 50 => -250 de colchón.
    data = _budget(stops, [_mov("roma", "1500")], date(2026, 8, 11),
                   {"roma": (40, 60), "paris": (40, 60)})
    c = data["cushion"]
    assert c["cushion_usd"] == Decimal("-200")   # 550 devengado vs 750 gastado
    assert c["needed_daily_usd"] == Decimal("25")
    assert c["needed_delta_pct"] == -50.0


def test_cushion_counts_prepaid_of_future_stops():
    """Una actividad ya pagada de una parada futura consume presupuesto de vivir
    aunque la parada no haya empezado: no puede quedar afuera del ritmo necesario.

    Hoy (11/8) es un día de traslado: Roma cerró y París todavía no empieza, así
    que hoy NO suma una noche a las que quedan."""
    stops = [ROMA, _stop("paris", order=2, arrival=date(2026, 9, 1),
                         departure=date(2026, 9, 11))]
    movs = [_mov("roma", "1000"), _mov("paris", "400")]  # 500 + 200 de share
    data = _budget(stops, movs, date(2026, 8, 11), {"roma": 50, "paris": 50})
    c = data["cushion"]
    assert c["living_to_date_usd"] == Decimal("500")     # el devengado excluye futuras
    assert c["cushion_usd"] == Decimal("0")
    # 1000 de presupuesto total − 700 ya comprometidos, en las 10 noches de París.
    assert c["needed_daily_usd"] == Decimal("30")


def test_cushion_is_empty_without_bands_and_after_the_trip():
    sin_banda = _budget([ROMA], [_mov("roma", "600")], date(2026, 8, 5))
    assert sin_banda["cushion"]["cushion_usd"] is None
    assert sin_banda["cushion"]["needed_daily_usd"] is None

    terminado = _budget([ROMA], [_mov("roma", "600")], date(2026, 12, 1), {"roma": 50})
    assert terminado["cushion"]["cushion_usd"] == Decimal("200")  # el balance queda
    assert terminado["cushion"]["remaining_nights"] == 0
    assert terminado["cushion"]["needed_daily_usd"] is None       # no hay ritmo que pedir


def test_cushion_before_the_trip_spreads_over_every_night():
    data = _budget([ROMA], [], date(2026, 7, 1), {"roma": 50})
    c = data["cushion"]
    assert c["remaining_nights"] == 10        # sin días vividos, no se suma "hoy"
    assert c["needed_daily_usd"] == Decimal("50")


# -------------------------------------------------------- en qué se te va


def test_category_mix_compares_proportions_not_amounts():
    """La mezcla de la parada contra la del viaje. Roma se lleva el 100% del
    café del viaje, así que su share duplica al del viaje."""
    FOOD, COFFEE = 2, 3
    stops = [ROMA, _stop("paris", order=2, arrival=date(2026, 7, 20),
                         departure=date(2026, 7, 30))]
    movs = [
        _mov("roma", "400", cat=FOOD),      # 200 share
        _mov("roma", "400", cat=COFFEE),    # 200 share
        _mov("paris", "800", cat=FOOD),     # 400 share, otra parada
    ]
    data = _budget(stops, movs, date(2026, 8, 5), {"roma": 50, "paris": 50})
    mix = data["current"]["by_category"]

    assert [m["category_id"] for m in mix] == [FOOD, COFFEE]  # ordenado desc
    comida, cafe = mix
    assert comida["living_usd"] == Decimal("200")
    assert comida["share_pct"] == 50.0
    assert comida["trip_share_pct"] == 75.0                  # 600 de 800
    assert round(comida["ratio"], 3) == 0.667
    assert cafe["trip_share_pct"] == 25.0
    assert cafe["ratio"] == 2.0                              # el doble de lo normal


def test_category_mix_per_day_sums_to_the_city_rate():
    """Canario de unidad: el $/día por categoría tiene que usar el MISMO divisor
    que `other_per_day_usd`, o el desglose no cierra con el total de la ciudad."""
    FOOD, COFFEE = 2, 3
    movs = [_mov("roma", "400", cat=FOOD), _mov("roma", "200", cat=COFFEE)]
    data = _budget([ROMA], movs, date(2026, 8, 5), {"roma": 50})  # día 5 de 10
    cur = data["current"]

    assert sum(m["per_day_usd"] for m in cur["by_category"]) == cur["living_per_day_usd"]
    comida, cafe = cur["by_category"]
    assert comida["per_day_usd"] == Decimal("40")   # 200 de share en 5 días
    assert cafe["per_day_usd"] == Decimal("20")


def test_category_mix_delta_against_the_trip_average():
    """Roma se come el café: acá va a USD 20/día contra un promedio de 10."""
    FOOD, COFFEE = 2, 3
    stops = [_stop("paris", order=1, arrival=date(2026, 7, 22),
                   departure=date(2026, 8, 1)), ROMA]
    movs = [
        _mov("paris", "400", cat=FOOD),     # 200 share en 10 noches
        _mov("roma", "200", cat=COFFEE),    # 100 share en 5 días vividos
    ]
    data = _budget(stops, movs, date(2026, 8, 5), {"roma": 50, "paris": 50})
    cafe = next(m for m in data["current"]["by_category"] if m["category_id"] == COFFEE)

    assert cafe["per_day_usd"] == Decimal("20")       # 100 / 5
    assert cafe["trip_per_day_usd"] == Decimal("100") / 15  # 100 / 15 noches vividas
    assert cafe["delta_per_day_usd"] == Decimal("20") - Decimal("100") / 15


def test_category_mix_trip_baseline_ignores_future_stops():
    """Una entrada ya pagada de una parada futura es parte de la MEZCLA
    (`share`) pero no de un promedio POR DÍA: sus noches no se vivieron.
    Sin la base devengada, el promedio del viaje se diluía y toda la ciudad en
    curso aparecía gastando de más."""
    COFFEE = 3
    futura = _stop("paris", order=2, arrival=date(2026, 9, 1),
                   departure=date(2026, 9, 11))
    movs = [_mov("roma", "200", cat=COFFEE)]
    solo = _budget([ROMA, futura], movs, date(2026, 8, 5), {"roma": 50})
    con_prepago = _budget(
        [ROMA, futura], movs + [_mov("paris", "600", cat=COFFEE)],
        date(2026, 8, 5), {"roma": 50},
    )

    def _cafe(d):
        return next(m for m in d["current"]["by_category"] if m["category_id"] == COFFEE)

    assert _cafe(con_prepago)["trip_per_day_usd"] == _cafe(solo)["trip_per_day_usd"]
    # El share sí lo cuenta: la plata de París está comprometida y es parte de
    # la mezcla del viaje. Las dos bases dicen cosas distintas a propósito.
    assert _cafe(con_prepago)["share_pct"] == 100.0
    assert _cafe(con_prepago)["trip_share_pct"] == 100.0


def test_category_mix_is_empty_without_living_spend():
    data = _budget([ROMA], [_mov("roma", "1000", cat=LODGING)], date(2026, 8, 5),
                   {"roma": 50})
    assert data["current"]["by_category"] == []


# ------------------------------------------------------ el costo del viaje


def test_cost_estimates_the_unbooked_nights():
    """Roma reservada y París no: las noches que faltan se estiman al precio
    real por noche, y el total es la suma de los tres bloques."""
    paris = _stop("paris", order=2, arrival=date(2026, 8, 11), departure=date(2026, 8, 21))
    movs = [
        _mov("roma", "2000", cat=LODGING),   # 1000 de share en 10 noches = 100/noche
        _mov("roma", "1000"),                # 500 de vivir en 10 noches = 50/día
        _mov(None, "600"),                   # 300 de generales
    ]
    # Día 3 de París: Roma cerrada da el ritmo, y París todavía no lo diluye.
    data = _budget([ROMA, paris], movs, date(2026, 8, 13), {"roma": 50, "paris": 50})
    c = data["cost"]

    assert c["unbooked_nights"] == 10                       # las de París
    assert c["lodging_estimated_usd"] == Decimal("1000")    # 100 × 10
    assert c["lodging_projected_usd"] == Decimal("2000")    # 1000 reservado + 1000
    assert c["lodging_is_estimated"] is True
    assert c["basis"] == "projected"
    assert c["living_usd"] == Decimal("1000")               # 50/día × 20 noches
    assert c["general_usd"] == Decimal("300")
    assert c["total_usd"] == Decimal("3300")
    assert c["total_usd"] == c["living_usd"] + c["lodging_projected_usd"] + c["general_usd"]


def test_cost_without_unbooked_nights_has_no_estimate():
    """Todo reservado: no hay nada que estimar y el total es el comprometido."""
    movs = [_mov("roma", "2000", cat=LODGING), _mov("roma", "1000")]
    data = _budget([ROMA], movs, date(2026, 8, 21), {"roma": 50})
    c = data["cost"]

    assert c["unbooked_nights"] == 0
    assert c["lodging_estimated_usd"] == Decimal("0")
    assert c["lodging_is_estimated"] is False
    assert c["lodging_projected_usd"] == Decimal("1000")
    assert c["total_usd"] == Decimal("1500")   # 500 de vivir + 1000 de dormir


def test_cost_without_any_booking_does_not_invent_a_price():
    """Sin una sola noche reservada no hay base para estimar: None, y el total
    sigue siendo un número (el vivir + los generales que sí existen)."""
    data = _budget([ROMA], [_mov("roma", "1000"), _mov(None, "400")],
                   date(2026, 8, 21), {"roma": 50})
    c = data["cost"]

    assert data["fixed"]["per_night_usd"] is None
    assert c["unbooked_nights"] == 10
    assert c["lodging_estimated_usd"] is None
    assert c["lodging_is_estimated"] is False
    assert c["lodging_projected_usd"] == Decimal("0")
    assert c["total_usd"] == Decimal("700")    # 500 de vivir + 200 de generales


def test_cost_without_closed_cities_is_committed_not_projected():
    """Sin ninguna ciudad cerrada no hay ritmo: el total es lo comprometido
    hasta hoy y el `basis` lo dice, para que la página no lo llame proyección."""
    data = _budget([ROMA], [_mov("roma", "600")], date(2026, 8, 4), {"roma": 50})
    p, c = data["projection"], data["cost"]

    assert p["projected_living_usd"] is None
    assert c["basis"] == "committed"
    assert c["living_usd"] == p["living_to_date_usd"] == Decimal("300")


def test_cost_does_not_project_generals():
    """Los vuelos del tramo que falta ya están comprados: se suman tal cual y
    no se extrapolan por día. Espeja `analytics._project`."""
    paris = _stop("paris", order=2, arrival=date(2026, 8, 11), departure=date(2026, 8, 21))
    movs = [_mov("roma", "1000"), _mov(None, "800")]
    data = _budget([ROMA, paris], movs, date(2026, 8, 13), {"roma": 50, "paris": 50})
    c = data["cost"]

    assert c["general_usd"] == data["fixed"]["general_usd"] == Decimal("400")
    assert c["living_usd"] == Decimal("1000")   # el vivir SÍ se proyecta a 20 noches


def test_cost_unbooked_nights_come_from_the_itinerary_not_the_bands():
    """Las noches sin reservar salen de `total_nights` (el universo de
    `fixed_block`), no de `budget_nights`: la parada del otro no tiene noches
    propias en el presupuesto pero tampoco alojamiento que estimarle."""
    stops = [
        _stop("portugal", order=1, arrival=date(2026, 9, 4), departure=date(2026, 9, 12),
              owner_username="bruno"),
        _stop("pititas", order=2, arrival=date(2026, 9, 4), departure=date(2026, 9, 12),
              is_local=True, owner_username="katia"),
    ]
    data = _budget(stops, [_mov("portugal", "160")], date(2026, 9, 20),
                   {"portugal": 50, "pititas": 50})

    assert data["projection"]["budget_nights"] == 8         # solo Portugal
    assert data["cost"]["unbooked_nights"] == data["fixed"]["total_nights"]
    assert data["cost"]["unbooked_nights"] >= 0
