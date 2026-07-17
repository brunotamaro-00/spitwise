from sqlalchemy import select

from app.categories.catalog import CATEGORIES
from app.categories.seed import seed_categories
from app.db.models import Category


def test_catalog_has_ten():
    names = [c[0] for c in CATEGORIES]
    assert names == [
        "Alojamiento",
        "Comida",
        "Supermercado",
        "Transporte",
        "Actividades",
        "Compras",
        "Salidas",
        "Regalos",
        "Salud",
        "Otros",
    ]


async def test_seed_is_idempotent(db_session):
    await seed_categories(db_session)
    await seed_categories(db_session)
    rows = (await db_session.execute(select(Category).order_by(Category.sort_order))).scalars().all()
    assert len(rows) == 10
    assert rows[0].name == "Alojamiento"
    assert rows[0].sort_order == 0


async def test_seed_backfills_descriptions(db_session):
    await seed_categories(db_session)
    rows = (await db_session.execute(select(Category).order_by(Category.sort_order))).scalars().all()
    by_name = {c.name: c.description for c in rows}
    assert "teleférico" in by_name["Transporte"]
    assert all(by_name.values())
    # Re-seed actualiza descripciones existentes (no solo crea).
    rows[0].description = "vieja"
    await db_session.flush()
    await seed_categories(db_session)
    updated = (await db_session.execute(
        select(Category).where(Category.name == rows[0].name))).scalar_one()
    assert updated.description != "vieja"
