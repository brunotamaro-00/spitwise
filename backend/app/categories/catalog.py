# 11 categorías fijas del viaje (orden estable = sort_order).
# La descripción se inyecta en el prompt del parser para guiar la clasificación:
# son el mecanismo de clasificación, no documentación. Si dos descripciones se
# pisan, el parser elige mal — mantenerlas mutuamente excluyentes.
CATEGORIES: list[tuple[str, str, str]] = [
    ("Alojamiento", "🏨",
     "hoteles, hostels, airbnb, camping, tasas turísticas de alojamiento"),
    ("Comida", "🍽️",
     "sentarse a comer: restaurantes, paradores, almuerzos y cenas, delivery de "
     "una comida completa. Café/desayuno/merienda al paso o de cafetería va en "
     "Cafetería; provisiones para cocinar van en Supermercado"),
    ("Cafetería", "☕",
     "café, desayunos, meriendas y comida al paso (sentado o para llevar): "
     "cafeterías, panaderías, heladerías, brunch, snacks de calle. Sin alcohol "
     "(eso es Salidas). Almuerzos y cenas de restaurante van en Comida"),
    ("Supermercado", "🛒",
     "provisiones para cocinar o llevar: supermercado, almacén, verdulería, "
     "carnicería, fiambrería, kiosco, agua. Comida ya preparada va en Comida o Cafetería"),
    ("Transporte", "🚆",
     "tren, bus, metro/subte, tranvía, taxi/uber, vuelos, ferry, teleférico, funicular, "
     "alquiler de bici/auto, nafta, peajes, estacionamiento, pases de transporte"),
    ("Actividades", "🎟️",
     "entradas y experiencias: museos, tours, excursiones, castillos, miradores, "
     "espectáculos, parques, termas"),
    ("Compras", "🛍️",
     "para uno mismo o para regalar: ropa, calzado, electrónica, artículos "
     "personales, equipaje, regalos, souvenirs, postales"),
    ("Salidas", "🍷",
     "salir a tomar algo con alcohol: bares, pubs, cervezas/birras, vinos, tragos, "
     "boliches, salidas nocturnas. Cualquier bebida alcohólica va acá. El café sin "
     "alcohol va en Cafetería"),
    ("Lavandería", "🧺",
     "lavar y secar ropa: lavanderías, lavaderos automáticos, tintorería, "
     "servicio de lavado, jabón para la ropa"),
    ("Salud", "💊",
     "farmacia, medicamentos, consultas médicas, dentista, seguro médico, "
     "ópticas, tests/vacunas"),
    ("Otros", "📦",
     "SOLO si de verdad no encaja en ninguna otra: SIM/datos, "
     "comisiones bancarias, trámites"),
]
