# Escenarios de charla — última corrida

> **Auto-generado** por `scripts/bot_scenario_runner.py`.
> Cada corrida **borra y reemplaza** este archivo (no acumula historial).
> Catálogo: `SUITE_CRITICAL` (1–10) + `CONVERSATIONS_EXTRA` (11–14) en el script.

- Corrida: `2026-07-19T12:46:34-03:00`
- Suite: **catálogo completo (14)**
- provider=`openai` parser=`gpt-5-mini` chat=`gpt-5-mini`
- Hoy ficticio: `2026-08-20` (parada activa: Lisboa)
- Escenarios corridos: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14 (14 conversaciones)
- Latencia: fases espejo de `process_message` (stops → due → dispatch); Meta send/typing **no** medidos

---

## 1 · Cuotas + corrección de total

**Meta:** Gasto en etapas (30% hoy / resto check-in) y corregir el total del batch.

**Mirar (qué corregir si falla):**
- Turno 1: 2 filas mismo batch_key; montos 129+301 (=430); 2ª con pay=2026-09-03 y status=pending
- Turno 2 FAIL típico: solo edita la cuota 2/2 a 480 (total 609). Debe redistribuir el batch a total 480 (≈144+336) o editar el gasto lógico, no un renglón suelto
- Card no debe mostrar deuda por la cuota pending

**Dónde tocar:** `llm/client.py (installments) · bot/editor.py (edit amount + batch) · bot/capture.py (expand_installments)`

**Bruno:** hostel interlaken 430 chf, 30% hoy y el resto al check-in el 3 de septiembre _cuotas_

**Latencia:** dispatch 5.2s · stops 0.0s · due 0.0s · **total 5.2s** (sin Meta send)

**Bot:**

```
✅ *2 gastos guardados* · 📍 Interlaken · 👤 Pagó Bruno

- 🏨 Hostel (1/2) · CHF 129,0 → USD 154,8
- 🏨 Hostel (2/2) · CHF 301,0 → USD 361,2 · 📅 03/09

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
#5 expense 129.00 CHF usd=154.80 desc='Hostel (1/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=b8d92257f9828205
#6 expense 301.00 CHF usd=361.20 desc='Hostel (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=b8d92257f9828205
```

</details>

**Bruno:** no, el total era 480 no 430 _edit monto del batch_

**Latencia:** dispatch 3.0s · stops 0.0s · due 0.0s · **total 3.0s** (sin Meta send)

**Bot:**

```
✏️ *Editado* · _Hostel_

💰 Total: CHF 430,0 → *CHF 480,0*
- Hostel (1/2) · CHF 144,0 → USD 172,8
- Hostel (2/2) · CHF 336,0 → USD 403,2 · 📅 03/09
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 144.00 CHF usd=172.80 desc='Hostel (1/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=b8d92257f9828205
#6 expense 336.00 CHF usd=403.20 desc='Hostel (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=b8d92257f9828205
```

</details>

---

## 2 · Multi-gasto mezclado + fix de split

**Meta:** 3 ítems (payer/split distintos) y corregir el split del taxi por ref.

**Mirar (qué corregir si falla):**
- Turno 1: 3 movimientos Roma, pay=ayer; cena paid_by=katia con split=shared ('pagó' ≠ 'solo de'); taxi payer_only Bruno; helado shared
- FAIL típico: cena nace payer_only / Solo Katia sin que lo digan
- Turno 2: debe editar el Taxi (ref_text), no el último (helado). DB: taxi.split → shared. FAIL: 'Nada que cambiar'

**Dónde tocar:** `llm/client.py (split vs paid_by; expenses[]) · bot/editor.py (resolve ref_text en batch)`

**Bruno:** en Roma ayer: cena 45 euros pagó katia, taxi 12 solo mío, helado 5 _batch 3 ítems_

**Latencia:** dispatch 6.3s · stops 0.0s · due 0.0s · **total 6.4s** (sin Meta send)

**Bot:**

```
✅ *3 gastos guardados* · 📍 Roma

- 🍽️ Cena · EUR 45,0 → USD 49,5 · pagó Katia
- 🚆 Taxi · EUR 12,0 → USD 13,2 · Solo Bruno · pagó Bruno
- 🍽️ Helado · EUR 5,0 → USD 5,5 · pagó Bruno

💰 Total: *USD 68,2*
⚖️ *Bruno* le debe *USD 22,0* por esto
(movement_id=9)
```

<details><summary>DB (últimos)</summary>

```
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 144.00 CHF usd=172.80 desc='Hostel (1/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=b8d92257f9828205
#6 expense 336.00 CHF usd=403.20 desc='Hostel (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=b8d92257f9828205
#7 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#8 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=payer_only paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=1047044633e40848
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
```

</details>

**Bruno:** el taxi en realidad era compartido _edit split taxi_

**Latencia:** dispatch 3.5s · stops 0.0s · due 0.0s · **total 3.5s** (sin Meta send)

**Bot:**

```
✏️ *Editado* · _Taxi_

÷: Solo Bruno → *÷ 50/50*
```

<details><summary>DB (últimos)</summary>

```
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 144.00 CHF usd=172.80 desc='Hostel (1/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=b8d92257f9828205
#6 expense 336.00 CHF usd=403.20 desc='Hostel (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=b8d92257f9828205
#7 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#8 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=1047044633e40848
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
```

</details>

---

## 3 · Day-trip + payer/split + saldo

**Meta:** Sintra (no parada) → Lisboa; pagó Katia + solo ella; pregunta de deuda.

