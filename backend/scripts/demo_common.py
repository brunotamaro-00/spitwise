"""Piezas compartidas por los dos seeds de datos ficticios.

- `seed_demo_data.py` — demo local sobre SQLite, con itinerario hardcodeado.
- `seed_demo_money.py` — deploy público, sin itinerario propio: sincroniza las
  paradas desde Andiamo y siembra solo movimientos sobre ellas.

Acá vive todo lo que no depende de dónde salgan las paradas: tasas de FX,
ritmo de gasto por región y los helpers que arman un `Movement`.
"""
import random
from datetime import date, datetime, time
from decimal import Decimal

from app.cashback import net_amount
from app.db.models import Movement

# Tasas fijas: un seed no debe depender de la API de FX ni cambiar de corrida
# en corrida. `fx_source="manual"` marca que son puestas a mano.
FX = {"USD": Decimal("1.0"), "GBP": Decimal("1.27"), "EUR": Decimal("1.08"),
      "CHF": Decimal("1.12"), "CZK": Decimal("0.043"), "PLN": Decimal("0.25"),
      "HUF": Decimal("0.0028")}

# Ritmo diario por región (USD del HOGAR = ~2× pp del PRESUPUESTO).
# comida = restaurantes; super = mercado/hostel cocina; salidas = birras/pubs.
# `lodging_night` = total del hogar por noche, derivado de los promedios reales
# del presupuesto por región (lo usa el seed que no trae montos por parada).
REGION_DAILY = {
    "uk": {
        "food_pp": (38, 52),
        "cafe_pp": (9, 16),
        "local_transport": (4, 14),
        "activity": (20, 55),
        "salida": (16, 40),
        "compras_chance": 0.08,
        "lodging_night": (85, 115),
    },
    "west": {  # NL + París + Alsacia
        "food_pp": (32, 48),
        "cafe_pp": (8, 15),
        "local_transport": (3, 12),
        "activity": (18, 50),
        "salida": (14, 36),
        "compras_chance": 0.10,
        "lodging_night": (75, 115),
    },
    "portugal": {  # Bruno solo → no ×2
        "food_pp": (25, 38),
        "cafe_pp": (4, 8),
        "local_transport": (3, 10),
        "activity": (12, 35),
        "salida": (10, 28),
        "compras_chance": 0.06,
        "solo": True,
        "lodging_night": (28, 40),
    },
    "ch": {
        "food_pp": (42, 60),
        "cafe_pp": (10, 18),
        "local_transport": (5, 18),
        "activity": (40, 90),
        "salida": (18, 45),
        "compras_chance": 0.05,
        "lodging_night": (85, 100),
    },
    "east": {
        "food_pp": (17, 26),
        "cafe_pp": (4, 9),
        "local_transport": (2, 8),
        "activity": (12, 35),
        "salida": (8, 22),
        "compras_chance": 0.06,
        "lodging_night": (45, 100),
    },
    "south": {  # IT + ES
        "food_pp": (28, 40),
        "cafe_pp": (6, 12),
        "local_transport": (3, 12),
        "activity": (18, 48),
        "salida": (12, 32),
        "compras_chance": 0.08,
        "lodging_night": (75, 92),
    },
}

# Región por slug. Cubre el itinerario real de Andiamo (incluidas las paradas
# candidatas y las de la demo local) — un slug nuevo cae en DEFAULT_REGION.
REGION_BY_SLUG = {
    "londres": "uk", "york": "uk", "edimburgo": "uk", "fort-william": "uk",
    "portree": "uk", "inverness": "uk", "edimburgo-2": "uk",
    "amsterdam": "west", "paris": "west",
    "lisboa": "portugal", "porto": "portugal", "pititas": "portugal",
    "estrasburgo": "west", "colmar": "west", "friburgo": "west",
    "interlaken": "ch", "grindelwald": "ch", "lauterbrunnen": "ch",
    "innsbruck": "east", "viena": "east", "praga": "east", "cracovia": "east",
    "budapest": "east", "liubliana": "east",
    "florencia": "south", "roma": "south", "napoles": "south",
    "puglia": "south", "calabria": "south", "sicilia": "south",
    "sur-italia": "south", "margen-flex": "south",
    "barcelona": "south", "madrid": "south",
}

DEFAULT_REGION = "west"


def region_for(slug: str) -> str:
    return REGION_BY_SLUG.get(slug, DEFAULT_REGION)


def rate_for(currency: str | None) -> tuple[str, Decimal]:
    """Moneda + tasa, con fallback a EUR: una parada nueva en Andiamo con una
    moneda que este seed no conoce no debe tumbar la corrida."""
    code = (currency or "EUR").upper()
    if code not in FX:
        code = "EUR"
    return code, FX[code]


