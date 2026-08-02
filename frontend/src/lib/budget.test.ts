import { describe, expect, it } from "vitest";

import {
  bandGeometry,
  bandLabel,
  bandLevel,
  categoryPerDay,
  levelTone,
  coverageLine,
  currentVerdict,
  cushionRead,
  projectionRead,
  stayProgress,
} from "@/lib/budget";
import type { CurrentCityBudget, TripCushion } from "@/types";

const base: CurrentCityBudget = {
  stop_slug: "viena",
  city_name: "Viena",
  country_flag: "🇦🇹",
  arrival_date: "2026-09-23",
  departure_date: "2026-09-28",
  lived_nights: 3,
  total_nights: 5,
  remaining_days: 3,
  target_min_usd: "56.00",
  target_max_usd: "70.00",
  target_daily_usd: "63.00",
  living_usd: "102.00",
  living_per_day_usd: "34.00",
  budget_to_date_usd: "189.00",
  variance_usd: "-87.00",
  remaining_budget_usd: "213.00",
  remaining_daily_usd: "71.00",
  band_position: "under",
  edge_delta_pct: -39.3,
  delta_pct: -46,
  by_category: [],
};

const cur = (over: Partial<CurrentCityBudget>): CurrentCityBudget => ({ ...base, ...over });

describe("currentVerdict", () => {
  it("con margen devuelve el sobrante por día y los días que quedan", () => {
    expect(currentVerdict(base)).toEqual({ kind: "margin", amountUsd: "71.00", days: 3 });
  });

  it("pasado de presupuesto muestra el excedente TOTAL, no el por día negativo", () => {
    const v = currentVerdict(cur({ remaining_daily_usd: "-103.32", remaining_budget_usd: "-103.32" }));
    expect(v).toEqual({ kind: "over", amountUsd: "103.32" });
  });

  it("sin plan no hay veredicto", () => {
    expect(currentVerdict(cur({ target_daily_usd: null, remaining_daily_usd: null })).kind).toBe(
      "no_target",
    );
  });

  it("un remanente de exactamente cero sigue siendo margen, no sobregiro", () => {
    expect(currentVerdict(cur({ remaining_daily_usd: "0.00" })).kind).toBe("margin");
  });
});

describe("bandLevel / levelTone / bandLabel", () => {
  it("recorre la rampa de ahorro a pasarse fuerte", () => {
    expect(bandLevel(30, 40, 60)).toBe("save");
    expect(bandLevel(45, 40, 60)).toBe("plan");
    expect(bandLevel(58, 40, 60)).toBe("edge");   // último cuarto de la banda
    expect(bandLevel(65, 40, 60)).toBe("over");   // +8% del techo
    expect(bandLevel(90, 40, 60)).toBe("far");    // +50%
  });

  it("una banda de ancho cero cae en 'plan', nunca en 'al límite'", () => {
    expect(bandLevel(50, 50, 50)).toBe("plan");
  });

  it("fuera del eje de la barra el color se hace cargo, sea cual sea el plan", () => {
    // Un plan holgado (110–115) gastando 125: solo +9% del techo, pero la barra
    // ya no puede crecer, así que el nivel tiene que decirlo igual.
    expect(bandLevel(125, 110, 115)).toBe("far");
  });

  it("sin ritmo (parada futura) no hay nivel", () => {
    expect(bandLevel(null, 40, 60)).toBeNull();
    expect(levelTone(null)).toBe("neutral");
  });

  it("cada paso tiene su tono, y pasarse fuerte sí es rojo", () => {
    expect(levelTone("save")).toBe("teal");
    expect(levelTone("plan")).toBe("green");
    expect(levelTone("edge")).toBe("amber");
    expect(levelTone("over")).toBe("orange");
    expect(levelTone("far")).toBe("red");
  });

  it("adentro del rango el texto avisa si está pegado al techo", () => {
    expect(bandLabel("in", null)).toBe("en plan");
    expect(bandLabel("in", null, "edge")).toBe("al límite");
  });

  it("solo afuera del rango se muestra un %, y contra el borde violado", () => {
    expect(bandLabel("over", 9.4)).toBe("+9%");
    expect(bandLabel("under", -25)).toBe("ahorrando");
  });

  it("sin posición (futura o sin plan) no hay veredicto", () => {
    expect(bandLabel(null, 30)).toBeNull();
  });

  it("pasado sin % no queda con un '+0%' vacío", () => {
    expect(bandLabel("over", null)).toBe("pasado");
  });
});

describe("categoryPerDay", () => {
  const row = (per: string | null, delta: string | null) => ({
    per_day_usd: per,
    delta_per_day_usd: delta,
  });

  it("todo rubro con gasto lleva su comparación, no solo los desviados", () => {
    expect(categoryPerDay(row("25.00", "10.40"))?.delta).toBe("+USD 10 vs tu promedio");
    expect(categoryPerDay(row("8.00", "-2.10"))?.delta).toBe("−USD 2 vs tu promedio");
  });

  it("un delta que redondea a cero se dice con palabras, no como '+USD 0'", () => {
    expect(categoryPerDay(row("8.00", "0.37"))?.delta).toBe("igual que tu promedio");
    expect(categoryPerDay(row("8.00", "-0.40"))?.delta).toBe("igual que tu promedio");
  });

  it("sin días vividos no hay $/día que inventar", () => {
    expect(categoryPerDay(row(null, null))).toBeNull();
  });

  it("sin promedio del viaje se muestra el ritmo solo", () => {
    expect(categoryPerDay(row("25.00", null))).toEqual({
      rate: "USD 25/día",
      delta: null,
    });
  });
});

