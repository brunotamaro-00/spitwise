# Escenarios bot — canal VIAJE (guías + notas)

Corrida: **2026-08-01 20:29** · hoy ficticio `2026-09-25` (Viena) · suite: suite viaje (16)

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

⏱ dispatch `12.3s` · total `12.3s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

```
Dale — para mañana (estamos en Viena) te tiro un día que mezcla lo mejor sin matarnos:

- Mañana: **Schönbrunn — jardines + subir a la Gloriette (gratis)** o si preferís centro, **Stephansdom** temprano para la foto sin gente.  
- Media mañana/tarde: **Naschmarkt Flohmarkt** (es sábado 26 — mejor ir antes de las 10:00) para comida y cosas locas.  
- Tarde: pasear la **Ringstrasse** y/o **Belvedere** (si querés ver *El Beso*).  
- Noche: si hay función, **Staatsoper standing €18** (llegar con tiempo) o ir a un **heuriger** (Stammersdorf/Oberlaa mejor que Grinzing) para probar *Sturm* y vinos locales.  

📖 Más: guía de actividades de Viena — http://localhost:3000/guias/viena/actividades
```

### bruno

**→** ¿y qué dice el doc de desvíos cercanos de Viena? algún day trip decente?
*follow-up → viena/desvios-cercanos*

⏱ dispatch `8.7s` · total `8.7s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

```
Buena — el doc de *Desvíos cercanos* tiene esto claro:

- **El mejor day trip: Wachau (Melk + Dürnstein + crucero por el Danubio)** — tren a Melk ~1h + barco DDSG (estacional) y pueblos/viñedos; día completo.  
- **Alternativa corta: Bratislava** — ~1h en tren (EURegio Ticket €18 ida/vta) o Twin City Liner en barco; medio día alcanza.  
- Otras opciones: **Baden**, **Semmeringbahn** o **Neusiedlersee** (este último mejor con auto).  

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

⏱ dispatch `11.2s` · total `11.2s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=list_guides,search_guides,read_guide_doc

```
Sí — ojo con las restricciones de domingo en Polonia. Resumen corto:

- **Żabka** suele estar **24h** y **abre domingos**; es la opción segura.  
- **Biedronka / Lidl / Kaufland** suelen cerrar **más temprano (hasta 21–22h)** y **en algunos domingos hay restricciones** (no todos los domingos abren).  
- Consejo de la guía: **comprar el sábado por las dudas** si necesitás cocinar.

📖 Más: http://localhost:3000/guias/cracovia/gastronomia
```

### katia

**→** y lo del tip en Polonia: si digo dziękuję al pagar, ¿qué pasa con el vuelto?
*dziękuję = quedate el cambio*

⏱ dispatch `8.4s` · total `8.4s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

```
Buenísimo — lo que anotamos en la guía:

- **Ojo:** decir *“dziękuję”* al darle el dinero **se interpreta como “quedate el cambio”**.  
- Consejo: **no digas dziękuję hasta recibir el vuelto** si querés que te lo den.  
- Doc: *Gastronomía* (Cracovia) — 📖 Más: http://localhost:3000/guias/cracovia/gastronomia
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

⏱ dispatch `7.5s` · total `7.5s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=list_notes

```
- **Anotación:** *Auschwitz — crítico* (Cracovia, pinned).
- **Qué dice:** reservar en *visit.auschwitz.org*; slot preferido *lun/mar 5-6 oct 09:00*; *Educator ~150 PLN*; *Día completo; respeto*; bus *MDA ~1h30*.
- Si querés, mirá la guía de **Cracovia** para logística y alternativas.
```

### bruno

**→** ok y según la guía cuánto sale el tour con educator?
*read guía → ~150 PLN*

⏱ dispatch `7.6s` · total `7.7s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

```
- Según la guía: *tour con educator oficial*: **150 PLN** por adulto.  
- Si buscás paquete desde Cracovia con transporte incluido, la guía marca **~160–250 PLN**.  
- 📖 Más: http://localhost:3000/guias/cracovia/actividades
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

⏱ dispatch `9.2s` · total `9.2s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

