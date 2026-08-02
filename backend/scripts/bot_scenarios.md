# Escenarios de charla — última corrida

> **Auto-generado** por `scripts/bot_scenario_runner.py`.
> Cada corrida **borra y reemplaza** este archivo (no acumula historial).
> Catálogo: `SUITE_CRITICAL` (1–10) + `CONVERSATIONS_EXTRA` (11–27) en el script.
> Los **checks** son deterministas (DB / intent / tools): si fallan, el runner sale con exit 1. El texto se evalúa a ojo.

- Corrida: `2026-08-01T23:32:56-03:00`
- Suite: **catálogo completo (27)**
- provider=`openai` parser=`gpt-5-mini` chat=`gpt-5-mini`
- Hoy ficticio: `2026-08-20` (parada activa: Lisboa)
- Escenarios corridos: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27 (27 conversaciones)
- Checks: **23 ok** · **4 con fallas** · 0 sin checks
- Latencia: fases espejo de `process_message` (stops → due → dispatch); Meta send/typing **no** medidos

---

## 1 · Cuotas + corrección de total ✅

**Id:** `cuotas-total` — reproducir con `--only cuotas-total`

**Meta:** Gasto en etapas (30% hoy / resto check-in) y corregir el total del batch.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 1: 2 filas mismo batch_key; montos 129+301 (=430); 2ª con pay=2026-09-03 y status=pending
- Turno 2 FAIL típico: solo edita la cuota 2/2 a 480 (total 609). Debe redistribuir el batch a total 480 (≈144+336) o editar el gasto lógico, no un renglón suelto
- Card no debe mostrar deuda por la cuota pending

**Dónde tocar:** `llm/client.py (installments) · bot/editor.py (edit amount + batch) · bot/capture.py (expand_installments)`

**Bruno:** hostel interlaken 430 chf, 30% hoy y el resto al check-in el 3 de septiembre _cuotas_

**Latencia:** dispatch 5.9s · stops 0.0s · due 0.0s · **total 5.9s** (sin Meta send)

**Traza:** intent=expense · tools=-

**Bot:**

```
✅ *2 gastos guardados* · 📍 Interlaken · 👤 Pagó Bruno

- 🏨 Hostel Interlaken (1/2) · CHF 129,0 → USD 154,8
- 🏨 Hostel Interlaken (2/2) · CHF 301,0 → USD 361,2 · 📅 03/09

💰 Total: *USD 516,0*
⚖️ *Katia* le debe *USD 77,4* por esto
(movement_id=6)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 129.00 CHF usd=154.80 desc='Hostel Interlaken (1/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=447bb4e6e43930bb
#6 expense 301.00 CHF usd=361.20 desc='Hostel Interlaken (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=447bb4e6e43930bb
```

</details>

**Bruno:** no, el total era 480 no 430 _edit monto del batch_

**Latencia:** dispatch 4.2s · stops 0.0s · due 0.0s · **total 4.2s** (sin Meta send)

**Traza:** intent=edit · tools=-

**Bot:**

```
✏️ *Editado* · _Hostel Interlaken_

💰 Total: CHF 430,0 → *CHF 480,0*
- Hostel Interlaken (1/2) · CHF 144,0 → USD 172,8
- Hostel Interlaken (2/2) · CHF 336,0 → USD 403,2 · 📅 03/09
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 144.00 CHF usd=172.80 desc='Hostel Interlaken (1/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=447bb4e6e43930bb
#6 expense 336.00 CHF usd=403.20 desc='Hostel Interlaken (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=447bb4e6e43930bb
```

</details>

---

## 2 · Multi-gasto mezclado + fix de split ✅

**Id:** `batch-split-fix` — reproducir con `--only batch-split-fix`

**Meta:** 3 ítems (payer/split distintos) y corregir el split del taxi por ref.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 1: 3 movimientos Roma, pay=ayer; cena paid_by=katia con split=shared ('pagó' ≠ 'solo de'); taxi payer_only Bruno; helado shared
- FAIL típico: cena nace payer_only / Solo Katia sin que lo digan
- Turno 2: debe editar el Taxi (ref_text), no el último (helado). DB: taxi.split → shared. FAIL: 'Nada que cambiar'

**Dónde tocar:** `llm/client.py (split vs paid_by; expenses[]) · bot/editor.py (resolve ref_text en batch)`

**Bruno:** en Roma ayer: cena 45 euros pagó katia, taxi 12 solo mío, helado 5 _batch 3 ítems_

**Latencia:** dispatch 8.3s · stops 0.0s · due 0.0s · **total 8.3s** (sin Meta send)

**Traza:** intent=expense · tools=-

**Bot:**

```
✅ *3 gastos guardados* · 📍 Roma

- 🍽️ Cena · EUR 45,0 → USD 49,5 · pagó Katia
- 🚆 Taxi · EUR 12,0 → USD 13,2 · Solo Bruno · pagó Bruno
- ☕ Helado · EUR 5,0 → USD 5,5 · pagó Bruno

💰 Total: *USD 68,2*
⚖️ *Bruno* le debe *USD 22,0* por esto
(movement_id=7)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=135dad02014a3bd7
#6 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=payer_only paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=135dad02014a3bd7
#7 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Cafetería pay=2026-08-19 status=confirmed batch=135dad02014a3bd7
```

</details>

**Bruno:** el taxi en realidad era compartido _edit split taxi_

**Latencia:** dispatch 4.1s · stops 0.0s · due 0.0s · **total 4.1s** (sin Meta send)

**Traza:** intent=edit · tools=-

**Bot:**

```
✏️ *Editado* · _Taxi_

÷: Solo Bruno → *÷ 50/50*
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=135dad02014a3bd7
#6 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=135dad02014a3bd7
#7 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Cafetería pay=2026-08-19 status=confirmed batch=135dad02014a3bd7
```

</details>

---

## 3 · Day-trip + payer/split + saldo ✅

**Id:** `daytrip-payer` — reproducir con `--only daytrip-payer`

**Meta:** Sintra (no parada) → Lisboa; pagó Katia + solo ella; pregunta de deuda.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 1: city_name=Lisboa (no 'Sintra' libre); shared; pagó Bruno
- Turno 2: paid_by=katia + split=payer_only (Solo Katia). FAIL: other_only / Solo Bruno
- Turno 3: responder con el paseo recién editado (USD 30,8 a favor de Katia), no pedir ciudad si hay uno solo reciente

**Dónde tocar:** `bot/capture.py (resolve_place) · llm/client.py (new_split relativo al NUEVO paid_by) · bot/qa.py + qa/tools.py`

**Bruno:** paseo a sintra 28 euros _daytrip → Lisboa_

**Latencia:** dispatch 3.9s · stops 0.0s · due 0.0s · **total 3.9s** (sin Meta send)

**Traza:** intent=expense · tools=-

**Bot:**

```
✅ *Gasto guardado*

🎟️ Actividades — Paseo
💰 EUR 28,0 → USD 30,8
📍 Lisboa
👤 Pagó Bruno · ÷ 50/50
⚖️ *Katia* le debe *USD 15,4* por esto
(movement_id=5)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=shared paid_by=bruno cat=Actividades pay=None status=confirmed batch=None
```

</details>

**Bruno:** en realidad lo pagó katia y es solo de ella _edit paid_by + split_

**Latencia:** dispatch 5.5s · stops 0.0s · due 0.0s · **total 5.5s** (sin Meta send)

