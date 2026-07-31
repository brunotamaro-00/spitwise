import { describe, expect, it } from "vitest";

import { coverageLine, currentVerdict, stayProgress } from "@/lib/budget";
import type { CurrentCityBudget } from "@/types";

const base: CurrentCityBudget = {
  stop_slug: "viena",
  city_name: "Viena",
  country_flag: "🇦🇹",
  arrival_date: "2026-09-23",
  departure_date: "2026-09-28",
  lived_nights: 3,
  total_nights: 5,
  remaining_days: 3,
  target_daily_usd: "63.00",
  living_usd: "102.00",
  living_per_day_usd: "34.00",
  budget_to_date_usd: "189.00",
  variance_usd: "-87.00",
  remaining_budget_usd: "213.00",
  remaining_daily_usd: "71.00",
  delta_pct: -46,
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

  it("sin target no hay veredicto", () => {
    expect(currentVerdict(cur({ target_daily_usd: null, remaining_daily_usd: null })).kind).toBe(
      "no_target",
    );
  });

  it("un remanente de exactamente cero sigue siendo margen, no sobregiro", () => {
    expect(currentVerdict(cur({ remaining_daily_usd: "0.00" })).kind).toBe("margin");
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

  it("con más de tres sin presupuesto, resume el resto", () => {
    const c = coverageLine(10, 40, ["Praga", "Viena", "Roma", "Madrid", "Bled"]);
    expect(c.text).toMatch(/Praga, Viena, Roma y 2 más/);
  });

  it("sin nombres a mano no deja el prefijo colgado", () => {
    const c = coverageLine(105, 108, []);
    expect(c.text).toBe("3 noches de 108 sin presupuesto");
    expect(c.text).not.toMatch(/:/);
  });

  it("sin ningún presupuesto lo dice explícito", () => {
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