```
Perfecto — lo que *tenemos que probar sí o sí* según la guía de Praga:

- **Svíčková na smetaně** (ternera en salsa cremosa con knedlíky) — plato nacional.  
- **Guláš** con knedlíky — contundente y barato (Mlejnice recomendado).  
- **Pivo de tanque (tankové)** — la experiencia cervecera local; 0.5L **50-70 CZK**.  
- **Knedlíky** (dumplings) como acompañamiento en todo.  
- **Smažený sýr** (queso frito) para un comfort food barato.  
- **Koláče / buchty / bábovka** — la repostería checa real (mejor que el trdelník turístico).  
- Si querés foto: **trdelník** está por todos lados pero la guía lo marca como trampa turística.

📖 Más: http://localhost:3000/guias/praga/gastronomia
```

### katia

**→** y según nuestras notas, la propina en Praga es igual que en Polonia?
*nota Propina Chequia vs dziękuję PL*

⏱ dispatch `6.6s` · total `6.6s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=list_notes

```
No, **según nuestras notas no es igual**.  
- En Praga: **redondear / ~10%** y pedir la cuenta con *"Účet, prosím."*  
- Nota aclara: **NO es como Polonia** (el "dziękuję" no reemplaza dar vuelto).  

La anotación está guardada bajo *Propina Chequia* (parada: Praga).
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

⏱ dispatch `6.6s` · total `6.6s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=list_notes

```
Sí, algunas cosas marcadas como urgentes en *nuestras notas* para **Cracovia**:

- *Auschwitz — crítico*: reservar en **visit.auschwitz.org**, slot preferido **lun/mar 5-6 oct 09:00**, Educator ~**150 PLN**; día entero y respeto.  
- *Hostel Cracovia*: **check-in 15:00**, código **4421**.  
- *Domingos*: *Zakaz handlu* — la mayoría de los supermercados cierran; **comprar el sábado** (abren Żabka y gastronomía).  
- Monedas: **PLN** (y otras notas: CHF, CZK, HUF); anotamos *"dziękuję al pagar = quedate el cambio"*.
```

### bruno

**→** bárbaro. ¿cuánto llevamos gastado en Viena?
*cambio a finanzas*

⏱ dispatch `7.9s` · total `7.9s`

🔍 intent=question · canal=qa · outcome=ok · tools=aggregate_expenses

```
📍 *Viena*  
💸 Total gastado: *USD 92,4* (2 gastos).
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

⏱ dispatch `11.7s` · total `11.7s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc,search_guides

```
No hay info en nuestras guías sobre el **IKEA de Viena** ni sus horarios de domingo.  
Revisé la guía *Actividades* y el resto de docs de Viena: no lo menciona.

Si querés, buscá el horario en la **web oficial de IKEA Austria** o en Google Maps; nuestras guías no lo cubren.
```

### katia

**→** ok olvidate. para Interlaken, ¿qué anotamos de lo caro / pases?
*nota Suiza caro / Swiss Travel*

⏱ dispatch `13.1s` · total `13.1s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=list_notes,search_guides,read_guide_doc

```
Perfecto — esto es lo que anotamos sobre lo caro y los pases en Interlaken:

- Nota nuestra *pinned*: **"Suiza caro"** — **CHF**, hacer picnic/ir al súper; **Jungfraujoch carísimo** (mirar Lauterbrunnen/Grindelwald en la guía).  
- Pases: **Eurail** (ya comprado) cubre trenes SBB/BOB y barcos; **teleféricos y trenes de montaña van aparte con −25% con Eurail**.  
- Alternativas: **Swiss Half Fare Card CHF 150 (1 mes)**; **Jungfrau Travel Pass CHF 210 / 3 días** (si vas full montaña); **Swiss Travel Pass desde CHF 254** no conviene.  
- Regla práctica: usar **2–3 días de Eurail** en Suiza y comprar tickets sueltos para teleféricos.  

📖 Más detalle: guía Transporte de Interlaken — http://localhost:3000/guias/interlaken/transporte
```

---

## 7. Frases útiles Polonia (guía país) ✅

**Id:** `frases-polonia` — reproducir con `--only frases-polonia`

**Goal:** Pedidos de idioma: read/search polonia/frases-utiles, no inventar vocabulario.