**Traza:** intent=edit · tools=-

**Bot:**

```
✏️ *Editado* · _Paseo_

👤: Pagó Bruno → *Pagó Katia*
÷: ÷ 50/50 → *Solo Katia*
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
```

</details>

**Bruno:** ¿cuánto le debo a katia por ese paseo? _Q&A_

**Latencia:** dispatch 10.7s · stops 0.0s · due 0.0s · **total 10.7s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=-

**Bot:**

```
No le debés nada por ese paseo: fue *solo katia* · *USD 30,8* 💸  
El saldo confirmado sigue siendo que vos le debés *USD 60,5* a katia.
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
```

</details>

---

## 4 · Pago futuro + ¿entra al saldo? + traer a hoy ✅

**Id:** `pending-a-hoy` — reproducir con `--only pending-a-hoy`

**Meta:** payment_date futura → pending; preguntar si cuenta; mover a hoy.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 1: city=Paris; status=pending; pay=2026-09-15; split=shared (NO inventar Solo Katia)
- Turno 2: respuesta debe decir que NO entra al balance todavía (pending excluido de compute_balance). FAIL: 'sí, ya está incluido'
- Turno 3: pay→hoy, status→confirmed; city debe seguir Paris. FAIL: arrastra ciudad a Lisboa

**Dónde tocar:** `llm/client.py (no inventar split) · bot/qa.py / qa/tools get_balance · bot/editor.py (edit date sin re-resolve city)`

**Bruno:** entrada al louvre 44 eur, se paga el 15 de septiembre en paris _pending futuro_

**Latencia:** dispatch 4.6s · stops 0.0s · due 0.0s · **total 4.6s** (sin Meta send)

**Traza:** intent=expense · tools=-

**Bot:**

```
✅ *Gasto guardado*

🎟️ Actividades — Entrada al Louvre
💰 EUR 44,0 → USD 48,4
📍 Paris
👤 Pagó Bruno · ÷ 50/50
📅 Se paga el 15/09 · TC provisorio
(movement_id=5)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-09-15 status=pending batch=None
```

</details>

**Bruno:** eso del louvre, ¿ya entra en el saldo o todavía no? _Q&A pending vs balance_

**Latencia:** dispatch 8.4s · stops 0.0s · due 0.0s · **total 8.4s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=-

**Bot:**

```
Todavía no: la entrada al Louvre está *pendiente* y no entra al saldo confirmado. 💸 *USD 48,4* · se paga el *15/09* 📅 — el saldo confirmado sigue siendo *bruno le debe USD 60,5 a katia*.
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-09-15 status=pending batch=None
```

</details>

**Bruno:** ok, poné que se paga hoy _edit payment_date_

**Latencia:** dispatch 4.1s · stops 0.0s · due 0.0s · **total 4.1s** (sin Meta send)

**Traza:** intent=edit · tools=-

**Bot:**

```
✏️ *Editado* · _Entrada al Louvre_

📅: 15/09 → *20/08*
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
```

</details>

---

## 5 · Corrección corta post-carga ✅

**Id:** `correccion-corta` — reproducir con `--only correccion-corta`

**Meta:** last_expense → edit por mensaje sin monto propio.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 1: city=Pititas; owner default puede ya ser Solo Katia — anotar estado real en DB
- Turno 2: intent=edit (ref_last), NO expense nuevo; un solo movement_id. Si ya era payer_only, 'Nada que cambiar' es OK; si era shared → payer_only
- No debe aparecer un 2.º tren

**Dónde tocar:** `llm/client.py (regla Último gasto) · bot/editor.py · stops_local / capture.owner_split`

**Katia:** tren 39 usd en pititas _carga_

**Latencia:** dispatch 3.9s · stops 0.0s · due 0.0s · **total 3.9s** (sin Meta send)

**Traza:** intent=expense · tools=-

**Bot:**

```
✅ *Gasto guardado*

🚆 Transporte — Tren
💰 USD 39,0
📍 Pititas
👤 Pagó Katia · Solo Katia
(movement_id=5)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
```

</details>

**Katia:** no, contalo solo para katia _edit split corto_

**Latencia:** dispatch 4.1s · stops 0.0s · due 0.0s · **total 4.1s** (sin Meta send)

**Traza:** intent=edit · tools=-

**Bot:**

```
Nada que cambiar: ya estaba así. 👌
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
```

</details>

---

## 6 · Delete por texto + confirmación ✅

**Id:** `delete-por-texto` — reproducir con `--only delete-por-texto`

**Meta:** intent delete del parser → botones; nunca hard-delete.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 1: Museo en Roma; paid_by=katia; split=payer_only (Solo Katia). FAIL: Solo Bruno / other_only
- Turno 2: botones de confirm; el resumen debe ser el museo, NO otro gasto (FAIL visto: ofreció 'Cena Lisboa')
- Turno 3: tras tap, el museo desaparece de la DB; no hard-delete en el turno 2

**Dónde tocar:** `bot/editor.py (resolve ref_text delete) · bot/interactive.py · llm/client.py (solo de ella → payer_only si paga ella)`

**Bruno:** museo vaticano 25 eur en roma, solo de katia, pagó katia _carga_

**Latencia:** dispatch 3.9s · stops 0.0s · due 0.0s · **total 3.9s** (sin Meta send)

**Traza:** intent=expense · tools=-

**Bot:**

```
✅ *Gasto guardado*

🎟️ Actividades — Museo Vaticano
💰 EUR 25,0 → USD 27,5
📍 Roma
👤 Pagó Katia · Solo Katia
(movement_id=5)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 25.00 EUR usd=27.50 desc='Museo Vaticano' city=Roma split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
```

</details>

**Bruno:** borrá el museo _delete NL_

**Latencia:** dispatch 4.1s · stops 0.0s · due 0.0s · **total 4.1s** (sin Meta send)

**Traza:** intent=delete · tools=-

**Bot:**

```
⚠️ ¿Borrar este movimiento? Es irreversible.
Museo Vaticano · EUR 25,0 · 02/08 · Roma · Pagó Katia
[botones]
  · Borrar 🗑️  (`del_confirm:nWbebnM1evS3El3ZjjILhQGv`)
  · Cancelar  (`del_cancel:nWbebnM1evS3El3ZjjILhQGv`)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 25.00 EUR usd=27.50 desc='Museo Vaticano' city=Roma split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
```

</details>

**Bruno:** [tap] `del_confirm:nWbebnM1evS3El3ZjjILhQGv` _confirmar_

**Latencia:** dispatch 0.0s · stops 0.0s · due 0.0s · **total 0.0s** (sin Meta send)

**Traza:** intent=- · tools=-

**Bot:**

```
🗑️ *Borrado*

Museo Vaticano · EUR 25,0 · 02/08 · Roma · Pagó Katia
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

## 7 · Settlement cruzado + ¿quién debe? ❌

**Id:** `settlement-cruzado` — reproducir con `--only settlement-cruzado`

**Meta:** Bruno salda con 'le pasé…'; Katia pregunta el neto.

**Checks deterministas: ❌ FALLAN**
- no debe crearse un gasto de hotel

**Mirar (qué corregir si falla):**
- Turno 1: type=settlement; Bruno→Katia; amount=80 USD; no crear expense de hotel
- Turno 2: desde wa_id de Katia, get_balance coherente post-settlement; no invertir deudor

**Dónde tocar:** `bot/capture.py (settlement) · balance.py · bot/qa.py`

**Bruno:** le pasé 80 usd a katia por lo del hotel de paris _settlement_

**Latencia:** dispatch 4.3s · stops 0.0s · due 0.0s · **total 4.3s** (sin Meta send)

**Traza:** intent=settlement · tools=-

**Bot:**

```
💸 *Pago de saldo*

