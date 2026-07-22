from decimal import Decimal

from app.api.auth import hash_password
from app.cashback import net_amount, normalize_cashback, validate_cashback


# ---- unit del helper -------------------------------------------------------

def test_net_amount_pct():
    assert net_amount(Decimal("20"), "pct", Decimal("2")) == Decimal("19.60")


def test_net_amount_fixed():
    assert net_amount(Decimal("20"), "amount", Decimal("5")) == Decimal("15.00")


def test_net_amount_no_cashback_is_identity():
    assert net_amount(Decimal("20"), None, None) == Decimal("20")
    assert net_amount(Decimal("20"), "pct", None) == Decimal("20")


def test_net_amount_clamped_at_zero():
    # cashback fijo mayor al bruto no vuelve negativo.
    assert net_amount(Decimal("5"), "amount", Decimal("9")) == Decimal("0.00")


def test_normalize_cashback_degrades():
    assert normalize_cashback("bogus", Decimal("2")) == (None, None)
    assert normalize_cashback("pct", Decimal("0")) == (None, None)
    assert normalize_cashback("pct", Decimal("150")) == (None, None)
    assert normalize_cashback("pct", Decimal("2")) == ("pct", Decimal("2.00"))


def test_validate_cashback_rules():
    assert validate_cashback(None, None, Decimal("20")) is None
    assert validate_cashback("pct", None, Decimal("20")) is not None
    assert validate_cashback("pct", Decimal("120"), Decimal("20")) is not None
    assert validate_cashback("amount", Decimal("30"), Decimal("20")) is not None
    assert validate_cashback("pct", Decimal("2"), Decimal("20")) is None


# ---- API -------------------------------------------------------------------

async def _auth(app_client):
    from app.db.models import User
    async with app_client._maker() as s:
        s.add_all([User(username="bruno", password_hash=hash_password("pw")),
                   User(username="katia", password_hash=hash_password("pw"))])
        await s.commit()
    r = await app_client.post("/api/v1/auth/login", data={"username": "bruno", "password": "pw"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_create_expense_with_pct_cashback(app_client):
    h = await _auth(app_client)
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "20.00", "currency": "USD", "description": "cena",
        "cashback_kind": "pct", "cashback_value": "2",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    # amount guarda el BRUTO; amount_usd es el NETO (20 - 2%).
    assert body["amount"] == "20.00"
    assert body["amount_usd"] == "19.60"
    assert body["cashback_kind"] == "pct"
    assert body["cashback_value"] == "2.00"


async def test_create_with_fixed_cashback_gbp(app_client):
    h = await _auth(app_client)
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "100.00", "currency": "GBP", "fx_rate": "1.30",
        "cashback_kind": "amount", "cashback_value": "10",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    # neto local 90 × 1.30 = 117.
    assert body["amount"] == "100.00"
    assert body["amount_usd"] == "117.00"
    assert body["cashback_kind"] == "amount"


async def test_fixed_cashback_over_amount_rejected(app_client):
    h = await _auth(app_client)
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "20.00", "currency": "USD",
        "cashback_kind": "amount", "cashback_value": "30",
    })
    assert r.status_code == 422


async def test_edit_add_and_remove_cashback_recomputes_usd(app_client):
    h = await _auth(app_client)
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "20.00", "currency": "USD", "description": "cena",
    })
    mid = r.json()["id"]
    assert r.json()["amount_usd"] == "20.00"

    # Agregar cashback recalcula amount_usd al neto.
    r2 = await app_client.patch(f"/api/v1/movements/{mid}", headers=h, json={
        "cashback_kind": "pct", "cashback_value": "10",
    })
    assert r2.status_code == 200, r2.text
    assert r2.json()["amount_usd"] == "18.00"

    # Sacarlo (ambos null) vuelve al bruto.
    r3 = await app_client.patch(f"/api/v1/movements/{mid}", headers=h, json={
        "cashback_kind": None, "cashback_value": None,
    })
    assert r3.status_code == 200, r3.text
    assert r3.json()["amount_usd"] == "20.00"
    assert r3.json()["cashback_kind"] is None


async def test_shared_cashback_splits_the_net_balance(app_client):
    """Un shared con cashback reparte el NETO (invariante confirmado: baja a los dos)."""
    h = await _auth(app_client)
    await app_client.post("/api/v1/movements", headers=h, json={
        "amount": "20.00", "currency": "USD", "split": "shared",
        "cashback_kind": "pct", "cashback_value": "2",
    })
    bal = (await app_client.get("/api/v1/balance", headers=h)).json()
    # Bruno pagó 19.6 neto compartido → Katia le debe la mitad: 9.80.
    assert bal["amount_usd"] == "9.80"


async def test_settlement_ignores_cashback(app_client):
    h = await _auth(app_client)
    r = await app_client.post("/api/v1/movements", headers=h, json={
        "type": "settlement", "amount": "50.00", "currency": "USD",
        "cashback_kind": "pct", "cashback_value": "5",
    })
    assert r.status_code == 201, r.text
    assert r.json()["amount_usd"] == "50.00"
    assert r.json()["cashback_kind"] is None


# ---- canal bot (WhatsApp) --------------------------------------------------

class _FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    async def parse(self, text, **kwargs):
        return self.payload


async def test_bot_capture_persists_cashback_and_nets_usd(db_session):
    from datetime import date

    from sqlalchemy import select

    from app.bot.capture import handle_capture
    from app.categories.seed import seed_categories
    from app.db.models import Movement, User

    today = date(2026, 8, 20)
    u1 = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    db_session.add_all([u1, User(username="katia", password_hash=hash_password("pw"),
                                 whatsapp_wa_id="549222")])
    await seed_categories(db_session)
    await db_session.commit()

    payload = {
        "intent": "expense", "amount": "20", "currency": "USD", "description": "cena",
        "category": "Comida", "split": "shared", "paid_by": None, "date": None, "city": None,
        "confidence": 0.9, "candidates": [], "cashback_kind": "pct", "cashback_value": "2",
    }
    reply = await handle_capture(db_session, u1, "549111", "20 usd cena cashback 2%",
                                 today, llm_client=_FakeLLM(payload))
    mv = (await db_session.execute(select(Movement))).scalar_one()
    assert mv.amount == Decimal("20")           # bruto persistido
    assert mv.cashback_kind == "pct"
    assert mv.cashback_value == Decimal("2")
    assert mv.amount_usd == Decimal("19.60")    # neto en USD
    # La card muestra el neto y una línea de cashback, no el bruto en el monto.
    assert "19,6" in reply.text
    assert "Cashback" in reply.text
