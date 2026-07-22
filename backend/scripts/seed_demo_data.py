"""Seed de datos dummy para el demo local (SQLite).

Construye una DB lista para navegar la app "como si estuvieras en el medio del
viaje": un itinerario de 100 noches donde HOY cae en el día 40 (faltan 60). Las
fechas se calculan desde `date.today()`, así que la demo siempre luce mid-trip
sin importar cuándo se corra.

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

from app.cashback import net_amount
from app.categories.seed import seed_categories
from app.config import get_settings
from app.db.engine import async_session_factory, make_engine
from app.db.models import Base, Category, Movement, Stop, User
from app.users import seed_users_from_env

TODAY = date.today()
# HOY = día 40 (la llegada a la 1.ª parada es el día 1). Alineado al itinerario
# confirmado de Andiamo (sin candidatas ni Pititas): ~95 noches.
START = TODAY - timedelta(days=39)

# Banderas: Inglaterra/Escocia usan secuencias de subdivisión (gbeng / gbsct),
# no el 🏴 negro pelado — el frontend las resuelve a las SVG correctas.
ENGLAND = "🏴\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f"
SCOTLAND = "🏴\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f"

# (slug Andiamo, nombre, país, flag, moneda, noches) — solo paradas confirmadas.
ITINERARY = [
    ("londres", "Londres", "Reino Unido", ENGLAND, "GBP", 8),
    ("york", "York", "Reino Unido", ENGLAND, "GBP", 2),
    ("edimburgo", "Edimburgo", "Reino Unido", SCOTLAND, "GBP", 3),
    ("fort-william", "Fort William", "Reino Unido", SCOTLAND, "GBP", 2),
    ("portree", "Portree", "Reino Unido", SCOTLAND, "GBP", 2),
    ("inverness", "Inverness", "Reino Unido", SCOTLAND, "GBP", 2),
    ("edimburgo-2", "Edimburgo (tránsito)", "Reino Unido", SCOTLAND, "GBP", 1),
    ("amsterdam", "Ámsterdam", "Países Bajos", "🇳🇱", "EUR", 4),
    ("paris", "París", "Francia", "🇫🇷", "EUR", 6),
    ("lisboa", "Lisboa", "Portugal", "🇵🇹", "EUR", 5),
    ("porto", "Porto", "Portugal", "🇵🇹", "EUR", 3),
    ("estrasburgo", "Estrasburgo", "Francia", "🇫🇷", "EUR", 2),  # ← HOY (día 40)
    ("colmar", "Colmar", "Francia", "🇫🇷", "EUR", 2),
    ("friburgo", "Friburgo", "Alemania", "🇩🇪", "EUR", 3),
    ("interlaken", "Interlaken", "Suiza", "🇨🇭", "CHF", 4),
    ("viena", "Viena", "Austria", "🇦🇹", "EUR", 5),
    ("praga", "Praga", "Chequia", "🇨🇿", "CZK", 5),
    ("cracovia", "Cracovia", "Polonia", "🇵🇱", "PLN", 4),
    ("budapest", "Budapest", "Hungría", "🇭🇺", "HUF", 4),
    ("liubliana", "Liubliana", "Eslovenia", "🇸🇮", "EUR", 4),
    ("florencia", "Florencia", "Italia", "🇮🇹", "EUR", 5),
    ("roma", "Roma", "Italia", "🇮🇹", "EUR", 7),
    ("napoles", "Nápoles", "Italia", "🇮🇹", "EUR", 2),
    ("barcelona", "Barcelona", "España", "🇪🇸", "EUR", 5),
    ("madrid", "Madrid", "España", "🇪🇸", "EUR", 5),
]

TOTAL_NIGHTS = sum(n for *_, n in ITINERARY)

FX = {"USD": Decimal("1.0"), "GBP": Decimal("1.27"), "EUR": Decimal("1.08"),
      "CHF": Decimal("1.12"), "CZK": Decimal("0.043"), "PLN": Decimal("0.25"),
      "HUF": Decimal("0.0028")}

# categoría -> (min, max) en USD por movimiento (se convierte a moneda local al
# guardar, así CZK/HUF quedan en miles y no en centavos).
SPEND = {
    "Alojamiento": (90, 170),
    "Comida": (18, 65),
    "Supermercado": (12, 40),
    "Transporte": (6, 45),
    "Actividades": (15, 70),
    "Compras": (20, 90),
    "Salidas": (14, 55),
    "Salud": (8, 25),
}


async def main() -> None:
    random.seed(42)
    settings = get_settings()
    engine = make_engine(settings.database_url)
    Session = async_session_factory(engine)

    # Bootstrap: tablas + categorías + usuarios (idempotente).
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

        # Reinicio idempotente de datos de viaje.
        await s.execute(delete(Movement))
        await s.execute(delete(Stop))

        cursor = START
        for order, (slug, name, country, flag, cur, nights) in enumerate(ITINERARY):
            arrival = cursor
            departure = cursor + timedelta(days=nights)
            cursor = departure
            s.add(Stop(
                slug=slug, order=order, name=name, country=country, country_flag=flag,
                arrival_date=arrival, departure_date=departure, currency_code=cur,
                timezone="Europe/London", is_transit=False,
            ))

            past_or_current = arrival <= TODAY
            lodging_usd = random.randint(*SPEND["Alojamiento"]) * nights
            if past_or_current:
                _add_mov(s, cats["Alojamiento"], cur, lodging_usd,
                         arrival, slug, name, bruno, "shared", f"Airbnb {name}")
            else:
                # Reserva futura: cargada HOY con fecha de pago al check-in =>
                # pending (TC proxy). Ejercita el feature real de payment_date.
                _add_mov(s, cats["Alojamiento"], cur, lodging_usd,
                         TODAY, slug, name, bruno, "shared", f"Airbnb {name}",
                         payment_date=arrival, status="pending")
                continue  # futuro: solo la reserva de alojamiento

            # Gastos diarios variados hasta HOY (nada más allá).
            for i in range(nights):
                day = arrival + timedelta(days=i)
                if day > TODAY:
                    break
                for catname in random.sample(
                    ["Comida", "Transporte", "Actividades", "Compras", "Salidas", "Supermercado", "Salud"],
                    k=random.randint(2, 4),
                ):
                    payer = random.choice([bruno, katia])
                    split = random.choices(["shared", "payer_only", "other_only"], weights=[8, 1, 1])[0]
                    _add_mov(s, cats[catname], cur, random.randint(*SPEND[catname]),
                             day, slug, name, payer, split, _desc(catname, name))

        # Generales del viaje (vuelos / pases), sin ciudad.
        _add_mov(s, None, "USD", 640, START - timedelta(days=1), None, None, bruno, "shared", "Vuelos EZE-LON")
        _add_mov(s, None, "USD", 180, START + timedelta(days=20), None, None, katia, "shared", "Eurail pass")

        # Cashback de tarjeta — casos fijos para desarrollar / QA visual.
        # amount guarda el BRUTO; amount_usd = neto × FX (ver app/cashback.py).
        _add_mov(s, cats["Comida"], "EUR", 54, TODAY - timedelta(days=2),
                 "estrasburgo", "Estrasburgo", bruno, "shared",
                 "Cena · cashback 2%", cashback_kind="pct", cashback_value=Decimal("2"))
        _add_mov(s, cats["Compras"], "EUR", 120, TODAY - timedelta(days=5),
                 "paris", "París", katia, "payer_only",
                 "Souvenirs · cashback 5 €", cashback_kind="amount", cashback_value=Decimal("5"))
        _add_mov(s, cats["Actividades"], "GBP", 80, START + timedelta(days=3),
                 "londres", "Londres", bruno, "shared",
                 "Museo · cashback 3%", cashback_kind="pct", cashback_value=Decimal("3"))
        _add_mov(s, cats["Transporte"], "GBP", 45, START + timedelta(days=1),
                 "londres", "Londres", katia, "shared",
                 "Oyster · cashback 2 £", cashback_kind="amount", cashback_value=Decimal("2"))
        _add_mov(s, cats["Salidas"], "EUR", 68, TODAY - timedelta(days=1),
                 "estrasburgo", "Estrasburgo", katia, "shared",
                 "Vinos · cashback 1.5%", cashback_kind="pct", cashback_value=Decimal("1.5"))

        # Un settlement (pago de saldo) reciente.
        s.add(Movement(
            type="settlement", amount=Decimal("150"), currency="USD", amount_usd=Decimal("150"),
            fx_rate=Decimal("1.0"), fx_source="manual", paid_by=katia.id, split="shared",
            description="Le pasé 150 usd", created_by=katia.id,
            created_at=_created(TODAY - timedelta(days=3)),
        ))

        # Gastos futuros que YA llegaron a su fecha y esperan confirmación manual
        # (status='awaiting': TC lockeado, pero afuera del balance hasta confirmar).
        # Ejercita la alerta de /movimientos. Se cargaron hace tiempo (con la 1a
        # cuota) y su fecha de pago ya cayó.
        current = next(
            (st for st in (await s.execute(select(Stop))).scalars().all()
             if st.arrival_date <= TODAY < st.departure_date),
            None,
        )
        cur_slug = current.slug if current else None
        cur_city = current.name if current else None
        cur_code = current.currency_code if current else "EUR"
        # Vencido ayer, cargado hace 10 días por Bruno.
        _add_mov(s, cats["Alojamiento"], cur_code, 420, TODAY - timedelta(days=10),
                 cur_slug, cur_city, bruno, "shared", "Airbnb — saldo (2/2)",
                 payment_date=TODAY - timedelta(days=1), status="awaiting")
        # Vencido hace una semana, cargado hace ~20 días por Katia.
        _add_mov(s, cats["Actividades"], cur_code, 96, TODAY - timedelta(days=20),
                 cur_slug, cur_city, katia, "shared", "Entradas tour — saldo (3/3)",
                 payment_date=TODAY - timedelta(days=7), status="awaiting")
        # Aún futuro pero a 1 día: aparece en la alerta (caso "desde 1 día antes").
        _add_mov(s, cats["Transporte"], cur_code, 60, TODAY,
                 cur_slug, cur_city, bruno, "shared", "Tren — saldo (2/2)",
                 payment_date=TODAY + timedelta(days=1), status="pending")

        await s.commit()
        movs = (await s.execute(select(Movement))).scalars().all()
        print(
            f"seeded {len(ITINERARY)} stops ({TOTAL_NIGHTS} noches), {len(movs)} movimientos\n"
            f"HOY={TODAY} · inicio={START} · fin={START + timedelta(days=TOTAL_NIGHTS)} "
            f"(día 40/{TOTAL_NIGHTS})"
        )


def _desc(cat: str, city: str) -> str:
    samples = {
        "Comida": ["Cena", "Almuerzo", "Café y medialunas", "Fish & chips", "Ramen"],
        "Transporte": ["Metro", "Taxi", "Tren", "Bus", "Bici"],
        "Actividades": ["Museo", "Tour a pie", "Castillo", "Mirador", "Excursión"],
        "Compras": ["Remera", "Souvenir", "Libro", "Zapatillas"],
        "Salidas": ["Pub", "Vinos", "Birras", "Cóctel"],
        "Supermercado": ["Provisiones", "Agua y snacks", "Verdulería"],
        "Salud": ["Farmacia", "Ibuprofeno"],
    }
    return f"{random.choice(samples.get(cat, ['Gasto']))} · {city}"


def _created(day: date) -> datetime:
    """created_at plausible (naive-UTC, como server_default) para que los grupos
    por día de carga del listado luzcan mid-trip."""
    return datetime.combine(day, time(hour=random.randint(9, 22), minute=random.randint(0, 59)))


def _add_mov(s, cat, cur, usd_amount, day, slug, city, paid_by, split, desc,
             *, payment_date=None, status="confirmed",
             cashback_kind=None, cashback_value=None) -> None:
    """`usd_amount` está en USD; se convierte a la moneda local del stop.
    `day` es el día de CARGA (created_at); una reserva futura va con
    payment_date + status='pending'. Con cashback, `amount` queda en bruto
    local y `amount_usd` hornea el neto."""
    rate = FX[cur]
    usd = Decimal(str(usd_amount))
    local = (usd / rate).quantize(Decimal("0.01"))
    net = net_amount(local, cashback_kind, cashback_value)
    s.add(Movement(
        type="expense", amount=local, currency=cur,
        amount_usd=(net * rate).quantize(Decimal("0.01")),
        fx_rate=rate, fx_source="manual", paid_by=paid_by.id, split=split,
        description=desc, category_id=cat.id if cat else None,
        stop_slug=slug, city_name=city, created_by=paid_by.id,
        payment_date=payment_date, status=status,
        cashback_kind=cashback_kind, cashback_value=cashback_value,
        created_at=_created(day),
    ))


if __name__ == "__main__":
    asyncio.run(main())