**Mirar (qué corregir si falla):**
- Turno 1: city_name=Lisboa (no 'Sintra' libre); shared; pagó Bruno
- Turno 2: paid_by=katia + split=payer_only (Solo Katia). FAIL: other_only / Solo Bruno
- Turno 3: responder con el paseo recién editado (USD 30,8 a favor de Katia), no pedir ciudad si hay uno solo reciente

**Dónde tocar:** `bot/capture.py (resolve_place) · llm/client.py (new_split relativo al NUEVO paid_by) · bot/qa.py + qa/tools.py`

**Bruno:** paseo a sintra 28 euros _daytrip → Lisboa_

**Latencia:** dispatch 3.2s · stops 0.0s · due 0.0s · **total 3.2s** (sin Meta send)

**Bot:**

```
✅ *Gasto guardado*

🎟️ Actividades — Paseo
💰 EUR 28,0 → USD 30,8
📍 Lisboa
👤 Pagó Bruno · ÷ 50/50
⚖️ *Katia* le debe *USD 15,4* por esto
(movement_id=10)
```

<details><summary>DB (últimos)</summary>

```
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 144.00 CHF usd=172.80 desc='Hostel (1/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=b8d92257f9828205
#6 expense 336.00 CHF usd=403.20 desc='Hostel (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=b8d92257f9828205
#7 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#8 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=1047044633e40848
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=shared paid_by=bruno cat=Actividades pay=None status=confirmed batch=None
```

</details>

**Bruno:** en realidad lo pagó katia y es solo de ella _edit paid_by + split_

**Latencia:** dispatch 3.2s · stops 0.0s · due 0.0s · **total 3.2s** (sin Meta send)

**Bot:**

```
✏️ *Editado* · _Paseo_

👤: Pagó Bruno → *Pagó Katia*
÷: ÷ 50/50 → *Solo Katia*
```

<details><summary>DB (últimos)</summary>

```
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 144.00 CHF usd=172.80 desc='Hostel (1/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=b8d92257f9828205
#6 expense 336.00 CHF usd=403.20 desc='Hostel (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=b8d92257f9828205
#7 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#8 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=1047044633e40848
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
```

</details>

**Bruno:** ¿cuánto le debo a katia por ese paseo? _Q&A_

**Latencia:** dispatch 9.8s · stops 0.0s · due 0.0s · **total 9.9s** (sin Meta send)

**Bot:**

```
El Paseo del *19/07* fue *USD 30,8* y está marcado *solo katia*, así que no le debés nada: 💸 *USD 0,0*.
```

<details><summary>DB (últimos)</summary>

```
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 144.00 CHF usd=172.80 desc='Hostel (1/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=b8d92257f9828205
#6 expense 336.00 CHF usd=403.20 desc='Hostel (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=b8d92257f9828205
#7 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#8 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=1047044633e40848
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
```

</details>

---

## 4 · Pago futuro + ¿entra al saldo? + traer a hoy

**Meta:** payment_date futura → pending; preguntar si cuenta; mover a hoy.

**Mirar (qué corregir si falla):**
- Turno 1: city=Paris; status=pending; pay=2026-09-15; split=shared (NO inventar Solo Katia)
- Turno 2: respuesta debe decir que NO entra al balance todavía (pending excluido de compute_balance). FAIL: 'sí, ya está incluido'
- Turno 3: pay→hoy, status→confirmed; city debe seguir Paris. FAIL: arrastra ciudad a Lisboa

**Dónde tocar:** `llm/client.py (no inventar split) · bot/qa.py / qa/tools get_balance · bot/editor.py (edit date sin re-resolve city)`

**Bruno:** entrada al louvre 44 eur, se paga el 15 de septiembre en paris _pending futuro_

**Latencia:** dispatch 5.1s · stops 0.0s · due 0.0s · **total 5.1s** (sin Meta send)

**Bot:**

```
✅ *Gasto guardado*

🎟️ Actividades — Entrada al Louvre
💰 EUR 44,0 → USD 48,4
📍 Paris
👤 Pagó Bruno · ÷ 50/50
📅 Se paga el 15/09 · TC provisorio
(movement_id=11)
```

<details><summary>DB (últimos)</summary>

```
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 144.00 CHF usd=172.80 desc='Hostel (1/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=b8d92257f9828205
#6 expense 336.00 CHF usd=403.20 desc='Hostel (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=b8d92257f9828205
#7 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#8 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=1047044633e40848
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-09-15 status=pending batch=None
```

</details>

**Bruno:** eso del louvre, ¿ya entra en el saldo o todavía no? _Q&A pending vs balance_

**Latencia:** dispatch 9.3s · stops 0.0s · due 0.0s · **total 9.3s** (sin Meta send)

**Bot:**

```
No — el Louvre está *PENDIENTE* y se paga el *15/09* 📅, así que todavía no entra al saldo. El importe pendiente: *USD 48,4*.  
💸 Saldo actual: *katia le debe USD 10,5 a bruno*.
```

<details><summary>DB (últimos)</summary>

```
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 144.00 CHF usd=172.80 desc='Hostel (1/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=b8d92257f9828205
#6 expense 336.00 CHF usd=403.20 desc='Hostel (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=b8d92257f9828205
#7 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#8 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=1047044633e40848
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-09-15 status=pending batch=None
```

</details>

**Bruno:** ok, poné que se paga hoy _edit payment_date_

**Latencia:** dispatch 3.4s · stops 0.0s · due 0.0s · **total 3.4s** (sin Meta send)

**Bot:**

```
✏️ *Editado* · _Entrada al Louvre_

📅: 15/09 → *20/08*
```

<details><summary>DB (últimos)</summary>

