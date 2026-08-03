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
Las bandas salen de `Itinerary/PRESUPUESTO.md`, sección *Resumen por Ciudad*
(tabla maestra). Ese doc da por ciudad **comida + transporte local +
actividades + alojamiento**. Acá hace falta el USD/día pp de "vivir"
(todo menos alojamiento y generales):

    vivir_lo = comida_lo + transp_local_lo + actividades_lo
    vivir_hi = comida_hi + transp_local_hi + actividades_hi
    min = vivir_lo / noches
    max = vivir_hi / noches

Los bordes se emparejan por **escenario**, no cruzados: el piso del doc va
con el piso; el techo con el techo. Cruzarlos daría una banda artificialmente
ancha que no corresponde a ninguna lectura real del presupuesto.

La aritmética se hace en código a propósito: cuando el PRESUPUESTO se
actualice, se toca la tabla `CIUDADES` de abajo y el diff del PR muestra qué
cambió de la fuente, no un número mágico ya digerido.

**Qué NO entra**
- Alojamiento: es otra columna en /presupuesto (reservas).
- Transporte interciudad (Eurail, vuelos, Italo, auto Highlands): vive en
  generales / fijos, no en el ritmo diario de la parada.
- eSIM, seguros, ETA/ETIAS, Amazon: gastos generales (sin ciudad).
- Lavandería: global en "Otros"; no se prorratea acá (antes iba en un uplift
  porque el transporte local tampoco estaba por ciudad; ahora sí lo está).

**Pititas** es una sola parada local de 8 noches: se suman las filas
Ámsterdam-Pititas (3n) + París-Pititas (5n) del doc y se divide por 8.

