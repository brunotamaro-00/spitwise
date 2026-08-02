# Escenarios bot — canal VIAJE (guías + notas)

Corrida: **2026-08-01 23:52** · hoy ficticio `2026-09-25` (Viena) · suite: suite viaje (16)

Seed: **96** guide docs desde `andiamo/content/guides` · **9** notas · **7** stops.

> Cada corrida reescribe este archivo. Checklist **Mirar** = qué validar a ojo.

## 1. Viena deíctica + follow-up day-trip ✅

**Id:** `viena-deictico` — reproducir con `--only viena-deictico`

**Goal:** Resolver 'acá/mañana' con parada de hoy=Viena; segunda vuelta pide desvío sin repetir el doc entero.

**Checks deterministas: ✅ pasan**

**Mirar:**
- Turno 1: intent trip_question; cita cosas reales de Viena (Schönbrunn, Belvedere, Naschmarkt, café vienés…). Link a /guias/viena/…. FAIL si inventa o habla de Lisboa.
- Turno 2: sigue en canal viaje; usa desvíos/day-trips de Viena o dice si el doc no cubre mucho. FAIL si cambia a finanzas o inventa Bratislava sin estar en la guía.

**Dónde tocar:** `bot/trip_qa.py · qa/trip_tools.py · llm/client.py (trip_question)`

### bruno

**→** che, ¿qué hacemos mañana acá que valga la pena?
*deíctico → viena/actividades*

⏱ dispatch `22.3s` · total `22.3s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

```
Perfecto — para mañana en Viena tenés opciones según onda:

- Mañana: **Schönbrunn — jardines + subir a la Gloriette (GRATIS)** o temprano **Stephansdom** y subir a la Torre Sur (**€6**) para fotos sin gente.  
- Mediodía: almuerzo en **Naschmarkt** (puestos y opciones rápidas).  
- Tarde: **Belvedere** si querés ver *El Beso* (**€19.50** online) o subir a **Kahlenberg** y bajar a un heuriger (ojo: **muchos heuriger cierran entre semana**, fijate el calendario "ausg'steckt").  
- Noche: si pinta música, **Staatsoper standing parterre €18** (ir con tiempo) o un café histórico tipo **Café Central / Sacher** para cerrar.

📖 Más: http://localhost:3000/guias/viena/actividades
```

### bruno

**→** ¿y qué dice el doc de desvíos cercanos de Viena? algún day trip decente?
*follow-up → viena/desvios-cercanos*

⏱ dispatch `13.8s` · total `13.8s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

```
Perfecto — lo que dice el doc "Desvíos cercanos" de Viena:

- **Prioridad alta: Wachau (Melk + Dürnstein + Danubio)** — *tren a Melk ~1h + barco DDSG*; día completo, mezcla abadía + crucero + pueblos. Ojo: **barco es estacional, confirmar**.  
- **Prioridad media: Bratislava** — *REX ~1h* o Twin City Liner (barco); **EURegio Ticket €18 ida/vta** recomendado; alcanza medio día.  
- También menciona: **Baden bei Wien, Semmeringbahn, Neusiedlersee** (este último mejor con auto) y que **Hallstatt queda lejos** para day trip.  

📖 Más: http://localhost:3000/guias/viena/desvios-cercanos
```

---

## 2. Polonia: domingo + dziękuję (guía país + notas) ✅

**Id:** `polonia-domingo` — reproducir con `--only polonia-domingo`

**Goal:** Pregunta de costumbres que exige search/read de polonia/costumbres y/o notas globales.

**Checks deterministas: ✅ pasan**

**Mirar:**
- Turno 1: menciona domingo sin comercio / zakaz handlu / comprar sábado / Żabka. Fuente: costumbres Polonia o nota 'Domingo en Polonia'. FAIL si dice que abre todo.
- Turno 2: explica dziękuję = no querés vuelto. FAIL si confunde con propina checa o inventa otro protocolo.

**Dónde tocar:** `qa/trip_tools.py (search_guides country) · seed notas Monedas/Domingo`