```
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 144.00 CHF usd=172.80 desc='Hostel (1/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=b8d92257f9828205
#6 expense 336.00 CHF usd=403.20 desc='Hostel (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=b8d92257f9828205
#7 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#8 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=1047044633e40848
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
```

</details>

---

## 5 · Corrección corta post-carga

**Meta:** last_expense → edit por mensaje sin monto propio.

**Mirar (qué corregir si falla):**
- Turno 1: city=Pititas; owner default puede ya ser Solo Katia — anotar estado real en DB
- Turno 2: intent=edit (ref_last), NO expense nuevo; un solo movement_id. Si ya era payer_only, 'Nada que cambiar' es OK; si era shared → payer_only
- No debe aparecer un 2.º tren

**Dónde tocar:** `llm/client.py (regla Último gasto) · bot/editor.py · stops_local / capture.owner_split`

**Katia:** tren 39 usd en pititas _carga_

**Latencia:** dispatch 3.2s · stops 0.0s · due 0.0s · **total 3.2s** (sin Meta send)

**Bot:**

```
✅ *Gasto guardado*

🚆 Transporte — Tren
💰 USD 39,0
📍 Pititas
👤 Pagó Katia · Solo Katia
(movement_id=12)
```

<details><summary>DB (últimos)</summary>

```
#5 expense 144.00 CHF usd=172.80 desc='Hostel (1/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=b8d92257f9828205
#6 expense 336.00 CHF usd=403.20 desc='Hostel (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=b8d92257f9828205
#7 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#8 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=1047044633e40848
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
```

</details>

**Katia:** no, contalo solo para katia _edit split corto_

**Latencia:** dispatch 3.8s · stops 0.0s · due 0.0s · **total 3.8s** (sin Meta send)

**Bot:**

```
Nada que cambiar: ya estaba así. 👌
```

<details><summary>DB (últimos)</summary>

```
#5 expense 144.00 CHF usd=172.80 desc='Hostel (1/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=b8d92257f9828205
#6 expense 336.00 CHF usd=403.20 desc='Hostel (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=b8d92257f9828205
#7 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#8 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=1047044633e40848
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
```

</details>

---

## 6 · Delete por texto + confirmación

**Meta:** intent delete del parser → botones; nunca hard-delete.

**Mirar (qué corregir si falla):**
- Turno 1: Museo en Roma; paid_by=katia; split=payer_only (Solo Katia). FAIL: Solo Bruno / other_only
- Turno 2: botones de confirm; el resumen debe ser el museo, NO otro gasto (FAIL visto: ofreció 'Cena Lisboa')
- Turno 3: tras tap, el museo desaparece de la DB; no hard-delete en el turno 2

**Dónde tocar:** `bot/editor.py (resolve ref_text delete) · bot/interactive.py · llm/client.py (solo de ella → payer_only si paga ella)`

**Bruno:** museo vaticano 25 eur en roma, solo de katia, pagó katia _carga_

**Latencia:** dispatch 3.5s · stops 0.0s · due 0.0s · **total 3.5s** (sin Meta send)

**Bot:**

```
✅ *Gasto guardado*

🎟️ Actividades — Museo Vaticano
💰 EUR 25,0 → USD 27,5
📍 Roma
👤 Pagó Katia · Solo Katia
(movement_id=13)
```

<details><summary>DB (últimos)</summary>

```
#6 expense 336.00 CHF usd=403.20 desc='Hostel (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=b8d92257f9828205
#7 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#8 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=1047044633e40848
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#13 expense 25.00 EUR usd=27.50 desc='Museo Vaticano' city=Roma split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
```

</details>

**Bruno:** borrá el museo _delete NL_

**Latencia:** dispatch 4.1s · stops 0.0s · due 0.0s · **total 4.1s** (sin Meta send)

**Bot:**

```
⚠️ ¿Borrar este movimiento? Es irreversible.
Museo Vaticano · EUR 25,0 · 19/07 · Roma · Pagó Katia
[botones]
  · Borrar 🗑️  (`del_confirm:Vy-vngy6DFYt_8zjhIgvL9rJ`)
  · Cancelar  (`del_cancel:0`)
```

<details><summary>DB (últimos)</summary>

```
#6 expense 336.00 CHF usd=403.20 desc='Hostel (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=b8d92257f9828205
#7 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#8 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=1047044633e40848
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#13 expense 25.00 EUR usd=27.50 desc='Museo Vaticano' city=Roma split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
```

</details>

**Bruno:** [tap] `del_confirm:Vy-vngy6DFYt_8zjhIgvL9rJ` _confirmar_

**Latencia:** dispatch 0.0s · stops 0.0s · due 0.0s · **total 0.0s** (sin Meta send)

**Bot:**

```
🗑️ *Borrado*

Museo Vaticano · EUR 25,0 · 19/07 · Roma · Pagó Katia
```

<details><summary>DB (últimos)</summary>

```
#5 expense 144.00 CHF usd=172.80 desc='Hostel (1/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=b8d92257f9828205
#6 expense 336.00 CHF usd=403.20 desc='Hostel (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=b8d92257f9828205
#7 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#8 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=1047044633e40848
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
```

</details>

---

## 7 · Settlement cruzado + ¿quién debe?

**Meta:** Bruno salda con 'le pasé…'; Katia pregunta el neto.

**Mirar (qué corregir si falla):**
- Turno 1: type=settlement; Bruno→Katia; amount=80 USD; no crear expense de hotel
- Turno 2: desde wa_id de Katia, get_balance coherente post-settlement; no invertir deudor

**Dónde tocar:** `bot/capture.py (settlement) · balance.py · bot/qa.py`

**Bruno:** le pasé 80 usd a katia por lo del hotel de paris _settlement_