*Bruno* → *Katia*
💰 USD 80,0
(movement_id=5)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 settlement 80.00 USD usd=80.00 desc='Pago a Katia por hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
```

</details>

**Katia:** che y ahora quién debe plata? _Q&A balance_

**Latencia:** dispatch 8.7s · stops 0.0s · due 0.0s · **total 8.7s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=-

**Bot:**

```
Ahora *katia le debe a bruno* *USD 19,5* 💸  
Es el saldo confirmado entre ustedes.
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 settlement 80.00 USD usd=80.00 desc='Pago a Katia por hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
```

</details>

---

## 8 · Batch + borrar (fast path) + confirmar los N ✅

**Id:** `batch-borrar` — reproducir con `--only batch-borrar`

**Meta:** Multi-gasto + comando borrar sin LLM + del_confirm del batch.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 1: 3 gastos mismo batch_key, city=Paris
- Turno 2: fast path (dispatch ~0s LLM); botones 'Borrar los 3' + 'Solo el último' + Cancelar
- Turno 3: desaparecen los 3 del batch, no solo el último

**Dónde tocar:** `bot/dispatcher.py (_handle_delete_command) · bot/interactive.py`

**Bruno:** en paris: metro 4 eur, croissant 3, agua 2 _batch 3_

**Latencia:** dispatch 8.4s · stops 0.0s · due 0.0s · **total 8.4s** (sin Meta send)

**Traza:** intent=expense · tools=-

**Bot:**

```
✅ *3 gastos guardados* · 📍 Paris · 👤 Pagó Bruno

- 🚆 Metro · EUR 4,0 → USD 4,4
- ☕ Croissant · EUR 3,0 → USD 3,3
- ☕ Agua · EUR 2,0 → USD 2,2

💰 Total: *USD 9,9*
⚖️ *Katia* le debe *USD 5,0* por esto
(movement_id=7)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 4.00 EUR usd=4.40 desc='Metro' city=Paris split=shared paid_by=bruno cat=Transporte pay=None status=confirmed batch=d595209c53bde8f3
#6 expense 3.00 EUR usd=3.30 desc='Croissant' city=Paris split=shared paid_by=bruno cat=Cafetería pay=None status=confirmed batch=d595209c53bde8f3
#7 expense 2.00 EUR usd=2.20 desc='Agua' city=Paris split=shared paid_by=bruno cat=Cafetería pay=None status=confirmed batch=d595209c53bde8f3
```

</details>

**Bruno:** borrar _fast path_

**Latencia:** dispatch 0.0s · stops 0.0s · due 0.0s · **total 0.0s** (sin Meta send)

**Traza:** intent=- · tools=-

**Bot:**

```
⚠️ Eso entró como *3 gastos juntos*. ¿Borrar? Es irreversible.
Metro · EUR 4,0 · 02/08 · Paris · Pagó Bruno
Croissant · EUR 3,0 · 02/08 · Paris · Pagó Bruno
Agua · EUR 2,0 · 02/08 · Paris · Pagó Bruno
[botones]
  · Borrar los 3 🗑️  (`del_confirm:Bh2iIwg62PQ1cN8P2C7X7-86`)
  · Solo el último  (`del_confirm:iiZakh8lDv7E9H-UseZlH6v0`)
  · Cancelar  (`del_cancel:Bh2iIwg62PQ1cN8P2C7X7-86`)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 4.00 EUR usd=4.40 desc='Metro' city=Paris split=shared paid_by=bruno cat=Transporte pay=None status=confirmed batch=d595209c53bde8f3
#6 expense 3.00 EUR usd=3.30 desc='Croissant' city=Paris split=shared paid_by=bruno cat=Cafetería pay=None status=confirmed batch=d595209c53bde8f3
#7 expense 2.00 EUR usd=2.20 desc='Agua' city=Paris split=shared paid_by=bruno cat=Cafetería pay=None status=confirmed batch=d595209c53bde8f3
```

</details>

**Bruno:** [tap] `del_confirm:Bh2iIwg62PQ1cN8P2C7X7-86` _confirmar batch_

**Latencia:** dispatch 0.0s · stops 0.0s · due 0.0s · **total 0.0s** (sin Meta send)

**Traza:** intent=- · tools=-

**Bot:**

```
🗑️ *Borrado* · 3 movimientos

Metro · EUR 4,0 · 02/08 · Paris · Pagó Bruno
Croissant · EUR 3,0 · 02/08 · Paris · Pagó Bruno
Agua · EUR 2,0 · 02/08 · Paris · Pagó Bruno
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

## 9 · Stop local / owner split (Pititas) ✅

**Id:** `pititas-owner` — reproducir con `--only pititas-owner`

**Meta:** Default split por owner_username; después forzar shared.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 1: city=Pititas; Bruno puede cargar ahí; split default Solo Katia (owner). Relativo a paid_by=bruno → other_only en DB / label Solo Katia
- Turno 2: edit → shared; un solo movimiento

**Dónde tocar:** `bot/capture.py (owner_split) · stops_local.py · bot/editor.py`

**Bruno:** super 22 eur en pititas _owner default_

**Latencia:** dispatch 3.9s · stops 0.0s · due 0.0s · **total 3.9s** (sin Meta send)

**Traza:** intent=expense · tools=-

**Bot:**

```
✅ *Gasto guardado*

🛒 Supermercado — Super
💰 EUR 22,0 → USD 24,2
📍 Pititas
👤 Pagó Bruno · Solo Katia
📅 Pagado el 20/08
⚖️ *Katia* le debe *USD 24,2* por esto
(movement_id=5)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 22.00 EUR usd=24.20 desc='Super' city=Pititas split=other_only paid_by=bruno cat=Supermercado pay=2026-08-20 status=confirmed batch=None
```

</details>

**Bruno:** en realidad era compartido _edit → shared_

**Latencia:** dispatch 3.9s · stops 0.0s · due 0.0s · **total 3.9s** (sin Meta send)

**Traza:** intent=edit · tools=-

**Bot:**

```
✏️ *Editado* · _Super_

÷: Solo Katia → *÷ 50/50*
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 22.00 EUR usd=24.20 desc='Super' city=Pititas split=shared paid_by=bruno cat=Supermercado pay=2026-08-20 status=confirmed batch=None
```

</details>

---

## 10 · Moneda explícita ≠ moneda ciudad + edit ✅

**Id:** `moneda-explicita` — reproducir con `--only moneda-explicita`

**Meta:** USD dicho en Lisboa (EUR); después corregir a euros.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 1: currency=USD (no forzar EUR de Lisboa); amount=40; city=Lisboa
- Turno 2: edit currency→EUR + recalc amount_usd; no crear 2.ª cena

**Dónde tocar:** `llm/client.py (currency explícita) · bot/editor.py (new_currency + FX)`

**Bruno:** cena 40 usd en lisboa _USD explícito_

**Latencia:** dispatch 4.0s · stops 0.0s · due 0.0s · **total 4.0s** (sin Meta send)

**Traza:** intent=expense · tools=-

**Bot:**

