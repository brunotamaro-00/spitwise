"""Regresiones de los bordes de escritura sobre gastos diferidos.

Todo lo de acá salió de una auditoría: cada test fija un caso donde editar un
movimiento le movía la plata o el estado sin que nadie lo pidiera. Los dos ejes:

- `awaiting` = venció, TC lockeado, esperando confirmación manual. Solo
  `POST /confirm` lo mete al balance (invariante 4).
- `amount_usd` sale SIEMPRE del neto (bruto - cashback) × TC (invariante 10).
"""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.api.auth import hash_password
from app.db.models import FxRate, Movement, User
from app.due import next_status_for_date


async def _auth(app_client):
    async with app_client._maker() as s:
        s.add_all([User(username="bruno", password_hash=hash_password("pw")),
                   User(username="katia", password_hash=hash_password("pw"))])
        await s.commit()
    r = await app_client.post("/api/v1/auth/login", data={"username": "bruno", "password": "pw"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _set_status(app_client, mid: int, status: str, **fields):
    """Deja el movimiento en un estado que normalmente escribe solo el server."""
    async with app_client._maker() as s:
        mv = (await s.execute(select(Movement).where(Movement.id == mid))).scalar_one()
        mv.status = status
        for k, v in fields.items():
            setattr(mv, k, v)
        await s.commit()


# ---- next_status_for_date (unit) -------------------------------------------

def test_next_status_keeps_awaiting_on_past_date():
    today = date(2026, 9, 5)
    # Un awaiting no se auto-confirma por corregirle la fecha.
    assert next_status_for_date("awaiting", date(2026, 9, 3), today) == "awaiting"
    # Pero una fecha futura lo devuelve a la cola de liquidación.
    assert next_status_for_date("awaiting", date(2026, 12, 1), today) == "pending"
    # Un pending que pasa a fecha pasada sí se confirma (camino de siempre).
    assert next_status_for_date("pending", date(2026, 9, 3), today) == "confirmed"
    assert next_status_for_date("confirmed", None, today) == "confirmed"


# ---- PATCH sobre un awaiting -----------------------------------------------

async def test_patch_description_does_not_confirm_awaiting(app_client):
    """El caso reproducido en la auditoría: editar SOLO la descripción de un
    gasto vencido lo pasaba a confirmed y lo metía al balance."""
    h = await _auth(app_client)
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "50.00", "currency": "USD", "description": "entradas tour",
    })
    mid = r.json()["id"]
    await _set_status(app_client, mid, "awaiting", payment_date=date(2026, 7, 19))

    r2 = await app_client.patch(f"/api/v1/movements/{mid}", headers=h, json={
        "description": "entradas tour museo",
    })
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "awaiting"
    assert r2.json()["description"] == "Entradas tour museo"


async def test_patch_resending_same_payment_date_is_not_a_change(app_client):
    """Un cliente que re-manda el body entero no debe re-derivar el status."""
    h = await _auth(app_client)
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "50.00", "currency": "USD", "description": "hostel",
        "payment_date": "2026-07-19",
    })
    mid = r.json()["id"]
    await _set_status(app_client, mid, "awaiting")

    r2 = await app_client.patch(f"/api/v1/movements/{mid}", headers=h, json={
        "description": "hostel centro", "payment_date": "2026-07-19",
    })
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "awaiting"


async def test_patch_amount_on_awaiting_keeps_locked_rate(app_client):
    """El TC de un awaiting ya lo fijó due.py con el valor real del vencimiento:
    corregir el monto recalcula el USD con ESA tasa, no con una nueva."""
    h = await _auth(app_client)
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "100.00", "currency": "CHF", "fx_rate": "1.20",
    })
    mid = r.json()["id"]
    # due.py lo liquidó: tasa real 1.25, y la fuente vuelve a ser del proveedor.
    await _set_status(app_client, mid, "awaiting", payment_date=date(2026, 7, 19),
                      fx_rate=Decimal("1.25"), fx_source="frankfurter",
                      amount_usd=Decimal("125.00"))

    r2 = await app_client.patch(f"/api/v1/movements/{mid}", headers=h, json={"amount": "200.00"})
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["fx_rate"] == "1.250000"
    assert body["amount_usd"] == "250.00"
    assert body["status"] == "awaiting"


# ---- POST /confirm ---------------------------------------------------------