### katia

**→** cuando estemos en Cracovia, ¿qué onda con el domingo? ¿podemos ir al súper?
*zakaz handlu*

⏱ dispatch `13.3s` · total `13.3s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

```
Sí — podemos comprar, pero ojo con la ley de domingos. Resumen rápido:

- *Żabka* y muchos kioscos/food-to-go suelen estar **24h**; *Biedronka/Lidl/Kaufland* pueden cerrar por la **restricción de domingos** (no siempre abren).  
- Recomendación de la guía: **comprar el sábado** por las dudas; si no, depender de Żabka o de puestos/food halls.  
- También hay *Hala Targowa* y Stary Kleparz que suelen funcionar los domingos por la mañana.

📖 Más: http://localhost:3000/guias/cracovia/gastronomia
```

### katia

**→** y lo del tip en Polonia: si digo dziękuję al pagar, ¿qué pasa con el vuelto?
*dziękuję = quedate el cambio*

⏱ dispatch `11.1s` · total `11.1s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

```
Sí — ojo con eso: en Polonia *decir “dziękuję” al entregar el dinero se interpreta como “quedate el cambio”*.  
Entonces **no digas “dziękuję” hasta recibir el vuelto** si querés que te lo devuelvan.  
Si querés dejar propina, lo mejor es **decir el total** o dejar efectivo aparte (~10% si gustó).  
📖 Más: http://localhost:3000/guias/cracovia/gastronomia
```

---

## 3. Auschwitz: nota propia + precio de la guía ✅

**Id:** `auschwitz-nota` — reproducir con `--only auschwitz-nota`

**Goal:** Mezclar list_notes (reserva dummy) con read_guide de actividades/day-trip Cracovia.

**Checks deterministas: ✅ pasan**

**Mirar:**
- Turno 1: cita la nota (slot / visit.auschwitz.org / respeto). FAIL si dice que no hay notas o inventa un horario distinto al seeded.
- Turno 2: ~150 PLN del educator (guía Cracovia). FAIL si inventa euros sin citar PLN o responde sin tool.

**Dónde tocar:** `trip_tools list_notes + read_guide_doc · notas seed Auschwitz`

### bruno

**→** ¿qué anotamos de Auschwitz?
*list_notes cracovia*

⏱ dispatch `12.9s` · total `12.9s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=list_notes

```
Tenemos una nota guardada sobre Auschwitz:

- *Reserva*: **visit.auschwitz.org**.  
- *Slot preferido*: **lun/mar 5‑6 oct 09:00**.  
- *Precio educator*: **~150 PLN**.  
- *Duración*: **día completo**; *respeto*.  
- *Transporte*: **bus MDA ~1h30**.  
- Está marcada como **crítico / pinned** en nuestras anotaciones.
```

### bruno

**→** ok y según la guía cuánto sale el tour con educator?
*read guía → ~150 PLN*

⏱ dispatch `13.0s` · total `13.1s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

```
Según la guía de Cracovia: el tour con *educator* oficial cuesta **150 PLN** por persona.  
Si lo tomás como excursión desde la ciudad (transporte incluido) suelen salir **~160-250 PLN**.  
📖 Más: http://localhost:3000/guias/cracovia/actividades
```

---

## 4. Praga comida → propina (cross-doc + nota) ✅

**Id:** `praga-propina` — reproducir con `--only praga-propina`

**Goal:** Follow-up elíptico: gastronomía Praga y después propina checa vs polaca.

**Checks deterministas: ✅ pasan**

**Mirar:**
- Turno 1: platos reales (svíčková, guláš, pivo/tanque…). FAIL si lista comida polaca.
- Turno 2: Chequia ≠ dziękuję polaco; redondeo/~10%. Puede usar nota 'Propina Chequia'. FAIL si dice que es igual que Polonia.

**Dónde tocar:** `trip_qa follow-ups · search_guides + list_notes`

### katia

**→** en Praga qué tenemos que comer sí o sí?
*praga/gastronomia*

