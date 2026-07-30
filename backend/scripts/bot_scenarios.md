# Escenarios de charla — última corrida

> **Auto-generado** por `scripts/bot_scenario_runner.py`.
> Cada corrida **borra y reemplaza** este archivo (no acumula historial).
> Catálogo: `SUITE_CRITICAL` (1–10) + `CONVERSATIONS_EXTRA` (11–17) en el script.
> Los **checks** son deterministas (DB / intent / tools): si fallan, el runner sale con exit 1. El texto se evalúa a ojo.

- Corrida: `2026-07-30T13:18:39-03:00`
- Suite: **custom (2)**
- provider=`openai` parser=`gpt-5-mini` chat=`gpt-5-mini`
- Hoy ficticio: `2026-08-20` (parada activa: Lisboa)
- Escenarios corridos: 19, 20 (2 conversaciones)
- Checks: **2 ok** · **0 con fallas** · 0 sin checks
- Latencia: fases espejo de `process_message` (stops → due → dispatch); Meta send/typing **no** medidos

---

## 19 · Dos remitentes intercalados ✅

**Id:** `dos-remitentes` — reproducir con `--only dos-remitentes`

**Meta:** El 'último gasto' es por chat: una corrección no cruza de teléfono.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 3: debe editar el CAFÉ de Bruno (8 eur), no el tren de Katia
- FAIL histórico: recent_movement global → 'no, fueron 8' editaba el tren ajeno
- El tren de Katia queda intacto en 39

**Dónde tocar:** `bot/editor.py (recent_movement created_by) · bot/dispatcher.py`

**Katia:** tren 39 usd _carga Katia_

**Latencia:** dispatch 4.2s · stops 0.0s · due 0.0s · **total 4.2s** (sin Meta send)

**Traza:** intent=expense · tools=-

**Bot:**

```
✅ *Gasto guardado*

🚆 Transporte — Tren
💰 USD 39,0
📍 Lisboa
👤 Pagó Katia · ÷ 50/50
⚖️ *Bruno* le debe *USD 19,5* por esto
(movement_id=5)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 39.00 USD usd=39.00 desc='Tren' city=Lisboa split=shared paid_by=katia cat=Transporte pay=None status=confirmed batch=None
```

</details>

**Bruno:** cafe 5 eur en lisboa _carga Bruno_

**Latencia:** dispatch 4.3s · stops 0.0s · due 0.0s · **total 4.3s** (sin Meta send)

**Traza:** intent=expense · tools=-

**Bot:**

```
✅ *Gasto guardado*

☕ Cafetería — Café
💰 EUR 5,0 → USD 5,5
📍 Lisboa
👤 Pagó Bruno · ÷ 50/50
📅 Pagado el 20/08
⚖️ *Katia* le debe *USD 2,8* por esto
(movement_id=6)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 39.00 USD usd=39.00 desc='Tren' city=Lisboa split=shared paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#6 expense 5.00 EUR usd=5.50 desc='Café' city=Lisboa split=shared paid_by=bruno cat=Cafetería pay=2026-08-20 status=confirmed batch=None
```

</details>

**Bruno:** no, fueron 8 _corrección de Bruno_

**Latencia:** dispatch 4.1s · stops 0.0s · due 0.0s · **total 4.1s** (sin Meta send)

**Traza:** intent=edit · tools=-

**Bot:**

```
✏️ *Editado* · _Café_

💰: EUR 5,0 → *EUR 8,0*
💵: USD 5,5 → *USD 8,8*
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 39.00 USD usd=39.00 desc='Tren' city=Lisboa split=shared paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#6 expense 8.00 EUR usd=8.80 desc='Café' city=Lisboa split=shared paid_by=bruno cat=Cafetería pay=2026-08-20 status=confirmed batch=None
```

</details>

---

## 20 · Cuotas que no cierran ✅

**Id:** `cuotas-invalidas` — reproducir con `--only cuotas-invalidas`

**Meta:** Etapas declaradas pero imposibles de repartir: aclarar, no guardar mal.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- O entra en etapas con montos que suman 300, o NO entra nada y el bot pide los montos/fechas. FAIL: un gasto único de 300 con fecha de hoy y sin aviso
- El texto tiene que decir qué falta (montos o fechas de cada etapa)

**Dónde tocar:** `bot/capture.py (expand_installments + INSTALLMENTS_UNCLEAR) · llm/client.py`

**Bruno:** hostel praga 300 eur, una parte ahora y el resto después _etapas sin montos ni fechas_

**Latencia:** dispatch 4.4s · stops 0.0s · due 0.0s · **total 4.4s** (sin Meta send)

**Traza:** intent=expense · tools=-

**Bot:**

```
🤔 Entendí que eso se paga *en partes*, pero no me cerraron los montos, así que no lo guardé. Decímelo con el total y las etapas: _hostel 430 chf, 30% hoy y el resto el 3 de septiembre_.
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
| 19 · Dos remitentes intercalados | 1 | katia | carga Katia | 4.2 | 0.0 | 0.0 | 4.2 |
| 19 · Dos remitentes intercalados | 2 | bruno | carga Bruno | 4.3 | 0.0 | 0.0 | 4.3 |
| 19 · Dos remitentes intercalados | 3 | bruno | corrección de Bruno | 4.1 | 0.0 | 0.0 | 4.1 |
| 20 · Cuotas que no cierran | 1 | bruno | etapas sin montos ni fechas | 4.4 | 0.0 | 0.0 | 4.4 |

Promedio dispatch **4.3s** · promedio total **4.3s** · más lento: bruno «hostel praga 300 eur, una parte ahora y …» (4.4s)

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
