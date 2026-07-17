"""GET /dashboard/pace: serialización y coherencia con /dashboard/summary."""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.api.auth import hash_password


def _freeze_today(monkeypatch, d: date):
    import app.api.dashboard as dash
    monkeypatch.setattr(dash, "today_in_tz", lambda tz, **kw: d)


async def _seed_and_auth(app_client):
    """Londres (3 noches) + París (3 noches). Alojamiento 90 en Londres,
    comida 30 en Londres, general 60 sin ciudad. Todo shared => bruno mitad."""
    from app.db.models import Category, Movement, Stop, User

    async with app_client._maker() as s:
        u1 = User(username="bruno", password_hash=hash_password("pw"))
        u2 = User(username="katia", password_hash=hash_password("pw"))
        s.add_all([u1, u2])
        await s.flush()
        cats = (await s.execute(select(Category))).scalars().all()
        lodging = next(c.id for c in cats if c.name == "Alojamiento")
        comida = next(c.id for c in cats if c.name == "Comida")
        s.add_all([
            Stop(slug="londres", order=1, name="Londres", country_flag="🇬🇧",
                 arrival_date=date(2026, 8, 5), departure_date=date(2026, 8, 8)),
            Stop(slug="paris", order=2, name="París", country_flag="🇫🇷",
                 arrival_date=date(2026, 8, 29), departure_date=date(2026, 9, 1)),
            Movement(type="expense", amount=Decimal("90"), currency="USD",
                     amount_usd=Decimal("90"), fx_rate=Decimal("1"), fx_source="frankfurter",
                     paid_by=u1.id, split="shared", category_id=lodging,
                     stop_slug="londres", city_name="Londres",
                     movement_date=date(2026, 8, 5), created_by=u1.id),
            Movement(type="expense", amount=Decimal("30"), currency="USD",
                     amount_usd=Decimal("30"), fx_rate=Decimal("1"), fx_source="frankfurter",
                     paid_by=u2.id, split="shared", category_id=comida,
                     stop_slug="londres", city_name="Londres",
                     movement_date=date(2026, 8, 6), created_by=u2.id),
            Movement(type="expense", amount=Decimal("60"), currency="USD",
                     amount_usd=Decimal("60"), fx_rate=Decimal("1"), fx_source="frankfurter",
                     paid_by=u1.id, split="shared", category_id=None,
                     stop_slug=None, city_name=None,
                     movement_date=date(2026, 7, 10), created_by=u1.id),
        ])
        await s.commit()
    r = await app_client.post("/api/v1/auth/login", data={"username": "bruno", "password": "pw"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_pace_pre_trip(app_client, monkeypatch):
    h = await _seed_and_auth(app_client)
    _freeze_today(monkeypatch, date(2026, 7, 1))
    r = await app_client.get("/api/v1/dashboard/pace", headers=h)
    assert r.status_code == 200
    j = r.json()

    t = j["trip"]
    assert t["status"] == "not_started"
    assert t["total_nights"] == 6
    assert t["elapsed_nights"] == 0
    assert t["total_usd"] == "90.00"       # 45 + 15 + 30
    assert t["general_usd"] == "30.00"
    assert t["general_per_day_usd"] == "5.00"
    assert t["run_rate_usd"] is None
    assert t["projected_total_usd"] is None
    assert t["avg_per_day_usd"] == "10.00"  # sin generales: 60 (ciudades) / 6

    cities = {c["stop_slug"]: c for c in j["cities"]}
    assert list(cities) == ["londres", "paris"]  # itinerario completo, aun sin gastos
    lon = cities["londres"]
    assert lon["status"] == "future"
    assert lon["lodging_usd"] == "45.00"
    assert lon["other_usd"] == "15.00"
    assert lon["per_day_usd"] == "20.00"    # 60 / 3 noches
    assert lon["lodging_per_night_usd"] == "15.00"
    assert lon["delta_vs_trip_pct"] is None  # futura: nunca grita
    assert cities["paris"]["movement_count"] == 0
    assert cities["paris"]["per_day_usd"] == "0.00"


async def test_pace_mid_stay(app_client, monkeypatch):
    h = await _seed_and_auth(app_client)
    _freeze_today(monkeypatch, date(2026, 8, 6))  # día 2 de Londres
    r = await app_client.get("/api/v1/dashboard/pace", headers=h)
    j = r.json()

    t = j["trip"]
    assert t["status"] == "in_progress"
    assert t["elapsed_nights"] == 2
    # Devengado total: alojamiento 15/noche x2 + comida 15 + general 30*2/6 = 55.
    assert t["accrued_usd"] == "55.00"
    # Ritmo sin generales: (55 - 10) / 2 = 22,50.
    assert t["run_rate_usd"] == "22.50"
    # Londres está en curso y no hay ciudad cerrada: sin proyección.
    assert t["projected_total_usd"] is None

    lon = {c["stop_slug"]: c for c in j["cities"]}["londres"]
    assert lon["status"] == "current"
    assert lon["elapsed_nights"] == 2
    assert lon["per_day_usd"] == "22.50"    # (15*2 + 15) / 2
    # Londres es la única ciudad y el ritmo ya no lleva generales: es el
    # promedio mismo, así que el delta es 0 (antes daba -18% por los generales).
    assert lon["delta_vs_trip_pct"] is not None
    assert abs(lon["delta_vs_trip_pct"]) < 0.1


async def test_pace_total_matches_summary(app_client, monkeypatch):
    h = await _seed_and_auth(app_client)
    _freeze_today(monkeypatch, date(2026, 8, 6))
    pace = (await app_client.get("/api/v1/dashboard/pace", headers=h)).json()
    summ = (await app_client.get("/api/v1/dashboard/summary", headers=h)).json()
    assert pace["trip"]["total_usd"] == summ["total_usd"]


async def test_pace_excludes_other_only_consumption(app_client, monkeypatch):
    from app.db.models import Movement, User

    h = await _seed_and_auth(app_client)
    async with app_client._maker() as s:
        bruno = (await s.execute(select(User).where(User.username == "bruno"))).scalar_one()
        s.add(Movement(type="expense", amount=Decimal("10"), currency="USD",
                       amount_usd=Decimal("10"), fx_rate=Decimal("1"),
                       fx_source="frankfurter", paid_by=bruno.id, split="other_only",
                       stop_slug="paris", city_name="París",
                       movement_date=date(2026, 8, 30), created_by=bruno.id))
        await s.commit()
    _freeze_today(monkeypatch, date(2026, 7, 1))
    j = (await app_client.get("/api/v1/dashboard/pace", headers=h)).json()
    # El other_only pagado por bruno es consumo de katia: no aparece en su pace.
    assert j["trip"]["total_usd"] == "90.00"
    paris = {c["stop_slug"]: c for c in j["cities"]}["paris"]
    assert paris["total_usd"] == "0.00"


async def test_pace_pititas_visible_for_both(app_client, monkeypatch):
    """Parada local de katia con gasto compartido: bruno la ve en su pace,
    pero sus fechas no suman noches a su itinerario (overlap con Portugal)."""
    from app.db.models import Movement, Stop, User

    h = await _seed_and_auth(app_client)
    async with app_client._maker() as s:
        katia = (await s.execute(select(User).where(User.username == "katia"))).scalar_one()
        s.add_all([
            Stop(slug="portugal", order=3, name="Portugal",
                 arrival_date=date(2026, 9, 4), departure_date=date(2026, 9, 12)),
            Stop(slug="pititas", order=4, name="Pititas", country_flag="😊",
                 arrival_date=date(2026, 9, 4), departure_date=date(2026, 9, 12),
                 is_local=True, owner_username="katia"),
            Movement(type="expense", amount=Decimal("40"), currency="EUR",
                     amount_usd=Decimal("40"), fx_rate=Decimal("1"), fx_source="frankfurter",
                     paid_by=katia.id, split="shared", category_id=None,
                     stop_slug="pititas", city_name="Pititas",
                     movement_date=date(2026, 9, 6), created_by=katia.id),
        ])
        await s.commit()
    _freeze_today(monkeypatch, date(2026, 7, 1))
    j = (await app_client.get("/api/v1/dashboard/pace", headers=h)).json()
    cities = {c["stop_slug"]: c for c in j["cities"]}
    assert cities["pititas"]["total_usd"] == "20.00"  # mitad de 40
    # Noches: Londres 3 + París 3 + Portugal 8 = 14 (Pititas solapa, no suma).
    assert j["trip"]["total_nights"] == 14
