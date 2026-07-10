from sqlalchemy import select

from app.categories.catalog import CATEGORIES
from app.categories.seed import seed_categories
from app.db.models import Category


def test_catalog_has_seven():
    names = [c[0] for c in CATEGORIES]
    assert names == [
        "Alojamiento",
        "Comida",
        "Transporte",
        "Actividades",
        "Compras",
        "Bebidas/Salidas",
        "Otros",
    ]


async def test_seed_is_idempotent(db_session):
    await seed_categories(db_session)
    await seed_categories(db_session)
    rows = (await db_session.execute(select(Category).order_by(Category.sort_order))).scalars().all()
    assert len(rows) == 7
    assert rows[0].name == "Alojamiento"
    assert rows[0].sort_order == 0
