"""Seed de datos dummy para el demo local (SQLite).

Construye una DB lista para navegar la app "como si estuvieras en el medio del
viaje": un itinerario de ~95 noches donde HOY cae en el día 40 (faltan ~55).
Las fechas se calculan desde `date.today()`, así que la demo siempre luce
mid-trip sin importar cuándo se corra.

Montos alineados a Itinerary/PRESUPUESTO.md (confirmados Spitwise + ritmo
diario $/pp). Alojamiento usa los totales reales del hogar; comida/transporte/
actividades siguen el estimado por región; prepago (vuelos, Eurail, seguros,
entradas) se carga como generales o en la ciudad correspondiente.

Es self-bootstrapping: crea las tablas y siembra categorías + usuarios si la DB
está vacía, después puebla stops y movimientos.

Uso (ver "Demo local" en CLAUDE.md):

    cd backend
    DATABASE_URL="sqlite+aiosqlite:///$(pwd)/demo.db" \
    SECRET_KEY=demo-secret-key-local-only \
    AUTH_USERS="bruno:demo:5491111,katia:demo:5492222" \
    ENVIRONMENT=dev \
    .venv/bin/python scripts/seed_demo_data.py
"""
import asyncio
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import delete, select

from app.categories.seed import seed_categories
from app.config import get_settings
from app.db.engine import async_session_factory, make_engine
from app.db.models import Base, Category, Movement, Stop, User
from app.users import seed_users_from_env
from demo_common import REGION_BY_SLUG, _add_mov, _created, _seed_day  # noqa: F401

TODAY = date.today()
# HOY = día 40 (la llegada a la 1.ª parada es el día 1). Alineado a Andiamo /
# PRESUPUESTO: 108 noches (5 ago → 21 nov): paradas fechadas + Sur Italia 10n
# + margen flex 3n. Pititas es paralelo (no suma).
START = TODAY - timedelta(days=39)
# Día del viaje en el que cae HOY (1-indexed). Mantener mid-trip ~Alsacia.
TODAY_TRIP_DAY = 40

# Banderas: Inglaterra/Escocia usan secuencias de subdivisión (gbeng / gbsct),
# no el 🏴 negro pelado — el frontend las resuelve a las SVG correctas.
ENGLAND = "🏴\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f"
SCOTLAND = "🏴\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f"

# (slug, nombre, país, flag, moneda, noches)
# lodging_usd = total hogar (shared) o personal si split != shared.
# Del PRESUPUESTO confirmado hasta Interlaken; post-Suiza = punto medio × 2 pp.
ITINERARY = [
    # slug, name, country, flag, cur, nights, lodging_usd, split
    ("londres", "Londres", "Reino Unido", ENGLAND, "GBP", 8, 601.72, "shared"),
    ("york", "York", "Reino Unido", ENGLAND, "GBP", 2, 238.00, "shared"),
    ("edimburgo", "Edimburgo", "Reino Unido", SCOTLAND, "GBP", 3, 270.02, "shared"),
    ("fort-william", "Fort William", "Reino Unido", SCOTLAND, "GBP", 2, 215.40, "shared"),
    ("portree", "Portree", "Reino Unido", SCOTLAND, "GBP", 2, 188.06, "shared"),
    ("inverness", "Inverness", "Reino Unido", SCOTLAND, "GBP", 2, 196.28, "shared"),
    ("edimburgo-2", "Edimburgo (tránsito)", "Reino Unido", SCOTLAND, "GBP", 1, 122.00, "shared"),
    ("amsterdam", "Ámsterdam", "Países Bajos", "🇳🇱", "EUR", 4, 460.83, "shared"),
    ("paris", "París", "Francia", "🇫🇷", "EUR", 6, 532.68, "shared"),
    # Portugal: solo Bruno (Katia en Pititas en paralelo).
    ("lisboa", "Lisboa", "Portugal", "🇵🇹", "EUR", 5, 152.87, "payer_only"),
    ("porto", "Porto", "Portugal", "🇵🇹", "EUR", 3, 111.60, "payer_only"),
    ("estrasburgo", "Estrasburgo", "Francia", "🇫🇷", "EUR", 2, 237.00, "shared"),  # ← HOY
    ("colmar", "Colmar", "Francia", "🇫🇷", "EUR", 2, 136.00, "shared"),
    ("friburgo", "Friburgo", "Alemania", "🇩🇪", "EUR", 3, 252.69, "shared"),
    ("interlaken", "Interlaken", "Suiza", "🇨🇭", "CHF", 4, 365.32, "shared"),
    # Post-Suiza: midpoint del rango pp × 2 (hogar).
    ("viena", "Viena", "Austria", "🇦🇹", "EUR", 5, 530.00, "shared"),
    ("praga", "Praga", "Chequia", "🇨🇿", "CZK", 5, 300.00, "shared"),
    ("cracovia", "Cracovia", "Polonia", "🇵🇱", "PLN", 4, 168.00, "shared"),
    ("budapest", "Budapest", "Hungría", "🇭🇺", "HUF", 4, 188.00, "shared"),
    ("liubliana", "Liubliana", "Eslovenia", "🇸🇮", "EUR", 4, 288.00, "shared"),
    ("florencia", "Florencia", "Italia", "🇮🇹", "EUR", 5, 440.00, "shared"),
    ("roma", "Roma", "Italia", "🇮🇹", "EUR", 7, 616.00, "shared"),
    ("napoles", "Nápoles", "Italia", "🇮🇹", "EUR", 2, 176.00, "shared"),
    # Sur de Italia (Puglia/Sicilia tentativo) — cierra el hueco Nápoles→Bcn.
    ("sur-italia", "Sur de Italia", "Italia", "🇮🇹", "EUR", 10, 880.00, "shared"),
    ("barcelona", "Barcelona", "España", "🇪🇸", "EUR", 5, 390.00, "shared"),
    ("madrid", "Madrid", "España", "🇪🇸", "EUR", 5, 390.00, "shared"),
    # Colchón del PRESUPUESTO (ubicación TBD) — is_flex_margin en el Stop.
    ("margen-flex", "Margen flex", None, None, "EUR", 3, 234.00, "shared"),
]