⏱ dispatch `13.0s` · total `13.0s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

```
Perfecto — lo que en la guía figura como imperdible:

- **Svíčková na smetaně** (el plato nacional) — *~180-250 CZK*.  
- **Guláš** con knedlíky — *~120-180 CZK*.  
- **Pivo (tankové)**: cerveza de tanque local — *~50-70 CZK la 0.5L*.  
- **Vepřo‑knedlo‑zelo** (cerdo + dumplings + chucrut).  
- Para picar/rápido: **chlebíčky** y **klobása**.  
- Para dulce: probar **koláče / buchty** (la guía marca al **trdelník** como trampa turística).

📖 Más: http://localhost:3000/guias/praga/gastronomia
```

### katia

**→** y según nuestras notas, la propina en Praga es igual que en Polonia?
*nota Propina Chequia vs dziękuję PL*

⏱ dispatch `11.1s` · total `11.1s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=list_notes

```
Sí — según *nuestras notas* para Praga: **redondear / ~10%**.  
La nota aclara: **NO es como Polonia** (ojo con dar por descontado el vuelto; cita: *Účet, prosím.*).  
Documento encontrado: *Propina Chequia* (nota en Praga).
```

---

## 5. Cambio de canal: guía → plata ✅

**Id:** `cambio-canal` — reproducir con `--only cambio-canal`

**Goal:** Aislamiento: viaje grounded y después intent question con montos de DB.

**Checks deterministas: ✅ pasan**

**Mirar:**
- Turno 1: trip_question → notas Cracovia (Auschwitz / hostel). FAIL si va a aggregate.
- Turno 2: intent question → agente financiero; total Viena del seed (Cena/Museum). FAIL si el agente de guías inventa un monto.

**Dónde tocar:** `dispatcher latest_fresh_channel · llm/client borde plata/contenido`

### bruno

**→** algo urgente que tengamos anotado para Cracovia?
*notas pinned Auschwitz/hostel*

⏱ dispatch `8.6s` · total `8.6s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=list_notes

```
Sí: tenemos varias anotaciones urgentes para **Cracovia**.

- *Auschwitz — crítico*: reservar en **visit.auschwitz.org**; slot preferido **5–6 oct 09:00**, Educator **~150 PLN**.  
- **Hostel Cracovia**: check-in **15:00**, código **4421**.  
- Moneda y pago: **PLN** (también aparece CZK/HUF/CHF en notas); recomendación registrada: **OTP Bank, nunca Euronet**.  
- Compra previa: **Zakaz handlu** — muchos supermercados cerrados los domingos; comprar el sábado (Żabka y restaurantes suelen abrir).

Si querés que busque algún voucher o reserva en los docs, decime qué querés que busque.
```

### bruno

**→** bárbaro. ¿cuánto llevamos gastado en Viena?
*cambio a finanzas*

⏱ dispatch `8.9s` · total `8.9s`

🔍 intent=question · canal=qa · outcome=ok · tools=aggregate_expenses

```
📍 *Viena* — 💸 Total gastado: *USD 92,4* (2 gastos, total del viaje entre los dos).
```

---

## 6. Grounding negativo + Suiza caro ✅

**Id:** `grounding-negativo` — reproducir con `--only grounding-negativo`

**Goal:** Pregunta fuera de guías → 'no está'; después pregunta cubierta por nota Interlaken.

**Checks deterministas: ✅ pasan**

**Mirar:**
- Turno 1: admite que las guías/notas no cubren IKEA. FAIL si inventa horarios.
- Turno 2: cita nota Interlaken (CHF, picnic, Jungfraujoch caro) o guía Suiza. FAIL si vuelve a inventar sobre IKEA.

**Dónde tocar:** `trip_qa grounding · list_notes interlaken`

### katia

**→** el IKEA de Viena abre los domingos? a qué hora?
*NO está en las guías*

⏱ dispatch `10.6s` · total `10.6s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides

