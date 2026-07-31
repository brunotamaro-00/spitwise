# Escenarios de charla — última corrida

> **Auto-generado** por `scripts/bot_scenario_runner.py`.
> Cada corrida **borra y reemplaza** este archivo (no acumula historial).
> Catálogo: `SUITE_CRITICAL` (1–10) + `CONVERSATIONS_EXTRA` (11–27) en el script.
> Los **checks** son deterministas (DB / intent / tools): si fallan, el runner sale con exit 1. El texto se evalúa a ojo.

- Corrida: `2026-07-31T11:05:12-03:00`
- Suite: **custom (19)**
- provider=`openai` parser=`gpt-5-mini` chat=`gpt-5-mini`
- Hoy ficticio: `2026-08-20` (parada activa: Lisboa)
- Escenarios corridos: 1, 2, 5, 6, 7, 10, 15, 17, 22, 23, 20, 12, 3, 4, 13, 18, 25, 26, 27 (19 conversaciones)
- Checks: **15 ok** · **4 con fallas** · 0 sin checks
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

**Latencia:** dispatch 6.9s · stops 0.0s · due 0.0s · **total 6.9s** (sin Meta send)

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
#5 expense 129.00 CHF usd=154.80 desc='Hostel Interlaken (1/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=7748b545958b141a
#6 expense 301.00 CHF usd=361.20 desc='Hostel Interlaken (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=7748b545958b141a
```

</details>

**Bruno:** no, el total era 480 no 430 _edit monto del batch_

**Latencia:** dispatch 4.5s · stops 0.0s · due 0.0s · **total 4.5s** (sin Meta send)

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
#5 expense 144.00 CHF usd=172.80 desc='Hostel Interlaken (1/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=7748b545958b141a
#6 expense 336.00 CHF usd=403.20 desc='Hostel Interlaken (2/2)' city=Interlaken split=shared paid_by=bruno cat=Alojamiento pay=2026-09-03 status=pending batch=7748b545958b141a
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

**Latencia:** dispatch 7.9s · stops 0.0s · due 0.0s · **total 7.9s** (sin Meta send)

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
#5 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=dd190ed0153d5290
#6 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=payer_only paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=dd190ed0153d5290
#7 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Cafetería pay=2026-08-19 status=confirmed batch=dd190ed0153d5290
```

</details>

**Bruno:** el taxi en realidad era compartido _edit split taxi_

**Latencia:** dispatch 4.2s · stops 0.0s · due 0.0s · **total 4.2s** (sin Meta send)

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
#5 expense 45.00 EUR usd=49.50 desc='Cena' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-19 status=confirmed batch=dd190ed0153d5290
#6 expense 12.00 EUR usd=13.20 desc='Taxi' city=Roma split=shared paid_by=bruno cat=Transporte pay=2026-08-19 status=confirmed batch=dd190ed0153d5290
#7 expense 5.00 EUR usd=5.50 desc='Helado' city=Roma split=shared paid_by=bruno cat=Cafetería pay=2026-08-19 status=confirmed batch=dd190ed0153d5290
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

**Latencia:** dispatch 4.1s · stops 0.0s · due 0.0s · **total 4.1s** (sin Meta send)

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

**Latencia:** dispatch 4.5s · stops 0.0s · due 0.0s · **total 4.5s** (sin Meta send)

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

**Latencia:** dispatch 4.5s · stops 0.0s · due 0.0s · **total 4.5s** (sin Meta send)

**Traza:** intent=delete · tools=-

**Bot:**

```
⚠️ ¿Borrar este movimiento? Es irreversible.
Museo Vaticano · EUR 25,0 · 31/07 · Roma · Pagó Katia
[botones]
  · Borrar 🗑️  (`del_confirm:ICnKb1ArAtyuO9VfQj9vuiEa`)
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

**Bruno:** [tap] `del_confirm:ICnKb1ArAtyuO9VfQj9vuiEa` _confirmar_

**Latencia:** dispatch 0.0s · stops 0.0s · due 0.0s · **total 0.0s** (sin Meta send)

**Traza:** intent=- · tools=-

**Bot:**

```
🗑️ *Borrado*

Museo Vaticano · EUR 25,0 · 31/07 · Roma · Pagó Katia
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

**Latencia:** dispatch 4.6s · stops 0.0s · due 0.0s · **total 4.6s** (sin Meta send)

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
#5 settlement 80.00 USD usd=80.00 desc='Pago por hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
```

</details>

**Katia:** che y ahora quién debe plata? _Q&A balance_

**Latencia:** dispatch 11.0s · stops 0.0s · due 0.0s · **total 11.0s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=-

**Bot:**

```
Che, ahora *katia le debés a bruno* *USD 19,5* 💸 (solo gastos confirmados).
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 settlement 80.00 USD usd=80.00 desc='Pago por hotel de Paris' city=None split=shared paid_by=bruno cat=None pay=None status=confirmed batch=None
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