```
✅ *Gasto guardado*

🍽️ Comida — Cena
💰 USD 40,0
📍 Lisboa
👤 Pagó Bruno · ÷ 50/50
⚖️ *Katia* le debe *USD 20,0* por esto
(movement_id=5)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 40.00 USD usd=40.00 desc='Cena' city=Lisboa split=shared paid_by=bruno cat=Comida pay=None status=confirmed batch=None
```

</details>

**Bruno:** era en euros, no dólares _edit currency_

**Latencia:** dispatch 3.8s · stops 0.0s · due 0.0s · **total 3.8s** (sin Meta send)

**Traza:** intent=edit · tools=-

**Bot:**

```
✏️ *Editado* · _Cena_

💱: USD → *EUR*
💵: USD 40,0 → *USD 44,0*
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 40.00 EUR usd=44.00 desc='Cena' city=Lisboa split=shared paid_by=bruno cat=Comida pay=None status=confirmed batch=None
```

</details>

---

## 11 · Categoría ambigua + cat_pick ✅

**Id:** `cat-pick` — reproducir con `--only cat-pick`

**Meta:** Descripción vaga → botones de categoría; confirmar con tap.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 1: confidence baja → botones cat_pick (2–3). FAIL si guarda directo (p.ej. Compras) sin preguntar
- Turno 2: tras tap, gasto confirmado con esa category_id. Si el runner omite el tap, el turno 1 falló el umbral

**Dónde tocar:** `bot/capture.py (candidates / pending) · bot/interactive.py (cat_pick)`

**Bruno:** me cobraron 35 eur en lisboa por aquello _categoría ambigua_

**Latencia:** dispatch 4.4s · stops 0.0s · due 0.0s · **total 4.4s** (sin Meta send)

**Traza:** intent=expense · tools=-

**Bot:**

```
🤔 ¿Qué categoría? _Aquello_ · *EUR 35,0 → USD 38,5*
[botones]
  · 📦 Otros  (`cat_pick:abGTKtBF9kPx2CmCRtFUtmpd|11`)
  · 🎟️ Actividades  (`cat_pick:abGTKtBF9kPx2CmCRtFUtmpd|6`)
  · 🍽️ Comida  (`cat_pick:abGTKtBF9kPx2CmCRtFUtmpd|2`)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
```

</details>

**Bruno:** [tap] `cat_pick:abGTKtBF9kPx2CmCRtFUtmpd|11` _tap 1.er candidato_

**Latencia:** dispatch 0.0s · stops 0.0s · due 0.0s · **total 0.0s** (sin Meta send)

**Traza:** intent=- · tools=-

**Bot:**

```
✅ *Gasto guardado*

📦 Otros — Aquello
💰 EUR 35,0 → USD 38,5
📍 Lisboa
👤 Pagó Bruno · ÷ 50/50
⚖️ *Katia* le debe *USD 19,3* por esto
(movement_id=5)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 35.00 EUR usd=38.50 desc='Aquello' city=Lisboa split=shared paid_by=bruno cat=Otros pay=None status=confirmed batch=None
```

</details>

---

## 12 · Q&A follow-up elíptico ❌

**Id:** `qa-followup` — reproducir con `--only qa-followup`

**Meta:** Historial fresco: reusar intención cambiando ciudad/attribution.

**Checks deterministas: ❌ FALLAN**
- los 3 turnos son financieros, fueron ['qa', 'trip', 'qa']

**Mirar (qué corregir si falla):**
- Turno 1: total comida Paris desde tools (seed: Cena Paris USD 88 half-share context)
- Turno 2: reusa categoría Comida + ciudad Roma; no preguntar '¿comida o total?'
- Turno 3: attribution=paid para Bruno en Roma (no share)

**Dónde tocar:** `bot/qa.py (historial) · qa/tools.py (attribution)`

**Bruno:** ¿cuánto gastamos en comida en paris? _Q&A_

**Latencia:** dispatch 13.2s · stops 0.0s · due 0.0s · **total 13.2s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=aggregate_expenses

**Bot:**

```
En *París* 🍽️ gastamos *USD 88,0* 💸.
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
```

</details>

**Bruno:** ¿y en roma? _follow-up ciudad_

**Latencia:** dispatch 12.2s · stops 0.0s · due 0.0s · **total 12.2s** (sin Meta send)

**Traza:** intent=trip_question · canal=trip · outcome=ok · tools=list_guides

**Bot:**

```
¿Te referís a lo mismo que hablábamos de *Lisboa* (por ejemplo actividades, transporte, precios) o querés info distinta sobre *Roma*? Decime qué tema y lo busco en nuestras guías/notes.
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
```

</details>

**Bruno:** ¿y cuánto puse yo de bolsillo ahí? _attribution paid_

**Latencia:** dispatch 13.1s · stops 0.0s · due 0.0s · **total 13.1s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=-

**Bot:**

```
En *París* 📍 vos pusiste de bolsillo *USD 88,0* 💸.
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

## 13 · General / pre-viaje sin ciudad ✅

**Id:** `general-sin-ciudad` — reproducir con `--only general-sin-ciudad`

**Meta:** Fecha fuera de itinerario → city null; Q&A lo admite.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 1: city_name=null / sin stop; split=payer_only; currency=USD; pay≈2026-07-01
- Turno 2: admitir General / sin ciudad; NO inventar Roma/Londres

**Dónde tocar:** `bot/capture.py (resolve_place fuera de rango) · bot/qa.py`

**Bruno:** seguro de viaje 320 usd el 1 de julio, solo mío _fuera de rango_

**Latencia:** dispatch 4.2s · stops 0.0s · due 0.0s · **total 4.2s** (sin Meta send)

**Traza:** intent=expense · tools=-

**Bot:**

```
✅ *Gasto guardado*

📦 Otros — Seguro de viaje
💰 USD 320,0
📍 Sin ciudad
👤 Pagó Bruno · Solo Bruno
📅 Pagado el 01/07
(movement_id=5)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 320.00 USD usd=320.00 desc='Seguro de viaje' city=None split=payer_only paid_by=bruno cat=Otros pay=2026-07-01 status=confirmed batch=None
```

</details>

**Bruno:** ¿en qué ciudad quedó el seguro? _Q&A_

**Latencia:** dispatch 9.3s · stops 0.0s · due 0.0s · **total 9.3s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=-

**Bot:**

```
📍 El seguro de viaje quedó *sin ciudad*.
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 320.00 USD usd=320.00 desc='Seguro de viaje' city=None split=payer_only paid_by=bruno cat=Otros pay=2026-07-01 status=confirmed batch=None
```

</details>

---

## 14 · Settlement 'me pasó' desde Katia ✅

**Id:** `settlement-me-paso` — reproducir con `--only settlement-me-paso`

**Meta:** Dirección del pago desde el otro lado + saldo.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 1: settlement Bruno→Katia (paid_by=bruno); no expense; no invertir
- Turno 2: saldo fast path (~0s dispatch LLM) refleja el neto post-pago

**Dónde tocar:** `llm/client.py (settlement dirección) · bot/capture.py · bot/quick.py`

**Katia:** bruno me pasó 50 usd _settlement_

**Latencia:** dispatch 4.5s · stops 0.0s · due 0.0s · **total 4.5s** (sin Meta send)

**Traza:** intent=settlement · tools=-

**Bot:**

```
💸 *Pago de saldo*

