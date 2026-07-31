"""build_budget: target de vivir por parada contra el gasto real.

Los helpers llaman `build_trip_pace` **real** y le pasan el resultado a
`build_budget`. Es a propósito: el riesgo de esta arquitectura no es la
aritmética del presupuesto, es que los dos módulos se desacoplen y /ciudades
termine diciendo un número y /presupuesto otro.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.analytics import build_trip_pace
from app.budget import build_budget

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


def _mov(slug, usd, cat=OTHER, split="shared", paid_by=1):
    return SimpleNamespace(
        type="expense", split=split, amount_usd=Decimal(usd),
        paid_by=paid_by, stop_slug=slug, category_id=cat,
    )


def _budget(stops, movements, today, targets=None, username="bruno", user_id=1):
    pace = build_trip_pace(
        stops, movements, lodging_category_id=LODGING,
        user_id=user_id, username=username, today=today,
    )
    return build_budget(pace, {k: Decimal(v) for k, v in (targets or {}).items()})


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
