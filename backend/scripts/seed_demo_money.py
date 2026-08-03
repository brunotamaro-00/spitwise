"""Seed de movimientos ficticios para el deploy público (demo.spitwise.lat).

A diferencia de `seed_demo_data.py` (demo local, itinerario hardcodeado), este
script **no inventa paradas**: sincroniza el itinerario desde la demo de Andiamo
con el mismo camino que usa producción (`sync_stops`) y siembra movimientos
sobre lo que haya venido. Así el deploy público demuestra la integración real en
vez de dos snapshots que se contradicen — duplicar el itinerario acá garantizaba
que los slugs divergieran y que el primer arranque archivara paradas con gastos.

De cada parada se leen slug, nombre, moneda y fechas; el ritmo de gasto sale de
la tabla por región de `demo_common`. Se saltean candidatas, margen flex,
archivadas y las que no tengan fechas.

DESTRUCTIVO sobre `movements`. Lo corre el cron nocturno de Railway para limpiar
lo que hayan cargado los visitantes. Nunca apuntarlo a la DB de producción.

Uso:

    cd backend
    ANDIAMO_URL=https://demo.andiamo.lat TRIP_SHARED_API_KEY=... \
    DATABASE_URL=... SECRET_KEY=... AUTH_USERS="bruno:demo:,katia:demo:" \
    DEMO_MODE=true DEMO_TODAY=2026-09-25 \
    python scripts/seed_demo_money.py

DEMO_TODAY es obligatorio y tiene que ser el mismo valor que sirve la API
(`trip_time.today_in_tz`) y que congela Andiamo (NEXT_PUBLIC_DEMO_TODAY).
"""
import asyncio
import random
import sys
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import delete, select

from app.andiamo import sync_stops
from app.categories.seed import seed_categories
from app.config import get_settings
from app.db.engine import async_session_factory, make_engine
from app.db.models import Category, Movement, Stop, StopBudget, User
from app.users import seed_users_from_env
from demo_common import (
    REGION_DAILY,
    _add_mov,
    _created,
    _seed_day,
    budget_band_for,
    ensure_cities_in_plan,
    ensure_cities_over,
    region_for,
)

# Lo fija main() con _frozen_today(); a nivel módulo no, para que importar este
# script (tests, tooling) no reviente por una env var faltante.
TODAY: date


def _frozen_today() -> date:
    """El "hoy" de la demo sale de DEMO_TODAY, no del reloj.

    Tiene que ser el mismo que sirve la API (`trip_time.today_in_tz`) y el mismo
    que congela Andiamo: sembrar contra una fecha y renderizar contra otra deja
    la demo incoherente en silencio (paradas actuales distintas, gastos "del
    futuro"). Por eso falla ruidoso en vez de caer a date.today().
    """
    raw = get_settings().demo_today
    if not raw:
        raise SystemExit(
            "Falta DEMO_TODAY (YYYY-MM-DD). Es el hoy congelado de la demo y "
            "tiene que coincidir con NEXT_PUBLIC_DEMO_TODAY de Andiamo."
        )
    return date.fromisoformat(raw)


def _budgetable(stop: Stop) -> bool:
    """Paradas que cuentan en la cobertura de /presupuesto.

    Espeja `app.budget._eligible` sobre las filas crudas de Stop. Ojo: NO es
    `_usable` — el margen flex no recibe gastos pero sí tiene noches en el
    itinerario, así que sin target baja la cobertura y la demo abriría con la
    proyección en modo "parcial".
    """
    return (
        not stop.is_candidate
        and not stop.is_archived
        and stop.arrival_date is not None
        and stop.departure_date is not None
        and stop.departure_date > stop.arrival_date
    )


def _seed_budgets(s, stops) -> None:
    for stop in stops:
        if not _budgetable(stop):
            continue
        band = budget_band_for(stop)
        if band is not None:
            s.add(StopBudget(stop_slug=stop.slug,
                             daily_min_usd=band[0], daily_max_usd=band[1]))


def _usable(stop: Stop) -> bool:
    """Paradas que reciben gastos: las mismas que `GET /stops` le muestra al
    frontend, y con fechas — una candidata sin fechas no tiene días que sembrar."""
    return (
        not stop.is_candidate
        and not stop.is_flex_margin
        and not stop.is_archived
        and stop.arrival_date is not None
        and stop.departure_date is not None
        and stop.departure_date > stop.arrival_date
    )