*Bruno* → *Katia*
💰 USD 50,0
(movement_id=5)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 settlement 50.00 USD usd=50.00 desc='Transferencia de Bruno' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
```

</details>

**Bruno:** saldo _fast path_

**Latencia:** dispatch 0.0s · stops 0.0s · due 0.0s · **total 0.0s** (sin Meta send)

**Traza:** intent=- · tools=-

**Bot:**

```
⚖️ *Balance*

*Bruno* le debe *USD 10,5* a *Katia*
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 settlement 50.00 USD usd=50.00 desc='Transferencia de Bruno' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
```

</details>

---

## 15 · Multi-hostel con seña USD + resto en moneda local ✅

**Id:** `multi-hostel` — reproducir con `--only multi-hostel`

**Meta:** Mensaje real: varios hostels, cada uno con seña en USD hoy y resto en GBP a la fecha de ingreso, más uno simple con fecha.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- 5 movimientos, un solo batch_key: FW 34 USD confirmed hoy + FW 134 GBP pending 12/09; Portree 94 USD confirmed + 70 GBP pending 15/09; ClinkMama 403 EUR pending 25/08
- FAIL histórico: se pierden las etapas GBP (solo quedan las señas USD) o cada etapa nace como gasto suelto sin (i/n)
- Ciudades: Fort William / Portree / Lisboa (paradas reales); montos GBP con TC proxy de hoy

**Dónde tocar:** `llm/client.py (installments por ítem + currency) · bot/capture.py (expand_installments modo directo)`

**Bruno:** 34 usd Hostel Fort William hoy. El resto (134 GBP) a pagar al ingresar (12 de septiembre)

94 USD Hostel Portree hoy. El resto (70 GBP) a pagar al ingresar (15 de septiembre)

Hostel ClinkMama 403 euros el 25 de agosto en Lisboa _multi-hostel etapas mixtas_

**Latencia:** dispatch 10.8s · stops 0.0s · due 0.0s · **total 10.8s** (sin Meta send)

**Traza:** intent=expense · tools=-

**Bot:**

```
✅ *5 gastos guardados* · 👤 Pagó Bruno

- 🏨 Hostel Fort William (1/2) · USD 34,0 · Fort William
- 🏨 Hostel Fort William (2/2) · GBP 134,0 → USD 174,2 · Fort William · 📅 12/09
- 🏨 Hostel Portree (1/2) · USD 94,0 · Portree
- 🏨 Hostel Portree (2/2) · GBP 70,0 → USD 91,0 · Portree · 📅 15/09
- 🏨 Hostel ClinkMama · EUR 403,0 → USD 443,3 · Lisboa · 📅 25/08

💰 Total: *USD 836,5*
⚖️ *Katia* le debe *USD 64,0* por esto
(movement_id=9)
```

<details><summary>DB (últimos)</summary>

```
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 34.00 USD usd=34.00 desc='Hostel Fort William (1/2)' city=Fort William split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=42921a22d92a34f5
#6 expense 134.00 GBP usd=174.20 desc='Hostel Fort William (2/2)' city=Fort William split=shared paid_by=bruno cat=Alojamiento pay=2026-09-12 status=pending batch=42921a22d92a34f5
#7 expense 94.00 USD usd=94.00 desc='Hostel Portree (1/2)' city=Portree split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=42921a22d92a34f5
#8 expense 70.00 GBP usd=91.00 desc='Hostel Portree (2/2)' city=Portree split=shared paid_by=bruno cat=Alojamiento pay=2026-09-15 status=pending batch=42921a22d92a34f5
#9 expense 403.00 EUR usd=443.30 desc='Hostel ClinkMama' city=Lisboa split=shared paid_by=bruno cat=Alojamiento pay=2026-08-25 status=pending batch=42921a22d92a34f5
```

</details>

---

## 16 · Guías: qué hacer + cómo llegar ✅

**Id:** `guias-que-hacer` — reproducir con `--only guias-que-hacer`

**Meta:** trip_question grounded: lee las guías cacheadas y linkea a Andiamo.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 1: intent trip_question (no question ni unknown); parada de hoy = Lisboa; responde con contenido del doc 'actividades' seeded (Belém / Alfama), corto, con link a /guias/lisboa/actividades. FAIL si inventa contenido no seeded
- Turno 2: sigue en el canal de viaje; cita el tren desde Rossio (€2,30) del doc transporte. FAIL si responde de cultura general sin tools

**Dónde tocar:** `llm/client.py (intent trip_question) · bot/trip_qa.py · qa/trip_tools.py`

**Bruno:** ¿qué podemos hacer mañana acá? _trip_question deíctico_

**Latencia:** dispatch 11.4s · stops 0.0s · due 0.0s · **total 11.4s** (sin Meta send)

**Traza:** intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

**Bot:**

```
Perfecto — para mañana en Lisboa podés:  

- **Torre de Belém** — **€8**, recomiendan **ir antes de las 10**.  
- **Alfama** — perderse por las callecitas y subir al **mirador Santa Luzia**.  
- **Pastéis de Belém** — ir a probarlos (la guía aclara que **la cola avanza rápido**).  

📖 Más: https://andiamo.lat/guias/lisboa/actividades
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
```

</details>

**Bruno:** ¿y cómo llegamos a Sintra? _follow-up transporte_

**Latencia:** dispatch 12.1s · stops 0.0s · due 0.0s · **total 12.1s** (sin Meta send)

**Traza:** intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

**Bot:**

```
Para ir a **Sintra**:  
- Tomamos el **tren desde Rossio** — sale **cada 20 min**.  
- Precio: **€2,30** si pagás con la tarjeta **Viva Viagem**.  
- (La guía también sugiere evitar las horas pico; el tranvía 28 es otra opción temprano.)  

📖 Más: https://andiamo.lat/guias/lisboa/transporte
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

## 17 · Mixta: guía → nota → plata (cambio de canal) ✅

**Id:** `mixta-guia-plata` — reproducir con `--only mixta-guia-plata`

**Meta:** Aislamiento de canales: viaje y finanzas alternan sin pisarse.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 1: trip_question → list_notes; responde el check-in 15hs / código 4421 de la nota seeded. FAIL si dice que no hay notas o va al agente financiero
- Turno 2: intent question (plata) → agente financiero: total Lisboa desde tools (seed: Cena Lisboa USD 66). FAIL si el agente de guías intenta responder montos

**Dónde tocar:** `llm/client.py (borde plata/contenido) · bot/dispatcher.py (ruteo por canal)`

**Katia:** ¿qué anotamos del hostel de lisboa? _list_notes_

**Latencia:** dispatch 10.9s · stops 0.0s · due 0.0s · **total 10.9s** (sin Meta send)

**Traza:** intent=trip_question · canal=trip · outcome=ok · tools=list_notes

**Bot:**

```
Tenés esto de nuestro viaje para *Lisboa*:

- *Hostel Lisboa*: Check-in *15hs*, código puerta *4421* (nota marcada como pinned).

Si querés que agregue algo nuevo decímelo y lo anoto.
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
```

</details>

**Katia:** ¿cuánto llevamos gastado acá en lisboa? _vuelve a finanzas_

**Latencia:** dispatch 12.8s · stops 0.0s · due 0.0s · **total 12.8s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=aggregate_expenses

**Bot:**