**Latencia:** dispatch 3.9s · stops 0.0s · due 0.0s · **total 3.9s** (sin Meta send)

**Bot:**

```
💸 *Pago de saldo*

*Bruno* → *Katia*
💰 USD 80,0
(movement_id=13)
```

<details><summary>DB (últimos)</summary>

```
#6 expense 336.00 CHF usd=403.20 desc='Hostel (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=b8d92257f9828205
#7 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#8 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=1047044633e40848
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#13 settlement 80.00 USD usd=80.00 desc='Por lo del hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
```

</details>

**Katia:** che y ahora quién debe plata? _Q&A balance_

**Latencia:** dispatch 8.5s · stops 0.0s · due 0.0s · **total 8.5s** (sin Meta send)

**Bot:**

```
💸 *Katia le debe USD 114,7 a bruno.*  
⚠️ Además hay 1 gasto pendiente por *USD 403,2* (no cuenta en el saldo hasta su fecha: 03/09).
```

<details><summary>DB (últimos)</summary>

```
#6 expense 336.00 CHF usd=403.20 desc='Hostel (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=b8d92257f9828205
#7 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#8 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=1047044633e40848
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#13 settlement 80.00 USD usd=80.00 desc='Por lo del hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
```

</details>

---

## 8 · Batch + borrar (fast path) + confirmar los N

**Meta:** Multi-gasto + comando borrar sin LLM + del_confirm del batch.

**Mirar (qué corregir si falla):**
- Turno 1: 3 gastos mismo batch_key, city=Paris
- Turno 2: fast path (dispatch ~0s LLM); botones 'Borrar los 3' + 'Solo el último' + Cancelar
- Turno 3: desaparecen los 3 del batch, no solo el último

**Dónde tocar:** `bot/dispatcher.py (_handle_delete_command) · bot/interactive.py`

**Bruno:** en paris: metro 4 eur, croissant 3, agua 2 _batch 3_

**Latencia:** dispatch 6.8s · stops 0.0s · due 0.0s · **total 6.8s** (sin Meta send)

**Bot:**

```
✅ *3 gastos guardados* · 📍 Paris · 👤 Pagó Bruno

- 🚆 Metro · EUR 4,0 → USD 4,4
- 🍽️ Croissant · EUR 3,0 → USD 3,3
- 🍽️ Agua · EUR 2,0 → USD 2,2

💰 Total: *USD 9,9*
⚖️ *Katia* le debe *USD 5,0* por esto
(movement_id=16)
```

<details><summary>DB (últimos)</summary>

```
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#13 settlement 80.00 USD usd=80.00 desc='Por lo del hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
#14 expense 4.00 EUR usd=4.40 desc='Metro' city=Paris split=shared paid_by=bruno cat=Transporte pay=None status=confirmed batch=cb07427bbe738970
#15 expense 3.00 EUR usd=3.30 desc='Croissant' city=Paris split=shared paid_by=bruno cat=Comida pay=None status=confirmed batch=cb07427bbe738970
#16 expense 2.00 EUR usd=2.20 desc='Agua' city=Paris split=shared paid_by=bruno cat=Comida pay=None status=confirmed batch=cb07427bbe738970
```

</details>

**Bruno:** borrar _fast path_

**Latencia:** dispatch 0.0s · stops 0.0s · due 0.0s · **total 0.0s** (sin Meta send)

**Bot:**

```
⚠️ Eso entró como *3 gastos juntos*. ¿Borrar? Es irreversible.
Metro · EUR 4,0 · 19/07 · Paris · Pagó Bruno
Croissant · EUR 3,0 · 19/07 · Paris · Pagó Bruno
Agua · EUR 2,0 · 19/07 · Paris · Pagó Bruno
[botones]
  · Borrar los 3 🗑️  (`del_confirm:QSWh3DKvgCE3xCqeIyKWhJuI`)
  · Solo el último  (`del_confirm:KZX0sMG_VstPIjJqu9C8PzVo`)
  · Cancelar  (`del_cancel:0`)
```

<details><summary>DB (últimos)</summary>

```
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#13 settlement 80.00 USD usd=80.00 desc='Por lo del hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
#14 expense 4.00 EUR usd=4.40 desc='Metro' city=Paris split=shared paid_by=bruno cat=Transporte pay=None status=confirmed batch=cb07427bbe738970
#15 expense 3.00 EUR usd=3.30 desc='Croissant' city=Paris split=shared paid_by=bruno cat=Comida pay=None status=confirmed batch=cb07427bbe738970
#16 expense 2.00 EUR usd=2.20 desc='Agua' city=Paris split=shared paid_by=bruno cat=Comida pay=None status=confirmed batch=cb07427bbe738970
```

</details>

**Bruno:** [tap] `del_confirm:QSWh3DKvgCE3xCqeIyKWhJuI` _confirmar batch_

**Latencia:** dispatch 0.0s · stops 0.0s · due 0.0s · **total 0.0s** (sin Meta send)

**Bot:**

```
🗑️ *Borrado* · 3 movimientos

Metro · EUR 4,0 · 19/07 · Paris · Pagó Bruno
Croissant · EUR 3,0 · 19/07 · Paris · Pagó Bruno
Agua · EUR 2,0 · 19/07 · Paris · Pagó Bruno
```

<details><summary>DB (últimos)</summary>

```
#6 expense 336.00 CHF usd=403.20 desc='Hostel (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=b8d92257f9828205
#7 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#8 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=1047044633e40848
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#13 settlement 80.00 USD usd=80.00 desc='Por lo del hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
```

</details>

---

## 9 · Stop local / owner split (Pititas)

**Meta:** Default split por owner_username; después forzar shared.