async def test_confirm_rejects_far_future_pending(app_client):
    """Confirmar un pending lejano lo clavaba al TC proxy para siempre:
    settle_due_movements solo mira status='pending' y nunca lo volvería a ver."""
    h = await _auth(app_client)
    far = (date.today() + timedelta(days=90)).isoformat()
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "500.00", "currency": "USD", "payment_date": far,
    })
    assert r.json()["status"] == "pending"
    r2 = await app_client.post(f"/api/v1/movements/{r.json()['id']}/confirm", headers=h, json={})
    assert r2.status_code == 409, r2.text


async def test_confirm_accepts_awaiting_and_enters_balance(app_client):
    h = await _auth(app_client)
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "50.00", "currency": "USD", "split": "shared",
    })
    mid = r.json()["id"]
    await _set_status(app_client, mid, "awaiting", payment_date=date(2026, 7, 19))

    # Fuera del balance mientras espera.
    assert (await app_client.get("/api/v1/balance", headers=h)).json()["debtor_id"] is None

    r2 = await app_client.post(f"/api/v1/movements/{mid}/confirm", headers=h, json={})
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "confirmed"
    assert (await app_client.get("/api/v1/balance", headers=h)).json()["debtor_id"] is not None


# ---- FX: no pisar una tasa buena con un fallback ---------------------------

async def test_edit_does_not_overwrite_good_rate_with_fallback(app_client, monkeypatch):
    """Con el proveedor caído, corregir el monto conservaba la tasa de
    emergencia en vez de la histórica — y no se reintentaba nunca."""
    h = await _auth(app_client)
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "100.00", "currency": "CHF", "fx_rate": "1.25",
    })
    mid = r.json()["id"]
    # Tasa buena ya guardada por el proveedor.
    await _set_status(app_client, mid, "confirmed", fx_source="frankfurter")

    async def broken_rate(*a, **kw):
        return Decimal("1.0"), "fallback"

    monkeypatch.setattr("app.fx.get_rate_to_usd", broken_rate)
    r2 = await app_client.patch(f"/api/v1/movements/{mid}", headers=h, json={"amount": "200.00"})
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["fx_source"] == "frankfurter"
    assert body["fx_rate"] == "1.250000"
    assert body["amount_usd"] == "250.00"


async def test_edit_uses_new_rate_when_provider_works(app_client, monkeypatch):
    """Contraparte del anterior: con proveedor sano, la tasa sí se actualiza —
    la guarda es solo contra el fallback, no contra recotizar en general."""
    h = await _auth(app_client)
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "100.00", "currency": "CHF", "fx_rate": "1.10",
    })
    mid = r.json()["id"]
    await _set_status(app_client, mid, "confirmed", fx_source="frankfurter")

    async def good_rate(*a, **kw):
        return Decimal("1.30"), "frankfurter"

    monkeypatch.setattr("app.fx.get_rate_to_usd", good_rate)
    r2 = await app_client.patch(f"/api/v1/movements/{mid}", headers=h, json={"amount": "200.00"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["amount_usd"] == "260.00"
    assert r2.json()["fx_rate"] == "1.300000"


# ---- Cashback: PATCH parcial ----------------------------------------------

async def test_patch_only_cashback_value_keeps_kind(app_client):
    """Mandar solo el valor pisaba el kind con el None default de Pydantic:
    422 seguro, y era imposible corregir nada más que el porcentaje."""
    h = await _auth(app_client)
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "100.00", "currency": "USD",
        "cashback_kind": "pct", "cashback_value": "2",
    })
    mid = r.json()["id"]
    assert r.json()["amount_usd"] == "98.00"

    r2 = await app_client.patch(f"/api/v1/movements/{mid}", headers=h, json={"cashback_value": "5"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["cashback_kind"] == "pct"
    assert r2.json()["amount_usd"] == "95.00"


async def test_create_on_owned_stop_splits_to_owner_from_web(app_client):
    """owner_split vivía solo en el bot: el mismo gasto se repartía distinto
    según se cargara por WhatsApp o por la web."""
    from app.db.models import Stop

    h = await _auth(app_client)
    async with app_client._maker() as s:
        s.add(Stop(slug="pititas", name="Pititas", order=99, is_local=True,
                   owner_username="katia", arrival_date=date(2026, 7, 1),
                   departure_date=date(2026, 7, 10)))
        await s.commit()

    # Paga Bruno un gasto de la parada de Katia => other_only (es de ella).
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "40.00", "currency": "USD", "stop_slug": "pititas", "split": "shared",
    })
    assert r.status_code == 201, r.text
    assert r.json()["split"] == "other_only"
