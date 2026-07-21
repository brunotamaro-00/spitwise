# Escenarios bot — canal VIAJE (guías + notas)

Corrida: **2026-07-21 15:52** · hoy ficticio `2026-09-25` (Viena) · suite: suite viaje (10)

Seed: **88** guide docs desde `andiamo/content/guides` · **9** notas · **7** stops.

> Cada corrida reescribe este archivo. Checklist **Mirar** = qué validar a ojo.

## 1. Viena deíctica + follow-up day-trip

**Goal:** Resolver 'acá/mañana' con parada de hoy=Viena; segunda vuelta pide desvío sin repetir el doc entero.

**Mirar:**
- Turno 1: intent trip_question; cita cosas reales de Viena (Schönbrunn, Belvedere, Naschmarkt, café vienés…). Link a /guias/viena/…. FAIL si inventa o habla de Lisboa.
- Turno 2: sigue en canal viaje; usa desvíos/day-trips de Viena o dice si el doc no cubre mucho. FAIL si cambia a finanzas o inventa Bratislava sin estar en la guía.

**Dónde tocar:** `bot/trip_qa.py · qa/trip_tools.py · llm/client.py (trip_question)`

### bruno

**→** che, ¿qué hacemos mañana acá que valga la pena?
*deíctico → viena/actividades*

⏱ dispatch `12.8s` · total `12.8s`

```
Perfecto — para mañana (sábado 26/9) las guías recomiendan esto, según lo que anotamos:

- Mañana temprano: **Naschmarkt + Flohmarkt** (mejor antes de las 10am).  
- Tarde: paseo por **Schönbrunn (jardines + Gloriette gratis)** o **Belvedere** si querés ver *El Beso* (Belvedere requiere hora).  
- Café a media tarde: vivir la **cultura del café vienés** en un histórico (Central/Sperl/Sacher según ganas).  
- Noche: **heuriger** (temporada de *Sturm* en sept — buscar abiertos) o intentar **standing en la Staatsoper** (€18 parterre) si hay función.

📖 Más: http://localhost:3000/guias/viena/actividades
```

### bruno

**→** ¿y qué dice el doc de desvíos cercanos de Viena? algún day trip decente?
*follow-up → viena/desvios-cercanos*

⏱ dispatch `10.6s` · total `10.6s`

```
Según el doc de *Desvíos cercanos*: los day trips recomendados son:

- **Wachau (Melk + Dürnstein + crucero por el Danubio)** — *prioridad alta*, día completo; **tren a Melk ~1h + barco DDSG** (el barco es estacional, confirmar).  
- **Bratislava** — *prioridad media*, ~1h en tren; **EURegio Ticket €18** (ida/vta) o Twin City Liner (barco).  
- Opciones menores: **Baden bei Wien** (spa), **Semmeringbahn** (tren panorámico) y **Neusiedlersee** (mejor con coche).  
📖 Más: http://localhost:3000/guias/viena/desvios-cercanos
```

---

## 2. Polonia: domingo + dziękuję (guía país + notas)

**Goal:** Pregunta de costumbres que exige search/read de polonia/costumbres y/o notas globales.

**Mirar:**
- Turno 1: menciona domingo sin comercio / zakaz handlu / comprar sábado / Żabka. Fuente: costumbres Polonia o nota 'Domingo en Polonia'. FAIL si dice que abre todo.
- Turno 2: explica dziękuję = no querés vuelto. FAIL si confunde con propina checa o inventa otro protocolo.

**Dónde tocar:** `qa/trip_tools.py (search_guides country) · seed notas Monedas/Domingo`

### katia

**→** cuando estemos en Cracovia, ¿qué onda con el domingo? ¿podemos ir al súper?
*zakaz handlu*

⏱ dispatch `13.8s` · total `13.8s`

```
Sí, pero con cuidado: **hay una ley que restringe el comercio algunos domingos**.  
- **Żabka (24h)** y muchos locales de comida suelen estar abiertos.  
- **Biedronka / Lidl** pueden estar cerrados en los domingos restringidos; los supermercados suelen cerrar a **21-22h** los días normales.  
Mejor comprar lo básico el sábado por las dudas. 📖 Más: http://localhost:3000/guias/cracovia/gastronomia
```

### katia

**→** y lo del tip en Polonia: si digo dziękuję al pagar, ¿qué pasa con el vuelto?
*dziękuję = quedate el cambio*

