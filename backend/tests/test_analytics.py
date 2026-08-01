"""build_trip_pace: prorrateo de alojamiento, devengado y ritmo del viaje."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.analytics import build_trip_pace, itinerary_dates, lived_days, stop_status

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


def _pace(stops, movements, today, username="bruno", user_id=1):
    return build_trip_pace(
        stops, movements, lodging_category_id=LODGING,
        user_id=user_id, username=username, today=today,
    )


def _city(data, slug):
    return next(c for c in data["cities"] if c["stop_slug"] == slug)


def test_mid_stay_prorates_lodging():
    """10 noches, alojamiento share 500 pagado el día 1, hoy es el día 4:
    devenga 50/noche x 4 + el resto, no los 500 de golpe."""
    stops = [_stop("roma", arrival=date(2026, 8, 1), departure=date(2026, 8, 11))]
    movs = [_mov("roma", "1000", cat=LODGING), _mov("roma", "160")]
    data = _pace(stops, movs, today=date(2026, 8, 4))

    c = _city(data, "roma")
    assert c["status"] == "current"
    assert c["elapsed_nights"] == 4
    assert c["lodging_per_night_usd"] == Decimal("50")
    assert c["per_day_usd"] == Decimal("70")  # (50*4 + 80) / 4
    assert data["trip"]["accrued_usd"] == Decimal("280")
    assert data["trip"]["run_rate_usd"] == Decimal("70")
    # Sin ciudades cerradas todavía (Roma está en curso): no se proyecta.
    assert data["trip"]["projected_total_usd"] is None


def test_past_city_uses_all_nights():
    stops = [_stop("roma", arrival=date(2026, 8, 1), departure=date(2026, 8, 11))]
    movs = [_mov("roma", "1000", cat=LODGING), _mov("roma", "160")]
    data = _pace(stops, movs, today=date(2026, 9, 1))
    c = _city(data, "roma")
    assert c["status"] == "past"
    assert c["per_day_usd"] == Decimal("58")  # (500 + 80) / 10


def test_future_city_has_no_delta():
    """Ciudad futura con solo prepago: per_day existe pero el delta es None
    para que la reserva no 'grite' sobre el promedio."""
    stops = [
        _stop("roma", order=1, arrival=date(2026, 8, 1), departure=date(2026, 8, 11)),
        _stop("paris", order=2, arrival=date(2026, 9, 1), departure=date(2026, 9, 6)),
    ]
    movs = [_mov("roma", "200"), _mov("paris", "300", cat=LODGING)]
    data = _pace(stops, movs, today=date(2026, 8, 4))
    c = _city(data, "paris")
    assert c["status"] == "future"
    assert c["per_day_usd"] == Decimal("30")  # 150 / 5 noches
    assert c["delta_vs_trip_pct"] is None
    # Roma sí compara contra el ritmo.
    assert _city(data, "roma")["delta_vs_trip_pct"] is not None


def test_general_expenses_prorated_globally():
    """Los generales (sin parada, o slug huérfano) van al bucket global:
    G/N por día, G*E/N en el devengado, nunca a una ciudad."""
    stops = [_stop("roma", arrival=date(2026, 8, 1), departure=date(2026, 8, 11))]
    movs = [
        _mov(None, "600"),          # vuelos: share 300
        _mov("huerfana", "100"),    # slug sin Stop: share 50, también general
        _mov("roma", "160"),
    ]
    data = _pace(stops, movs, today=date(2026, 8, 5))
    t = data["trip"]
    assert t["general_usd"] == Decimal("350")
    assert t["general_per_day_usd"] == Decimal("35")  # 350 / 10 noches
    assert _city(data, "roma")["total_usd"] == Decimal("80")
    # Devengado: 80 (roma, ya arrancada) + 350*5/10 = 255.
    assert t["accrued_usd"] == Decimal("255")


def test_projection_uses_closed_cities_plus_generals():
    """Proyección = generales + noches × ritmo de lo cerrado. Roma (10 noches,
    cerrada) gastó 500; la ciudad en curso y los prepagos futuros no cuentan."""
    stops = [
        _stop("roma", order=1, arrival=date(2026, 8, 1), departure=date(2026, 8, 11)),
        _stop("paris", order=2, arrival=date(2026, 8, 11), departure=date(2026, 8, 16)),
        _stop("niza", order=3, arrival=date(2026, 9, 1), departure=date(2026, 9, 6)),
    ]
    movs = [
        _mov("roma", "1000", cat=LODGING),   # share 500, ciudad cerrada
        _mov("paris", "200"),                # share 100, en curso (no cuenta)
        _mov("niza", "600", cat=LODGING),    # share 300, prepago futuro (no cuenta)
        _mov(None, "400"),                   # generales: share 200
    ]
    data = _pace(stops, movs, today=date(2026, 8, 13))  # día 3 de París
    t = data["trip"]
    # 20 noches totales; ritmo cerrado = 500/10 = 50; 50*20 + 200 generales.
    assert t["total_nights"] == 20
    assert t["projected_total_usd"] == Decimal("1200")


def test_pre_trip_baseline_is_committed_over_nights():
    stops = [_stop("roma", arrival=date(2026, 8, 1), departure=date(2026, 8, 11))]
    movs = [_mov("roma", "1000", cat=LODGING), _mov(None, "200")]
    data = _pace(stops, movs, today=date(2026, 7, 1))
    t = data["trip"]
    assert t["status"] == "not_started"
    assert t["elapsed_nights"] == 0
    assert t["run_rate_usd"] is None
    assert t["projected_total_usd"] is None
    # Baseline sin generales: solo lo comprometido en ciudades / noches.
    assert t["avg_per_day_usd"] == Decimal("50")  # 500 (roma) / 10
    assert t["accrued_usd"] == Decimal("0")


def test_shares_respected():
    """other_only pagado por bruno no cuenta para bruno; payer_only sí, entero."""
    stops = [_stop("roma", arrival=date(2026, 8, 1), departure=date(2026, 8, 11))]
    movs = [
        _mov("roma", "100", split="other_only", paid_by=1),  # consumo de katia
        _mov("roma", "40", split="payer_only", paid_by=1),   # solo bruno
    ]
    data = _pace(stops, movs, today=date(2026, 9, 1), user_id=1)
    assert _city(data, "roma")["total_usd"] == Decimal("40")
    data_katia = _pace(stops, movs, today=date(2026, 9, 1), user_id=2, username="katia")
    assert _city(data_katia, "roma")["total_usd"] == Decimal("100")


def test_candidate_excluded_archived_accrues():
    stops = [
        _stop("roma", order=1, arrival=date(2026, 8, 1), departure=date(2026, 8, 11)),
        _stop("bled", order=2, arrival=date(2026, 8, 11), is_candidate=True),
        _stop("vieja", order=3, arrival=date(2026, 7, 1), departure=date(2026, 7, 3),
              is_archived=True),
    ]
    movs = [_mov("vieja", "60")]
    data = _pace(stops, movs, today=date(2026, 8, 2))
    slugs = [c["stop_slug"] for c in data["cities"]]
    assert "bled" not in slugs  # candidata sin gastos: fuera
    # Archivada: fila al final, past, fuera de N, devenga todo.
    assert slugs[-1] == "vieja"
    assert _city(data, "vieja")["status"] == "past"
    assert _city(data, "vieja")["in_itinerary"] is False  # archivada: fuera de N
    assert _city(data, "roma")["in_itinerary"] is True
    assert data["trip"]["total_nights"] == 10
    assert data["trip"]["accrued_usd"] == Decimal("30")


def test_zero_night_stop_accrues_on_arrival():
    stops = [
        _stop("roma", order=1, arrival=date(2026, 8, 1), departure=date(2026, 8, 11)),
        _stop("transito", order=2, arrival=date(2026, 8, 11), departure=date(2026, 8, 11),
              is_transit=True),
    ]
    movs = [_mov("transito", "50")]
    before = _pace(stops, movs, today=date(2026, 8, 5))
    assert _city(before, "transito")["per_day_usd"] is None
    assert before["trip"]["accrued_usd"] == Decimal("0")
    after = _pace(stops, movs, today=date(2026, 8, 11))
    assert after["trip"]["accrued_usd"] == Decimal("25")


def test_other_owned_stop_visible_only_with_spend():
    """Pititas (owner katia) solo aparece en el pace de bruno si él tiene parte
    de algún gasto ahí; y sus fechas nunca suman al N de bruno."""
    stops = [
        _stop("portugal", order=1, arrival=date(2026, 9, 4), departure=date(2026, 9, 12)),
        _stop("pititas", order=2, arrival=date(2026, 9, 4), departure=date(2026, 9, 12),
              is_local=True, owner_username="katia"),
    ]
    no_spend = _pace(stops, [_mov("portugal", "80")], today=date(2026, 9, 6))
    assert [c["stop_slug"] for c in no_spend["cities"]] == ["portugal"]
    assert no_spend["trip"]["total_nights"] == 8

    with_spend = _pace(
        stops, [_mov("portugal", "80"), _mov("pititas", "40")], today=date(2026, 9, 6)
    )
    assert {c["stop_slug"] for c in with_spend["cities"]} == {"portugal", "pititas"}
    assert with_spend["trip"]["total_nights"] == 8  # sigue sin duplicar días
    # `in_itinerary` marca la frontera de total_nights: la fila de Pititas existe
    # (bruno gastó ahí) pero sus 8 noches no son suyas. app/budget.py depende de
    # esto para no inventarle 8 noches de presupuesto.
    assert _city(with_spend, "portugal")["in_itinerary"] is True
    assert _city(with_spend, "pititas")["in_itinerary"] is False
    # Para katia, pititas es propia: mismas 8 noches (overlap dedup).
    katia = _pace(
        stops, [_mov("pititas", "40")], today=date(2026, 9, 6),
        username="katia", user_id=2,
    )
    assert katia["trip"]["total_nights"] == 8


def test_itinerary_dates_dedups_overlap():
    stops = [
        _stop("a", arrival=date(2026, 9, 4), departure=date(2026, 9, 12)),
        _stop("b", arrival=date(2026, 9, 4), departure=date(2026, 9, 12)),
    ]
    assert len(itinerary_dates(stops)) == 8


def test_status_and_lived_days_helpers():
    s = _stop("x", arrival=date(2026, 8, 1), departure=date(2026, 8, 11))
    assert stop_status(s, date(2026, 7, 31)) == "future"
    assert stop_status(s, date(2026, 8, 1)) == "current"
    assert stop_status(s, date(2026, 8, 11)) == "past"
    assert lived_days(s, date(2026, 8, 1)) == 1  # día de llegada = día 1
    assert lived_days(s, date(2026, 8, 10)) == 10
    assert lived_days(s, date(2026, 12, 1)) == 10


def test_living_by_category_sums_to_other():
    """El desglose de vivir es una partición de `other_usd`: ni el alojamiento
    ni los generales entran, y la suma cierra exacto. Es el guard de que
    /presupuesto no muestra un desglose que no da el total de la ciudad."""
    FOOD, COFFEE = 2, 3
    stops = [_stop("roma", arrival=date(2026, 8, 1), departure=date(2026, 8, 11))]
    movs = [
        _mov("roma", "500", cat=LODGING),
        _mov("roma", "120", cat=FOOD),
        _mov("roma", "40", cat=COFFEE),
        _mov("roma", "30", cat=None),          # sin categoría: igual es vivir
        _mov(None, "800", cat=FOOD),           # general: no pasa por ninguna ciudad
    ]
    data = _pace(stops, movs, date(2026, 8, 4))
    roma = _city(data, "roma")

    by_cat = roma["living_by_category"]
    assert by_cat == {FOOD: Decimal("60"), COFFEE: Decimal("20"), None: Decimal("15")}
    assert sum(by_cat.values()) == roma["other_usd"]
    assert LODGING not in by_cat
    # El del viaje es la suma de las ciudades, así que tampoco tiene generales.
    assert data["trip"]["living_by_category"] == by_cat
    assert sum(data["trip"]["living_by_category"].values()) < data["trip"]["total_usd"]
