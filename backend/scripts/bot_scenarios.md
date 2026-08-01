# Escenarios de charla — última corrida

> **Auto-generado** por `scripts/bot_scenario_runner.py`.
> Cada corrida **borra y reemplaza** este archivo (no acumula historial).
> Catálogo: `SUITE_CRITICAL` (1–10) + `CONVERSATIONS_EXTRA` (11–27) en el script.
> Los **checks** son deterministas (DB / intent / tools): si fallan, el runner sale con exit 1. El texto se evalúa a ojo.

- Corrida: `2026-08-01T20:18:59-03:00`
- Suite: **suite crítica (10)**
- provider=`openai` parser=`gpt-5-mini` chat=`gpt-5-mini`
- Hoy ficticio: `2026-08-20` (parada activa: Lisboa)
- Escenarios corridos: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 (10 conversaciones)
- Checks: **10 ok** · **0 con fallas** · 0 sin checks
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

**Latencia:** dispatch 4.6s · stops 0.0s · due 0.0s · **total 4.6s** (sin Meta send)

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
#5 expense 129.00 CHF usd=154.80 desc='Hostel Interlaken (1/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=500e768d54a49f12
#6 expense 301.00 CHF usd=361.20 desc='Hostel Interlaken (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=500e768d54a49f12
```

</details>

**Bruno:** no, el total era 480 no 430 _edit monto del batch_

**Latencia:** dispatch 3.0s · stops 0.0s · due 0.0s · **total 3.0s** (sin Meta send)

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
#5 expense 144.00 CHF usd=172.80 desc='Hostel Interlaken (1/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=500e768d54a49f12
#6 expense 336.00 CHF usd=403.20 desc='Hostel Interlaken (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=500e768d54a49f12
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

**Latencia:** dispatch 6.0s · stops 0.0s · due 0.0s · **total 6.0s** (sin Meta send)

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
#5 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=94b2fe9e242b5236
#6 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=payer_only paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=94b2fe9e242b5236
#7 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Cafetería pay=2026-08-19 status=confirmed batch=94b2fe9e242b5236
```

</details>

**Bruno:** el taxi en realidad era compartido _edit split taxi_

**Latencia:** dispatch 3.2s · stops 0.0s · due 0.0s · **total 3.2s** (sin Meta send)

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
#5 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=94b2fe9e242b5236
#6 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=94b2fe9e242b5236
#7 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Cafetería pay=2026-08-19 status=confirmed batch=94b2fe9e242b5236
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

**Latencia:** dispatch 3.1s · stops 0.0s · due 0.0s · **total 3.1s** (sin Meta send)

**Traza:** intent=expense · tools=-

**Bot:**

```
✅ *Gasto guardado*

🎟️ Actividades — Paseo a Sintra
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
#5 expense 28.00 EUR usd=30.80 desc='Paseo a Sintra' city=Lisboa split=shared paid_by=bruno cat=Actividades pay=None status=confirmed batch=None
```

</details>

**Bruno:** en realidad lo pagó katia y es solo de ella _edit paid_by + split_

**Latencia:** dispatch 3.0s · stops 0.0s · due 0.0s · **total 3.0s** (sin Meta send)

**Traza:** intent=edit · tools=-

**Bot:**

```
✏️ *Editado* · _Paseo a Sintra_

👤: Pagó Bruno → *Pagó Katia*
÷: ÷ 50/50 → *Solo Katia*
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 28.00 EUR usd=30.80 desc='Paseo a Sintra' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
```

</details>

**Bruno:** ¿cuánto le debo a katia por ese paseo? _Q&A_

**Latencia:** dispatch 38.5s · stops 0.0s · due 0.0s · **total 38.5s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=-

**Bot:**

```
No le debés nada por ese paseo. 📍 Lisboa · Paseo a Sintra · *USD 30,8* · *katia* · *solo katia*
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 28.00 EUR usd=30.80 desc='Paseo a Sintra' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
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

**Latencia:** dispatch 3.4s · stops 0.0s · due 0.0s · **total 3.4s** (sin Meta send)

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

**Latencia:** dispatch 6.8s · stops 0.0s · due 0.0s · **total 6.8s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=-

**Bot:**

```
No, todavía no entra: la entrada al Louvre está *PENDIENTE* por *USD 48,4* y está excluida del saldo hasta que se confirme. 📅 Se paga el *15/09*.  
💸 Saldo actual (confirmado): *bruno le debe USD 60,5 a katia*.
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

**Latencia:** dispatch 3.4s · stops 0.0s · due 0.0s · **total 3.4s** (sin Meta send)

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

**Latencia:** dispatch 3.6s · stops 0.0s · due 0.0s · **total 3.6s** (sin Meta send)

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

**Latencia:** dispatch 3.2s · stops 0.0s · due 0.0s · **total 3.2s** (sin Meta send)

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

**Latencia:** dispatch 3.8s · stops 0.0s · due 0.0s · **total 3.8s** (sin Meta send)

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

**Latencia:** dispatch 2.9s · stops 0.0s · due 0.0s · **total 2.9s** (sin Meta send)