⏱ dispatch `12.1s` · total `12.1s`

```
Sí: según la guía, **decir "dziękuję" al entregar el dinero se interpreta como "quédese el cambio"** — te van a dejar sin vuelto.  
Mejor: no digas *dziękuję* hasta después de recibir el vuelto (o confirmá en voz baja el total).  
📖 Más: http://localhost:3000/guias/cracovia/gastronomia
```

---

## 3. Auschwitz: nota propia + precio de la guía

**Goal:** Mezclar list_notes (reserva dummy) con read_guide de actividades/day-trip Cracovia.

**Mirar:**
- Turno 1: cita la nota (slot / visit.auschwitz.org / respeto). FAIL si dice que no hay notas o inventa un horario distinto al seeded.
- Turno 2: ~150 PLN del educator (guía Cracovia). FAIL si inventa euros sin citar PLN o responde sin tool.

**Dónde tocar:** `trip_tools list_notes + read_guide_doc · notas seed Auschwitz`

### bruno

**→** ¿qué anotamos de Auschwitz?
*list_notes cracovia*

⏱ dispatch `11.9s` · total `11.9s`

```
Apuntamos esto sobre *Auschwitz* (nota de Cracovia):

- *Reserva*: **visit.auschwitz.org**.  
- *Slot preferido*: **lun/mar 5-6 oct 09:00**.  
- *Educator*: **~150 PLN**.  
- *Logística*: *Día completo; respeto; bus MDA ~1h30.*

Si querés, lo miro en la guía de Cracovia para más detalles.
```

### bruno

**→** ok y según la guía cuánto sale el tour con educator?
*read guía → ~150 PLN*

⏱ dispatch `9.5s` · total `9.5s`

```
Según la guía, el tour con *educator* oficial cuesta **150 PLN** por persona.  
Si lo contratás desde Cracovia (con transporte incluido) suele salir entre **160–250 PLN**.  
📖 Más: http://localhost:3000/guias/cracovia/actividades
```

---

## 4. Praga comida → propina (cross-doc + nota)

**Goal:** Follow-up elíptico: gastronomía Praga y después propina checa vs polaca.

**Mirar:**
- Turno 1: platos reales (svíčková, guláš, pivo/tanque…). FAIL si lista comida polaca.
- Turno 2: Chequia ≠ dziękuję polaco; redondeo/~10%. Puede usar nota 'Propina Chequia'. FAIL si dice que es igual que Polonia.

**Dónde tocar:** `trip_qa follow-ups · search_guides + list_notes`

### katia

**→** en Praga qué tenemos que comer sí o sí?
*praga/gastronomia*

⏱ dispatch `15.2s` · total `15.2s`

```
Perfecto — lo imprescindible en Praga:

- **Svíčková na smetaně** (ternera en salsa cremosa con knedlíky) — *plato nacional*.  
- **Guláš** con knedlíky — contundente y típico (buen lugar: Restaurace Mlejnice).  
- **Vepřo‑knedlo‑zelo** (cerdo + dumplings + chucrut).  
- **Smažený sýr** (queso frito) si querés algo barato/vegetariano.  
- **Pivo de tanque** (cerveza local, 0.5L **50-70 CZK**) — casi obligatorio.  
- Probar: **chlebíčky** en una lahůdky y, si querés foto, un trdelník sabiendo que es turístico.

📖 Más: http://localhost:3000/guias/praga/gastronomia
```

### katia

**→** y según nuestras notas, la propina en Praga es igual que en Polonia?
*nota Propina Chequia vs dziękuję PL*

⏱ dispatch `10.8s` · total `10.8s`

```
No, **no es igual**. Según nuestras notas:  
- En **Praga** se suele **redondear / ~10%**.  
- **NO** es como en Polonia: allí dejamos el cambio o dicen *dziękuję*; en Chequia conviene pedir la cuenta: **Účet, prosím.**  
(Nota registrada: *Propina Chequia*).
```

---

## 5. Cambio de canal: guía → plata

**Goal:** Aislamiento: viaje grounded y después intent question con montos de DB.

**Mirar:**
- Turno 1: trip_question → notas Cracovia (Auschwitz / hostel). FAIL si va a aggregate.
- Turno 2: intent question → agente financiero; total Viena del seed (Cena/Museum). FAIL si el agente de guías inventa un monto.

**Dónde tocar:** `dispatcher latest_fresh_channel · llm/client borde plata/contenido`