**Mirar (qué corregir si falla):**
- Turno 1: city=Pititas; Bruno puede cargar ahí; split default Solo Katia (owner). Relativo a paid_by=bruno → other_only en DB / label Solo Katia
- Turno 2: edit → shared; un solo movimiento

**Dónde tocar:** `bot/capture.py (owner_split) · stops_local.py · bot/editor.py`

**Bruno:** super 22 eur en pititas _owner default_

**Latencia:** dispatch 3.5s · stops 0.0s · due 0.0s · **total 3.5s** (sin Meta send)

**Bot:**

```
✅ *Gasto guardado*

🛒 Supermercado — Super
💰 EUR 22,0 → USD 24,2
📍 Pititas
👤 Pagó Bruno · Solo Katia
⚖️ *Katia* le debe *USD 24,2* por esto
(movement_id=14)
```

<details><summary>DB (últimos)</summary>

```
#7 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#8 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=1047044633e40848
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#13 settlement 80.00 USD usd=80.00 desc='Por lo del hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
#14 expense 22.00 EUR usd=24.20 desc='Super' city=Pititas split=other_only paid_by=bruno cat=Supermercado pay=None status=confirmed batch=None
```

</details>

**Bruno:** en realidad era compartido _edit → shared_

**Latencia:** dispatch 3.3s · stops 0.0s · due 0.0s · **total 3.3s** (sin Meta send)

**Bot:**

```
✏️ *Editado* · _Super_

÷: Solo Katia → *÷ 50/50*
```

<details><summary>DB (últimos)</summary>

```
#7 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#8 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=1047044633e40848
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#13 settlement 80.00 USD usd=80.00 desc='Por lo del hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
#14 expense 22.00 EUR usd=24.20 desc='Super' city=Pititas split=shared paid_by=bruno cat=Supermercado pay=None status=confirmed batch=None
```

</details>

---

## 10 · Moneda explícita ≠ moneda ciudad + edit

**Meta:** USD dicho en Lisboa (EUR); después corregir a euros.

**Mirar (qué corregir si falla):**
- Turno 1: currency=USD (no forzar EUR de Lisboa); amount=40; city=Lisboa
- Turno 2: edit currency→EUR + recalc amount_usd; no crear 2.ª cena

**Dónde tocar:** `llm/client.py (currency explícita) · bot/editor.py (new_currency + FX)`

**Bruno:** cena 40 usd en lisboa _USD explícito_

**Latencia:** dispatch 3.5s · stops 0.0s · due 0.0s · **total 3.5s** (sin Meta send)

**Bot:**

```
✅ *Gasto guardado*

🍽️ Comida — Cena
💰 USD 40,0
📍 Lisboa
👤 Pagó Bruno · ÷ 50/50
📅 Pagado el 20/08
⚖️ *Katia* le debe *USD 20,0* por esto
(movement_id=15)
```

<details><summary>DB (últimos)</summary>

```
#8 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=1047044633e40848
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#13 settlement 80.00 USD usd=80.00 desc='Por lo del hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
#14 expense 22.00 EUR usd=24.20 desc='Super' city=Pititas split=shared paid_by=bruno cat=Supermercado pay=None status=confirmed batch=None
#15 expense 40.00 USD usd=40.00 desc='Cena' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-20 status=confirmed batch=None
```

</details>

**Bruno:** era en euros, no dólares _edit currency_

**Latencia:** dispatch 4.0s · stops 0.0s · due 0.0s · **total 4.0s** (sin Meta send)

**Bot:**

```
✏️ *Editado* · _Cena_

💱: USD → *EUR*
💵: USD 40,0 → *USD 44,0*
```

<details><summary>DB (últimos)</summary>

```
#8 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=1047044633e40848
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#13 settlement 80.00 USD usd=80.00 desc='Por lo del hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
#14 expense 22.00 EUR usd=24.20 desc='Super' city=Pititas split=shared paid_by=bruno cat=Supermercado pay=None status=confirmed batch=None
#15 expense 40.00 EUR usd=44.00 desc='Cena' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-20 status=confirmed batch=None
```

</details>

---

## 11 · Categoría ambigua + cat_pick

**Meta:** Descripción vaga → botones de categoría; confirmar con tap.

**Mirar (qué corregir si falla):**
- Turno 1: confidence baja → botones cat_pick (2–3). FAIL si guarda directo (p.ej. Compras) sin preguntar
- Turno 2: tras tap, gasto confirmado con esa category_id. Si el runner omite el tap, el turno 1 falló el umbral

**Dónde tocar:** `bot/capture.py (candidates / pending) · bot/interactive.py (cat_pick)`

**Bruno:** me cobraron 35 eur en lisboa por aquello _categoría ambigua_

**Latencia:** dispatch 3.9s · stops 0.0s · due 0.0s · **total 3.9s** (sin Meta send)

**Bot:**

```
🤔 ¿Qué categoría? _Cobro por aquello_ · *EUR 35,0 → USD 38,5*
[botones]
  · 📦 Otros  (`cat_pick:NhnhYFK9lKYCy-c9QWTqfC2I|10`)
  · 🍽️ Comida  (`cat_pick:NhnhYFK9lKYCy-c9QWTqfC2I|2`)
  · 🎟️ Actividades  (`cat_pick:NhnhYFK9lKYCy-c9QWTqfC2I|5`)
```

<details><summary>DB (últimos)</summary>

```
#8 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=1047044633e40848
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#13 settlement 80.00 USD usd=80.00 desc='Por lo del hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
#14 expense 22.00 EUR usd=24.20 desc='Super' city=Pititas split=shared paid_by=bruno cat=Supermercado pay=None status=confirmed batch=None
#15 expense 40.00 EUR usd=44.00 desc='Cena' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-20 status=confirmed batch=None
```

