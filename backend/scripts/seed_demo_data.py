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
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import delete, select

from app.categories.seed import seed_categories
from app.config import get_settings
from app.db.engine import async_session_factory, make_engine
from app.db.models import Base, Category, Movement, Stop, User
from app.users import seed_users_from_env

TODAY = date.today()
# HOY = día 40 (la llegada a la 1.ª parada es el día 1). Total: 100 noches.
START = TODAY - timedelta(days=39)
TOTAL_NIGHTS = 100

# Banderas: 🇬🇧 país; Escocia usa la secuencia de subdivisión (gb-sct), no el
# 🏴 negro pelado — el frontend la resuelve a la SVG del saltire.
SCOTLAND = "🏴\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f"

# (nombre, país, flag, moneda, noches)
ITINERARY = [
    ("Londres", "Reino Unido", "🇬🇧", "GBP", 6),
    ("Edimburgo", "Reino Unido", SCOTLAND, "GBP", 5),
    ("Fort William", "Reino Unido", SCOTLAND, "GBP", 3),
    ("Portree", "Reino Unido", SCOTLAND, "GBP", 3),
    ("Inverness", "Reino Unido", SCOTLAND, "GBP", 3),
    ("Glasgow", "Reino Unido", SCOTLAND, "GBP", 4),
    ("Dublín", "Irlanda", "🇮🇪", "EUR", 5),
    ("Ámsterdam", "Países Bajos", "🇳🇱", "EUR", 5),
    ("Brujas", "Bélgica", "🇧🇪", "EUR", 3),
    ("Friburgo", "Alemania", "🇩🇪", "EUR", 4),  # ← contiene HOY (día 40): en curso
    ("Múnich", "Alemania", "🇩🇪", "EUR", 5),
    ("Praga", "Chequia", "🇨🇿", "CZK", 5),
    ("Viena", "Austria", "🇦🇹", "EUR", 5),
    ("Budapest", "Hungría", "🇭🇺", "HUF", 5),
    ("Liubliana", "Eslovenia", "🇸🇮", "EUR", 3),
    ("Zagreb", "Croacia", "🇭🇷", "EUR", 3),
    ("Split", "Croacia", "🇭🇷", "EUR", 4),
    ("Roma", "Italia", "🇮🇹", "EUR", 6),
    ("Florencia", "Italia", "🇮🇹", "EUR", 4),
    ("Cinque Terre", "Italia", "🇮🇹", "EUR", 3),
    ("Niza", "Francia", "🇫🇷", "EUR", 4),
    ("Barcelona", "España", "🇪🇸", "EUR", 5),
    ("Madrid", "España", "🇪🇸", "EUR", 4),
    ("Lisboa", "Portugal", "🇵🇹", "EUR", 3),
]

FX = {"USD": Decimal("1.0"), "GBP": Decimal("1.27"), "EUR": Decimal("1.08"),
      "CZK": Decimal("0.043"), "HUF": Decimal("0.0028")}

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


def _slug(name: str) -> str:
    trans = str.maketrans("áéíóúñü ", "aeiounu-")
    return name.lower().translate(trans)


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
        for order, (name, country, flag, cur, nights) in enumerate(ITINERARY):
            arrival = cursor
            departure = cursor + timedelta(days=nights)
            cursor = departure
            slug = _slug(name)
            s.add(Stop(
                slug=slug, order=order, name=name, country=country, country_flag=flag,
                arrival_date=arrival, departure_date=departure, currency_code=cur,
                timezone="Europe/London", is_transit=False,
            ))

            past_or_current = arrival <= TODAY
            # Alojamiento: siempre (los futuros quedan como reserva "reservado").
            _add_mov(s, cats["Alojamiento"], cur, random.randint(*SPEND["Alojamiento"]) * nights,
                     arrival, slug, name, bruno, "shared", f"Airbnb {name}")

            if not past_or_current:
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

        # Un settlement (pago de saldo) reciente.
        s.add(Movement(
            type="settlement", amount=Decimal("150"), currency="USD", amount_usd=Decimal("150"),
            fx_rate=Decimal("1.0"), fx_source="manual", paid_by=katia.id, split="shared",
            description="Le pasé 150 usd", movement_date=TODAY - timedelta(days=3),
            created_by=katia.id,
        ))

        await s.commit()
        movs = (await s.execute(select(Movement))).scalars().all()
        current = next((n for (n, *_1, nights) in ITINERARY), None)
        print(
            f"seeded {len(ITINERARY)} stops ({TOTAL_NIGHTS} noches), {len(movs)} movimientos\n"
            f"HOY={TODAY} · inicio={START} · fin={START + timedelta(days=TOTAL_NIGHTS)} (día 40/100)"
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


def _add_mov(s, cat, cur, usd_amount, day, slug, city, paid_by, split, desc) -> None:
    """`usd_amount` está en USD; se convierte a la moneda local del stop."""
    rate = FX[cur]
    usd = Decimal(str(usd_amount))
    local = (usd / rate).quantize(Decimal("0.01"))
    s.add(Movement(
        type="expense", amount=local, currency=cur,
        amount_usd=(local * rate).quantize(Decimal("0.01")),
        fx_rate=rate, fx_source="manual", paid_by=paid_by.id, split=split,
        description=desc, category_id=cat.id if cat else None,
        stop_slug=slug, city_name=city, movement_date=day, created_by=paid_by.id,
    ))


if __name__ == "__main__":
    asyncio.run(main())