TOTAL_NIGHTS = sum(row[5] for row in ITINERARY)
assert TOTAL_NIGHTS == 108, f"esperado 108 noches Andiamo, got {TOTAL_NIGHTS}"

async def main() -> None:
    random.seed(42)
    settings = get_settings()
    engine = make_engine(settings.database_url)
    Session = async_session_factory(engine)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with Session() as s:
        await seed_categories(s)
        await seed_users_from_env(s)
        await s.commit()

    async with Session() as s:
        users = (await s.execute(select(User).order_by(User.id))).scalars().all()
        if len(users) < 2:
            raise SystemExit("Faltan usuarios: definí AUTH_USERS con 2 personas.")
        bruno = next((u for u in users if u.username == "bruno"), users[0])
        katia = next((u for u in users if u.username == "katia"), users[1])
        cats = {c.name: c for c in (await s.execute(select(Category))).scalars().all()}

        await s.execute(delete(Movement))
        await s.execute(delete(Stop))

        # --- Stops del itinerario + alojamiento ---
        cursor = START
        stop_dates: dict[str, tuple[date, date]] = {}
        for order, (slug, name, country, flag, cur, nights, lodging, split) in enumerate(ITINERARY):
            arrival = cursor
            departure = cursor + timedelta(days=nights)
            cursor = departure
            stop_dates[slug] = (arrival, departure)
            owner = "bruno" if slug in ("lisboa", "porto") else None
            is_flex = slug == "margen-flex"
            s.add(Stop(
                slug=slug, order=order, name=name, country=country, country_flag=flag,
                arrival_date=arrival, departure_date=departure, currency_code=cur,
                timezone="Europe/London", is_transit=slug.endswith("-2"),
                is_flex_margin=is_flex, owner_username=owner,
            ))

            past_or_current = arrival <= TODAY
            payer = bruno
            # Portugal: solo Bruno. Resto shared. Flex: solo la reserva (pending).
            if past_or_current:
                _add_mov(s, cats["Alojamiento"], cur, lodging,
                         arrival - timedelta(days=30), slug, name, payer, split,
                         f"Alojamiento {name}")
            else:
                _add_mov(s, cats["Alojamiento"], cur, lodging,
                         TODAY, slug, name, payer, split,
                         f"Alojamiento {name}",
                         payment_date=arrival, status="pending")

        # Pititas (local, solo Katia) — paralelo a Lisboa/Porto; no suma a 108.
        lis_arr, _ = stop_dates["lisboa"]
        _, por_dep = stop_dates["porto"]
        pititas_order = next(i for i, row in enumerate(ITINERARY) if row[0] == "lisboa")
        s.add(Stop(
            slug="pititas", order=pititas_order, name="Pititas", country=None,
            country_flag="👭", arrival_date=lis_arr, departure_date=por_dep,
            currency_code="EUR", timezone="Europe/Paris", is_local=True,
            owner_username="katia",
        ))
        if lis_arr <= TODAY:
            _add_mov(s, cats["Alojamiento"], "EUR", 611.00,
                     lis_arr - timedelta(days=30), "pititas", "Pititas", katia,
                     "payer_only", "Hospedaje Pititas")

        # --- Gastos diarios (solo hasta HOY; sin margen flex) ---
        for slug, name, _country, _flag, cur, nights, _lodging, _split in ITINERARY:
            if slug == "margen-flex":
                continue
            arrival, _dep = stop_dates[slug]
            region = REGION_BY_SLUG[slug]
            for i in range(nights):
                day = arrival + timedelta(days=i)
                if day > TODAY:
                    break
                _seed_day(s, cats, cur, day, slug, name, bruno, katia, region)

        # Pititas: días de Katia en paralelo (comida etc.).
        if lis_arr <= TODAY:
            for i in range((min(por_dep, TODAY + timedelta(days=1)) - lis_arr).days):
                day = lis_arr + timedelta(days=i)
                if day > TODAY:
                    break
                _seed_day(s, cats, "EUR", day, "pititas", "Pititas", bruno, katia,
                          "portugal", force_payer=katia)

        # --- Prepago confirmado (PRESUPUESTO § Gastos Confirmados) ---
        pre = START - timedelta(days=45)
        # Vuelos ida (personales).
        _add_mov(s, cats["Transporte"], "USD", 488.00, pre, None, None, bruno,
                 "payer_only", "Vuelo BUE→LHR Smiles")
        _add_mov(s, cats["Transporte"], "USD", 480.00, pre, None, None, katia,
                 "payer_only", "Vuelo BUE→LHR Smiles")
        # Vuelo vuelta (pending al final del viaje).
        _add_mov(s, cats["Transporte"], "USD", 945.00, TODAY, None, None, bruno,
                 "shared", "Vuelo MAD→BUE Plus Ultra",
                 payment_date=START + timedelta(days=TOTAL_NIGHTS - 1), status="pending")
        # Seguros.
        _add_mov(s, cats["Salud"], "USD", 320.00, pre + timedelta(days=2), None, None,
                 bruno, "payer_only", "Seguro Pax Assistance")
        _add_mov(s, cats["Salud"], "USD", 320.00, pre + timedelta(days=2), None, None,
                 katia, "payer_only", "Seguro Pax Assistance")
        # Eurail + Eurostar + tramos.
        _add_mov(s, cats["Transporte"], "USD", 740.00, pre + timedelta(days=5), None, None,
                 bruno, "shared", "Eurail Pass ×2")
        _add_mov(s, cats["Transporte"], "USD", 78.88, stop_dates["amsterdam"][0],
                 "amsterdam", "Ámsterdam", bruno, "shared", "Reserva Eurostar AMS→París")
        _add_mov(s, cats["Transporte"], "USD", 39.00, stop_dates["amsterdam"][0],
                 "amsterdam", "Ámsterdam", katia, "payer_only", "Tren AMS→París")
        _add_mov(s, cats["Transporte"], "USD", 184.35, stop_dates["edimburgo-2"][0],
                 "edimburgo-2", "Edimburgo (tránsito)", bruno, "shared",
                 "Vuelo EDI→AMS")
        _add_mov(s, cats["Transporte"], "USD", 342.00, stop_dates["fort-william"][0],
                 "fort-william", "Fort William", bruno, "shared", "Auto Highlands")
        # Portugal (Bruno).
        _add_mov(s, cats["Transporte"], "USD", 93.77, stop_dates["lisboa"][0] - timedelta(days=1),
                 "lisboa", "Lisboa", bruno, "payer_only", "Vuelo París→Lisboa")
        _add_mov(s, cats["Transporte"], "USD", 90.00, stop_dates["porto"][0] + timedelta(days=2),
                 "porto", "Porto", bruno, "payer_only", "Vuelo Porto→Estrasburgo")
        # Actividades ya compradas.
        _add_mov(s, cats["Actividades"], "USD", 138.19, stop_dates["londres"][0] + timedelta(days=2),
                 "londres", "Londres", bruno, "shared", "Tour Harry Potter")
        _add_mov(s, cats["Actividades"], "USD", 43.02, stop_dates["londres"][0] + timedelta(days=4),
                 "londres", "Londres", katia, "shared", "Museo Británico")
        _add_mov(s, cats["Actividades"], "USD", 68.00, stop_dates["edimburgo"][0] + timedelta(days=1),
                 "edimburgo", "Edimburgo", bruno, "shared", "Mary King's Close")
        _add_mov(s, cats["Actividades"], "USD", 53.74, stop_dates["amsterdam"][0] + timedelta(days=1),
                 "amsterdam", "Ámsterdam", katia, "shared", "Museo Ana Frank")
        # Gear.
        _add_mov(s, cats["Compras"], "USD", 118.00, pre + timedelta(days=10), None, None,
                 bruno, "payer_only", "Compras Amazon (equipaje)")

        # Cashback QA — descripciones normales; el badge sale de cashback_*.
        _add_mov(s, cats["Comida"], "EUR", 48.00, TODAY - timedelta(days=2),
                 "estrasburgo", "Estrasburgo", bruno, "shared", "Cena",
                 cashback_kind="pct", cashback_value=Decimal("2"))
        _add_mov(s, cats["Compras"], "EUR", 65.00, TODAY - timedelta(days=5),
                 "paris", "París", katia, "payer_only", "Souvenirs",
                 cashback_kind="amount", cashback_value=Decimal("5"))
        _add_mov(s, cats["Actividades"], "GBP", 55.00, START + timedelta(days=3),
                 "londres", "Londres", bruno, "shared", "Tour a pie",
                 cashback_kind="pct", cashback_value=Decimal("3"))
        _add_mov(s, cats["Transporte"], "GBP", 28.00, START + timedelta(days=1),
                 "londres", "Londres", katia, "shared", "Oyster top-up",
                 cashback_kind="amount", cashback_value=Decimal("2"))
        _add_mov(s, cats["Salidas"], "EUR", 36.00, TODAY - timedelta(days=1),
                 "estrasburgo", "Estrasburgo", katia, "shared", "Vinos",
                 cashback_kind="pct", cashback_value=Decimal("1.5"))

        # Settlement reciente.
        s.add(Movement(
            type="settlement", amount=Decimal("200"), currency="USD", amount_usd=Decimal("200"),
            fx_rate=Decimal("1.0"), fx_source="manual", paid_by=katia.id, split="shared",
            description="Le pasé 200 usd", created_by=katia.id,
            created_at=_created(TODAY - timedelta(days=3)),
        ))

        # Awaiting / pending de confirmación (montos realistas de cuotas).
        current = next(
            (st for st in (await s.execute(select(Stop))).scalars().all()
             if st.arrival_date and st.departure_date
             and st.arrival_date <= TODAY < st.departure_date
             and not st.is_local),
            None,
        )
        cur_slug = current.slug if current else None
        cur_city = current.name if current else None
        cur_code = current.currency_code if current else "EUR"
        _add_mov(s, cats["Alojamiento"], cur_code, 118.50, TODAY - timedelta(days=10),
                 cur_slug, cur_city, bruno, "shared", "Airbnb — saldo (2/2)",
                 payment_date=TODAY - timedelta(days=1), status="awaiting")
        _add_mov(s, cats["Actividades"], cur_code, 54.00, TODAY - timedelta(days=20),
                 cur_slug, cur_city, katia, "shared", "Entradas tour — saldo (2/2)",
                 payment_date=TODAY - timedelta(days=7), status="awaiting")
        _add_mov(s, cats["Transporte"], cur_code, 42.00, TODAY,
                 cur_slug, cur_city, bruno, "shared", "Tren — saldo (2/2)",
                 payment_date=TODAY + timedelta(days=1), status="pending")

        await s.commit()
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
            f"seeded {len(ITINERARY)} stops (+pititas) · {TOTAL_NIGHTS} noches · "
            f"{len(movs)} movimientos\n"
            f"HOY={TODAY} · inicio={START} · fin={START + timedelta(days=TOTAL_NIGHTS)} "
            f"(día {TODAY_TRIP_DAY}/{TOTAL_NIGHTS})\n"
            f"TOTAL USD {total.quantize(Decimal('0.1'))}"
        )
        for name, amt in sorted(by_cat.items(), key=lambda x: -x[1]):
            pct = (amt / total * 100) if total else 0
            print(f"  {name:14} USD {amt.quantize(Decimal('0.1')):>8}  ({pct:.0f}%)")


if __name__ == "__main__":
    asyncio.run(main())