</details>

**Bruno:** [tap] `cat_pick:NhnhYFK9lKYCy-c9QWTqfC2I|10` _tap 1.er candidato_

**Latencia:** dispatch 0.0s · stops 0.0s · due 0.0s · **total 0.0s** (sin Meta send)

**Bot:**

```
✅ *Gasto guardado*

📦 Otros — Cobro por aquello
💰 EUR 35,0 → USD 38,5
📍 Lisboa
👤 Pagó Bruno · ÷ 50/50
📅 Pagado el 20/08
⚖️ *Katia* le debe *USD 19,3* por esto
(movement_id=16)
```

<details><summary>DB (últimos)</summary>

```
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#13 settlement 80.00 USD usd=80.00 desc='Por lo del hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
#14 expense 22.00 EUR usd=24.20 desc='Super' city=Pititas split=shared paid_by=bruno cat=Supermercado pay=None status=confirmed batch=None
#15 expense 40.00 EUR usd=44.00 desc='Cena' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-20 status=confirmed batch=None
#16 expense 35.00 EUR usd=38.50 desc='Cobro por aquello' city=Lisboa split=shared paid_by=bruno cat=Otros pay=2026-08-20 status=confirmed batch=None
```

</details>

---

## 12 · Q&A follow-up elíptico

**Meta:** Historial fresco: reusar intención cambiando ciudad/attribution.

**Mirar (qué corregir si falla):**
- Turno 1: total comida Paris desde tools (seed: Cena Paris USD 88 half-share context)
- Turno 2: reusa categoría Comida + ciudad Roma; no preguntar '¿comida o total?'
- Turno 3: attribution=paid para Bruno en Roma (no share)

**Dónde tocar:** `bot/qa.py (historial) · qa/tools.py (attribution)`

**Bruno:** ¿cuánto gastamos en comida en paris? _Q&A_

**Latencia:** dispatch 11.0s · stops 0.0s · due 0.0s · **total 11.0s** (sin Meta send)

**Bot:**

```
*Paris* 🇫🇷  
💸 Total comida: *USD 88,0* (1 gasto)
```

<details><summary>DB (últimos)</summary>

```
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#13 settlement 80.00 USD usd=80.00 desc='Por lo del hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
#14 expense 22.00 EUR usd=24.20 desc='Super' city=Pititas split=shared paid_by=bruno cat=Supermercado pay=None status=confirmed batch=None
#15 expense 40.00 EUR usd=44.00 desc='Cena' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-20 status=confirmed batch=None
#16 expense 35.00 EUR usd=38.50 desc='Cobro por aquello' city=Lisboa split=shared paid_by=bruno cat=Otros pay=2026-08-20 status=confirmed batch=None
```

</details>

**Bruno:** ¿y en roma? _follow-up ciudad_

**Latencia:** dispatch 15.2s · stops 0.0s · due 0.0s · **total 15.2s** (sin Meta send)

**Bot:**

```
*Roma* 🇮🇹  
💸 Total comida: *USD 110,0* (3 gastos)
```

<details><summary>DB (últimos)</summary>

```
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#13 settlement 80.00 USD usd=80.00 desc='Por lo del hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
#14 expense 22.00 EUR usd=24.20 desc='Super' city=Pititas split=shared paid_by=bruno cat=Supermercado pay=None status=confirmed batch=None
#15 expense 40.00 EUR usd=44.00 desc='Cena' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-20 status=confirmed batch=None
#16 expense 35.00 EUR usd=38.50 desc='Cobro por aquello' city=Lisboa split=shared paid_by=bruno cat=Otros pay=2026-08-20 status=confirmed batch=None
```

</details>

**Bruno:** ¿y cuánto puse yo de bolsillo ahí? _attribution paid_

**Latencia:** dispatch 10.8s · stops 0.0s · due 0.0s · **total 10.8s** (sin Meta send)

**Bot:**

```
💸 *USD 240,6* — eso es lo que *pusiste vos de bolsillo* en los últimos movimientos que listaste.
```

<details><summary>DB (últimos)</summary>

```
#9 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=1047044633e40848
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#13 settlement 80.00 USD usd=80.00 desc='Por lo del hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
#14 expense 22.00 EUR usd=24.20 desc='Super' city=Pititas split=shared paid_by=bruno cat=Supermercado pay=None status=confirmed batch=None
#15 expense 40.00 EUR usd=44.00 desc='Cena' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-20 status=confirmed batch=None
#16 expense 35.00 EUR usd=38.50 desc='Cobro por aquello' city=Lisboa split=shared paid_by=bruno cat=Otros pay=2026-08-20 status=confirmed batch=None
```

</details>

---

## 13 · General / pre-viaje sin ciudad

**Meta:** Fecha fuera de itinerario → city null; Q&A lo admite.

**Mirar (qué corregir si falla):**
- Turno 1: city_name=null / sin stop; split=payer_only; currency=USD; pay≈2026-07-01
- Turno 2: admitir General / sin ciudad; NO inventar Roma/Londres

**Dónde tocar:** `bot/capture.py (resolve_place fuera de rango) · bot/qa.py`

**Bruno:** seguro de viaje 320 usd el 1 de julio, solo mío _fuera de rango_

**Latencia:** dispatch 3.4s · stops 0.0s · due 0.0s · **total 3.4s** (sin Meta send)

**Bot:**

```
✅ *Gasto guardado*

📦 Otros — Seguro de viaje
💰 USD 320,0
📍 Sin ciudad
👤 Pagó Bruno · Solo Bruno
📅 Pagado el 01/07
(movement_id=17)
```