**Latencia:** dispatch 4.2s · stops 0.0s · due 0.0s · **total 4.2s** (sin Meta send)

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

**Latencia:** dispatch 4.2s · stops 0.0s · due 0.0s · **total 4.2s** (sin Meta send)

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

**Latencia:** dispatch 10.6s · stops 0.0s · due 0.0s · **total 10.6s** (sin Meta send)

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
#5 expense 34.00 USD usd=34.00 desc='Hostel Fort William (1/2)' city=Fort William split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=ebd0ad0fafa87cc5
#6 expense 134.00 GBP usd=174.20 desc='Hostel Fort William (2/2)' city=Fort William split=shared paid_by=bruno cat=Alojamiento pay=2026-09-12 status=pending batch=ebd0ad0fafa87cc5
#7 expense 94.00 USD usd=94.00 desc='Hostel Portree (1/2)' city=Portree split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=ebd0ad0fafa87cc5
#8 expense 70.00 GBP usd=91.00 desc='Hostel Portree (2/2)' city=Portree split=shared paid_by=bruno cat=Alojamiento pay=2026-09-15 status=pending batch=ebd0ad0fafa87cc5
#9 expense 403.00 EUR usd=443.30 desc='Hostel ClinkMama' city=Lisboa split=shared paid_by=bruno cat=Alojamiento pay=2026-08-25 status=pending batch=ebd0ad0fafa87cc5
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

**Latencia:** dispatch 7.9s · stops 0.0s · due 0.0s · **total 7.9s** (sin Meta send)

**Traza:** intent=trip_question · canal=trip · outcome=ok · tools=list_notes

**Bot:**

```
Anotamos del *Hostel Lisboa*:

- **Check-in 15hs**
- **Código de la puerta: 4421**

(La nota está marcada como *pinned* en nuestras anotaciones.)
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

**Latencia:** dispatch 11.6s · stops 0.0s · due 0.0s · **total 11.6s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=aggregate_expenses

**Bot:**

```
Lisboa 📍
💸 Total: *USD 66,0* · 1 gasto
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

## 22 · Settlement corregido ✅

**Id:** `settlement-corregido` — reproducir con `--only settlement-corregido`

**Meta:** Corregir el monto de un pago de saldo recién cargado, sin crear un gasto.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 2: intent edit sobre el settlement (ref_last) → queda en 50
- FAIL histórico: el 'último movimiento' solo miraba gastos, así que 'no, eran 50' entraba como un GASTO nuevo de 50

**Dónde tocar:** `bot/editor.py (recent_movement include_settlements) · llm/client.py (regla del pago de saldo)`

**Bruno:** le pasé 80 usd a katia _settlement_

**Latencia:** dispatch 5.2s · stops 0.0s · due 0.0s · **total 5.2s** (sin Meta send)

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

**Latencia:** dispatch 4.4s · stops 0.0s · due 0.0s · **total 4.4s** (sin Meta send)

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

**Latencia:** dispatch 7.2s · stops 0.0s · due 0.0s · **total 7.2s** (sin Meta send)

**Traza:** intent=trip_question · canal=trip · outcome=ok · tools=-

**Bot:**

```
Llegamos a *Interlaken el 2026-09-01*.
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

## 20 · Cuotas que no cierran ✅

**Id:** `cuotas-invalidas` — reproducir con `--only cuotas-invalidas`

**Meta:** Etapas declaradas pero imposibles de repartir: aclarar, no guardar mal.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- O entra en etapas con montos que suman 300, o NO entra nada y el bot pide los montos/fechas. FAIL: un gasto único de 300 con fecha de hoy y sin aviso
- El texto tiene que decir qué falta (montos o fechas de cada etapa)

**Dónde tocar:** `bot/capture.py (expand_installments + INSTALLMENTS_UNCLEAR) · llm/client.py`

**Bruno:** hostel praga 300 eur, una parte ahora y el resto después _etapas sin montos ni fechas_

**Latencia:** dispatch 5.2s · stops 0.0s · due 0.0s · **total 5.2s** (sin Meta send)

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

**Latencia:** dispatch 13.6s · stops 0.0s · due 0.0s · **total 13.6s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=aggregate_expenses

**Bot:**

```
📍 *Paris* 🍽️
💸 Total: *USD 88,0* (1 gasto)
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