describe("bandGeometry", () => {
  it("el eje es fijo: el mismo gasto ocupa lo mismo con planes distintos", () => {
    // Es TODO el punto de la escala fija: antes cada barra se escalaba contra
    // su propia banda y dos ciudades muy distintas dibujaban lo mismo.
    expect(bandGeometry(68, 95, 81).value).toBe(bandGeometry(20, 30, 81).value);
    expect(bandGeometry(68, 95, 81).value).toBeCloseTo(67.5);  // 81 de 120
    // Y el plan de cada una cae en lugares distintos, que es lo que se escanea.
    expect(bandGeometry(68, 95, 81).bandStart).toBeCloseTo(56.67);
    expect(bandGeometry(20, 30, 81).bandStart).toBeCloseTo(16.67);
  });

  it("la banda más cara del itinerario entra entera en el eje", () => {
    const g = bandGeometry(71, 104, 90);
    expect(g.bandClipped).toBe(false);
    expect(g.bandStart + g.bandWidth).toBeLessThan(100);
  });

  it("un gasto por encima del eje capea y lo declara", () => {
    const g = bandGeometry(40, 60, 500);
    expect(g.value).toBe(100);
    expect(g.overCap).toBe(true);
  });

  it("adentro del eje no hay tope que marcar", () => {
    expect(bandGeometry(40, 60, 119).overCap).toBe(false);
    expect(bandGeometry(40, 60, null).overCap).toBe(false);
  });

  it("un plan más caro que el eje se declara recortado", () => {
    expect(bandGeometry(110, 140, 120).bandClipped).toBe(true);
    expect(bandGeometry(40, 60, 50).bandClipped).toBe(false);
  });

  it("sin gasto (parada futura) solo se dibuja el plan", () => {
    expect(bandGeometry(40, 60, null).value).toBeNull();
  });

  it("una banda de ancho cero no rompe la escala", () => {
    const g = bandGeometry(50, 50, 50);
    expect(g.bandWidth).toBe(0);
    expect(Number.isFinite(g.center)).toBe(true);
  });
});

const cushion = (over: Partial<TripCushion>): TripCushion => ({
  covered_nights: 20,
  budget_to_date_usd: "500.00",
  living_to_date_usd: "250.00",
  cushion_usd: "250.00",
  remaining_nights: 10,
  needed_daily_usd: "75.00",
  avg_target_daily_usd: "50.00",
  needed_delta_pct: 50,
  ...over,
});

describe("cushionRead", () => {
  it("colchón positivo", () => {
    expect(cushionRead(cushion({}))).toEqual({
      kind: "ahead",
      amountUsd: "250",
      neededUsd: "75.00",
      remainingNights: 10,
    });
  });

  it("pasarse se dice, con el monto en positivo y el signo en el kind", () => {
    const r = cushionRead(cushion({ cushion_usd: "-90.50" }));
    expect(r.kind).toBe("behind");
    expect(r).toMatchObject({ amountUsd: "90.5" });
  });

  it("sin planes cargados no hay colchón que mostrar", () => {
    expect(cushionRead(cushion({ cushion_usd: null, covered_nights: 0 })).kind).toBe("none");
  });

  it("cero es colchón, no sobregiro", () => {
    expect(cushionRead(cushion({ cushion_usd: "0.00" })).kind).toBe("ahead");
  });
});

describe("coverageLine", () => {
  it("cobertura completa", () => {
    const c = coverageLine(108, 108, []);
    expect(c.complete).toBe(true);
    expect(c.text).toMatch(/108 noches/);
  });

  it("cobertura parcial nombra las paradas que faltan", () => {
    const c = coverageLine(105, 108, ["Margen flex"]);
    expect(c.complete).toBe(false);
    expect(c.text).toMatch(/Margen flex/);
    expect(c.text).toMatch(/3 noches de 108/);
  });

  it("con más de tres sin plan, resume el resto", () => {
    const c = coverageLine(10, 40, ["Praga", "Viena", "Roma", "Madrid", "Bled"]);
    expect(c.text).toMatch(/Praga, Viena, Roma y 2 más/);
  });

  it("sin nombres a mano no deja el prefijo colgado", () => {
    const c = coverageLine(105, 108, []);
    expect(c.text).toBe("3 noches de 108 sin plan");
    expect(c.text).not.toMatch(/:/);
  });

  it("sin ningún plan lo dice explícito", () => {
    expect(coverageLine(0, 108, []).text).toMatch(/Ninguna parada/);
  });

  it("sin itinerario no inventa cobertura", () => {
    expect(coverageLine(0, 0, []).complete).toBe(false);
  });
});

describe("stayProgress", () => {
  it("cuenta días vividos, nunca los que faltan", () => {
    expect(stayProgress(3, 5)).toBe("día 3 de 5");
  });
});

describe("projectionRead", () => {
  const p = (projected: string | null) => ({
    projected_living_usd: projected,
    living_budget_min_usd: "5000.00",
    living_budget_max_usd: "8000.00",
  });

  it("adentro del rango NO es un desvío: ese es el punto de tener un rango", () => {
    expect(projectionRead(p("7992.00"))).toEqual({ kind: "inside" });
  });

  it("arriba del techo mide contra el techo, no contra el centro", () => {
    expect(projectionRead(p("8500.00"))).toEqual({ kind: "over", amountUsd: "500" });
  });

  it("abajo del piso mide contra el piso", () => {
    expect(projectionRead(p("4200.00"))).toEqual({ kind: "under", amountUsd: "800" });
  });

  it("sin proyección todavía no dice nada", () => {
    expect(projectionRead(p(null)).kind).toBe("none");
  });

  it("justo sobre el borde sigue siendo adentro", () => {
    expect(projectionRead(p("8000.00")).kind).toBe("inside");
  });
});