<details><summary>DB (últimos)</summary>

```
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#13 settlement 80.00 USD usd=80.00 desc='Por lo del hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
#14 expense 22.00 EUR usd=24.20 desc='Super' city=Pititas split=shared paid_by=bruno cat=Supermercado pay=None status=confirmed batch=None
#15 expense 40.00 EUR usd=44.00 desc='Cena' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-20 status=confirmed batch=None
#16 expense 35.00 EUR usd=38.50 desc='Cobro por aquello' city=Lisboa split=shared paid_by=bruno cat=Otros pay=2026-08-20 status=confirmed batch=None
#17 expense 320.00 USD usd=320.00 desc='Seguro de viaje' city=None split=payer_only paid_by=bruno cat=Otros pay=2026-07-01 status=confirmed batch=None
```

</details>

**Bruno:** ¿en qué ciudad quedó el seguro? _Q&A_

**Latencia:** dispatch 9.8s · stops 0.0s · due 0.0s · **total 9.8s** (sin Meta send)

**Bot:**

```
Quedó *sin ciudad asignada*.  
Hoy la parada activa es *Lisboa* 📍. Si querés que lo mueva a Lisboa decímelo y lo edito.
```

<details><summary>DB (últimos)</summary>

```
#10 expense 28.00 EUR usd=30.80 desc='Paseo' city=Lisboa split=payer_only paid_by=katia cat=Actividades pay=None status=confirmed batch=None
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#13 settlement 80.00 USD usd=80.00 desc='Por lo del hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
#14 expense 22.00 EUR usd=24.20 desc='Super' city=Pititas split=shared paid_by=bruno cat=Supermercado pay=None status=confirmed batch=None
#15 expense 40.00 EUR usd=44.00 desc='Cena' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-20 status=confirmed batch=None
#16 expense 35.00 EUR usd=38.50 desc='Cobro por aquello' city=Lisboa split=shared paid_by=bruno cat=Otros pay=2026-08-20 status=confirmed batch=None
#17 expense 320.00 USD usd=320.00 desc='Seguro de viaje' city=None split=payer_only paid_by=bruno cat=Otros pay=2026-07-01 status=confirmed batch=None
```

</details>

---

## 14 · Settlement 'me pasó' desde Katia

**Meta:** Dirección del pago desde el otro lado + saldo.

**Mirar (qué corregir si falla):**
- Turno 1: settlement Bruno→Katia (paid_by=bruno); no expense; no invertir
- Turno 2: saldo fast path (~0s dispatch LLM) refleja el neto post-pago

**Dónde tocar:** `llm/client.py (settlement dirección) · bot/capture.py · bot/quick.py`

**Katia:** bruno me pasó 50 usd _settlement_

**Latencia:** dispatch 4.0s · stops 0.0s · due 0.0s · **total 4.0s** (sin Meta send)

**Bot:**

```
💸 *Pago de saldo*

*Bruno* → *Katia*
💰 USD 50,0
(movement_id=18)
```

<details><summary>DB (últimos)</summary>

```
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#13 settlement 80.00 USD usd=80.00 desc='Por lo del hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
#14 expense 22.00 EUR usd=24.20 desc='Super' city=Pititas split=shared paid_by=bruno cat=Supermercado pay=None status=confirmed batch=None
#15 expense 40.00 EUR usd=44.00 desc='Cena' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-20 status=confirmed batch=None
#16 expense 35.00 EUR usd=38.50 desc='Cobro por aquello' city=Lisboa split=shared paid_by=bruno cat=Otros pay=2026-08-20 status=confirmed batch=None
#17 expense 320.00 USD usd=320.00 desc='Seguro de viaje' city=None split=payer_only paid_by=bruno cat=Otros pay=2026-07-01 status=confirmed batch=None
#18 settlement 50.00 USD usd=50.00 desc='Transferencia de Bruno' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
```

</details>

**Bruno:** saldo _fast path_

**Latencia:** dispatch 0.0s · stops 0.0s · due 0.0s · **total 0.0s** (sin Meta send)

**Bot:**

```
⚖️ *Balance*

*Katia* le debe *USD 218,1* a *Bruno*
```

<details><summary>DB (últimos)</summary>

```
#11 expense 44.00 EUR usd=48.40 desc='Entrada al Louvre' city=Paris split=shared paid_by=bruno cat=Actividades pay=2026-08-20 status=confirmed batch=None
#12 expense 39.00 USD usd=39.00 desc='Tren' city=Pititas split=payer_only paid_by=katia cat=Transporte pay=None status=confirmed batch=None
#13 settlement 80.00 USD usd=80.00 desc='Por lo del hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
#14 expense 22.00 EUR usd=24.20 desc='Super' city=Pititas split=shared paid_by=bruno cat=Supermercado pay=None status=confirmed batch=None
#15 expense 40.00 EUR usd=44.00 desc='Cena' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-20 status=confirmed batch=None
#16 expense 35.00 EUR usd=38.50 desc='Cobro por aquello' city=Lisboa split=shared paid_by=bruno cat=Otros pay=2026-08-20 status=confirmed batch=None
#17 expense 320.00 USD usd=320.00 desc='Seguro de viaje' city=None split=payer_only paid_by=bruno cat=Otros pay=2026-07-01 status=confirmed batch=None
#18 settlement 50.00 USD usd=50.00 desc='Transferencia de Bruno' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
```

</details>

---

## Resumen de latencia