### bruno

**→** algo urgente que tengamos anotado para Cracovia?
*notas pinned Auschwitz/hostel*

⏱ dispatch `8.9s` · total `8.9s`

```
Sí. Lo urgente que tenemos anotado para Cracovia:

- *Auschwitz — crítico*: **reservar en visit.auschwitz.org**, preferible slot **5-6 oct 09:00**; Educator ~**150 PLN**.  
- *Hostel Cracovia*: **check-in 15:00**, **código 4421**.  
- *Moneda/efectivo*: en Polonia usan **PLN** (nota: nuestras anotaciones dicen eso).  
- *Domingos*: **la mayoría de supermercados cerrados** — comprar el sábado.
```

### bruno

**→** bárbaro. ¿cuánto llevamos gastado en Viena?
*cambio a finanzas*

⏱ dispatch `12.0s` · total `12.0s`

```
*Viena* 📍
💸 Total: *USD 92,4* (2 gastos) — montos en USD.
```

---

## 6. Grounding negativo + Suiza caro

**Goal:** Pregunta fuera de guías → 'no está'; después pregunta cubierta por nota Interlaken.

**Mirar:**
- Turno 1: admite que las guías/notas no cubren IKEA. FAIL si inventa horarios.
- Turno 2: cita nota Interlaken (CHF, picnic, Jungfraujoch caro) o guía Suiza. FAIL si vuelve a inventar sobre IKEA.

**Dónde tocar:** `trip_qa grounding · list_notes interlaken`

### katia

**→** el IKEA de Viena abre los domingos? a qué hora?
*NO está en las guías*

⏱ dispatch `10.9s` · total `10.9s`

```
Las guías NO dicen nada del horario del *IKEA* en Viena, y en nuestras notas de Viena tampoco aparece.

Miralo en la guía *viena* buscando por “compras” u “horarios” o consultá la web oficial del IKEA (no está en nuestras guías).
```

### katia

**→** ok olvidate. para Interlaken, ¿qué anotamos de lo caro / pases?
*nota Suiza caro / Swiss Travel*

⏱ dispatch `10.0s` · total `10.0s`

```
- *Interlaken — apuntes*: **Suiza caro**. Recomendamos *picnic/súper*.  
- *Excursión alta*: **Jungfraujoch carísimo** — mirar alternativas *Lauterbrunnen/Grindelwald* en la guía.  
- Eso es lo que tenemos anotado sobre precios/pases para Interlaken.
```

---

## 7. Frases útiles Polonia (guía país)

**Goal:** Pedidos de idioma: read/search polonia/frases-utiles, no inventar vocabulario.

**Mirar:**
- Turno 1: cita formas de la guía (p.ej. rachunek/proszę, dziękuję). FAIL si inventa frases que no están o responde en checo/húngaro.
- Turno 2: sigue en frases PL (dzień dobry u equivalente de la guía). FAIL si cambia de país o alucina.

**Dónde tocar:** `search/read polonia/frases-utiles · trip_qa follow-up`

### bruno

**→** según nuestras frases útiles de Polonia, cómo pedimos la cuenta y cómo se dice gracias?
*frases-utiles → rachunek / dziękuję*

⏱ dispatch `9.4s` · total `9.4s`

```
Según nuestras frases útiles de Polonia:

- Para pedir la cuenta: **Rachunek, proszę** (ra-JÚ-nek PRO-she)  
- Para decir gracias: **Dziękuję** (dyen-KÚ-ye) — informal: **Dzięki** (DYEN-ki)

📖 Más: http://localhost:3000/guias/polonia/frases-utiles
```

### bruno

**→** y hay algo ahí sobre saludar al entrar a un negocio?
*follow-up frases · dzień dobry*

⏱ dispatch `22.2s` · total `22.2s`

```
Sí: las guías recomiendan saludar al entrar.  
- Decí **«Dzień dobry»** (buen día) al entrar a tiendas, restaurantes y especialmente a un *bar mleczny*.  
- Es parte del trato formal y se aprecia; ayuda a abrir la charla con gente mayor o personal más reservado.  

📖 Más: http://localhost:3000/guias/polonia/costumbres
```

---

## 8. Budapest: nota baños + guía termales

**Goal:** Nota propia de Budapest y después detalle de la guía (Széchenyi/Gellért).