```
Che, busqué en nuestras guías de Viena y **no dicen nada sobre el IKEA ni su horario los domingos**.

Busqué en:
- Actividades
- Gastronomía

Si querés, buscó en algún doc más de la guía (decime cuál) o lo vemos en la web vos misma — las guías no lo cubren.
```

### katia

**→** ok olvidate. para Interlaken, ¿qué anotamos de lo caro / pases?
*nota Suiza caro / Swiss Travel*

⏱ dispatch `12.9s` · total `12.9s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=list_notes

```
- *Nota*: **"Suiza caro"** (Interlaken) — **CHF. Picnic/súper. Jungfraujoch carísimo — mirar Lauterbrunnen/Grindelwald en la guía.**
- No hay anotación sobre **pases** (p. ej. Swiss Travel Pass) en nuestras notas.
- Si querés, miramos la guía de Interlaken/Lauterbrunnen para ver opciones de excursiones y pases (no lo anotamos).
```

---

## 7. Frases útiles Polonia (guía país) ❌

**Id:** `frases-polonia` — reproducir con `--only frases-polonia`

**Goal:** Pedidos de idioma: read/search polonia/frases-utiles, no inventar vocabulario.

**Checks deterministas: ❌ FALLAN**
- todos los turnos son del canal viaje, fueron ['trip', 'qa']

**Mirar:**
- Turno 1: cita formas de la guía (p.ej. rachunek/proszę, dziękuję). FAIL si inventa frases que no están o responde en checo/húngaro.
- Turno 2: sigue en frases PL (dzień dobry u equivalente de la guía). FAIL si cambia de país o alucina.

**Dónde tocar:** `search/read polonia/frases-utiles · trip_qa follow-up`

### bruno

**→** según nuestras frases útiles de Polonia, cómo pedimos la cuenta y cómo se dice gracias?
*frases-utiles → rachunek / dziękuję*

⏱ dispatch `14.8s` · total `14.8s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=list_guides,read_guide_doc

```
- *La cuenta:* **Rachunek, proszę** (ra-JÚ-nek PRO-she)  
- *Gracias:* **Dziękuję** (dyen-KÚ-ye) — informal: **Dzięki** (DYEN-ki)

📖 Más: http://localhost:3000/guias/polonia/frases-utiles
```

### bruno

**→** y hay algo ahí sobre saludar al entrar a un negocio?
*follow-up frases · dzień dobry*

⏱ dispatch `9.0s` · total `9.0s`

🔍 intent=question · canal=qa · outcome=ok · tools=-

```
Sí — en Austria es común saludar al entrar a un negocio. Lo más típico en Viena: decir "Grüß Gott" o "Servus" al entrar y un "Danke" al irse. En tiendas grandes o turistas no es obligatorio, pero se aprecia y suena bien. ¿Querés que te arme un mini listado de frases para usar?
```

---

## 8. Budapest: nota baños + guía termales ✅

**Id:** `budapest-banos` — reproducir con `--only budapest-banos`

**Goal:** Nota propia de Budapest y después detalle de la guía (Széchenyi/Gellért).

**Checks deterministas: ✅ pasan**

**Mirar:**
- Turno 1: nota Baños (Széchenyi/Gellért online, OTP, no reventa calle). FAIL si dice que no hay notas.
- Turno 2: contenido real de la guía Budapest (precios/tips termales si están). FAIL si inventa un spa que no figura o responde de cultura general.

**Dónde tocar:** `list_notes budapest · read_guide_doc budapest/actividades`

### katia

**→** qué anotamos de los baños en Budapest?
*list_notes budapest*

⏱ dispatch `9.0s` · total `9.0s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=list_notes

```
Encontré nuestra nota *Baños Budapest* (pinned).  
- **Széchenyi / Gellért**: comprar entrada **ONLINE** (no hay reventa en la calle).  
- **Efectivo**: llevar **HUF**; cambiar/usar **OTP Bank**.
```

### katia

**→** ok y según la guía de actividades, Széchenyi o Gellért — qué conviene?
*budapest/actividades termales*

⏱ dispatch `13.3s` · total `13.3s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