**Traza:** intent=delete · tools=-

**Bot:**

```
⚠️ ¿Borrar este movimiento? Es irreversible.
Museo Vaticano · EUR 25,0 · 01/08 · Roma · Pagó Katia
[botones]
  · Borrar 🗑️  (`del_confirm:vCLgCDe4k_fw3LFYOwpKe1DY`)
  · Cancelar  (`del_cancel:0`)
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

**Bruno:** [tap] `del_confirm:vCLgCDe4k_fw3LFYOwpKe1DY` _confirmar_

**Latencia:** dispatch 0.0s · stops 0.0s · due 0.0s · **total 0.0s** (sin Meta send)

**Traza:** intent=- · tools=-

**Bot:**

```
🗑️ *Borrado*

Museo Vaticano · EUR 25,0 · 01/08 · Roma · Pagó Katia
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

## 7 · Settlement cruzado + ¿quién debe? ✅

**Id:** `settlement-cruzado` — reproducir con `--only settlement-cruzado`

**Meta:** Bruno salda con 'le pasé…'; Katia pregunta el neto.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 1: type=settlement; Bruno→Katia; amount=80 USD; no crear expense de hotel
- Turno 2: desde wa_id de Katia, get_balance coherente post-settlement; no invertir deudor

**Dónde tocar:** `bot/capture.py (settlement) · balance.py · bot/qa.py`

**Bruno:** le pasé 80 usd a katia por lo del hotel de paris _settlement_

**Latencia:** dispatch 2.9s · stops 0.0s · due 0.0s · **total 2.9s** (sin Meta send)

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
#5 settlement 80.00 USD usd=80.00 desc='Pago a Katia' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
```

</details>

**Katia:** che y ahora quién debe plata? _Q&A balance_

**Latencia:** dispatch 7.7s · stops 0.0s · due 0.0s · **total 7.7s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=-

**Bot:**

```
Vos le debés *USD 19,5* a *bruno* 💸 (saldo confirmado).
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 settlement 80.00 USD usd=80.00 desc='Pago a Katia' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
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

**Latencia:** dispatch 5.7s · stops 0.0s · due 0.0s · **total 5.7s** (sin Meta send)

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
#5 expense 4.00 EUR usd=4.40 desc='Metro' city=Paris split=shared paid_by=bruno cat=Transporte pay=2026-08-20 status=confirmed batch=4b2787600aa47ebf
#6 expense 3.00 EUR usd=3.30 desc='Croissant' city=Paris split=shared paid_by=bruno cat=Cafetería pay=2026-08-20 status=confirmed batch=4b2787600aa47ebf
#7 expense 2.00 EUR usd=2.20 desc='Agua' city=Paris split=shared paid_by=bruno cat=Cafetería pay=2026-08-20 status=confirmed batch=4b2787600aa47ebf
```

</details>

**Bruno:** borrar _fast path_

**Latencia:** dispatch 0.0s · stops 0.0s · due 0.0s · **total 0.0s** (sin Meta send)

**Traza:** intent=- · tools=-

**Bot:**

```
⚠️ Eso entró como *3 gastos juntos*. ¿Borrar? Es irreversible.
Metro · EUR 4,0 · 01/08 · Paris · Pagó Bruno
Croissant · EUR 3,0 · 01/08 · Paris · Pagó Bruno
Agua · EUR 2,0 · 01/08 · Paris · Pagó Bruno
[botones]
  · Borrar los 3 🗑️  (`del_confirm:C79c6hQV1eoYOoy3Njfwhv03`)
  · Solo el último  (`del_confirm:XgnWX5qgO_IsxS6YeYAZ6m-U`)
  · Cancelar  (`del_cancel:0`)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 4.00 EUR usd=4.40 desc='Metro' city=Paris split=shared paid_by=bruno cat=Transporte pay=2026-08-20 status=confirmed batch=4b2787600aa47ebf
#6 expense 3.00 EUR usd=3.30 desc='Croissant' city=Paris split=shared paid_by=bruno cat=Cafetería pay=2026-08-20 status=confirmed batch=4b2787600aa47ebf
#7 expense 2.00 EUR usd=2.20 desc='Agua' city=Paris split=shared paid_by=bruno cat=Cafetería pay=2026-08-20 status=confirmed batch=4b2787600aa47ebf
```

</details>

**Bruno:** [tap] `del_confirm:C79c6hQV1eoYOoy3Njfwhv03` _confirmar batch_

**Latencia:** dispatch 0.0s · stops 0.0s · due 0.0s · **total 0.0s** (sin Meta send)

**Traza:** intent=- · tools=-

**Bot:**

```
🗑️ *Borrado* · 3 movimientos

Metro · EUR 4,0 · 01/08 · Paris · Pagó Bruno
Croissant · EUR 3,0 · 01/08 · Paris · Pagó Bruno
Agua · EUR 2,0 · 01/08 · Paris · Pagó Bruno
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

**Latencia:** dispatch 3.0s · stops 0.0s · due 0.0s · **total 3.0s** (sin Meta send)

**Traza:** intent=expense · tools=-

