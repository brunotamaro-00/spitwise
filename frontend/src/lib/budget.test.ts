import { describe, expect, it } from "vitest";

import {
  bandGeometry,
  bandLabel,
  bandTone,
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

describe("bandTone / bandLabel", () => {
  it("debajo del piso es ahorro, arriba del techo es aviso", () => {
    expect(bandTone("under")).toBe("teal");
    expect(bandTone("over")).toBe("amber");
  });

  it("adentro del rango el tono es neutro: estar en plan es lo esperado", () => {
    expect(bandTone("in")).toBe("neutral");
    expect(bandLabel("in", null)).toBe("en plan");
  });

  it("solo afuera del rango se muestra un %, y contra el borde violado", () => {
    expect(bandLabel("over", 9.4)).toBe("+9%");
    expect(bandLabel("under", -25)).toBe("ahorrando");
  });

  it("sin posición (futura o sin plan) no hay veredicto", () => {
    expect(bandLabel(null, 30)).toBeNull();
    expect(bandTone(null)).toBe("neutral");
  });

  it("pasado sin % no queda con un '+0%' vacío", () => {
    expect(bandLabel("over", null)).toBe("pasado");
  });
});

describe("bandGeometry", () => {
  it("deja aire arriba del techo: la zona del plan nunca llena la barra", () => {
    const g = bandGeometry(40, 60, 50);
    expect(g.bandStart + g.bandWidth).toBeLessThan(100);
    expect(g.center).toBeGreaterThan(g.bandStart);
    expect(g.center).toBeLessThan(g.bandStart + g.bandWidth);
  });

  it("un gasto muy por encima del techo no se sale de la barra", () => {
    const g = bandGeometry(40, 60, 500);
    expect(g.value).toBeLessThanOrEqual(100);
    expect(g.value).toBeGreaterThan(g.bandStart + g.bandWidth);
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