```
Entonces: **Gellért está CERRADO hasta 2028**, así que no es opción.  
- **Széchenyi** conviene para la experiencia icónica y fotos; precio aprox **~13,200 HUF (semana) / ~14,800 HUF (finde)**.  
- Tips rápidos: traje de baño y chanclas, llevar **HUF**, preferir mañana entre semana para menos gente; comprar entrada **online**.  
📖 Más: http://localhost:3000/guias/budapest/actividades
```

---

## 9. Próxima parada → transporte Praga ✅

**Id:** `proxima-praga` — reproducir con `--only proxima-praga`

**Goal:** Deíctico de itinerario (próxima=Praga) y después movilidad en esa ciudad.

**Checks deterministas: ✅ pasan**

**Mirar:**
- Turno 1: Praga + fecha de llegada del seed (2026-09-28). FAIL si dice Budapest/Cracovia como próxima o inventa fechas.
- Turno 2: tips reales de praga/transporte (metro/tranvía/Lítačka o lo que diga el doc). FAIL si habla de Viena o inventa líneas.

**Dónde tocar:** `trip_qa snapshot próximas · read praga/transporte`

### bruno

**→** después de acá, ¿a dónde vamos y cuándo llegamos?
*snapshot próximas → Praga 28/9*

⏱ dispatch `5.9s` · total `5.9s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=-

```
Después de acá vas para **Praga** — **llegan el 2026-09-28**; y después **Cracovia** — **llegan el 2026-10-03**; y luego **Budapest** — **llegan el 2026-10-07**.
```

### bruno

**→** joya. en Praga, según la guía de transporte, ¿cómo nos movemos en la ciudad?
*praga/transporte*

⏱ dispatch `10.9s` · total `10.9s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

```
Perfecto — según la guía de Praga:

- Centro **muy caminable**; usás transporte para distancias largas, cuestas o lluvia.  
- Usar **PID Lítačka (app)**: tickets por tiempo **30 min 36 CZK / 90 min 42 CZK / 24h 140 CZK** (app más barato).  
- Red: **metro (A/B/C)** + **tranvías** (los **22/23** suben al Castillo).  
- Aeropuerto: **bus 119** → metro A o **bus 100** → B (todo con ticket 90 min) o **Airport Express (AE)** a Praha hl.n.  
- Apps útiles: **PID Lítačka, Liftago, Bolt/Uber, ČD, RegioJet, Leo Express**.

📖 Más: http://localhost:3000/guias/praga/transporte
```

---

## 10. Bar mleczny + efectivo PLN (3 turnos) ✅

**Id:** `bar-mleczny` — reproducir con `--only bar-mleczny`

**Goal:** Cadena: costumbre milk bar → follow-up efectivo → pregunta plata (cambio de canal).

**Checks deterministas: ✅ pasan**

**Mirar:**
- Turno 1: milk bar / cantina / pedir en caja (costumbres PL). FAIL si lo confunde con café vienés o hospoda checa.
- Turno 2: cash only frecuente + ir antes de ~14h. Puede citar nota PLN/propina. FAIL si dice que todo es contactless sin matices.
- Turno 3: intent question → get_balance / agente financiero. FAIL si el agente de guías inventa un saldo.

**Dónde tocar:** `costumbres PL · list_notes · dispatcher canal plata`

### katia

**→** en Cracovia qué es un bar mleczny y cómo se pide según las costumbres?
*polonia/costumbres milk bar*

⏱ dispatch `13.2s` · total `13.2s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=list_guides,read_guide_doc

```
Un *bar mleczny* es una **cantina subvencionada** polaca de comida casera (pierogi, sopas, placki) — muy barata: **comida completa 15–25 PLN** (~€3-6).  
Cómo pedir / costumbres en Cracovia:  
- Ir **antes de las 14h** si querés variedad (se agotan platos).  
- Pedís en mostrador o al mozo el **menú/sopa + plato + bebida**; muchos usan cartel/vidriera con los platos.  
- Propina: **~10%** si gustó; atención cultural: **no digas “dziękuję”** hasta recibir el vuelto (decirlo puede interpretarse como “quedate el cambio”).  
📖 Más: http://localhost:3000/guias/cracovia/gastronomia
```

### katia

**→** ahí hace falta efectivo o va tarjeta? y a qué hora conviene ir?
*follow-up cash + antes 14h*

⏱ dispatch `14.4s` · total `14.4s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