| Escenario | Turno | Quién | Nota | dispatch_s | stops_s | due_s | total_s |
|---|---:|---|---|---:|---:|---:|---:|
| 1 · Cuotas + corrección de total | 1 | bruno | cuotas | 5.2 | 0.0 | 0.0 | 5.2 |
| 1 · Cuotas + corrección de total | 2 | bruno | edit monto del batch | 3.0 | 0.0 | 0.0 | 3.0 |
| 2 · Multi-gasto mezclado + fix de split | 1 | bruno | batch 3 ítems | 6.3 | 0.0 | 0.0 | 6.4 |
| 2 · Multi-gasto mezclado + fix de split | 2 | bruno | edit split taxi | 3.5 | 0.0 | 0.0 | 3.5 |
| 3 · Day-trip + payer/split + saldo | 1 | bruno | daytrip → Lisboa | 3.2 | 0.0 | 0.0 | 3.2 |
| 3 · Day-trip + payer/split + saldo | 2 | bruno | edit paid_by + split | 3.2 | 0.0 | 0.0 | 3.2 |
| 3 · Day-trip + payer/split + saldo | 3 | bruno | Q&A | 9.8 | 0.0 | 0.0 | 9.9 |
| 4 · Pago futuro + ¿entra al saldo? + traer a hoy | 1 | bruno | pending futuro | 5.1 | 0.0 | 0.0 | 5.1 |
| 4 · Pago futuro + ¿entra al saldo? + traer a hoy | 2 | bruno | Q&A pending vs balance | 9.3 | 0.0 | 0.0 | 9.3 |
| 4 · Pago futuro + ¿entra al saldo? + traer a hoy | 3 | bruno | edit payment_date | 3.4 | 0.0 | 0.0 | 3.4 |
| 5 · Corrección corta post-carga | 1 | katia | carga | 3.2 | 0.0 | 0.0 | 3.2 |
| 5 · Corrección corta post-carga | 2 | katia | edit split corto | 3.8 | 0.0 | 0.0 | 3.8 |
| 6 · Delete por texto + confirmación | 1 | bruno | carga | 3.5 | 0.0 | 0.0 | 3.5 |
| 6 · Delete por texto + confirmación | 2 | bruno | delete NL | 4.1 | 0.0 | 0.0 | 4.1 |
| 6 · Delete por texto + confirmación | 3 | bruno | confirmar | 0.0 | 0.0 | 0.0 | 0.0 |
| 7 · Settlement cruzado + ¿quién debe? | 1 | bruno | settlement | 3.9 | 0.0 | 0.0 | 3.9 |
| 7 · Settlement cruzado + ¿quién debe? | 2 | katia | Q&A balance | 8.5 | 0.0 | 0.0 | 8.5 |
| 8 · Batch + borrar (fast path) + confirmar los N | 1 | bruno | batch 3 | 6.8 | 0.0 | 0.0 | 6.8 |
| 8 · Batch + borrar (fast path) + confirmar los N | 2 | bruno | fast path | 0.0 | 0.0 | 0.0 | 0.0 |
| 8 · Batch + borrar (fast path) + confirmar los N | 3 | bruno | confirmar batch | 0.0 | 0.0 | 0.0 | 0.0 |
| 9 · Stop local / owner split (Pititas) | 1 | bruno | owner default | 3.5 | 0.0 | 0.0 | 3.5 |
| 9 · Stop local / owner split (Pititas) | 2 | bruno | edit → shared | 3.3 | 0.0 | 0.0 | 3.3 |
| 10 · Moneda explícita ≠ moneda ciudad + edit | 1 | bruno | USD explícito | 3.5 | 0.0 | 0.0 | 3.5 |
| 10 · Moneda explícita ≠ moneda ciudad + edit | 2 | bruno | edit currency | 4.0 | 0.0 | 0.0 | 4.0 |
| 11 · Categoría ambigua + cat_pick | 1 | bruno | categoría ambigua | 3.9 | 0.0 | 0.0 | 3.9 |
| 11 · Categoría ambigua + cat_pick | 2 | bruno | tap 1.er candidato | 0.0 | 0.0 | 0.0 | 0.0 |
| 12 · Q&A follow-up elíptico | 1 | bruno | Q&A | 11.0 | 0.0 | 0.0 | 11.0 |
| 12 · Q&A follow-up elíptico | 2 | bruno | follow-up ciudad | 15.2 | 0.0 | 0.0 | 15.2 |
| 12 · Q&A follow-up elíptico | 3 | bruno | attribution paid | 10.8 | 0.0 | 0.0 | 10.8 |
| 13 · General / pre-viaje sin ciudad | 1 | bruno | fuera de rango | 3.4 | 0.0 | 0.0 | 3.4 |
| 13 · General / pre-viaje sin ciudad | 2 | bruno | Q&A | 9.8 | 0.0 | 0.0 | 9.8 |
| 14 · Settlement 'me pasó' desde Katia | 1 | katia | settlement | 4.0 | 0.0 | 0.0 | 4.0 |
| 14 · Settlement 'me pasó' desde Katia | 2 | bruno | fast path | 0.0 | 0.0 | 0.0 | 0.0 |

Promedio dispatch **4.8s** · promedio total **4.8s** · más lento: bruno «¿y en roma?» (15.2s)

> En prod, al `total_s` se suman typing/react/send Graph (~0.3–1.5s típico, no medido acá).

---

## Cómo volver a correr

```bash
cd backend
.venv/bin/python scripts/bot_scenario_runner.py          # suite crítica (10)
.venv/bin/python scripts/bot_scenario_runner.py --all    # 14 (10+4)
.venv/bin/python scripts/bot_scenario_runner.py --only 1,4,6
```

Requiere `OPENAI_API_KEY` en `spitwise/.env`. Secuencial; pausas entre turnos.
