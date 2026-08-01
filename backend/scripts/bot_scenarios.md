# Escenarios de charla — última corrida

> **Auto-generado** por `scripts/bot_scenario_runner.py`.
> Cada corrida **borra y reemplaza** este archivo (no acumula historial).
> Catálogo: `SUITE_CRITICAL` (1–10) + `CONVERSATIONS_EXTRA` (11–27) en el script.
> Los **checks** son deterministas (DB / intent / tools): si fallan, el runner sale con exit 1. El texto se evalúa a ojo.

- Corrida: `2026-08-01T12:59:31-03:00`
- Suite: **custom (1)**
- provider=`openai` parser=`gpt-5-mini` chat=`gpt-5-mini`
- Hoy ficticio: `2026-08-20` (parada activa: Lisboa)
- Escenarios corridos: 27 (1 conversaciones)
- Checks: **1 ok** · **0 con fallas** · 0 sin checks
- Latencia: fases espejo de `process_message` (stops → due → dispatch); Meta send/typing **no** medidos

---

## 27 · Presupuesto de la ciudad ✅

**Id:** `presupuesto-ciudad` — reproducir con `--only presupuesto-ciudad`

**Meta:** '¿Vamos bien acá?' se responde contra el target de la parada, no contra el promedio del viaje; y una parada sin target se dice, no se estima.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 1: debe llamar budget_status y comparar contra el target de Lisboa (USD 40/día). FAIL: contesta con aggregate_expenses y el promedio del viaje
- Turno 2: Interlaken NO tiene target cargado. Tiene que decirlo. FAIL: inventa un target o lo deriva del promedio de las otras paradas
- Ninguno de los dos turnos puede crear ni tocar movimientos

**Dónde tocar:** `qa/tools.py budget_status · bot/qa.py (prompt) · app/budget.py`

**Bruno:** ¿vamos bien de guita en Lisboa? _target vs real_

**Latencia:** dispatch 26.6s · stops 0.0s · due 0.0s · **total 26.6s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=budget_status

**Bot:**

```
📍 *Lisboa*
💸 Vamos bien: estás *por debajo* del plan. El gasto de "vivir" hasta ahora es *USD 33,0* (≈ *USD 3,7* por día) vs el rango plan *USD 34,0–USD 46,0* por día.  
🧾 Queda *USD 183,5* por día para gastar hasta el check‑out si quisieran igualar el plan; tienen un colchón de *USD 835,5* en el viaje.  
Resumen corto: *estamos ahorrando* vs el plan (delta -90,8% respecto al centro).
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
```

</details>

**Bruno:** ¿y en Interlaken cuánto podemos gastar por día? _parada sin target_

**Latencia:** dispatch 15.4s · stops 0.0s · due 0.0s · **total 15.4s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=budget_status

**Bot:**

```
📍 *Interlaken*  
📅 Están programados *5 noches* ahí.  
No hay un objetivo de presupuesto cargado para *Interlaken*, así que no puedo calcular “cuánto por día” contra un plan.  
💸 De todas formas, en el viaje tienen un colchón de *USD 835,5* y para cerrar en plan necesitan un ritmo promedio de *USD 437,8* por día en lo que queda (esa cifra es del viaje global).  
Si querés que calcule cuánto podrían gastar por día contra un objetivo, cargá el target de *Interlaken* en la web y lo miro.
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
```

</details>

---

## Resumen de latencia

| Escenario | Turno | Quién | Nota | dispatch_s | stops_s | due_s | total_s |
|---|---:|---|---|---:|---:|---:|---:|
| 27 · Presupuesto de la ciudad | 1 | bruno | target vs real | 26.6 | 0.0 | 0.0 | 26.6 |
| 27 · Presupuesto de la ciudad | 2 | bruno | parada sin target | 15.4 | 0.0 | 0.0 | 15.4 |

Promedio dispatch **21.0s** · promedio total **21.0s** · más lento: bruno «¿vamos bien de guita en Lisboa?» (26.6s)

> En prod, al `total_s` se suman typing/react/send Graph (~0.3–1.5s típico, no medido acá).

---

## Cómo volver a correr

```bash
cd backend
.venv/bin/python scripts/bot_scenario_runner.py          # suite crítica (10)
.venv/bin/python scripts/bot_scenario_runner.py --all    # 17 (10+7)
.venv/bin/python scripts/bot_scenario_runner.py --only cuotas-total,pititas-owner
.venv/bin/python scripts/bot_scenario_runner.py --provider anthropic
```

Requiere `OPENAI_API_KEY` en `spitwise/.env`. Secuencial; pausas entre turnos.