**Highlands / Sur de Italia** agrupan varias paradas Andiamo (fort-william /
portree / inverness · puglia / sicilia / calabria) bajo la misma banda $/día
del bloque del doc.
"""
import argparse
import asyncio
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select

from app.config import get_settings
from app.db.engine import async_session_factory, make_engine
from app.db.models import Stop, StopBudget

# (noches, comida, transp_local, actividades) — de PRESUPUESTO.md *Tabla maestra*.
# Rangos en USD pp del bloque entero (no por día). El alojamiento queda afuera.
CIUDADES: dict[str, tuple[int, tuple[float, float], tuple[float, float], tuple[float, float]]] = {
    "londres":            (8,  (192, 312), (64, 90),  (190, 320)),
    "york":               (2,  (42, 68),   (0, 0),    (35, 70)),
    "edimburgo":          (3,  (66, 105),  (8, 22),   (75, 130)),
    "highlands":          (6,  (138, 222), (70, 105), (60, 160)),
    "edimburgo-transito": (1,  (22, 35),   (0, 8),    (0, 0)),
    "amsterdam":          (4,  (96, 152),  (12, 46),  (95, 165)),
    "paris":              (6,  (138, 222), (41, 55),  (150, 240)),
    "lisboa":             (5,  (85, 135),  (17, 33),  (50, 95)),
    "porto":              (3,  (51, 81),   (10, 19),  (35, 75)),
    # Pititas = Ámsterdam 3n + París 5n (Katia). Sumadas; se dividen por 8.
    "pititas":            (8,  (187, 299), (37, 77),  (120, 240)),
    "estrasburgo":        (2,  (44, 66),   (0, 11),   (15, 40)),
    "colmar":             (2,  (44, 66),   (0, 22),   (15, 32)),
    "friburgo":           (3,  (63, 96),   (0, 8),    (15, 35)),
    "interlaken":         (4,  (144, 212), (15, 40),  (60, 230)),
    # Innsbruck: 0 noches en el borrador; banda provisional del footnote si
    # se confirman 1–2 noches (comida + transp + Nordkette opcional).
    "innsbruck":          (1,  (22, 33),   (8, 9),    (0, 34)),
    "viena":              (5,  (105, 160), (22, 40),  (75, 140)),
    "praga":              (5,  (70, 110),  (10, 30),  (55, 100)),
    "cracovia":           (4,  (52, 84),   (8, 20),   (95, 140)),
    "budapest":           (4,  (52, 88),   (12, 20),  (85, 130)),
    "eslovenia":          (4,  (64, 100),  (15, 120), (60, 120)),
    "florencia":          (5,  (105, 160), (0, 15),   (85, 150)),
    "roma":               (7,  (147, 224), (25, 55),  (110, 190)),
    "napoles":            (2,  (34, 52),   (8, 20),   (35, 70)),
    "sur-italia":         (10, (180, 280), (60, 150), (80, 160)),
    "barcelona":          (5,  (105, 155), (10, 25),  (70, 140)),
    "madrid":             (5,  (95, 145),  (14, 38),  (40, 90)),
    "margen":             (3,  (54, 90),   (10, 30),  (20, 60)),
}

# Slug Andiamo / Spitwise → clave de CIUDADES. Varias paradas pueden compartir
# banda (Highlands, Sur de Italia, candidatas de la misma región).
BANDA_POR_SLUG = {
    "londres": "londres",
    "york": "york",
    "edimburgo": "edimburgo",
    "fort-william": "highlands",
    "portree": "highlands",
    "inverness": "highlands",
    "edimburgo-2": "edimburgo-transito",
    "amsterdam": "amsterdam",
    "paris": "paris",
    "lisboa": "lisboa",
    "porto": "porto",
    "pititas": "pititas",
    "estrasburgo": "estrasburgo",
    "colmar": "colmar",
    "friburgo": "friburgo",
    "interlaken": "interlaken",
    "grindelwald": "interlaken",
    "lauterbrunnen": "interlaken",
    "innsbruck": "innsbruck",
    "viena": "viena",
    "praga": "praga",
    "cracovia": "cracovia",
    "budapest": "budapest",
    "liubliana": "eslovenia",
    "bled": "eslovenia",
    "bovec": "eslovenia",
    "florencia": "florencia",
    "roma": "roma",
    "napoles": "napoles",
    "puglia": "sur-italia",
    "sicilia": "sur-italia",
    "calabria": "sur-italia",
    "barcelona": "barcelona",
    "madrid": "madrid",
}

# Fallback por país si el slug no está mapeado (parada nueva / candidata).
# Apunta a la ciudad "típica" del tramo, no a un promedio inventado: una
# parada nueva en Chequia hereda Praga; una en Italia hereda el Sur (el
# tramo abierto), salvo que el slug ya diga florencia/roma/napoles.
BANDA_POR_PAIS = {
    "Reino Unido": "londres",
    "Países Bajos": "amsterdam",
    "Francia": "estrasburgo",
    "Alemania": "friburgo",
    "Portugal": "lisboa",
    "Suiza": "interlaken",
    "Austria": "viena",
    "Chequia": "praga",
    "Polonia": "cracovia",
    "Hungría": "budapest",
    "Eslovenia": "eslovenia",
    "Italia": "sur-italia",
    "España": "madrid",
}


def _q(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def band_for_ciudad(ciudad: str) -> tuple[Decimal, Decimal]:
    """(min, max) de USD/día de vivir, por persona. Ver la derivación arriba."""
    noches, comida, transp, act = CIUDADES[ciudad]
    n = Decimal(noches)
    lo = (Decimal(str(comida[0])) + Decimal(str(transp[0])) + Decimal(str(act[0]))) / n
    hi = (Decimal(str(comida[1])) + Decimal(str(transp[1])) + Decimal(str(act[1]))) / n
    # Un bloque cuyo techo de un rubro baje más que el piso de otro podría
    # invertir la banda; el borde ordena en vez de escribir algo que budget.py
    # descartaría en silencio.
    return (_q(min(lo, hi)), _q(max(lo, hi)))


def ciudad_for(stop: Stop) -> str | None:
    """Clave de CIUDADES para una parada, o None si no hay mapeo."""
    if getattr(stop, "is_flex_margin", False):
        return "margen"
    if stop.slug in BANDA_POR_SLUG:
        return BANDA_POR_SLUG[stop.slug]
    return BANDA_POR_PAIS.get(stop.country or "")


def band_for_stop(stop: Stop) -> tuple[Decimal, Decimal] | None:
    """Banda de vivir para una parada, o None si no está mapeada."""
    ciudad = ciudad_for(stop)
    return band_for_ciudad(ciudad) if ciudad else None


# Aliases para callers viejos (demo_common importaba bloque_for / band_for_bloque).
def bloque_for(stop: Stop) -> str | None:
    return ciudad_for(stop)


def band_for_bloque(bloque: str) -> tuple[Decimal, Decimal]:
    return band_for_ciudad(bloque)


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
            ciudad = ciudad_for(stop)
            if ciudad is None:
                unmapped.append(stop.slug)
                continue
            lo, hi = band_for_ciudad(ciudad)
            verbo = "reescrito" if row is not None else "nuevo"
            print(f"  {stop.slug:<16} {lo:>7} – {hi:<7} USD/día  ({ciudad}, {verbo})")
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
                "  → agregá su slug a BANDA_POR_SLUG o su país a BANDA_POR_PAIS, "
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
