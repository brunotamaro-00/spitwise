from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.categories.catalog import CATEGORIES
from app.db.models import Category


async def seed_categories(session: AsyncSession) -> None:
    existing = {
        c.name: c
        for c in (await session.execute(select(Category))).scalars().all()
    }
    for order, (name, icon) in enumerate(CATEGORIES):
        cat = existing.get(name)
        if cat is None:
            session.add(Category(name=name, icon=icon, sort_order=order))
        else:
            cat.icon = icon
            cat.sort_order = order
    await session.flush()
