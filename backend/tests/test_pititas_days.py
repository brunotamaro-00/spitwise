"""Los días del itinerario no se duplican cuando dos paradas ocurren a la vez.

Portugal (4-12 sept) y Pititas (4-12 sept) pasan en simultáneo: Bruno en una,
Katia en la otra. Sumar duraciones contaba 8 días dos veces.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.api.auth import hash_password


async def _seed(app_client):
    from app.db.models import Category, Movement, Stop, User

    async with app_client._maker() as s:
        bruno = User(username="bruno", password_hash=hash_password("pw"))
        katia = User(username="katia", password_hash=hash_password("pw"))
        s.add_all([bruno, katia])
        await s.flush()
        cat = (await s.execute(select(Category))).scalars().first().id
        s.add_all([
            Stop(slug="paris", order=6, name="París", currency_code="EUR",
                 arrival_date=date(2026, 8, 29), departure_date=date(2026, 9, 4)),
            Stop(slug="portugal", order=7, name="Portugal", currency_code="EUR",
                 arrival_date=date(2026, 9, 4), departure_date=date(2026, 9, 12)),
            Stop(slug="pititas", order=7, name="Pititas", country_flag="👭",
                 currency_code="EUR", arrival_date=date(2026, 9, 4),
                 departure_date=date(2026, 9, 12), is_local=True, owner_username="katia"),
            Stop(slug="estrasburgo", order=8, name="Estrasburgo", currency_code="EUR",
                 arrival_date=date(2026, 9, 12), departure_date=date(2026, 9, 14)),
            # Gasto de Katia en Pititas, pagado por ella y compartido: a Bruno le
            # toca la mitad, así que Pititas aparece también en su tab.
            Movement(type="expense", amount=Decimal("40"), currency="EUR",
                     amount_usd=Decimal("40"), fx_rate=Decimal("1"), fx_source="frankfurter",
                     paid_by=katia.id, split="shared", category_id=cat,
                     stop_slug="pititas", city_name="Pititas",
                      created_by=katia.id),
        ])
        await s.commit()


async def _auth(app_client, who):
    r = await app_client.post("/api/v1/auth/login", data={"username": who, "password": "pw"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# París 6 + Portugal 8 + Estrasburgo 2 = 16 días de viaje. Pititas pasa en
# paralelo a Portugal, así que no agrega días a nadie.
_TRIP_DAYS = 16


async def test_katia_no_suma_los_dias_de_portugal(app_client):
    """El bug: 16 + 8 de Pititas = 24 días de un viaje de 16."""
    await _seed(app_client)
    h = await _auth(app_client, "katia")
    r = await app_client.get("/api/v1/dashboard/city/summary", headers=h)
    assert r.json()["days"] == _TRIP_DAYS


async def test_bruno_tampoco_suma_los_dias_de_pititas(app_client):
    await _seed(app_client)
    h = await _auth(app_client, "bruno")
    r = await app_client.get("/api/v1/dashboard/city/summary", headers=h)
    assert r.json()["days"] == _TRIP_DAYS


async def test_drilldown_de_pititas_muestra_sus_dias(app_client):
    """Bruno pagó la mitad de un gasto de Pititas, así que la ve en su tab: el
    drill-down tiene que mostrar los días de esa parada, no cero."""
    await _seed(app_client)
    for who in ("katia", "bruno"):
        h = await _auth(app_client, who)
        r = await app_client.get("/api/v1/dashboard/city/summary?slugs=pititas", headers=h)
        assert r.json()["days"] == 8, who
        assert r.json()["total_usd"] == "20.00", who  # mitad de 40


async def test_seleccionar_las_dos_paradas_no_duplica(app_client):
    """Portugal + Pititas seleccionadas a la vez siguen siendo 8 días, no 16."""
    await _seed(app_client)
    h = await _auth(app_client, "katia")
    r = await app_client.get(
        "/api/v1/dashboard/city/summary?slugs=portugal&slugs=pititas", headers=h
    )
    assert r.json()["days"] == 8
