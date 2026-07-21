# Eval canal documentos — documents-check (ad-hoc, descartable)

Corrida: 2026-07-21 · modelo `gpt-5` · 25 paradas del Andiamo real · hoy=2026-07-21

Este archivo se reescribe entero en cada corrida. Ground truth = README de la carpeta de fixtures (parseado en runtime).

## 1. `civitatis.com_es_voucher_…_1.pdf`

- Fecha: ✅ `2026-08-07` (esperado `2026-08-07`)
- Parada: ✅ `londres` (esperado `londres` — Londres)
- Kind: ✅ `ticket` (esperado `ticket`)
- Label: `Visita guiada Museo Británico`
- Nota: `A las 10:30 en Montague Place, entrada trasera del Museo Británico; llegar 15 minutos antes. Reserva A40247156 (ref. 364139049) a nombre de Bruno Tamaro, 2 adultos; guía con paraguas blanco con la bandera de España.`
- travel_doc=True · confidence=0.93 · 15.6s
- Referencia (README): Civitatis — visita guiada Museo Británico (ES), 2 adultos. Reserva `A40247156`.

## 2. `TicketOrder20260718-S17172460.pdf`

- Fecha: ✅ `2026-08-10` (esperado `2026-08-10`)
- Parada: ✅ `londres` (esperado `londres` — Londres)
- Kind: ✅ `ticket` (esperado `ticket`)
- Label: `Entrada Natural History Museum Londres`
- Nota: `Horario 10:45; 2 adultos (entrada gratuita). Order ID 7606683, sede South Kensington (Cromwell Road, London SW7 5BD).`
- travel_doc=True · confidence=0.97 · 13.7s
- Referencia (README): Natural History Museum — 2 entradas Adult Free. Order `7606683`.

## 3. `TicketOrder20260520-166259659.pdf`

- Fecha: ✅ `2026-08-11` (esperado `2026-08-11`)
- Parada: ✅ `londres` (esperado `londres` — Londres)
- Kind: ✅ `ticket` (esperado `ticket`)
- Label: `Entrada Warner Bros. Studio Tour London`
- Nota: `Martes 11/08/2026 12:30, 2 adultos. Referencia de reserva 7302280; llegar 20 min antes y mostrar el e-ticket (también para el shuttle desde Watford Junction).`
- travel_doc=True · confidence=0.94 · 18.1s
- Referencia (README): Warner Bros. Studio Tour (Harry Potter, Leavesden) — 2 e-tickets Adult. Ref `7302280`.

## 4. `eTicket-PW373965-BIK-1-0.pdf`

- Fecha: ✅ `2026-08-13` (esperado `2026-08-13`)
- Parada: ✅ `york` (esperado `york` — York)
- Kind: ✅ `train` (esperado `train`)
- Label: `Reserva de asiento tren Londres–York`
- Nota: `Sale 11:03 desde London Kings Cross y llega 13:03 a York. Coche F asiento 33 (LNER). Reserva PW373965; código CBBW7B8TKGP. Válido solo con ticket de viaje.`
- travel_doc=True · confidence=0.98 · 17.6s
- Referencia (README): LNER seat reservation — Kings Cross → York (F/33). Ref `PW373965`.

## 5. `eTicket-GU297882-BIK-1-0.pdf`

- Fecha: ✅ `2026-08-15` (esperado `2026-08-15`)
- Parada: ✅ `edimburgo` (esperado `edimburgo` — Edimburgo)
- Kind: ✅ `train` (esperado `train`)
- Label: `Tren York–Edimburgo`
- Nota: `Salida 10:19 y llegada 12:38 (LNER). Reserva de asiento: Coche B, asiento 65; válida solo con billete de tren. Booking reference GU297882, ticket CBBW7B8TKGR.`
- travel_doc=True · confidence=0.88 · 22.6s
- Referencia (README): LNER seat reservation — York → Edinburgh (B/65). Ref `GU297882`.

## 6. `ZYBHB5CW2C.pdf`