def _seed_day(s, cats, cur, day, slug, name, bruno, katia, region_key,
              *, force_payer=None) -> None:
    """Un día de viaje: alimentación ~presupuesto + transporte local ocasional
    + actividad/salida con menor frecuencia. Montos en USD del hogar (o 1p si solo)."""
    cfg = REGION_DAILY[region_key]
    solo = cfg.get("solo", False) or force_payer is not None
    payer = force_payer or random.choice([bruno, katia])
    # En Portugal del itinerario, Bruno paga y es payer_only.
    if region_key == "portugal" and force_payer is None:
        payer = bruno
        split = "payer_only"
        mult = 1
    elif force_payer is not None:
        split = "payer_only"
        mult = 1
    else:
        split = random.choices(["shared", "payer_only", "other_only"], weights=[9, 1, 0])[0]
        mult = 1 if split != "shared" else 2

    # Alimentación del día (pp × personas) repartida comida / super.
    lo, hi = cfg["food_pp"]
    food_day = random.uniform(lo, hi) * mult
    # ~55% restaurante, ~45% super (cocina hostel, sobre todo CH/east).
    super_share = 0.55 if region_key in ("ch", "east") else 0.40
    if random.random() < 0.85:
        # Almuerzo o cena
        meal = food_day * (1 - super_share) * random.uniform(0.45, 0.70)
        _add_mov(s, cats["Comida"], cur, round(meal, 2), day, slug, name, payer, split,
                 _desc("Comida", name))
    if random.random() < 0.55:
        grocery = food_day * super_share * random.uniform(0.6, 1.0)
        _add_mov(s, cats["Supermercado"], cur, round(grocery, 2), day, slug, name,
                 payer, split, _desc("Supermercado", name))
    # Segunda comida (cena) algunos días.
    if random.random() < 0.45:
        dinner = food_day * (1 - super_share) * random.uniform(0.30, 0.50)
        _add_mov(s, cats["Comida"], cur, round(dinner, 2), day, slug, name, payer, split,
                 _desc("Comida", name))

    # Cafetería (~2 de cada 3 días): es el gasto más cotidiano de un viaje así y
    # monto chico, así que aparece seguido sin mover el ritmo diario.
    if random.random() < 0.65:
        clo, chi = cfg["cafe_pp"]
        _add_mov(s, cats["Cafetería"], cur, round(random.uniform(clo, chi) * mult, 2),
                 day, slug, name, payer, split, _desc("Cafetería", name))

    # Transporte local (~70% de los días).
    if random.random() < 0.70:
        tlo, thi = cfg["local_transport"]
        _add_mov(s, cats["Transporte"], cur, round(random.uniform(tlo, thi) * mult, 2),
                 day, slug, name, payer, split, _desc("Transporte", name))

    # Actividad (~1 cada 2–3 días).
    if random.random() < 0.35:
        alo, ahi = cfg["activity"]
        _add_mov(s, cats["Actividades"], cur, round(random.uniform(alo, ahi) * mult, 2),
                 day, slug, name, payer, split, _desc("Actividades", name))

    # Salida (~1 cada 3 días).
    if random.random() < 0.30:
        slo, shi = cfg["salida"]
        _add_mov(s, cats["Salidas"], cur, round(random.uniform(slo, shi) * mult, 2),
                 day, slug, name, payer, split, _desc("Salidas", name))

    # Compras ocasionales.
    if random.random() < cfg["compras_chance"]:
        _add_mov(s, cats["Compras"], cur, round(random.uniform(12, 45) * mult, 2),
                 day, slug, name, payer, split, _desc("Compras", name))

    # Farmacia rara.
    if random.random() < 0.04:
        _add_mov(s, cats["Salud"], cur, round(random.uniform(6, 18) * mult, 2),
                 day, slug, name, payer, split, _desc("Salud", name))

    # Cajón de sastre: lo que no entra en ninguna de las otras diez.
    if random.random() < 0.06:
        _add_mov(s, cats["Otros"], cur, round(random.uniform(5, 22) * mult, 2),
                 day, slug, name, payer, split, _desc("Otros", name))


def _desc(cat: str, city: str) -> str:
    samples = {
        "Comida": ["Cena", "Almuerzo", "Fish & chips", "Ramen",
                   "Menú del día", "Pasta", "Brunch"],
        "Cafetería": ["Café", "Café y medialunas", "Flat white", "Cortado y factura",
                      "Café para llevar", "Merienda"],
        "Transporte": ["Metro", "Bus", "Tren local", "Bici", "Uber corto"],
        "Actividades": ["Museo", "Tour a pie", "Mirador", "Castillo", "Free walking tour"],
        "Compras": ["Souvenir", "Libro", "Remera", "Postales"],
        "Salidas": ["Pub", "Birras", "Vinos", "Cóctel"],
        "Supermercado": ["Provisiones", "Agua y snacks", "Desayuno hostel", "Mercado"],
        "Salud": ["Farmacia", "Ibuprofeno", "Protector solar"],
        "Lavandería": ["Lavandería", "Lavarropas del hostel", "Lavado y secado"],
        "Otros": ["Chip de datos", "Casillero de equipaje", "Propina", "Baño público",
                  "Candado"],
    }
    return f"{random.choice(samples.get(cat, ['Gasto']))} · {city}"


def _created(day: date) -> datetime:
    return datetime.combine(day, time(hour=random.randint(9, 22), minute=random.randint(0, 59)))


def _add_mov(s, cat, cur, usd_amount, day, slug, city, paid_by, split, desc,
             *, payment_date=None, status="confirmed",
             cashback_kind=None, cashback_value=None) -> None:
    """`usd_amount` en USD; se convierte a moneda local. Con cashback, `amount`
    queda en bruto y `amount_usd` hornea el neto."""
    _code, rate = rate_for(cur)
    usd = Decimal(str(usd_amount)).quantize(Decimal("0.01"))
    local = (usd / rate).quantize(Decimal("0.01"))
    net = net_amount(local, cashback_kind, cashback_value)
    s.add(Movement(
        type="expense", amount=local, currency=_code,
        amount_usd=(net * rate).quantize(Decimal("0.01")),
        fx_rate=rate, fx_source="manual", paid_by=paid_by.id, split=split,
        description=desc, category_id=cat.id if cat else None,
        stop_slug=slug, city_name=city, created_by=paid_by.id,
        payment_date=payment_date, status=status,
        cashback_kind=cashback_kind, cashback_value=cashback_value,
        created_at=_created(day),
    ))