**Latencia:** dispatch 18.7s · stops 0.0s · due 0.0s · **total 18.7s** (sin Meta send)

**Traza:** intent=trip_question · canal=trip · outcome=ok · tools=search_guides,list_guides

**Bot:**

```
Busqué "Roma" en nuestras guías y **no hay nada sobre Roma** en los docs.  
Las guías disponibles son: **Lisboa** (docs: Actividades, Transporte).  
Si querés que revise algo concreto —por ejemplo alojamientos o actividades— decime qué querés buscar y lo intento en nuestras guías.
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

**Latencia:** dispatch 12.7s · stops 0.0s · due 0.0s · **total 12.7s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=aggregate_expenses

**Bot:**

```
📍 *Paris* 🍽️
💸 Pusiste de bolsillo *USD 88,0* (1 gasto).
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

**Latencia:** dispatch 4.2s · stops 0.0s · due 0.0s · **total 4.2s** (sin Meta send)

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

**Latencia:** dispatch 4.6s · stops 0.0s · due 0.0s · **total 4.6s** (sin Meta send)

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

**Latencia:** dispatch 11.9s · stops 0.0s · due 0.0s · **total 11.9s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=-

**Bot:**

```
No le debés nada: el gasto *Paseo a Sintra* es *solo katia* · *USD 30,8* 📍Lisboa 💸
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

**Latencia:** dispatch 4.3s · stops 0.0s · due 0.0s · **total 4.3s** (sin Meta send)

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

**Latencia:** dispatch 9.4s · stops 0.0s · due 0.0s · **total 9.4s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=-

**Bot:**

```
No, todavía no entra al saldo. 📅 *Entrada al Louvre* quedó *pendiente* y se paga el *15/09* — son *USD 48,4* y por ahora está afuera del saldo.  
💸 Saldo confirmado ahora: *vos le debés USD 60,5 a katia*.
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

**Latencia:** dispatch 3.5s · stops 0.0s · due 0.0s · **total 3.5s** (sin Meta send)

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

## 13 · General / pre-viaje sin ciudad ✅

**Id:** `general-sin-ciudad` — reproducir con `--only general-sin-ciudad`

**Meta:** Fecha fuera de itinerario → city null; Q&A lo admite.

**Checks deterministas: ✅ pasan**

**Mirar (qué corregir si falla):**
- Turno 1: city_name=null / sin stop; split=payer_only; currency=USD; pay≈2026-07-01
- Turno 2: admitir General / sin ciudad; NO inventar Roma/Londres

**Dónde tocar:** `bot/capture.py (resolve_place fuera de rango) · bot/qa.py`

**Bruno:** seguro de viaje 320 usd el 1 de julio, solo mío _fuera de rango_

**Latencia:** dispatch 4.3s · stops 0.0s · due 0.0s · **total 4.3s** (sin Meta send)

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

**Latencia:** dispatch 13.4s · stops 0.0s · due 0.0s · **total 13.4s** (sin Meta send)

**Traza:** intent=trip_question · canal=trip · outcome=ok · tools=list_notes

**Bot:**

```
No hay anotación sobre el **seguro** en nuestras notas.  
Busqué en las notas del viaje y no aparece nada relacionado.
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

**Latencia:** dispatch 23.2s · stops 0.0s · due 0.0s · **total 23.2s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=aggregate_expenses,aggregate_expenses,get_itinerary

**Bot:**

```
Te paso lo pedido:

- *Roma* · *USD 55,0*
- *Paris* · *USD 308,0*
- *Lisboa* · *USD 66,0*

💸 Total (esas 3 ciudades): *USD 429,0* · 📅 Promedio por día del viaje (40 días): *USD 10,7*
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

**Latencia:** dispatch 12.7s · stops 0.0s · due 0.0s · **total 12.7s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=aggregate_expenses

**Bot:**

```
Perfecto. Miré lo que pusiste vos (paid) en esas 3 ciudades:

- *Paris* · *USD 88,0* 📍
- *Lisboa* · *USD 66,0* 📍
- *Roma* · *USD 0,0* 📍 (no pagaste nada ahí)

💸 Total que pusiste de bolsillo: *USD 154,0* · 📅 Promedio por día del viaje: *USD 10,7*
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

**Latencia:** dispatch 4.1s · stops 0.0s · due 0.0s · **total 4.1s** (sin Meta send)

**Traza:** intent=expense · tools=-

**Bot:**

```
✅ *Gasto guardado*