```
📍 *Lisboa*
💸 Total gastado: *USD 66,0* (1 gasto)
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

## 18 · Q&A multi-tool pesado ✅

**Id:** `qa-multitool` — reproducir con `--only qa-multitool`

**Meta:** Consulta que obliga a varias tools: comparación entre ciudades + promedio por día.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 1: varias tool calls en el turno (aggregate por ciudad / group_by=city + get_itinerary). Debe responder con los tres totales, no pedir que acote
- Si se corta por presupuesto, la síntesis final tiene que entregar lo que ya juntó (respuesta parcial grounded). FAIL: copy de degradación con tools exitosas
- Turno 2: attribution=paid para Bruno; sigue en el canal financiero

**Dónde tocar:** `llm/chat.py (presupuestos + síntesis) · qa/tools.py (aggregate) · bot/qa.py`

**Bruno:** comparame cuánto gastamos en Roma, Paris y Lisboa, y decime el promedio por día del viaje _multi-tool: aggregate x ciudad + itinerario_

**Latencia:** dispatch 17.9s · stops 0.0s · due 0.0s · **total 17.9s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=aggregate_expenses,aggregate_expenses,get_itinerary

**Bot:**

```
Perfecto — acá va.

📍 Gastos por ciudad (USD):
- *Paris*: *USD 308,0*
- *Lisboa*: *USD 66,0*
- *Roma*: *USD 55,0*

💸 Total gastado (USD): *USD 429,0*

📅 Promedio por día: *USD 10,7* · sobre *40 días* del itinerario

Si querés que te lo muestre detallado por gasto de cada ciudad, lo listo.
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
```

</details>

**Bruno:** y de eso, ¿cuánto puse yo de bolsillo? _follow-up attribution=paid_

**Latencia:** dispatch 15.2s · stops 0.0s · due 0.0s · **total 15.2s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=-

**Bot:**

```
Vos pusiste de bolsillo *USD 154,0* 💸 ( *USD 66,0* en Lisboa + *USD 88,0* en Paris).
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

**Latencia:** dispatch 4.6s · stops 0.0s · due 0.0s · **total 4.6s** (sin Meta send)

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

**Latencia:** dispatch 4.7s · stops 0.0s · due 0.0s · **total 4.7s** (sin Meta send)

**Traza:** intent=expense · tools=-

**Bot:**

```
✅ *Gasto guardado*

☕ Cafetería — Café
💰 EUR 5,0 → USD 5,5
📍 Lisboa
👤 Pagó Bruno · ÷ 50/50
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
#6 expense 5.00 EUR usd=5.50 desc='Café' city=Lisboa split=shared paid_by=bruno cat=Cafetería pay=None status=confirmed batch=None
```

</details>

**Bruno:** no, fueron 8 _corrección de Bruno_

**Latencia:** dispatch 4.7s · stops 0.0s · due 0.0s · **total 4.7s** (sin Meta send)

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
#6 expense 8.00 EUR usd=8.80 desc='Café' city=Lisboa split=shared paid_by=bruno cat=Cafetería pay=None status=confirmed batch=None
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

**Latencia:** dispatch 5.5s · stops 0.0s · due 0.0s · **total 5.5s** (sin Meta send)

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

## 21 · Mover un gasto a Pititas (owner split) ✅

**Id:** `ciudad-a-pititas` — reproducir con `--only ciudad-a-pititas`

**Meta:** Edición de ciudad hacia una parada con dueño: mismo default que al cargar.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 2: city → Pititas Y el reparto pasa a Solo Katia (dueña), como si hubiera nacido ahí. FAIL: queda 50/50 y el balance miente
- Si el mensaje hubiera pedido un reparto explícito, ese manda

**Dónde tocar:** `bot/editor.py (apply_changes + owner_split) · bot/capture.py (owner_split)`

**Bruno:** farmacia 15 eur _carga en Lisboa, shared_

**Latencia:** dispatch 4.7s · stops 0.0s · due 0.0s · **total 4.7s** (sin Meta send)

**Traza:** intent=expense · tools=-

**Bot:**

```
✅ *Gasto guardado*

💊 Salud — Farmacia
💰 EUR 15,0 → USD 16,5
📍 Lisboa
👤 Pagó Bruno · ÷ 50/50
⚖️ *Katia* le debe *USD 8,3* por esto
(movement_id=5)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 15.00 EUR usd=16.50 desc='Farmacia' city=Lisboa split=shared paid_by=bruno cat=Salud pay=None status=confirmed batch=None
```

</details>

**Bruno:** en realidad fue en pititas _edit ciudad_

**Latencia:** dispatch 4.7s · stops 0.0s · due 0.0s · **total 4.7s** (sin Meta send)

**Traza:** intent=edit · tools=-

**Bot:**

```
✏️ *Editado* · _Farmacia_

📍: Lisboa → *Pititas*
÷: ÷ 50/50 → *Solo Katia*
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 15.00 EUR usd=16.50 desc='Farmacia' city=Pititas split=other_only paid_by=bruno cat=Salud pay=None status=confirmed batch=None
```

</details>

---

## 22 · Settlement corregido ✅

**Id:** `settlement-corregido` — reproducir con `--only settlement-corregido`

**Meta:** Corregir el monto de un pago de saldo recién cargado, sin crear un gasto.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 2: intent edit sobre el settlement (ref_last) → queda en 50
- FAIL histórico: el 'último movimiento' solo miraba gastos, así que 'no, eran 50' entraba como un GASTO nuevo de 50

**Dónde tocar:** `bot/editor.py (recent_movement include_settlements) · llm/client.py (regla del pago de saldo)`

**Bruno:** le pasé 80 usd a katia _settlement_

**Latencia:** dispatch 4.5s · stops 0.0s · due 0.0s · **total 4.5s** (sin Meta send)

**Traza:** intent=settlement · tools=-

**Bot:**

```
💸 *Pago de saldo*

*Bruno* → *Katia*
💰 USD 80,0
(movement_id=5)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 settlement 80.00 USD usd=80.00 desc=None city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
```

</details>

**Bruno:** no, eran 50 _corrección del pago_

**Latencia:** dispatch 4.3s · stops 0.0s · due 0.0s · **total 4.3s** (sin Meta send)

**Traza:** intent=edit · tools=-

**Bot:**

```
✏️ *Editado* · _Settlement_

💰: USD 80,0 → *USD 50,0*
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 settlement 50.00 USD usd=50.00 desc=None city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
```

</details>

---

## 23 · Cuándo llegamos (calendario) ❌

**Id:** `cuando-llegamos` — reproducir con `--only cuando-llegamos`

**Meta:** Fijar en qué canal vive el calendario del itinerario (hoy: financiero).

**Checks deterministas: ❌ FALLAN**
- '¿cuándo llegamos?' está definido como financiero, fue a trip

**Mirar (qué corregir si falla):**
- Debe contestar 2026-09-01 (arrival del seed) desde get_itinerary, no de memoria
- Decisión de producto: vive en el canal financiero porque ahí está la tool. Si se mueve a viaje, hay que cambiar el check a propósito

**Dónde tocar:** `llm/client.py (intent question vs trip_question) · qa/tools.py get_itinerary`

**Katia:** ¿cuándo llegamos a Interlaken? _itinerario_

**Latencia:** dispatch 7.0s · stops 0.0s · due 0.0s · **total 7.0s** (sin Meta send)

**Traza:** intent=trip_question · canal=trip · outcome=ok · tools=-

**Bot:**

