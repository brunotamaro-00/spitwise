"""One-off (re-runnable): carga las bandas de "vivir" por parada.

Idempotente **por inserción**: solo crea las filas que faltan y nunca updatea.
Lo editado desde la web manda; volver a correr el script no lo pisa. `--force`
es la excepción documentada, para el one-off que abre las bandas después de la
migración 0013 (ver DEPLOY.md).

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
Las bandas salen de `Itinerary/PRESUPUESTO.md`, sección *Resumen por País*.
Ese doc da **rangos** y subtotales por bloque que **incluyen alojamiento**; acá
hace falta el USD/día pp de "vivir" (todo menos alojamiento y generales):

    min = (lo(subtotal) − lo(alojamiento)) / noches + UPLIFT_LOCAL_MIN
    max = (hi(subtotal) − hi(alojamiento)) / noches + UPLIFT_LOCAL_MAX

Los bordes se emparejan por **escenario**, no cruzados: el subtotal barato del
doc va con el alojamiento barato del mismo escenario. Cruzarlos (lo con hi)
daría una banda artificialmente ancha que no corresponde a ninguna lectura real
del presupuesto.

La aritmética se hace en código a propósito: cuando el PRESUPUESTO se
actualice, se toca la tabla `BLOQUES` de abajo y el diff del PR muestra qué
cambió de la fuente, no un número mágico ya digerido.

El **uplift** corrige un sesgo sistemático del doc. Dos rubros que en Spitwise
caen en una ciudad (y por lo tanto son "vivir") viven en tablas *globales* de
PRESUPUESTO.md, fuera de todos los subtotales por país. También son bandas, así
que también se abren:

    transporte local  $550-850 pp / 108 noches → $5,09 – $7,87 /día
    lavandería        $55-95   pp / 108 noches → $0,51 – $0,88 /día
                                                 ─────────────────
                                                  ≈ $5,60 – $8,75 /día

La eSIM NO entra: es un gasto **general**, se carga sin ciudad y por eso no es
"vivir" (queda en `general_usd`, con los vuelos y los seguros).

Sin el uplift todas las bandas quedan ~$7 bajas y la app muestra ámbar desde
el día 1, que es exactamente cómo deja de servir una herramienta así. Son dos
números auditables, y se sacan o se ajustan acá cuando haya datos reales.

Sesgo residual conocido: los subtotales de Reino Unido y Portugal ya incluyen
transporte intercity (auto de Highlands, vuelos), y los de Europa Central no
incluyen transporte de ningún tipo. Se acepta: corregirlo por bloque es una
tabla de excepciones que hay que re-derivar a mano en cada actualización del
doc, y la banda es un objetivo, no un límite.
"""
import argparse
import asyncio
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select

from app.config import get_settings
from app.db.engine import async_session_factory, make_engine
from app.db.models import Stop, StopBudget

# Ver el docstring: transporte local + lavandería, prorrateados en las 108
# noches del viaje. Van sumados a los dos bordes de todos los bloques. La eSIM
# queda afuera: es un gasto general (sin ciudad), así que nunca es "vivir".
UPLIFT_LOCAL_MIN = Decimal("5.60")
UPLIFT_LOCAL_MAX = Decimal("8.75")

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


def _q(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def band_for_bloque(bloque: str) -> tuple[Decimal, Decimal]:
    """(min, max) de USD/día de vivir, por persona. Ver la derivación arriba."""
    noches, subtotal, alojamiento = BLOQUES[bloque]
    n = Decimal(noches)
    lo = (Decimal(str(subtotal[0])) - Decimal(str(alojamiento[0]))) / n + UPLIFT_LOCAL_MIN
    hi = (Decimal(str(subtotal[1])) - Decimal(str(alojamiento[1]))) / n + UPLIFT_LOCAL_MAX
    # Un bloque cuyo alojamiento se encarece más rápido que el subtotal podría
    # invertir la banda; el borde ordena en vez de escribir algo que budget.py
    # descartaría en silencio.
    return (_q(min(lo, hi)), _q(max(lo, hi)))


def bloque_for(stop: Stop) -> str | None:
    if stop.slug in BLOQUE_POR_SLUG:
        return BLOQUE_POR_SLUG[stop.slug]
    return BLOQUE_POR_PAIS.get(stop.country or "")


async def main(dry_run: bool, force: bool) -> None:
    engine = make_engine(get_settings().database_url)
    maker = async_session_factory(engine)
    async with maker() as session:
        stops = (await session.execute(select(Stop))).scalars().all()
        existing = {
            r.stop_slug: r
            for r in (await session.execute(select(StopBudget))).scalars()
        }

        written = respected = 0
        unmapped: list[str] = []
        for stop in sorted(stops, key=lambda s: s.order):
            if stop.is_archived:
                continue
            row = existing.get(stop.slug)
            if row is not None and not force:
                print(f"  {stop.slug:<16} respetado (ya tenía banda)")
                respected += 1
                continue
            bloque = bloque_for(stop)
            if bloque is None:
                unmapped.append(stop.slug)
                continue
            lo, hi = band_for_bloque(bloque)
            verbo = "reescrito" if row is not None else "nuevo"
            print(f"  {stop.slug:<16} {lo:>7} – {hi:<7} USD/día  ({bloque}, {verbo})")
            if not dry_run:
                if row is None:
                    session.add(
                        StopBudget(
                            stop_slug=stop.slug, daily_min_usd=lo, daily_max_usd=hi
                        )
                    )
                else:
                    row.daily_min_usd, row.daily_max_usd = lo, hi
            written += 1

        if written and not dry_run:
            await session.commit()

        verbo = "se escribirían" if dry_run else "escritos"
        print(f"\n{verbo} {written}, respetados {respected}")
        if unmapped:
            # No es fatal, pero tiene que verse: una parada sin banda baja la
            # cobertura de /presupuesto, y eso no puede pasar en silencio.
            print(
                f"SIN MAPEO ({len(unmapped)}): {', '.join(unmapped)}\n"
                "  → agregá su país a BLOQUE_POR_PAIS o su slug a BLOQUE_POR_SLUG, "
                "o cargá la banda desde /presupuesto."
            )
    await engine.dispose()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="mostrar qué se escribiría, sin tocar la DB")
    ap.add_argument("--force", action="store_true",
                    help="pisar las bandas existentes con las del doc "
                         "(one-off de la migración 0013; borra lo editado en la web)")
    args = ap.parse_args()
    asyncio.run(main(args.dry_run, args.force))