🏨 Alojamiento — Hostel
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
#5 expense 200.00 EUR usd=220.00 desc='Hostel' city=Lisboa split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=None
```

</details>

**Bruno:** ¿qué tengo pendiente de pago? _filtro status_

**Latencia:** dispatch 9.3s · stops 0.0s · due 0.0s · **total 9.3s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=-

**Bot:**

```
No tenés pagos futuros pendientes registrados. ✅  
💸 Saldo confirmado: *USD 49,5* · katia te debe a vos.
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 200.00 EUR usd=220.00 desc='Hostel' city=Lisboa split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=None
```

</details>

**Bruno:** ¿y cuánto se paga en septiembre? _eje payment_date_

**Latencia:** dispatch 12.8s · stops 0.0s · due 0.0s · **total 12.8s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=aggregate_expenses

**Bot:**

```
No hay gastos cargados para *septiembre* (filtrado por fecha de pago). 📅  
Querés que lo vuelva a buscar solo con estado *pending* o *awaiting*?
```

<details><summary>DB (últimos)</summary>

```
#1 expense 200.00 EUR usd=220.00 desc='Hotel Paris' city=Paris split=shared paid_by=katia cat=Alojamiento pay=2026-08-10 status=confirmed batch=None
#2 expense 60.00 EUR usd=66.00 desc='Cena Lisboa' city=Lisboa split=shared paid_by=bruno cat=Comida pay=2026-08-19 status=confirmed batch=None
#3 expense 80.00 EUR usd=88.00 desc='Cena Paris' city=Paris split=shared paid_by=bruno cat=Comida pay=2026-08-08 status=confirmed batch=None
#4 expense 50.00 EUR usd=55.00 desc='Pasta Roma' city=Roma split=shared paid_by=katia cat=Comida pay=2026-08-03 status=confirmed batch=None
#5 expense 200.00 EUR usd=220.00 desc='Hostel' city=Lisboa split=shared paid_by=bruno cat=Alojamiento pay=None status=confirmed batch=None
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

**Latencia:** dispatch 15.4s · stops 0.0s · due 0.0s · **total 15.4s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=aggregate_expenses,get_itinerary

**Bot:**

```
💸 Gastamos por día: *USD 10,7*.  
Total viaje *USD 429,0* · *40* días del itinerario (uso los días de las paradas).
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

**Latencia:** dispatch 15.8s · stops 0.0s · due 0.0s · **total 15.8s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=budget_status

**Bot:**

```
*Lisboa* 🇵🇹
💸 Vivir hasta ahora: *USD 33,0* · objetivo diario: *USD 40,0*
📅 Quedan *2* días · gasto vivir por día: *USD 3,7* · resto por día hasta el check-out: *USD 183,5*

Vose: estaban re bien — *estás por debajo del target* (delta -90,8%), así que sí, *vamos bien de guita* en Lisboa.
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

**Latencia:** dispatch 12.2s · stops 0.0s · due 0.0s · **total 12.2s** (sin Meta send)

**Traza:** intent=question · canal=qa · outcome=ok · tools=budget_status

**Bot:**