```
Llegamos a *Interlaken el 2026-09-01*.  
Es la próxima parada después de Lisboa.
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

## 24 · Elíptica de plata tras hablar de guías ✅

**Id:** `eliptica-plata` — reproducir con `--only eliptica-plata`

**Meta:** Un follow-up corto con señal de plata sale del canal viaje aunque el hilo esté fresco.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 2: aunque el hilo fresco sea de guías, 'gastado' manda a finanzas
- FAIL: el agente de guías intenta responderlo y redirige (turno perdido)

**Dónde tocar:** `bot/dispatcher.py (unknown → ledger_signal) · bot/quick.py`

**Bruno:** ¿qué podemos hacer mañana acá? _canal viaje_

**Latencia:** dispatch 12.4s · stops 0.0s · due 0.0s · **total 12.4s** (sin Meta send)

**Traza:** intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

**Bot:**

```
Perfecto — para mañana en Lisboa podés:

- **Torre de Belém**: entrada **€8**, recomendable **ir antes de las 10**.  
- **Alfama**: perderse por las callecitas y subir al **mirador Santa Luzia**.  
- **Pastéis de Belém**: probar los pasteles — **la cola avanza rápido**.

📖 Más: https://andiamo.lat/guias/lisboa/actividades
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
```

</details>

**Bruno:** ¿y cuánto llevamos gastado? _elíptica de plata_

**Latencia:** dispatch 9.8s · stops 0.0s · due 0.0s · **total 9.8s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=aggregate_expenses

**Bot:**

```
💸 Llevamos gastado: *USD 429,0* (total del viaje, ambos).
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

## 25 · Pendientes por confirmar ❌

**Id:** `pendientes-query` — reproducir con `--only pendientes-query`

**Meta:** Preguntar qué está pendiente y qué se paga en septiembre (filtros de status/fecha de pago).

**Checks deterministas: ❌ FALLAN**
- el seed del turno 1 debe dejar 1 pendiente, hay 0
- canal financiero, fue [None, 'qa', 'qa']

**Mirar (qué corregir si falla):**
- Turno 2: debe listar el hostel como pendiente (status pending) y aclarar que no entra al saldo. FAIL: dice que no hay nada pendiente
- Turno 3: total de lo que se PAGA en septiembre (date_field=payment), no lo cargado en septiembre. FAIL: responde 0 porque filtró por fecha de carga

**Dónde tocar:** `qa/tools.py (status + date_field) · bot/qa.py (prompt)`

**Bruno:** hostel viena 200 eur, se paga el 10 de septiembre _pending futuro_

**Latencia:** dispatch 4.3s · stops 0.0s · due 0.0s · **total 4.3s** (sin Meta send)

**Traza:** intent=expense · tools=-

**Bot:**

```
✅ *Gasto guardado*

🏨 Alojamiento — Hostel Viena
💰 EUR 200,0 → USD 220,0
📍 Lisboa
👤 Pagó Bruno · ÷ 50/50
⚖️ *Katia* le debe *USD 110,0* por esto
(movement_id=5)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 200.00 EUR usd=220.00 desc='Hostel Viena' city=Lisboa split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=None
```

</details>

**Bruno:** ¿qué tengo pendiente de pago? _filtro status_

**Latencia:** dispatch 9.3s · stops 0.0s · due 0.0s · **total 9.4s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=-

**Bot:**

```
¿Te referís a gastos con fecha futura que tenés que pagar vos (pendientes), o querés saber si le debés plata a Katia / si ella te debe a vos (balance)?
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 200.00 EUR usd=220.00 desc='Hostel Viena' city=Lisboa split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=None
```

</details>

**Bruno:** ¿y cuánto se paga en septiembre? _eje payment_date_

**Latencia:** dispatch 11.9s · stops 0.0s · due 0.0s · **total 12.0s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=aggregate_expenses

**Bot:**

```
📅 *No hay gastos cargados con fecha de pago en septiembre* (USD).  
¿Querés que mire también los pendientes futuros sin filtrar por mes?
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 200.00 EUR usd=220.00 desc='Hostel Viena' city=Lisboa split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=None
```

</details>

---

## 26 · Promedio por día ✅

**Id:** `promedio-dia` — reproducir con `--only promedio-dia`

**Meta:** Promedio $/día con los días del itinerario, no los días con gastos.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Debe usar los días del itinerario (get_itinerary), no contar solo los días con movimientos. FAIL: divide por 4 días porque hay 4 gastos
- No puede degradar a la copy de 'no quiero contestarte de memoria': hay datos

**Dónde tocar:** `bot/qa.py (semántica del promedio) · qa/tools.py get_itinerary`

**Katia:** ¿cuánto estamos gastando por día? _promedio_

**Latencia:** dispatch 13.2s · stops 0.0s · due 0.0s · **total 13.2s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=aggregate_expenses,get_itinerary

**Bot:**

```
💸 Total gastado (todo el viaje): *USD 429,0*  
📅 Días del itinerario: *40*  
💸 Promedio por día: *USD 10,7* (se calcula con los días del itinerario)
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

## 27 · Presupuesto: deflección a la app ✅

**Id:** `presupuesto-deflect` — reproducir con `--only presupuesto-deflect`

**Meta:** El presupuesto no vive en el bot: '¿vamos bien?' se deriva a la sección Presupuesto de la web en una línea, sin estimar nada.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Tiene que decir en una línea que el presupuesto se mira en la app (sección Presupuesto). FAIL: estima un rango o contesta con el promedio del viaje, que es justo el número equivocado
- No puede quedar ninguna tool de presupuesto: budget_status ya no existe
- Una pregunta no crea ni toca movimientos

**Dónde tocar:** `bot/qa.py (_render_system → budget_link_rule) · bot/copy.py link_budget`

**Bruno:** ¿vamos bien de guita en Lisboa? _deflecta a la app_

**Latencia:** dispatch 15.1s · stops 0.0s · due 0.0s · **total 15.1s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=aggregate_expenses

**Bot:**

```
*Lisboa* 📍
No tengo el presupuesto acá en el bot; miralo en la app (no tengo link a mano).

💸 En total en Lisboa gastamos *USD 66,0*.