```
- **Efectivo:** las guías insisten en costumbres con dinero en mano (propina en efectivo; no decir “dziękuję” hasta recibir el vuelto) y los *bar mleczny* son muy baratos, así que **lleva efectivo** para estar cómodo.  
- **Tarjeta:** *las guías no dicen nada* explícito sobre si los milk bars aceptan tarjeta.  
- **Mejor hora:** **ir antes de las 14:00** (muchos platos se agotan).  
📖 Más: http://localhost:3000/guias/cracovia/gastronomia
```

### katia

**→** ok gracias. al margen: ¿quién debe plata ahora?
*cambio a finanzas → balance*

⏱ dispatch `9.5s` · total `9.5s`

🔍 intent=question · canal=qa · outcome=ok · tools=-

```
💸 Ahora: *USD 3,3* — *katia* le debe a *bruno*.
```

---

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

⏱ dispatch `12.9s` · total `12.9s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=list_guides,search_guides

```
Busqué “Harry Potter” en *Lisboa* y *Porto* y **las guías no dicen nada de eso**.

Si querés confirmarlo en los docs, fijate en:
- *Actividades* de **Lisboa**
- *Actividades* de **Porto**

Si querés que los lea y te diga si hay algo related (por ejemplo, tours temáticos, tiendas o film locations bajo otro nombre), decime cuál doc y lo abro.
```

### katia

**→** ¿y cuánto sale entrar?
*follow-up sobre el mismo lugar*

⏱ dispatch `15.7s` · total `15.7s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides

```
No hay datos de precios: **las guías no dicen nada sobre entradas ni tarifas de Harry Potter** en Lisboa ni en Porto.

Docs donde mirar (si querés que los abra): 
- *Actividades* — **Lisboa**
- *Actividades* — **Porto**
```

---

## 12. Dónde está el voucher del hostel ✅

**Id:** `voucher-buscar` — reproducir con `--only voucher-buscar`

**Goal:** Buscar un ARCHIVO guardado, no lo que dice una guía: tiene que ir a search_documents y devolver el link del voucher.

**Checks deterministas: ✅ pasan**

**Mirar:**
- Turno 1: usa search_documents y pasa el link http://localhost:3000/api/documents/d-viena-hostel. FAIL si lee la guía del hostel o inventa un link.
- Turno 2: encuentra la entrada de Auschwitz (parada Cracovia) con su link. FAIL si dice que no hay nada o mezcla con la nota de Auschwitz sin el archivo.

**Dónde tocar:** `qa/trip_tools.py (search_documents) · bot/trip_qa.py (prompt: archivo ≠ guía)`

### bruno

**→** ¿dónde está el voucher del hostel de Viena?
*documento, no guía*

⏱ dispatch `8.6s` · total `8.6s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_documents

```
Lo tengo: *Voucher del hostel en Viena*.

- *Archivo*: Voucher Wombats Viena  
- *Dónde*: parada **Viena**  
- *Notas*: *Check-in 15:00, código 8812*  
- 📎 **http://localhost:3000/api/documents/d-viena-hostel**
```

### bruno

**→** ¿y la entrada de Auschwitz la tenemos?
*follow-up sobre otro documento, otra parada*

⏱ dispatch `7.9s` · total `7.9s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_documents

```
Lo tenemos: *Entrada Auschwitz*.

- *Archivo*: **Entrada Auschwitz** (slot *6-oct 09:00*, *educator*)  
- *Dónde*: parada **Cracovia**  
- 📎 **http://localhost:3000/api/documents/d-auschwitz**
```

---

## 13. Documento que no existe ✅