```
*Interlaken* 🇨🇭
📅 Estancia: *5* noches (futura)
💸 Target diario: *no hay target cargado* · vivir hasta ahora: *USD 0,0*

No hay objetivo cargado para Interlaken, así que no puedo calcular "cuánto por día" — si querés, cargá un target en la app y te digo enseguida si van bien.
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
| 1 · Cuotas + corrección de total | 1 | bruno | cuotas | 6.9 | 0.0 | 0.0 | 6.9 |
| 1 · Cuotas + corrección de total | 2 | bruno | edit monto del batch | 4.5 | 0.0 | 0.0 | 4.5 |
| 2 · Multi-gasto mezclado + fix de split | 1 | bruno | batch 3 ítems | 7.9 | 0.0 | 0.0 | 7.9 |
| 2 · Multi-gasto mezclado + fix de split | 2 | bruno | edit split taxi | 4.2 | 0.0 | 0.0 | 4.2 |
| 5 · Corrección corta post-carga | 1 | katia | carga | 4.1 | 0.0 | 0.0 | 4.1 |
| 5 · Corrección corta post-carga | 2 | katia | edit split corto | 4.1 | 0.0 | 0.0 | 4.1 |
| 6 · Delete por texto + confirmación | 1 | bruno | carga | 4.5 | 0.0 | 0.0 | 4.5 |
| 6 · Delete por texto + confirmación | 2 | bruno | delete NL | 4.5 | 0.0 | 0.0 | 4.5 |
| 6 · Delete por texto + confirmación | 3 | bruno | confirmar | 0.0 | 0.0 | 0.0 | 0.0 |
| 7 · Settlement cruzado + ¿quién debe? | 1 | bruno | settlement | 4.6 | 0.0 | 0.0 | 4.6 |
| 7 · Settlement cruzado + ¿quién debe? | 2 | katia | Q&A balance | 11.0 | 0.0 | 0.0 | 11.0 |
| 10 · Moneda explícita ≠ moneda ciudad + edit | 1 | bruno | USD explícito | 4.2 | 0.0 | 0.0 | 4.2 |
| 10 · Moneda explícita ≠ moneda ciudad + edit | 2 | bruno | edit currency | 4.2 | 0.0 | 0.0 | 4.2 |
| 15 · Multi-hostel con seña USD + resto en moneda local | 1 | bruno | multi-hostel etapas mixtas | 10.6 | 0.0 | 0.0 | 10.6 |
| 17 · Mixta: guía → nota → plata (cambio de canal) | 1 | katia | list_notes | 7.9 | 0.0 | 0.0 | 7.9 |
| 17 · Mixta: guía → nota → plata (cambio de canal) | 2 | katia | vuelve a finanzas | 11.6 | 0.0 | 0.0 | 11.6 |
| 22 · Settlement corregido | 1 | bruno | settlement | 5.2 | 0.0 | 0.0 | 5.2 |
| 22 · Settlement corregido | 2 | bruno | corrección del pago | 4.4 | 0.0 | 0.0 | 4.4 |
| 23 · Cuándo llegamos (calendario) | 1 | katia | itinerario | 7.2 | 0.0 | 0.0 | 7.2 |
| 20 · Cuotas que no cierran | 1 | bruno | etapas sin montos ni fechas | 5.2 | 0.0 | 0.0 | 5.2 |
| 12 · Q&A follow-up elíptico | 1 | bruno | Q&A | 13.6 | 0.0 | 0.0 | 13.6 |
| 12 · Q&A follow-up elíptico | 2 | bruno | follow-up ciudad | 18.7 | 0.0 | 0.0 | 18.7 |
| 12 · Q&A follow-up elíptico | 3 | bruno | attribution paid | 12.7 | 0.0 | 0.0 | 12.7 |
| 3 · Day-trip + payer/split + saldo | 1 | bruno | daytrip → Lisboa | 4.2 | 0.0 | 0.0 | 4.2 |
| 3 · Day-trip + payer/split + saldo | 2 | bruno | edit paid_by + split | 4.6 | 0.0 | 0.0 | 4.6 |
| 3 · Day-trip + payer/split + saldo | 3 | bruno | Q&A | 11.9 | 0.0 | 0.0 | 11.9 |
| 4 · Pago futuro + ¿entra al saldo? + traer a hoy | 1 | bruno | pending futuro | 4.3 | 0.0 | 0.0 | 4.3 |
| 4 · Pago futuro + ¿entra al saldo? + traer a hoy | 2 | bruno | Q&A pending vs balance | 9.4 | 0.0 | 0.0 | 9.4 |
| 4 · Pago futuro + ¿entra al saldo? + traer a hoy | 3 | bruno | edit payment_date | 3.5 | 0.0 | 0.0 | 3.5 |
| 13 · General / pre-viaje sin ciudad | 1 | bruno | fuera de rango | 4.3 | 0.0 | 0.0 | 4.3 |
| 13 · General / pre-viaje sin ciudad | 2 | bruno | Q&A | 13.4 | 0.0 | 0.0 | 13.4 |
| 18 · Q&A multi-tool pesado | 1 | bruno | multi-tool: aggregate x ciudad + itinerario | 23.2 | 0.0 | 0.0 | 23.2 |
| 18 · Q&A multi-tool pesado | 2 | bruno | follow-up attribution=paid | 12.7 | 0.0 | 0.0 | 12.7 |
| 25 · Pendientes por confirmar | 1 | bruno | pending futuro | 4.1 | 0.0 | 0.0 | 4.1 |
| 25 · Pendientes por confirmar | 2 | bruno | filtro status | 9.3 | 0.0 | 0.0 | 9.3 |
| 25 · Pendientes por confirmar | 3 | bruno | eje payment_date | 12.8 | 0.0 | 0.0 | 12.8 |
| 26 · Promedio por día | 1 | katia | promedio | 15.4 | 0.0 | 0.0 | 15.4 |
| 27 · Presupuesto de la ciudad | 1 | bruno | target vs real | 15.8 | 0.0 | 0.0 | 15.8 |
| 27 · Presupuesto de la ciudad | 2 | bruno | parada sin target | 12.2 | 0.0 | 0.0 | 12.2 |

Promedio dispatch **8.3s** · promedio total **8.3s** · más lento: bruno «comparame cuánto gastamos en Roma, Paris…» (23.2s)

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