Últimos 1 gastos (USD):
- 19/08 · Cena Lisboa · *USD 66,0* · bruno · 50/50
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
| 1 · Cuotas + corrección de total | 1 | bruno | cuotas | 5.9 | 0.0 | 0.0 | 5.9 |
| 1 · Cuotas + corrección de total | 2 | bruno | edit monto del batch | 4.2 | 0.0 | 0.0 | 4.2 |
| 2 · Multi-gasto mezclado + fix de split | 1 | bruno | batch 3 ítems | 8.3 | 0.0 | 0.0 | 8.3 |
| 2 · Multi-gasto mezclado + fix de split | 2 | bruno | edit split taxi | 4.1 | 0.0 | 0.0 | 4.1 |
| 3 · Day-trip + payer/split + saldo | 1 | bruno | daytrip → Lisboa | 3.9 | 0.0 | 0.0 | 3.9 |
| 3 · Day-trip + payer/split + saldo | 2 | bruno | edit paid_by + split | 5.5 | 0.0 | 0.0 | 5.5 |
| 3 · Day-trip + payer/split + saldo | 3 | bruno | Q&A | 10.7 | 0.0 | 0.0 | 10.7 |
| 4 · Pago futuro + ¿entra al saldo? + traer a hoy | 1 | bruno | pending futuro | 4.6 | 0.0 | 0.0 | 4.6 |
| 4 · Pago futuro + ¿entra al saldo? + traer a hoy | 2 | bruno | Q&A pending vs balance | 8.4 | 0.0 | 0.0 | 8.4 |
| 4 · Pago futuro + ¿entra al saldo? + traer a hoy | 3 | bruno | edit payment_date | 4.1 | 0.0 | 0.0 | 4.1 |
| 5 · Corrección corta post-carga | 1 | katia | carga | 3.9 | 0.0 | 0.0 | 3.9 |
| 5 · Corrección corta post-carga | 2 | katia | edit split corto | 4.1 | 0.0 | 0.0 | 4.1 |
| 6 · Delete por texto + confirmación | 1 | bruno | carga | 3.9 | 0.0 | 0.0 | 3.9 |
| 6 · Delete por texto + confirmación | 2 | bruno | delete NL | 4.1 | 0.0 | 0.0 | 4.1 |
| 6 · Delete por texto + confirmación | 3 | bruno | confirmar | 0.0 | 0.0 | 0.0 | 0.0 |
| 7 · Settlement cruzado + ¿quién debe? | 1 | bruno | settlement | 4.3 | 0.0 | 0.0 | 4.3 |
| 7 · Settlement cruzado + ¿quién debe? | 2 | katia | Q&A balance | 8.7 | 0.0 | 0.0 | 8.7 |
| 8 · Batch + borrar (fast path) + confirmar los N | 1 | bruno | batch 3 | 8.4 | 0.0 | 0.0 | 8.4 |
| 8 · Batch + borrar (fast path) + confirmar los N | 2 | bruno | fast path | 0.0 | 0.0 | 0.0 | 0.0 |
| 8 · Batch + borrar (fast path) + confirmar los N | 3 | bruno | confirmar batch | 0.0 | 0.0 | 0.0 | 0.0 |
| 9 · Stop local / owner split (Pititas) | 1 | bruno | owner default | 3.9 | 0.0 | 0.0 | 3.9 |
| 9 · Stop local / owner split (Pititas) | 2 | bruno | edit → shared | 3.9 | 0.0 | 0.0 | 3.9 |
| 10 · Moneda explícita ≠ moneda ciudad + edit | 1 | bruno | USD explícito | 4.0 | 0.0 | 0.0 | 4.0 |
| 10 · Moneda explícita ≠ moneda ciudad + edit | 2 | bruno | edit currency | 3.8 | 0.0 | 0.0 | 3.8 |
| 11 · Categoría ambigua + cat_pick | 1 | bruno | categoría ambigua | 4.4 | 0.0 | 0.0 | 4.4 |
| 11 · Categoría ambigua + cat_pick | 2 | bruno | tap 1.er candidato | 0.0 | 0.0 | 0.0 | 0.0 |
| 12 · Q&A follow-up elíptico | 1 | bruno | Q&A | 13.2 | 0.0 | 0.0 | 13.2 |
| 12 · Q&A follow-up elíptico | 2 | bruno | follow-up ciudad | 12.2 | 0.0 | 0.0 | 12.2 |
| 12 · Q&A follow-up elíptico | 3 | bruno | attribution paid | 13.1 | 0.0 | 0.0 | 13.1 |
| 13 · General / pre-viaje sin ciudad | 1 | bruno | fuera de rango | 4.2 | 0.0 | 0.0 | 4.2 |
| 13 · General / pre-viaje sin ciudad | 2 | bruno | Q&A | 9.3 | 0.0 | 0.0 | 9.3 |
| 14 · Settlement 'me pasó' desde Katia | 1 | katia | settlement | 4.5 | 0.0 | 0.0 | 4.5 |
| 14 · Settlement 'me pasó' desde Katia | 2 | bruno | fast path | 0.0 | 0.0 | 0.0 | 0.0 |
| 15 · Multi-hostel con seña USD + resto en moneda local | 1 | bruno | multi-hostel etapas mixtas | 10.8 | 0.0 | 0.0 | 10.8 |
| 16 · Guías: qué hacer + cómo llegar | 1 | bruno | trip_question deíctico | 11.4 | 0.0 | 0.0 | 11.4 |
| 16 · Guías: qué hacer + cómo llegar | 2 | bruno | follow-up transporte | 12.1 | 0.0 | 0.0 | 12.1 |
| 17 · Mixta: guía → nota → plata (cambio de canal) | 1 | katia | list_notes | 10.9 | 0.0 | 0.0 | 10.9 |
| 17 · Mixta: guía → nota → plata (cambio de canal) | 2 | katia | vuelve a finanzas | 12.8 | 0.0 | 0.0 | 12.8 |
| 18 · Q&A multi-tool pesado | 1 | bruno | multi-tool: aggregate x ciudad + itinerario | 17.9 | 0.0 | 0.0 | 17.9 |
| 18 · Q&A multi-tool pesado | 2 | bruno | follow-up attribution=paid | 15.2 | 0.0 | 0.0 | 15.2 |
| 19 · Dos remitentes intercalados | 1 | katia | carga Katia | 4.6 | 0.0 | 0.0 | 4.6 |
| 19 · Dos remitentes intercalados | 2 | bruno | carga Bruno | 4.7 | 0.0 | 0.0 | 4.7 |
| 19 · Dos remitentes intercalados | 3 | bruno | corrección de Bruno | 4.7 | 0.0 | 0.0 | 4.7 |
| 20 · Cuotas que no cierran | 1 | bruno | etapas sin montos ni fechas | 5.5 | 0.0 | 0.0 | 5.5 |
| 21 · Mover un gasto a Pititas (owner split) | 1 | bruno | carga en Lisboa, shared | 4.7 | 0.0 | 0.0 | 4.7 |
| 21 · Mover un gasto a Pititas (owner split) | 2 | bruno | edit ciudad | 4.7 | 0.0 | 0.0 | 4.7 |
| 22 · Settlement corregido | 1 | bruno | settlement | 4.5 | 0.0 | 0.0 | 4.5 |
| 22 · Settlement corregido | 2 | bruno | corrección del pago | 4.3 | 0.0 | 0.0 | 4.3 |
| 23 · Cuándo llegamos (calendario) | 1 | katia | itinerario | 7.0 | 0.0 | 0.0 | 7.0 |
| 24 · Elíptica de plata tras hablar de guías | 1 | bruno | canal viaje | 12.4 | 0.0 | 0.0 | 12.4 |
| 24 · Elíptica de plata tras hablar de guías | 2 | bruno | elíptica de plata | 9.8 | 0.0 | 0.0 | 9.8 |
| 25 · Pendientes por confirmar | 1 | bruno | pending futuro | 4.3 | 0.0 | 0.0 | 4.3 |
| 25 · Pendientes por confirmar | 2 | bruno | filtro status | 9.3 | 0.0 | 0.0 | 9.4 |
| 25 · Pendientes por confirmar | 3 | bruno | eje payment_date | 11.9 | 0.0 | 0.0 | 12.0 |
| 26 · Promedio por día | 1 | katia | promedio | 13.2 | 0.0 | 0.0 | 13.2 |
| 27 · Presupuesto: deflección a la app | 1 | bruno | deflecta a la app | 15.1 | 0.0 | 0.0 | 15.1 |

Promedio dispatch **6.9s** · promedio total **6.9s** · más lento: bruno «comparame cuánto gastamos en Roma, Paris…» (17.9s)

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