**Id:** `doc-inexistente` — reproducir con `--only doc-inexistente`

**Goal:** Negar un documento exige haberlo buscado, igual que negar una guía.

**Checks deterministas: ✅ pasan**

**Mirar:**
- Turno único: llama search_documents y dice que no está guardado. FAIL si lo afirma sin buscar, o si inventa un vuelo. Puede ofrecer el dato de qué SÍ hay guardado, pero sin inventar.

**Dónde tocar:** `qa/trip_tools.py (search_documents) · bot/trip_qa.py (grounding)`

### katia

**→** ¿tenemos guardado el pasaje de avión de vuelta?
*no hay ningún documento de vuelo en el seed*

⏱ dispatch `14.1s` · total `14.1s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_documents

```
Busqué "pasaje de avión de vuelta" en nuestros documentos y **no hay nada guardado**.  
En el viaje tenemos **4 documentos** guardados en total, pero ninguno coincide.  
Si tenés la **aerolínea o la fecha exacta** decímela y lo vuelvo a buscar.
```

---

## 14. Dictar una nota con parada explícita ✅

**Id:** `nota-crear` — reproducir con `--only nota-crear`

**Goal:** Anotar algo por chat: preview + pending, sin tocar el ledger.

**Checks deterministas: ✅ pasan**

**Mirar:**
- Turno único: intent trip_note, card 📝 con el contenido y parada Praga, botones Guardar/Cancelar. FAIL si lo toma como gasto o como pregunta.

**Dónde tocar:** `llm/client.py (intent trip_note) · bot/trip_notes.py · bot/dispatcher.py`

### bruno

**→** anotá que el hostel de Praga pide efectivo para el depósito
*trip_note con ciudad explícita*

⏱ dispatch `4.3s` · total `4.3s`

🔍 intent=trip_note · tools=-

```
📝 *Nota*

*Hostel: depósito efectivo*
El hostel de Praga pide efectivo para el depósito
📍 Praga

_¿Guardo esto?_
[botones]
  · Guardar 📝  (`note_save:s3yExy5O9mg5lYuQIXjFxUiy`)
  · Cancelar  (`note_cancel:s3yExy5O9mg5lYuQIXjFxUiy`)
```

---

## 15. Nota sin ciudad → parada de hoy ✅

**Id:** `nota-general` — reproducir con `--only nota-general`

**Goal:** Sin ciudad, la nota cae en la parada de hoy (Viena), como un gasto.

**Checks deterministas: ✅ pasan**

**Mirar:**
- Turno único: trip_note imputado a Viena (parada de hoy). FAIL si lo manda a General teniendo parada, o si pregunta en qué ciudad.

**Dónde tocar:** `bot/trip_notes.py (resolve_place) · llm/client.py (city en trip_note)`

### katia

**→** tomá nota: el free tour sale 11am de la plaza
*sin ciudad → resolve_place con hoy*

⏱ dispatch `4.2s` · total `4.2s`

🔍 intent=trip_note · tools=-

```
📝 *Nota*

*Free tour*
El free tour sale 11am de la plaza
📍 Viena

_¿Guardo esto?_
[botones]
  · Guardar 📝  (`note_save:6h-2pfSrT48rbAVnWnjzf1N_`)
  · Cancelar  (`note_cancel:6h-2pfSrT48rbAVnWnjzf1N_`)
```

---

## 16. Nota que menciona plata ✅

**Id:** `nota-con-plata` — reproducir con `--only nota-con-plata`

**Goal:** El borde caro del prompt: un número adentro de una nota NO la convierte en gasto.

**Checks deterministas: ✅ pasan**

**Mirar:**
- Turno único: trip_note, CERO movimientos en la DB. FAIL grave: cargar un gasto de 20 PLN. FAIL menor: pedir aclaración en vez de anotar.

**Dónde tocar:** `llm/client.py (regla trip_note vs expense) · bot/dispatcher.py`

### bruno

**→** anotá que el hostel de Cracovia cobra 20 zloty de depósito en efectivo
*trip_note con monto y moneda — NO es expense*

⏱ dispatch `4.7s` · total `4.7s`

🔍 intent=trip_note · tools=-

```
📝 *Nota*