- Fecha: ✅ `2026-08-18` (esperado `2026-08-18`)
- Parada: ✅ `edimburgo` (esperado `edimburgo` — Edimburgo)
- Kind: ✅ `carRental` (esperado `carRental`)
- Label: `Auto Hertz Edimburgo`
- Nota: `Retiro 18/08/2026 07:00 y devolución 25/08/2026 07:00 en Aeropuerto de Edimburgo (EDI). Voucher 6BN5GGK y reserva L629E5E0144 a nombre de Katia Koatz; llevar pasaporte y tarjeta de crédito física para depósito (desde EUR 500).`
- travel_doc=True · confidence=0.96 · 29.1s
- Referencia (README): Rentcars/Hertz — retiro EDI apt (dev. 25). Ford Fiesta o similar. Conductora Katia. Ref `L629E5E0144`.

## 7. `Detalles-De-La-Reserva-WTB19C9D88.pdf`

- Fecha: ✅ `2026-08-20` (esperado `2026-08-20`)
- Parada: ✅ `portree` (esperado `portree` — Portree)
- Kind: ✅ `checkin` (esperado `checkin`)
- Label: `Check-in Portree Independent Hostel`
- Nota: `Check-in 20/08/2026 entre 16:00 y 21:00 (si llegan después, avisar); referencia WTB19C9D88. Huéspedes Bruno Tamaro y Katia Koatz; saldo £70 a pagar en efectivo al llegar.`
- travel_doc=True · confidence=0.98 · 25.5s
- Referencia (README): Portree Independent Hostel — check-in (2 noches, dorm mixed). Ref `WTB19C9D88`.

## 8. `N2629073689.pdf`

- Fecha: ✅ `2026-08-27` (esperado `2026-08-27`)
- Parada: ✅ `amsterdam` (esperado `amsterdam` — Ámsterdam)
- Kind: ✅ `ticket` (esperado `ticket`)
- Label: `Entrada Anne Frank House`
- Nota: `Inicio 19:30; llegar al menos 5 min antes; Entrada 2. 2 entradas Adulto para el Introductory program (English) a nombre de Bruno Tamaro; tickets 20250102536013 y 20250102535506 (mostrar en el celular, sin bolsos grandes).`
- travel_doc=True · confidence=0.9 · 28.6s
- Referencia (README): Anne Frank House — Introductory program (EN), 2 Adult €23.50.

## 9. `Tickets Amsterdam Centraal … Paris Nord.pdf`

- Fecha: ✅ `2026-08-29` (esperado `2026-08-29`)
- Parada: ✅ `paris` (esperado `paris` — París)
- Kind: ✅ `train` (esperado `train`)
- Label: `Tren Ámsterdam–París`
- Nota: `Sale 10:10 de Amsterdam Centraal (Eurostar 9434), llega 13:39 a Paris Gare du Nord. Coche 7 asientos 31 y 32; PNR VD4XNX; llegar al control a las 09:50; 2 pasajeros (Bruno y Katia).`
- travel_doc=True · confidence=0.99 · 22.7s
- Referencia (README): Eurostar AMS Centraal → Paris Nord (9434). Bruno 7/31 + Katia 7/32. PNR `VD4XNX`.

## Resumen

| Doc | Fecha | Parada | Kind | seg |
|---|---|---|---|---|
| `civitatis.com_es_voucher_…_1.pdf` | ✅ | ✅ | ✅ | 15.6 |
| `TicketOrder20260718-S17172460.pdf` | ✅ | ✅ | ✅ | 13.7 |
| `TicketOrder20260520-166259659.pdf` | ✅ | ✅ | ✅ | 18.1 |
| `eTicket-PW373965-BIK-1-0.pdf` | ✅ | ✅ | ✅ | 17.6 |
| `eTicket-GU297882-BIK-1-0.pdf` | ✅ | ✅ | ✅ | 22.6 |
| `ZYBHB5CW2C.pdf` | ✅ | ✅ | ✅ | 29.1 |
| `Detalles-De-La-Reserva-WTB19C9D88.pdf` | ✅ | ✅ | ✅ | 25.5 |
| `N2629073689.pdf` | ✅ | ✅ | ✅ | 28.6 |
| `Tickets Amsterdam Centraal … Paris Nord.pdf` | ✅ | ✅ | ✅ | 22.7 |

**9/9 documentos con los 3 campos correctos.**