**Checks deterministas: ✅ pasan**

**Mirar:**
- Turno 1: cita formas de la guía (p.ej. rachunek/proszę, dziękuję). FAIL si inventa frases que no están o responde en checo/húngaro.
- Turno 2: sigue en frases PL (dzień dobry u equivalente de la guía). FAIL si cambia de país o alucina.

**Dónde tocar:** `search/read polonia/frases-utiles · trip_qa follow-up`

### bruno

**→** según nuestras frases útiles de Polonia, cómo pedimos la cuenta y cómo se dice gracias?
*frases-utiles → rachunek / dziękuję*

⏱ dispatch `7.7s` · total `7.7s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=list_guides,read_guide_doc

```
- *La cuenta*: **Rachunek, proszę** (ra-JÚ-nek PRO-she).  
- *Gracias*: **Dziękuję** (dyen-KÚ-ye) — informal **Dzięki** (DYEN-ki).

📖 Más: http://localhost:3000/guias/polonia/frases-utiles
```

### bruno

**→** y hay algo ahí sobre saludar al entrar a un negocio?
*follow-up frases · dzień dobry*

⏱ dispatch `9.3s` · total `9.3s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

```
Sí: la guía dice saludar al entrar.  
- *Saludo*: **Dzień dobry** (buenos días) — usar al entrar a tiendas y restaurantes.  
- En milk bars lo remarcan: entrar con *Dzień dobry* y ser formal/respetuoso.  

📖 Más: http://localhost:3000/guias/polonia/costumbres
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

⏱ dispatch `6.5s` · total `6.5s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=list_notes

```
Tenemos una nota sobre los baños en Budapest (pinned):

- *Széchenyi / Gellért*: **comprar entrada ONLINE** (no reventa en la calle).  
- *Pago*: **efectivo HUF** en OTP Bank.

Eso es todo lo que anotamos sobre baños.
```

### katia

**→** ok y según la guía de actividades, Széchenyi o Gellért — qué conviene?
*budapest/actividades termales*

⏱ dispatch `9.5s` · total `9.5s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

```
Tenemos esa nota pinned:

- *Széchenyi / Gellért*: **comprar entrada ONLINE**.  
- *Pago*: **efectivo HUF** en OTP Bank.

Pero la guía de actividades aclara que **Gellért está CERRADO hasta 2028**, así que conviene ir a *Széchenyi* (icono, piscinas exteriores; **~13,200 HUF** entre semana / **~14,800 HUF** finde).  
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

⏱ dispatch `4.8s` · total `4.8s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=-

```
Después de Viena vamos a:

- **Praga** — llegada: *2026-09-28*  
- **Cracovia** — llegada: *2026-10-03*  
- **Budapest** — llegada: *2026-10-07*
```

### bruno

**→** joya. en Praga, según la guía de transporte, ¿cómo nos movemos en la ciudad?
*praga/transporte*

⏱ dispatch `8.3s` · total `8.3s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

```
Perfecto — según la guía de Transporte de Praga:

- Centro **muy caminable**; usar transporte para distancias largas o lluvia/cuestas.  
- App **PID Lítačka** = lo más barato: **30 min 36 CZK / 90 min 42 CZK / 24h 140 CZK** (activar antes de subir).  
- Red: **metro (A/B/C), tranvías** (22/23 suben al Castillo) y buses; **bus 119** conecta el aeropuerto (ticket 90 min sirve).  
- Taxis: **Bolt / Uber / Liftago**; evitar taxis de calle y cajeros Euronet (DCC).

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

⏱ dispatch `9.6s` · total `9.6s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

```
Un *bar mleczny* es básicamente una **cantina subsidiada (\"milk bar\")** de la era comunista: comida casera polaca muy barata (almuerzo completo **15–25 PLN**, pierogi < **15 PLN**).  
Cómo pedir / costumbres según la guía:  
- Ir temprano: **antes de las 14:00** suelen agotarse platos.  
- Mirás el menú (a veces en polaco) y pedís en la barra o al mostrador; Google Lens ayuda (la guía lo recomienda).  
- Precio en efectivo o tarjeta; **propina ~10% si gustó**. OJO: no digas *“dziękuję”* al entregar el dinero porque en Polonia eso se interpreta como “quedate el cambio” — esperá el vuelto.  
📖 Más: http://localhost:3000/guias/cracovia/gastronomia
```

