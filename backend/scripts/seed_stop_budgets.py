"""One-off (re-runnable): carga los targets de "vivir" por parada.

Idempotente **por inserción**: solo crea las filas que faltan y nunca updatea.
Lo editado desde la web manda; volver a correr el script no lo pisa.

Uso (correr DESPUÉS del primer sync del itinerario: los slugs se validan
contra las paradas ya sincronizadas):

    cd backend
    DATABASE_URL="postgresql+asyncpg://..." \
    .venv/bin/python scripts/seed_stop_budgets.py --dry-run
    DATABASE_URL="postgresql+asyncpg://..." \
    .venv/bin/python scripts/seed_stop_budgets.py

--------------------------------------------------------------------------
DERIVACIÓN DE LOS NÚMEROS
--------------------------------------------------------------------------
Los targets salen de `Itinerary/PRESUPUESTO.md`, sección *Resumen por País*.
Ese doc da **bandas** y subtotales por bloque que **incluyen alojamiento**;
acá hace falta el USD/día pp de "vivir" (todo menos alojamiento y generales):

    target = (mid(subtotal) − mid(alojamiento)) / noches + UPLIFT_LOCAL_USD

La aritmética se hace en código a propósito: cuando el PRESUPUESTO se
actualice, se toca la tabla `BLOQUES` de abajo y el diff del PR muestra qué
cambió de la fuente, no un número mágico ya digerido.

El **uplift** corrige un sesgo sistemático del doc. Dos rubros que en Spitwise
caen en una ciudad (y por lo tanto son "vivir") viven en tablas *globales* de
PRESUPUESTO.md, fuera de todos los subtotales por país:

    transporte local  $550-850 pp → mid 700 / 108 noches = $6,48/día
    lavandería        $55-95   pp → mid  75 / 108 noches = $0,69/día
                                                          ─────────
                                                           ≈ $7,2/día

La eSIM NO entra: es un gasto **general**, se carga sin ciudad y por eso no es
"vivir" (queda en `general_usd`, con los vuelos y los seguros).

Sin el uplift todos los targets quedan ~$7 bajos y la app muestra ámbar desde
el día 1, que es exactamente cómo deja de servir una herramienta así. Es un
solo número, auditable, y se saca o se ajusta acá cuando haya datos reales.

Sesgo residual conocido: los subtotales de Reino Unido y Portugal ya incluyen
transporte intercity (auto de Highlands, vuelos), y los de Europa Central no
incluyen transporte de ningún tipo. Se acepta: corregirlo por bloque es una
tabla de excepciones que hay que re-derivar a mano en cada actualización del
doc, y el target es un objetivo, no un límite.
"""
import argparse
import asyncio
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select

from app.config import get_settings
from app.db.engine import async_session_factory, make_engine
from app.db.models import Stop, StopBudget

# Ver el docstring: transporte local + lavandería, prorrateados en las 108
# noches del viaje. Van sumados a todos los bloques. La eSIM queda afuera: es
# un gasto general (sin ciudad), así que nunca cuenta como "vivir".
UPLIFT_LOCAL_USD = Decimal("7")

# (noches, banda del subtotal, banda del alojamiento) — de PRESUPUESTO.md.
# El alojamiento de los bloques ya reservados es un valor exacto, así que su
# "banda" es el mismo número dos veces.
BLOQUES: dict[str, tuple[int, tuple[float, float], tuple[float, float]]] = {
    "uk":        (20, (2170, 2650), (915.74, 915.74)),
    "nl":        (4,  (490, 610),   (230.42, 230.42)),
    "paris":     (6,  (622, 774),   (266.34, 266.34)),
    "portugal":  (8,  (730, 922),   (264.47, 264.47)),
    "pititas":   (8,  (1108, 1349), (611.00, 611.00)),
    "alsacia":   (7,  (592, 702),   (312.85, 312.85)),
    "suiza":     (4,  (520, 720),   (182.66, 182.66)),
    "austria":   (5,  (495, 780),   (240, 410)),
    "chequia":   (5,  (270, 390),   (130, 170)),
    "polonia":   (4,  (196, 304),   (68, 100)),
    "hungria":   (4,  (214, 331),   (76, 112)),
    "eslovenia": (4,  (260, 388),   (120, 168)),
    "italia":    (24, (1884, 2640), (912, 1200)),
    "espana":    (10, (750, 1060),  (330, 450)),
}

