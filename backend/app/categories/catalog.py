# 10 categorías fijas del viaje (orden estable = sort_order).
# La descripción se inyecta en el prompt del parser para guiar la clasificación:
# son el mecanismo de clasificación, no documentación. Si dos descripciones se
# pisan, el parser elige mal — mantenerlas mutuamente excluyentes.
CATEGORIES: list[tuple[str, str, str]] = [
    ("Alojamiento", "🏨",
     "hoteles, hostels, airbnb, camping, tasas turísticas de alojamiento"),
    ("Comida", "🍽️",
     "comida ya preparada: restaurantes, cafés, desayunos/almuerzos/cenas, "
     "panadería, snacks, helados, delivery. Si son provisiones para cocinar "
     "o llevar, va en Supermercado"),
    ("Supermercado", "🛒",
     "provisiones para cocinar o llevar: supermercado, almacén, verdulería, "
     "carnicería, fiambrería, kiosco, agua. Si es comida ya preparada, va en Comida"),
    ("Transporte", "🚆",
     "tren, bus, metro/subte, tranvía, taxi/uber, vuelos, ferry, teleférico, funicular, "
     "alquiler de bici/auto, nafta, peajes, estacionamiento, pases de transporte"),
    ("Actividades", "🎟️",
     "entradas y experiencias: museos, tours, excursiones, castillos, miradores, "
     "espectáculos, parques, termas"),
    ("Compras", "🛍️",
     "para uno mismo: ropa, calzado, electrónica, artículos personales, equipaje. "
     "Si es para regalar a otro, va en Regalos"),
    ("Salidas", "🍷",
     "salir a tomar algo: bares, pubs, cervezas/birras, vinos, tragos, "
     "boliches, salidas nocturnas. Cualquier bebida alcohólica va acá"),
    ("Regalos", "🎁",
     "para otros: regalos, souvenirs para llevar de vuelta, postales. "
     "NO compras personales, eso va en Compras"),
    ("Salud", "💊",
     "farmacia, medicamentos, consultas médicas, dentista, seguro médico, "
     "ópticas, tests/vacunas"),
    ("Otros", "📦",
     "SOLO si de verdad no encaja en ninguna otra: lavandería, SIM/datos, "
     "comisiones bancarias, trámites"),
]