### katia

**→** ahí hace falta efectivo o va tarjeta? y a qué hora conviene ir?
*follow-up cash + antes 14h*

⏱ dispatch `10.4s` · total `10.4s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides,read_guide_doc

```
Las guías no dicen nada sobre si aceptan **tarjeta** en los milk bars (no está especificado).  

- Mejor llevar **algo de efectivo** por las dudas; la guía sí recomienda que los milk bars son muy baratos (15–25 PLN comida).  
- **Hora:** ir temprano, ideal **antes de las 14:00** (almuerzo 12–15h; muchos platos se agotan).  
- Tip práctico: **propina ~10%** si te gustó y no digas *“dziękuję”* al entregar el dinero hasta recibir el vuelto.  
📖 Más: http://localhost:3000/guias/cracovia/gastronomia
```

### katia

**→** ok gracias. al margen: ¿quién debe plata ahora?
*cambio a finanzas → balance*

⏱ dispatch `6.5s` · total `6.5s`

🔍 intent=question · canal=qa · outcome=ok · tools=-

```
💸 *katia* le debe *USD 3,3* a *bruno*.
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

⏱ dispatch `10.1s` · total `10.1s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=list_guides,search_guides,search_guides

```
Las guías no dicen nada de *Harry Potter* ni en **Lisboa** ni en **Porto**.

- Revisé los docs de *Actividades* de ambas guías.
- Si querés mirar vos: **Lisboa — Actividades** 📖 http://localhost:3000/guias/lisboa/actividades  
- **Porto — Actividades** 📖 http://localhost:3000/guias/porto/actividades
```

### katia

**→** ¿y cuánto sale entrar?
*follow-up sobre el mismo lugar*

⏱ dispatch `9.7s` · total `9.7s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_guides

```
Revisé las guías buscando *Harry Potter* (todas) y **no hay nada sobre atracciones ni precios de entrada** en Lisboa ni en Porto.  

- Las guías no dicen cuánto sale entrar ni mencionan lugares relacionados.
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

⏱ dispatch `5.7s` · total `5.7s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_documents

```
- Está guardado como *Voucher Wombats Viena* (parada **Viena**).  
- *Check-in 15:00*, código *8812* (según la nota).  
- 📎 http://localhost:3000/api/documents/d-viena-hostel
```

### bruno

**→** ¿y la entrada de Auschwitz la tenemos?
*follow-up sobre otro documento, otra parada*

⏱ dispatch `6.5s` · total `6.5s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_documents

```
- Sí — *Entrada Auschwitz* guardada en la parada **Cracovia**.  
- *Fecha y hora: 6-oct, 09:00* (slot) — nota: *educator*.  
- 📎 http://localhost:3000/api/documents/d-auschwitz
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

⏱ dispatch `9.4s` · total `9.4s`

🔍 intent=trip_question · canal=trip · outcome=ok · tools=search_documents,search_documents

```
No, **no tenemos guardado el pasaje de avión de vuelta** en nuestros documentos.  
Lo busqué con los términos *"pasaje de avión de vuelta"* y *"vuelo vuelta"* y no salió nada.  
Si querés que intente con otro nombre exacto (compañía, número de reserva) decime cuál.
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

⏱ dispatch `5.1s` · total `5.1s`

🔍 intent=trip_note · tools=-

```
📝 *Nota*

*Hostel: depósito en efectivo*
El hostel de Praga pide efectivo para el depósito
📍 Praga

_¿Guardo esto?_
[botones]
  · Guardar 📝  (`note_save:hEuLQ_d99Ca5XukJu5YI02jo`)
  · Cancelar  (`note_cancel:hEuLQ_d99Ca5XukJu5YI02jo`)
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

⏱ dispatch `3.3s` · total `3.3s`

🔍 intent=trip_note · tools=-