async def main() -> None:
    # Semilla fija + hoy congelado: dos corridas del cron producen exactamente
    # la misma demo, no una parecida.
    random.seed(42)
    global TODAY
    TODAY = _frozen_today()
    settings = get_settings()
    if not settings.andiamo_url:
        raise SystemExit("Falta ANDIAMO_URL: este seed toma el itinerario de Andiamo.")

    engine = make_engine(settings.database_url)
    Session = async_session_factory(engine)

    # Las tablas las crea Alembic en el arranque del servicio; acá solo se
    # completa lo idempotente que el lifespan también siembra.
    async with Session() as s:
        await seed_categories(s)
        await seed_users_from_env(s)
        await s.commit()

    async with Session() as s:
        result = await sync_stops(s)
        if result["status"] != "ok" or result["synced"] == 0:
            raise SystemExit(
                f"Sync con Andiamo falló ({result}). No se siembra nada: sin "
                "itinerario los movimientos quedarían huérfanos."
            )
        print(f"Itinerario sincronizado desde {settings.andiamo_url}: {result}")

        users = (await s.execute(select(User).order_by(User.id))).scalars().all()
        if len(users) < 2:
            raise SystemExit("Faltan usuarios: definí AUTH_USERS con 2 personas.")
        bruno = next((u for u in users if u.username == "bruno"), users[0])
        katia = next((u for u in users if u.username == "katia"), users[1])
        cats = {c.name: c for c in (await s.execute(select(Category))).scalars().all()}

        await s.execute(delete(Movement))
        await s.execute(delete(StopBudget))
        _seed_budgets(s, (await s.execute(select(Stop))).scalars().all())

        stops = [
            st for st in (await s.execute(select(Stop).order_by(Stop.order))).scalars().all()
            if _usable(st)
        ]
        if not stops:
            raise SystemExit("El itinerario sincronizado no tiene paradas con fechas.")

        first, last = stops[0], stops[-1]
        days = 0

        for stop in stops:
            region = region_for(stop.slug)
            cur = stop.currency_code or "EUR"
            nights = (stop.departure_date - stop.arrival_date).days

            # Alojamiento: se paga al reservar (~30 días antes). Una parada
            # futura queda `pending` con fecha de pago en el check-in, que es lo
            # que alimenta el banner "por confirmar" y la ciudad "reservada".
            lo, hi = REGION_DAILY[region]["lodging_night"]
            lodging = round(random.uniform(lo, hi) * nights, 2)
            split = "payer_only" if region == "portugal" else "shared"
            if stop.arrival_date <= TODAY:
                _add_mov(s, cats["Alojamiento"], cur, lodging,
                         stop.arrival_date - timedelta(days=30), stop.slug, stop.name,
                         bruno, split, f"Alojamiento {stop.name}")
            else:
                _add_mov(s, cats["Alojamiento"], cur, lodging, TODAY, stop.slug, stop.name,
                         bruno, split, f"Alojamiento {stop.name}",
                         payment_date=stop.arrival_date, status="pending")

            # Gasto del día a día, solo hasta hoy.
            for i in range(nights):
                day = stop.arrival_date + timedelta(days=i)
                if day > TODAY:
                    break
                _seed_day(s, cats, cur, day, stop.slug, stop.name, bruno, katia, region)
                days += 1

            # Lavandería: no es diaria, es una vez cada estadía larga. Va acá y
            # no en _seed_day justamente por eso.
            mid = stop.arrival_date + timedelta(days=nights // 2)
            if nights >= 4 and mid <= TODAY:
                _add_mov(s, cats["Lavandería"], cur, round(random.uniform(18, 26), 2),
                         mid, stop.slug, stop.name, random.choice([bruno, katia]),
                         "shared", f"Lavandería · {stop.name}")

        _seed_prepaid(s, cats, bruno, katia, stops)
        _seed_edge_cases(s, cats, bruno, katia, stops)
        pushed = await ensure_cities_over(s, today=TODAY, bruno=bruno, cats=cats)
        if pushed:
            print(f"overspend forzado: {', '.join(pushed)}")
        lifted = await ensure_cities_in_plan(s, today=TODAY, bruno=bruno, cats=cats)
        if lifted:
            print(f"en plan forzado: {', '.join(lifted)}")

        # Validar antes de commitear: si algo no cierra, el rollback deja la
        # demo de ayer —que estaba bien— en vez de publicar una rota.
        await _report(s, cats, stops, first, last, days)
        await s.commit()


def _seed_prepaid(s, cats, bruno, katia, stops) -> None:
    """Gastos generales sin ciudad (vuelos, seguros, pases) + el vuelo de vuelta
    como `pending`, que es lo que hace visible el estado 'por confirmar'."""
    pre = stops[0].arrival_date - timedelta(days=45)
    _add_mov(s, cats["Transporte"], "USD", 488.00, pre, None, None, bruno,
             "payer_only", "Vuelo BUE→LHR Smiles")
    _add_mov(s, cats["Transporte"], "USD", 480.00, pre, None, None, katia,
             "payer_only", "Vuelo BUE→LHR Smiles")
    _add_mov(s, cats["Salud"], "USD", 320.00, pre + timedelta(days=2), None, None,
             bruno, "payer_only", "Seguro Pax Assistance")
    _add_mov(s, cats["Salud"], "USD", 320.00, pre + timedelta(days=2), None, None,
             katia, "payer_only", "Seguro Pax Assistance")
    _add_mov(s, cats["Transporte"], "USD", 740.00, pre + timedelta(days=5), None, None,
             bruno, "shared", "Eurail Pass ×2")
    # eSIM: general SIN ciudad. No es "vivir" (no se consume en una parada), así
    # que queda en general_usd y fuera del presupuesto diario.
    _add_mov(s, cats["Otros"], "USD", 120.00, pre + timedelta(days=3), None, None,
             bruno, "payer_only", "eSIM datos 3,5 meses")
    _add_mov(s, cats["Otros"], "USD", 120.00, pre + timedelta(days=3), None, None,
             katia, "payer_only", "eSIM datos 3,5 meses")
    _add_mov(s, cats["Compras"], "USD", 118.00, pre + timedelta(days=10), None, None,
             bruno, "payer_only", "Compras Amazon (equipaje)")
    _add_mov(s, cats["Transporte"], "USD", 945.00, TODAY, None, None, bruno,
             "shared", "Vuelo MAD→BUE Plus Ultra",
             payment_date=stops[-1].departure_date, status="pending")


def _seed_edge_cases(s, cats, bruno, katia, stops) -> None:
    """Casos que hacen visibles features del producto: cashback (% y monto
    fijo), un settlement, y gastos `awaiting`/`pending` en la parada actual."""
    past = [st for st in stops if st.arrival_date <= TODAY]
    early = past[0] if past else stops[0]
    current = next(
        (st for st in stops if st.arrival_date <= TODAY < st.departure_date),
        past[-1] if past else stops[0],
    )
    cur_code = current.currency_code or "EUR"

    _add_mov(s, cats["Comida"], cur_code, 48.00, TODAY - timedelta(days=2),
             current.slug, current.name, bruno, "shared", "Cena",
             cashback_kind="pct", cashback_value=Decimal("2"))
    _add_mov(s, cats["Salidas"], cur_code, 36.00, TODAY - timedelta(days=1),
             current.slug, current.name, katia, "shared", "Vinos",
             cashback_kind="pct", cashback_value=Decimal("1.5"))
    _add_mov(s, cats["Actividades"], early.currency_code or "EUR", 55.00,
             early.arrival_date + timedelta(days=1), early.slug, early.name,
             bruno, "shared", "Tour a pie",
             cashback_kind="pct", cashback_value=Decimal("3"))
    _add_mov(s, cats["Compras"], early.currency_code or "EUR", 65.00,
             early.arrival_date + timedelta(days=2), early.slug, early.name,
             katia, "payer_only", "Souvenirs",
             cashback_kind="amount", cashback_value=Decimal("5"))

    # Settlement: hace que el neto entre los dos no sea el bruto acumulado.
    s.add(Movement(
        type="settlement", amount=Decimal("200"), currency="USD", amount_usd=Decimal("200"),
        fx_rate=Decimal("1.0"), fx_source="manual", paid_by=katia.id, split="shared",
        description="Le pasé 200 usd", created_by=katia.id,
        created_at=_created(TODAY - timedelta(days=3)),
    ))

    # UN solo gasto por confirmar, vencido ayer. `awaiting` = venció la fecha de
    # pago y espera confirmación manual en la web (la liquidación lazy no lo
    # toca: solo mira `pending`, y además el TC va lockeado por fx_source=manual).
    #
    # Uno y no tres a propósito: el banner es para mostrar la feature, no para
    # que la demo abra con una pila de pendientes que parece deuda técnica. Las
    # reservas de alojamiento futuras siguen siendo `pending`, pero su fecha de
    # pago es el check-in, así que no entran a `needsConfirmation` (que agarra
    # `awaiting` siempre y `pending` recién a ≤1 día del vencimiento).
    _add_mov(s, cats["Alojamiento"], cur_code, 118.50, TODAY - timedelta(days=10),
             current.slug, current.name, bruno, "shared", "Airbnb — saldo (2/2)",
             payment_date=TODAY - timedelta(days=1), status="awaiting")


async def _report(s, cats, stops, first, last, days) -> None:
    movs = (await s.execute(select(Movement))).scalars().all()
    by_cat: dict[str, Decimal] = {}
    total = Decimal("0")
    for m in movs:
        if m.type != "expense":
            continue
        total += Decimal(m.amount_usd)
        cname = next((c.name for c in cats.values() if c.id == m.category_id), "Sin cat")
        by_cat[cname] = by_cat.get(cname, Decimal("0")) + Decimal(m.amount_usd)
    print(
        f"seeded {len(stops)} paradas · {days} días con gasto · {len(movs)} movimientos\n"
        f"HOY={TODAY} · inicio={first.arrival_date} · fin={last.departure_date}\n"
        f"TOTAL USD {total.quantize(Decimal('0.1'))}"
    )
    for name, amt in sorted(by_cat.items(), key=lambda x: -x[1]):
        pct = (amt / total * 100) if total else 0
        print(f"  {name:14} USD {amt.quantize(Decimal('0.1')):>8}  ({pct:.0f}%)")

    missing = sorted(set(cats) - set(by_cat))
    if missing:
        raise SystemExit(
            f"Categorías sin un solo movimiento: {', '.join(missing)}. La demo "
            "muestra el catálogo completo en el donut y los filtros; una vacía "
            "se lee como feature a medio hacer."
        )

    # Espeja `lib/share.needsConfirmation` del frontend: `awaiting` siempre,
    # `pending` recién a ≤1 día del vencimiento. Si el hoy congelado se mueve
    # cerca de un check-in, la reserva de la próxima ciudad entra sola al aviso
    # y la demo abre con dos pendientes en vez de uno — que es justo lo que se
    # quiso sacar. Falla ruidoso antes de que lo vea nadie.
    to_confirm = [
        m for m in movs
        if m.type == "expense"
        and (
            m.status == "awaiting"
            or (m.status == "pending" and m.payment_date and m.payment_date <= TODAY + timedelta(days=1))
        )
    ]
    if len(to_confirm) != 1:
        raise SystemExit(
            f"Se esperaba 1 gasto por confirmar y hay {len(to_confirm)}: "
            f"{[(m.description, m.status, str(m.payment_date)) for m in to_confirm]}"
        )
    print(f"\n✓ 1 gasto por confirmar: {to_confirm[0].description} "
          f"(vence {to_confirm[0].payment_date})")

    # La demo pública no puede abrir /presupuesto a medio llenar: una parada sin
    # banda baja la cobertura y la proyección sale en modo "parcial", que se
    # lee como feature rota. Cae antes del commit, así que un fallo deja la
    # demo de ayer en pie.
    all_stops = (await s.execute(select(Stop))).scalars().all()
    seeded = {b.stop_slug for b in (await s.execute(select(StopBudget))).scalars()}
    uncovered = sorted(st.slug for st in all_stops if _budgetable(st) and st.slug not in seeded)
    if uncovered:
        raise SystemExit(
            f"Paradas sin banda de presupuesto: {', '.join(uncovered)}. Mapealas "
            "en scripts/seed_stop_budgets.py (BANDA_POR_SLUG / BANDA_POR_PAIS)."
        )
    print(f"✓ presupuesto: {len(seeded)} paradas con banda (cobertura 100%)")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except SystemExit as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
