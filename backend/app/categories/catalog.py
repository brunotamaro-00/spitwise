# 7 categorías fijas del viaje (orden estable = sort_order).
# La descripción se inyecta en el prompt del parser para guiar la clasificación.
CATEGORIES: list[tuple[str, str, str]] = [
    ("Alojamiento", "🏨",
     "hoteles, hostels, airbnb, camping, tasas turísticas de alojamiento"),
    ("Comida", "🍽️",
     "restaurantes, cafés, desayunos/almuerzos/cenas, supermercado, panadería, snacks, helados"),
    ("Transporte", "🚆",
     "tren, bus, metro/subte, tranvía, taxi/uber, vuelos, ferry, teleférico, funicular, "
     "alquiler de bici/auto, nafta, peajes, estacionamiento, pases de transporte"),
    ("Actividades", "🎟️",
     "entradas y experiencias: museos, tours, excursiones, castillos, miradores, "
     "espectáculos, parques, termas"),
    ("Compras", "🛍️",
     "ropa, souvenirs, regalos, electrónica, artículos personales, farmacia"),
    ("Bebidas/Salidas", "🍷",
     "bares, pubs, birras, vinos, tragos, boliches, salidas nocturnas"),
    ("Otros", "📦",
     "SOLO si de verdad no encaja en ninguna otra: lavandería, SIM/datos, "
     "comisiones bancarias, trámites"),
]