# Bloque por país de la parada (`Stop.country`, que viene de Andiamo). Mapear
# por país y no por lista de slugs es lo que hace esto escalable: una parada
# nueva en Polonia hereda su target sin tocar el script.
BLOQUE_POR_PAIS = {
    "Reino Unido": "uk",
    "Países Bajos": "nl",
    "Francia": "alsacia",   # Estrasburgo y Colmar; París va por override
    "Alemania": "alsacia",  # Friburgo pertenece al bloque Alsacia + Selva Negra
    "Portugal": "portugal",
    "Suiza": "suiza",
    "Austria": "austria",
    "Chequia": "chequia",
    "Polonia": "polonia",
    "Hungría": "hungria",
    "Eslovenia": "eslovenia",
    "Italia": "italia",
    "España": "espana",
}

# Cortes que no siguen la frontera del país.
BLOQUE_POR_SLUG = {
    "paris": "paris",          # París tiene su propio bloque en el doc
    "pititas": "pititas",      # parada local de Katia
    "margen-flex": "italia",   # colchón pensado para el sur; sin país propio
}


def _mid(banda: tuple[float, float]) -> Decimal:
    lo, hi = banda
    return (Decimal(str(lo)) + Decimal(str(hi))) / 2


def target_for_bloque(bloque: str) -> Decimal:
    noches, subtotal, alojamiento = BLOQUES[bloque]
    vivir = (_mid(subtotal) - _mid(alojamiento)) / noches + UPLIFT_LOCAL_USD
    return vivir.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def bloque_for(stop: Stop) -> str | None:
    if stop.slug in BLOQUE_POR_SLUG:
        return BLOQUE_POR_SLUG[stop.slug]
    return BLOQUE_POR_PAIS.get(stop.country or "")


async def main(dry_run: bool) -> None:
    engine = make_engine(get_settings().database_url)
    maker = async_session_factory(engine)
    async with maker() as session:
        stops = (await session.execute(select(Stop))).scalars().all()
        existing = {
            r.stop_slug for r in (await session.execute(select(StopBudget))).scalars()
        }

        inserted = respected = 0
        unmapped: list[str] = []
        for stop in sorted(stops, key=lambda s: s.order):
            if stop.is_archived:
                continue
            if stop.slug in existing:
                print(f"  {stop.slug:<16} respetado (ya tenía target)")
                respected += 1
                continue
            bloque = bloque_for(stop)
            if bloque is None:
                unmapped.append(stop.slug)
                continue
            target = target_for_bloque(bloque)
            print(f"  {stop.slug:<16} {target:>7} USD/día  ({bloque})")
            if not dry_run:
                session.add(StopBudget(stop_slug=stop.slug, daily_usd=target))
            inserted += 1

        if inserted and not dry_run:
            await session.commit()

        verbo = "se insertarían" if dry_run else "insertados"
        print(f"\n{verbo} {inserted}, respetados {respected}")
        if unmapped:
            # No es fatal, pero tiene que verse: una parada sin target baja la
            # cobertura de /presupuesto, y eso no puede pasar en silencio.
            print(
                f"SIN MAPEO ({len(unmapped)}): {', '.join(unmapped)}\n"
                "  → agregá su país a BLOQUE_POR_PAIS o su slug a BLOQUE_POR_SLUG, "
                "o cargá el target desde /presupuesto."
            )
    await engine.dispose()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="mostrar qué se insertaría, sin escribir")
    asyncio.run(main(ap.parse_args().dry_run))
