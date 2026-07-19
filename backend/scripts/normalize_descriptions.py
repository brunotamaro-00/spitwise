"""One-off (re-runnable): estandariza las descripciones ya cargadas.

Aplica app.textnorm.normalize_description (primera letra en mayúscula + nombres
propios = nombres de Stops en su capitalización canónica) a todos los
movimientos existentes. Idempotente: solo updatea las filas que cambian.

Uso contra prod (Railway):

    cd backend
    DATABASE_URL="postgresql+asyncpg://..." \
    .venv/bin/python scripts/normalize_descriptions.py
"""
import asyncio

from sqlalchemy import select

from app.config import get_settings
from app.db.engine import async_session_factory, make_engine
from app.db.models import Movement
from app.textnorm import load_proper_nouns, normalize_description


async def main() -> None:
    engine = make_engine(get_settings().database_url)
    maker = async_session_factory(engine)
    async with maker() as session:
        nouns = await load_proper_nouns(session)
        rows = (await session.execute(select(Movement))).scalars().all()
        changed = 0
        for mv in rows:
            new = normalize_description(mv.description, nouns)
            if new != mv.description:
                print(f"  #{mv.id}: {mv.description!r} -> {new!r}")
                mv.description = new
                changed += 1
        if changed:
            await session.commit()
        print(f"normalizados {changed} de {len(rows)} movimientos")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