**Bot:**

```
✅ *Gasto guardado*

🛒 Supermercado — Super
💰 EUR 22,0 → USD 24,2
📍 Pititas
👤 Pagó Bruno · Solo Katia
⚖️ *Katia* le debe *USD 24,2* por esto
(movement_id=5)
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 22.00 EUR usd=24.20 desc='Super' city=Pititas split=other_only paid_by=bruno cat=Supermercado pay=None status=confirmed batch=None
```

</details>

**Bruno:** en realidad era compartido _edit → shared_

**Latencia:** dispatch 2.7s · stops 0.0s · due 0.0s · **total 2.7s** (sin Meta send)

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
#5 expense 22.00 EUR usd=24.20 desc='Super' city=Pititas split=shared paid_by=bruno cat=Supermercado pay=None status=confirmed batch=None
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

**Latencia:** dispatch 2.9s · stops 0.0s · due 0.0s · **total 2.9s** (sin Meta send)

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

**Latencia:** dispatch 2.9s · stops 0.0s · due 0.0s · **total 2.9s** (sin Meta send)

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

## Resumen de latencia

| Escenario | Turno | Quién | Nota | dispatch_s | stops_s | due_s | total_s |
|---|---:|---|---|---:|---:|---:|---:|
| 1 · Cuotas + corrección de total | 1 | bruno | cuotas | 4.6 | 0.0 | 0.0 | 4.6 |
| 1 · Cuotas + corrección de total | 2 | bruno | edit monto del batch | 3.0 | 0.0 | 0.0 | 3.0 |
| 2 · Multi-gasto mezclado + fix de split | 1 | bruno | batch 3 ítems | 6.0 | 0.0 | 0.0 | 6.0 |
| 2 · Multi-gasto mezclado + fix de split | 2 | bruno | edit split taxi | 3.2 | 0.0 | 0.0 | 3.2 |
| 3 · Day-trip + payer/split + saldo | 1 | bruno | daytrip → Lisboa | 3.1 | 0.0 | 0.0 | 3.1 |
| 3 · Day-trip + payer/split + saldo | 2 | bruno | edit paid_by + split | 3.0 | 0.0 | 0.0 | 3.0 |
| 3 · Day-trip + payer/split + saldo | 3 | bruno | Q&A | 38.5 | 0.0 | 0.0 | 38.5 |
| 4 · Pago futuro + ¿entra al saldo? + traer a hoy | 1 | bruno | pending futuro | 3.4 | 0.0 | 0.0 | 3.4 |
| 4 · Pago futuro + ¿entra al saldo? + traer a hoy | 2 | bruno | Q&A pending vs balance | 6.8 | 0.0 | 0.0 | 6.8 |
| 4 · Pago futuro + ¿entra al saldo? + traer a hoy | 3 | bruno | edit payment_date | 3.4 | 0.0 | 0.0 | 3.4 |
| 5 · Corrección corta post-carga | 1 | katia | carga | 3.6 | 0.0 | 0.0 | 3.6 |
| 5 · Corrección corta post-carga | 2 | katia | edit split corto | 3.2 | 0.0 | 0.0 | 3.2 |
| 6 · Delete por texto + confirmación | 1 | bruno | carga | 3.8 | 0.0 | 0.0 | 3.8 |
| 6 · Delete por texto + confirmación | 2 | bruno | delete NL | 2.9 | 0.0 | 0.0 | 2.9 |
| 6 · Delete por texto + confirmación | 3 | bruno | confirmar | 0.0 | 0.0 | 0.0 | 0.0 |
| 7 · Settlement cruzado + ¿quién debe? | 1 | bruno | settlement | 2.9 | 0.0 | 0.0 | 2.9 |
| 7 · Settlement cruzado + ¿quién debe? | 2 | katia | Q&A balance | 7.7 | 0.0 | 0.0 | 7.7 |
| 8 · Batch + borrar (fast path) + confirmar los N | 1 | bruno | batch 3 | 5.7 | 0.0 | 0.0 | 5.7 |
| 8 · Batch + borrar (fast path) + confirmar los N | 2 | bruno | fast path | 0.0 | 0.0 | 0.0 | 0.0 |
| 8 · Batch + borrar (fast path) + confirmar los N | 3 | bruno | confirmar batch | 0.0 | 0.0 | 0.0 | 0.0 |
| 9 · Stop local / owner split (Pititas) | 1 | bruno | owner default | 3.0 | 0.0 | 0.0 | 3.0 |
| 9 · Stop local / owner split (Pititas) | 2 | bruno | edit → shared | 2.7 | 0.0 | 0.0 | 2.7 |
| 10 · Moneda explícita ≠ moneda ciudad + edit | 1 | bruno | USD explícito | 2.9 | 0.0 | 0.0 | 2.9 |
| 10 · Moneda explícita ≠ moneda ciudad + edit | 2 | bruno | edit currency | 2.9 | 0.0 | 0.0 | 2.9 |

Promedio dispatch **4.8s** · promedio total **4.8s** · más lento: bruno «¿cuánto le debo a katia por ese paseo?» (38.5s)

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