*Hostel: depósito*
El hostel de Cracovia cobra 20 zloty de depósito en efectivo
📍 Cracovia

_¿Guardo esto?_
[botones]
  · Guardar 📝  (`note_save:beTlpJHbkYsM46vpqLsDuPtE`)
  · Cancelar  (`note_cancel:beTlpJHbkYsM46vpqLsDuPtE`)
```

---

## Resumen latencia

| # | Escenario | Turno | Quién | dispatch_s | total_s |
|---:|---|---:|---|---:|---:|
| 1 | Viena deíctica + follow-up day-trip | 1 | bruno | 22.3 | 22.3 |
| 1 | Viena deíctica + follow-up day-trip | 2 | bruno | 13.8 | 13.8 |
| 2 | Polonia: domingo + dziękuję (guía país + notas) | 1 | katia | 13.3 | 13.3 |
| 2 | Polonia: domingo + dziękuję (guía país + notas) | 2 | katia | 11.1 | 11.1 |
| 3 | Auschwitz: nota propia + precio de la guía | 1 | bruno | 12.9 | 12.9 |
| 3 | Auschwitz: nota propia + precio de la guía | 2 | bruno | 13.0 | 13.1 |
| 4 | Praga comida → propina (cross-doc + nota) | 1 | katia | 13.0 | 13.0 |
| 4 | Praga comida → propina (cross-doc + nota) | 2 | katia | 11.1 | 11.1 |
| 5 | Cambio de canal: guía → plata | 1 | bruno | 8.6 | 8.6 |
| 5 | Cambio de canal: guía → plata | 2 | bruno | 8.9 | 8.9 |
| 6 | Grounding negativo + Suiza caro | 1 | katia | 10.6 | 10.6 |
| 6 | Grounding negativo + Suiza caro | 2 | katia | 12.9 | 12.9 |
| 7 | Frases útiles Polonia (guía país) | 1 | bruno | 14.8 | 14.8 |
| 7 | Frases útiles Polonia (guía país) | 2 | bruno | 9.0 | 9.0 |
| 8 | Budapest: nota baños + guía termales | 1 | katia | 9.0 | 9.0 |
| 8 | Budapest: nota baños + guía termales | 2 | katia | 13.3 | 13.3 |
| 9 | Próxima parada → transporte Praga | 1 | bruno | 5.9 | 5.9 |
| 9 | Próxima parada → transporte Praga | 2 | bruno | 10.9 | 10.9 |
| 10 | Bar mleczny + efectivo PLN (3 turnos) | 1 | katia | 13.2 | 13.2 |
| 10 | Bar mleczny + efectivo PLN (3 turnos) | 2 | katia | 14.4 | 14.4 |
| 10 | Bar mleczny + efectivo PLN (3 turnos) | 3 | katia | 9.5 | 9.5 |
| 11 | Harry Potter en Lisboa o Porto (multi-ciudad + sinónimos) | 1 | katia | 12.9 | 12.9 |
| 11 | Harry Potter en Lisboa o Porto (multi-ciudad + sinónimos) | 2 | katia | 15.7 | 15.7 |
| 12 | Dónde está el voucher del hostel | 1 | bruno | 8.6 | 8.6 |
| 12 | Dónde está el voucher del hostel | 2 | bruno | 7.9 | 7.9 |
| 13 | Documento que no existe | 1 | katia | 14.1 | 14.1 |
| 14 | Dictar una nota con parada explícita | 1 | bruno | 4.3 | 4.3 |
| 15 | Nota sin ciudad → parada de hoy | 1 | katia | 4.2 | 4.2 |
| 16 | Nota que menciona plata | 1 | bruno | 4.7 | 4.7 |

```bash
cd backend
.venv/bin/python scripts/bot_trip_scenario_runner.py
.venv/bin/python scripts/bot_trip_scenario_runner.py --only 2,3,6
```