```
📝 *Nota*

*Free tour*
El free tour sale 11am de la plaza
📍 Viena

_¿Guardo esto?_
[botones]
  · Guardar 📝  (`note_save:9aY4R6Rv_wg6TX49Z72Zn68Q`)
  · Cancelar  (`note_cancel:9aY4R6Rv_wg6TX49Z72Zn68Q`)
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

⏱ dispatch `3.2s` · total `3.2s`

🔍 intent=trip_note · tools=-

```
📝 *Nota*

*Hostel: depósito*
El hostel de Cracovia cobra 20 zloty de depósito en efectivo
📍 Cracovia

_¿Guardo esto?_
[botones]
  · Guardar 📝  (`note_save:3Gz1d_qEJrEWtrIKxuQmvCFM`)
  · Cancelar  (`note_cancel:3Gz1d_qEJrEWtrIKxuQmvCFM`)
```

---

## Resumen latencia

| # | Escenario | Turno | Quién | dispatch_s | total_s |
|---:|---|---:|---|---:|---:|
| 1 | Viena deíctica + follow-up day-trip | 1 | bruno | 12.3 | 12.3 |
| 1 | Viena deíctica + follow-up day-trip | 2 | bruno | 8.7 | 8.7 |
| 2 | Polonia: domingo + dziękuję (guía país + notas) | 1 | katia | 11.2 | 11.2 |
| 2 | Polonia: domingo + dziękuję (guía país + notas) | 2 | katia | 8.4 | 8.4 |
| 3 | Auschwitz: nota propia + precio de la guía | 1 | bruno | 7.5 | 7.5 |
| 3 | Auschwitz: nota propia + precio de la guía | 2 | bruno | 7.6 | 7.7 |
| 4 | Praga comida → propina (cross-doc + nota) | 1 | katia | 9.2 | 9.2 |
| 4 | Praga comida → propina (cross-doc + nota) | 2 | katia | 6.6 | 6.6 |
| 5 | Cambio de canal: guía → plata | 1 | bruno | 6.6 | 6.6 |
| 5 | Cambio de canal: guía → plata | 2 | bruno | 7.9 | 7.9 |
| 6 | Grounding negativo + Suiza caro | 1 | katia | 11.7 | 11.7 |
| 6 | Grounding negativo + Suiza caro | 2 | katia | 13.1 | 13.1 |
| 7 | Frases útiles Polonia (guía país) | 1 | bruno | 7.7 | 7.7 |
| 7 | Frases útiles Polonia (guía país) | 2 | bruno | 9.3 | 9.3 |
| 8 | Budapest: nota baños + guía termales | 1 | katia | 6.5 | 6.5 |
| 8 | Budapest: nota baños + guía termales | 2 | katia | 9.5 | 9.5 |
| 9 | Próxima parada → transporte Praga | 1 | bruno | 4.8 | 4.8 |
| 9 | Próxima parada → transporte Praga | 2 | bruno | 8.3 | 8.3 |
| 10 | Bar mleczny + efectivo PLN (3 turnos) | 1 | katia | 9.6 | 9.6 |
| 10 | Bar mleczny + efectivo PLN (3 turnos) | 2 | katia | 10.4 | 10.4 |
| 10 | Bar mleczny + efectivo PLN (3 turnos) | 3 | katia | 6.5 | 6.5 |
| 11 | Harry Potter en Lisboa o Porto (multi-ciudad + sinónimos) | 1 | katia | 10.1 | 10.1 |
| 11 | Harry Potter en Lisboa o Porto (multi-ciudad + sinónimos) | 2 | katia | 9.7 | 9.7 |
| 12 | Dónde está el voucher del hostel | 1 | bruno | 5.7 | 5.7 |
| 12 | Dónde está el voucher del hostel | 2 | bruno | 6.5 | 6.5 |
| 13 | Documento que no existe | 1 | katia | 9.4 | 9.4 |
| 14 | Dictar una nota con parada explícita | 1 | bruno | 5.1 | 5.1 |
| 15 | Nota sin ciudad → parada de hoy | 1 | katia | 3.3 | 3.3 |
| 16 | Nota que menciona plata | 1 | bruno | 3.2 | 3.2 |

```bash
cd backend
.venv/bin/python scripts/bot_trip_scenario_runner.py
.venv/bin/python scripts/bot_trip_scenario_runner.py --only 2,3,6
```
