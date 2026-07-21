"""Multi-gasto: N movimientos de un mensaje, confirmación única, borrar batch."""
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.api.auth import hash_password
from app.bot.capture import handle_capture
from app.bot.dispatcher import _handle_delete_command
from app.bot.interactive import handle_interactive
from app.db.models import Movement, User

TODAY = date(2026, 8, 6)


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    async def parse(self, text, **kwargs):
        return self.payload


def _payload(**over):
    base = {
        "intent": "expense", "amount": None, "currency": None, "description": None,
        "category": None, "split": "shared", "paid_by": None, "date": None, "city": None,
        "confidence": 0.9, "candidates": [], "expenses": [],
    }
    base.update(over)
    return base


def _item(**over):
    base = {
        "kind": "expense", "amount": None, "currency": "USD", "description": None,
        "category": None, "split": "shared", "paid_by": None, "date": None, "city": None,
        "confidence": 0.9, "candidates": [],
    }
    base.update(over)
    return base


async def _users(db_session):
    bruno = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549110")
    katia = User(username="katia", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    db_session.add_all([bruno, katia])
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    await db_session.commit()
    return bruno, katia


def _three_payload():
    return _payload(amount="40", category="Comida", description="cena", expenses=[
        _item(amount="40", category="Comida", description="cena"),
        _item(amount="12", category="Transporte", description="taxi"),
        _item(amount="5", category="Comida", description="helado"),
    ])


async def _capture_three(db_session, bruno, text="cena 40, taxi 12, helado 5"):
    fake = FakeLLM(_three_payload())
    return await handle_capture(db_session, bruno, "549110", text, TODAY, llm_client=fake)


async def test_batch_creates_all_movements_one_key(db_session):
    bruno, _ = await _users(db_session)
    reply = await _capture_three(db_session, bruno)
    movs = (await db_session.execute(select(Movement).order_by(Movement.id))).scalars().all()
    assert len(movs) == 3
    assert len({m.batch_key for m in movs}) == 1 and movs[0].batch_key
    assert all(m.raw_message == "cena 40, taxi 12, helado 5" for m in movs)
    assert reply.movement_id == movs[-1].id
    assert not reply.buttons
    text = reply.text or ""
    assert "3 gastos guardados" in text
    assert "Cena" in text and "Taxi" in text and "Helado" in text
    # Total 57 USD, Katia debe la mitad (todo shared, pagó bruno).
    assert "USD 57,0" in text
    assert "*Katia* le debe *USD 28,5*" in text


async def test_batch_uncertain_category_saves_without_buttons(db_session):
    bruno, _ = await _users(db_session)
    payload = _payload(amount="40", expenses=[
        _item(amount="40", category="Comida", description="cena"),
        _item(amount="9", category="Compras", description="cosa",
              confidence=0.3, candidates=["Compras", "Cafetería"]),
    ])
    reply = await handle_capture(db_session, bruno, "549110", "cena 40 y cosa 9",
                                 TODAY, llm_client=FakeLLM(payload))
    assert not reply.buttons  # sin pendings en batch
    movs = (await db_session.execute(select(Movement))).scalars().all()
    assert len(movs) == 2  # se guardó igual
    assert "❓" in (reply.text or "")


async def test_batch_settlement_item_mixed(db_session):
    bruno, _ = await _users(db_session)
    payload = _payload(amount="40", expenses=[
        _item(amount="40", category="Comida", description="cena", city="ignorada"),
        _item(kind="settlement", amount="50"),
    ])
    reply = await handle_capture(db_session, bruno, "549110", "cena 40 y le pasé 50",
                                 TODAY, llm_client=FakeLLM(payload))
    movs = (await db_session.execute(select(Movement).order_by(Movement.id))).scalars().all()
    settle = movs[1]
    assert settle.type == "settlement"
    assert settle.category_id is None and settle.city_name is None and settle.stop_slug is None
    assert "💸" in (reply.text or "")
    # Neto: cena shared 20 + settlement 50 → Katia debe 70.
    assert "USD 70,0" in (reply.text or "")


async def test_batch_respects_per_item_payer_and_split(db_session):
    bruno, _ = await _users(db_session)
    payload = _payload(amount="30", expenses=[
        _item(amount="30", category="Comida", description="cena"),
        _item(amount="10", category="Salud", description="remedio",
              paid_by="katia", split="payer_only"),
    ])
    await handle_capture(db_session, bruno, "549110", "cena 30, remedio 10 de katia",
                         TODAY, llm_client=FakeLLM(payload))
    movs = (await db_session.execute(select(Movement).order_by(Movement.id))).scalars().all()
    katia = (await db_session.execute(select(User).where(User.username == "katia"))).scalar_one()
    assert movs[1].paid_by == katia.id and movs[1].split == "payer_only"
    assert movs[0].paid_by != movs[1].paid_by


async def test_batch_cap_at_ten(db_session):
    bruno, _ = await _users(db_session)
    payload = _payload(amount="1", expenses=[
        _item(amount=str(i + 1), description=f"item{i}", category="Otros") for i in range(14)
    ])
    await handle_capture(db_session, bruno, "549110", "muchos", TODAY, llm_client=FakeLLM(payload))
    movs = (await db_session.execute(select(Movement))).scalars().all()
    assert len(movs) == 10


async def test_borrar_after_batch_offers_whole_batch(db_session):
    bruno, _ = await _users(db_session)
    await _capture_three(db_session, bruno)
    reply = await _handle_delete_command(db_session, bruno)
    assert len(reply.buttons) == 3
    labels = [b[1] for b in reply.buttons]
    assert labels[0] == "Borrar los 3 🗑️"
    assert labels[1] == "Solo el último"
    # Confirmar el batch entero borra los 3.
    confirm_id = reply.buttons[0][0]
    done = await handle_interactive(db_session, bruno, "549110", confirm_id, TODAY)
    assert "3 movimientos" in (done.text or "")
    assert (await db_session.execute(select(Movement))).scalars().all() == []


async def test_borrar_after_batch_only_last(db_session):
    bruno, _ = await _users(db_session)
    await _capture_three(db_session, bruno)
    reply = await _handle_delete_command(db_session, bruno)
    done = await handle_interactive(db_session, bruno, "549110", reply.buttons[1][0], TODAY)
    movs = (await db_session.execute(select(Movement))).scalars().all()
    assert len(movs) == 2
    assert "Helado" in (done.text or "")  # movement_summary capitaliza


async def test_borrar_single_keeps_legacy_flow(db_session):
    bruno, _ = await _users(db_session)
    fake = FakeLLM(_payload(amount="20", currency="USD", description="taxi", category="Transporte"))
    await handle_capture(db_session, bruno, "549110", "taxi 20", TODAY, llm_client=fake)
    reply = await _handle_delete_command(db_session, bruno)
    assert len(reply.buttons) == 2  # Borrar / Cancelar, como siempre


async def test_edit_by_reference_matches_only_named_item(db_session):
    from app.bot.editor import find_candidates
    bruno, _ = await _users(db_session)
    await _capture_three(db_session, bruno)
    # Los 3 comparten raw_message; "cena" debe matchear solo la cena.
    got = await find_candidates(db_session, ref_last=False, ref_text="cena", ref_date=None)
    assert len(got) == 1
    assert got[0].description == "Cena"