**Mirar:**
- Turno 1: nota Baños (Széchenyi/Gellért online, OTP, no reventa calle). FAIL si dice que no hay notas.
- Turno 2: contenido real de la guía Budapest (precios/tips termales si están). FAIL si inventa un spa que no figura o responde de cultura general.

**Dónde tocar:** `list_notes budapest · read_guide_doc budapest/actividades`

### katia

**→** qué anotamos de los baños en Budapest?
*list_notes budapest*

⏱ dispatch `9.0s` · total `9.0s`

```
Anotamos esto en **Baños Budapest**:

- **Széchenyi / Gellért**: comprar entrada *ONLINE* (no comprarle a revendedores en la calle).  
- **Efectivo**: llevar **HUF**; cambiar/retirar en **OTP Bank**.

Eso es todo lo que tenemos en las notas.
```

### katia

**→** ok y según la guía de actividades, Széchenyi o Gellért — qué conviene?
*budapest/actividades termales*

⏱ dispatch `14.1s` · total `14.1s`

```
- **Gellért** está *cerrado desde 01.10.2025* y **no reabre hasta 2028**, así que no es opción para este viaje.  
- **Széchenyi**: si querés *fotos icónicas y piscinas exteriores*, **Széchenyi** (≈ **13,200 HUF** entresemana / **14,800 HUF** finde) es la elección.  
- Si buscás algo más auténtico y atmosférico, la guía recomienda **Rudas** (otomano, rooftop, ~**11,000-12,000 HUF**)—además tiene la opción nocturna Rudas Night.

📖 Más: Actividades (Budapest) <http://localhost:3000/guias/budapest/actividades>
```

---

## 9. Próxima parada → transporte Praga

**Goal:** Deíctico de itinerario (próxima=Praga) y después movilidad en esa ciudad.

**Mirar:**
- Turno 1: Praga + fecha de llegada del seed (2026-09-28). FAIL si dice Budapest/Cracovia como próxima o inventa fechas.
- Turno 2: tips reales de praga/transporte (metro/tranvía/Lítačka o lo que diga el doc). FAIL si habla de Viena o inventa líneas.

**Dónde tocar:** `trip_qa snapshot próximas · read praga/transporte`

### bruno

**→** después de acá, ¿a dónde vamos y cuándo llegamos?
*snapshot próximas → Praga 28/9*

⏱ dispatch `8.2s` · total `8.2s`

```
Después de Viena vamos a:

- **Praga** — llegamos el **28/09/2026**.  
- **Cracovia** — llegamos el **03/10/2026**.  
- **Budapest** — llegamos el **07/10/2026**.
```

### bruno

**→** joya. en Praga, según la guía de transporte, ¿cómo nos movemos en la ciudad?
*praga/transporte*

⏱ dispatch `12.8s` · total `12.8s`

```
Perfecto — según la guía de Praga, así nos movemos:

- **A pie**: el casco histórico es *muy* caminable (Staré Město, Malá Strana, Hradčany).  
- **App/tickets:** usar **PID Lítačka** (30/90 min / 24h: **36 / 42 / 140 CZK** app). Activar ≥1 min antes.  
- **Tranvía/metro:** metro A/B/C y tranvías (22/23 suben al Castillo).  
- **Taxis:** **Bolt / Uber / Liftago**; evitar taxis de calle.  
- **Aeropuerto:** bus **119** (→ metro A) o **100** (→ metro B) en un ticket de 90 min.  
📖 Más: http://localhost:3000/guias/praga/transporte
```

---

## 10. Bar mleczny + efectivo PLN (3 turnos)

**Goal:** Cadena: costumbre milk bar → follow-up efectivo → pregunta plata (cambio de canal).

**Mirar:**
- Turno 1: milk bar / cantina / pedir en caja (costumbres PL). FAIL si lo confunde con café vienés o hospoda checa.
- Turno 2: cash only frecuente + ir antes de ~14h. Puede citar nota PLN/propina. FAIL si dice que todo es contactless sin matices.
- Turno 3: intent question → get_balance / agente financiero. FAIL si el agente de guías inventa un saldo.

**Dónde tocar:** `costumbres PL · list_notes · dispatcher canal plata`

### katia

**→** en Cracovia qué es un bar mleczny y cómo se pide según las costumbres?
*polonia/costumbres milk bar*

⏱ dispatch `18.3s` · total `18.3s`

