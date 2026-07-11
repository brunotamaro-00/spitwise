from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.db.models import Category, Movement, User


async def test_insert_movement_roundtrip(db_session):
    u1 = User(username="bruno")
    u2 = User(username="katia")
    cat = Category(name="Comida", icon="🍽️")
    db_session.add_all([u1, u2, cat])
    await db_session.flush()

    mv = Movement(
        type="expense",
        amount=Decimal("45.00"),
        currency="GBP",
        amount_usd=Decimal("57.15"),
        fx_rate=Decimal("1.27"),
        fx_source="frankfurter",
        paid_by=u1.id,
        split="shared",
        description="cena",
        category_id=cat.id,
        stop_slug="londres",
        city_name="Londres",
        movement_date=date(2026, 8, 6),
        created_by=u1.id,
    )
    db_session.add(mv)
    await db_session.flush()

    got = (await db_session.execute(select(Movement))).scalar_one()
    assert got.amount_usd == Decimal("57.15")
    assert got.split == "shared"
    assert got.stop_slug == "londres"
