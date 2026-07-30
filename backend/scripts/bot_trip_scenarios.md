# Escenarios bot — canal VIAJE (guías + notas)

Corrida: **2026-07-30 13:19** · hoy ficticio `2026-09-25` (Viena) · suite: custom (1)

Seed: **96** guide docs desde `andiamo/content/guides` · **9** notas · **7** stops.

> Cada corrida reescribe este archivo. Checklist **Mirar** = qué validar a ojo.

## 11. Harry Potter en Lisboa o Porto (multi-ciudad + sinónimos) ✅

**Id:** `harry-potter` — reproducir con `--only harry-potter`

**Goal:** Consulta que ninguna guía nombra literalmente: hay que expandirla (Hogwarts / Livraria Lello) y cubrir DOS ciudades sin quedarse a mitad de camino.

**Checks deterministas: ✅ pasan**

**Mirar:**
- Turno 1: tiene que encontrar la Livraria Lello de Porto (la guía la liga a Hogwarts) y decir en una línea, grounded, qué hay o no hay en Lisboa. FAIL histórico: search_guides exige TODAS las palabras ('harry' + 'potter' + 'lisboa' + 'porto') y devuelve 0 hits → 'las guías no dicen nada'
- FAIL grave: contestar de cultura general (tour de HP, estudios) sin tools
- Turno 2: precio TAL CUAL la guía (€10 Silver / €15.95 Gold). FAIL si inventa un precio o cambia de ciudad

**Dónde tocar:** `qa/trip_tools.py (search escalonado, multi guide_slugs) · bot/trip_qa.py`

### katia

**→** ¿hay algo de Harry Potter para ver en Lisboa o en Porto?
*multi-ciudad + sinónimo (ninguna guía dice 'Harry Potter')*

⏱ dispatch `17.5s` · total `17.5s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=list_guides,search_guides,read_guide_doc,read_guide_doc

```
Hice la búsqueda en nuestras guías.

- Lisboa: *las guías no dicen nada de Harry Potter en Lisboa.*  
- Porto: sí hay referencia — **Livraria Lello** aparece como *inspiración parcial de Hogwarts* (entrada **€10** Silver / **€15.95** Gold; mejor al abrir o después de las 17h). 📖 Más: http://localhost:3000/guias/porto/actividades

Si querés que revise otras palabras (ej. "Wizards", "Hogwarts", "JK Rowling") lo intento en las guías.
```

### katia

**→** ¿y cuánto sale entrar?
*follow-up sobre el mismo lugar*

⏱ dispatch `17.7s` · total `17.7s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=list_guides,search_guides,read_guide_doc

```
- En Porto: **Livraria Lello** — entrada **€10 (Silver)** o **€15.95 (Gold)**; el ticket Silver se descuenta si comprás un libro de €10+; mejor ir al abrir o después de las 17h.  
- En Lisboa: *las guías no dicen nada de Harry Potter allí.*  
📖 Más sobre Lello: http://localhost:3000/guias/porto/actividades
```

---

## Resumen latencia

| # | Escenario | Turno | Quién | dispatch_s | total_s |
|---:|---|---:|---|---:|---:|
| 11 | Harry Potter en Lisboa o Porto (multi-ciudad + sinónimos) | 1 | katia | 17.5 | 17.5 |
| 11 | Harry Potter en Lisboa o Porto (multi-ciudad + sinónimos) | 2 | katia | 17.7 | 17.7 |

```bash
cd backend
.venv/bin/python scripts/bot_trip_scenario_runner.py
.venv/bin/python scripts/bot_trip_scenario_runner.py --only 2,3,6
```