```
Un *bar mleczny* es la **cantina subvencionada polaca**: comida casera y muy barata (almuerzo completo **15-25 PLN**, pierogi y sopas).  
Cómo pedir / costumbres (según la guía):

- Ir temprano: **mejor antes de las 14:00** porque se agotan platos.  
- Pedí en el mostrador o en caja según el lugar: elegís plato/sopa y bebida; muchos funcionan por menú del día.  
- Bebida típica gratis/asequible: **kompot**; probá pierogi o żurek.  
- Propina: ~**10%** si querés; ojo con decir *dziękuję* al pagar — la guía advierte que decirlo antes de recibir el vuelto puede interpretarse como “quédese con el cambio”.  
- Recomendados: *Bar Mleczny Flisak*, *Pod Temidą*, *Bar Mleczny Centralny* (Nowa Huta).

📖 Más: http://localhost:3000/guias/cracovia/gastronomia
```

### katia

**→** ahí hace falta efectivo o va tarjeta? y a qué hora conviene ir?
*follow-up cash + antes 14h*

⏱ dispatch `22.7s` · total `22.7s`

```
- **Las guías no dicen** explícitamente si los *bar mleczny* aceptan tarjeta.  
- La guía recomienda evitar Euronet y **usar cajeros de bancos polacos** y **pagar en PLN** (rechazar conversiones DCC), así que llevá algo de efectivo por si acaso.  
- Horario: **ir antes de las 14:00** porque se agotan los platos.  

📖 Más: http://localhost:3000/guias/cracovia/actividades
```

### katia

**→** ok gracias. al margen: ¿quién debe plata ahora?
*cambio a finanzas → balance*

⏱ dispatch `11.5s` · total `11.5s`

```
💸 Ahora: *katia* le debe *USD 3,3* a *bruno* (solo confirmados, los pendientes no se cuentan).
```

---

## Resumen latencia

| # | Escenario | Turno | Quién | dispatch_s | total_s |
|---:|---|---:|---|---:|---:|
| 1 | Viena deíctica + follow-up day-trip | 1 | bruno | 12.8 | 12.8 |
| 1 | Viena deíctica + follow-up day-trip | 2 | bruno | 10.6 | 10.6 |
| 2 | Polonia: domingo + dziękuję (guía país + notas) | 1 | katia | 13.8 | 13.8 |
| 2 | Polonia: domingo + dziękuję (guía país + notas) | 2 | katia | 12.1 | 12.1 |
| 3 | Auschwitz: nota propia + precio de la guía | 1 | bruno | 11.9 | 11.9 |
| 3 | Auschwitz: nota propia + precio de la guía | 2 | bruno | 9.5 | 9.5 |
| 4 | Praga comida → propina (cross-doc + nota) | 1 | katia | 15.2 | 15.2 |
| 4 | Praga comida → propina (cross-doc + nota) | 2 | katia | 10.8 | 10.8 |
| 5 | Cambio de canal: guía → plata | 1 | bruno | 8.9 | 8.9 |
| 5 | Cambio de canal: guía → plata | 2 | bruno | 12.0 | 12.0 |
| 6 | Grounding negativo + Suiza caro | 1 | katia | 10.9 | 10.9 |
| 6 | Grounding negativo + Suiza caro | 2 | katia | 10.0 | 10.0 |
| 7 | Frases útiles Polonia (guía país) | 1 | bruno | 9.4 | 9.4 |
| 7 | Frases útiles Polonia (guía país) | 2 | bruno | 22.2 | 22.2 |
| 8 | Budapest: nota baños + guía termales | 1 | katia | 9.0 | 9.0 |
| 8 | Budapest: nota baños + guía termales | 2 | katia | 14.1 | 14.1 |
| 9 | Próxima parada → transporte Praga | 1 | bruno | 8.2 | 8.2 |
| 9 | Próxima parada → transporte Praga | 2 | bruno | 12.8 | 12.8 |
| 10 | Bar mleczny + efectivo PLN (3 turnos) | 1 | katia | 18.3 | 18.3 |
| 10 | Bar mleczny + efectivo PLN (3 turnos) | 2 | katia | 22.7 | 22.7 |
| 10 | Bar mleczny + efectivo PLN (3 turnos) | 3 | katia | 11.5 | 11.5 |

```bash
cd backend
.venv/bin/python scripts/bot_trip_scenario_runner.py
.venv/bin/python scripts/bot_trip_scenario_runner.py --only 2,3,6
```
