import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import TripPaceCard from "./TripPaceCard";
import type { TripBlock, TripPace } from "@/types";

/** El copy de esta tarjeta es lo único que explica que el $/día va sin generales
 *  y la proyección con ellos adentro. Sin test, un refactor lo borra sin ruido. */
const base: TripBlock = {
  status: "in_progress",
  start: "2026-08-05",
  end: "2026-11-18",
  total_nights: 95,
  elapsed_nights: 51,
  total_usd: "9000.00",
  general_usd: "1768.50",
  general_per_day_usd: "18.61",
  avg_per_day_usd: "100.00",
  run_rate_usd: "105.30",
  accrued_usd: "6000.00",
  projected_total_usd: "11701.40",
};

const pace = (trip: Partial<TripBlock>): TripPace => ({
  trip: { ...base, ...trip },
  cities: [],
  as_of: "2026-09-25",
});

describe("TripPaceCard", () => {
  it("aclara que el ritmo excluye generales", () => {
    render(<TripPaceCard pace={pace({})} />);
    // Las cifras grandes van en dólares enteros (precisión "whole"): 105,30 → 105.
    expect(screen.getByText(/USD 105$/)).toBeTruthy();
    expect(screen.getByText("en ciudades · sin generales")).toBeTruthy();
  });

  it("muestra generales aparte y la proyección diciendo que los incluye", () => {
    render(<TripPaceCard pace={pace({})} />);
    expect(screen.getByText("Generales aparte")).toBeTruthy();
    expect(screen.getByText("USD 1.769")).toBeTruthy();
    expect(screen.getByText("Proyección del viaje")).toBeTruthy();
    expect(screen.getByText("incluye generales")).toBeTruthy();
    expect(screen.getByText("USD 11.701")).toBeTruthy();
  });

  it("sin generales no promete que la proyección los incluya", () => {
    render(<TripPaceCard pace={pace({ general_usd: "0", general_per_day_usd: null })} />);
    expect(screen.queryByText("Generales aparte")).toBeNull();
    expect(screen.getByText("Proyección del viaje")).toBeTruthy();
    expect(screen.queryByText("incluye generales")).toBeNull();
  });

  it("no proyecta con menos de 3 noches vividas", () => {
    // Dos días de gasto no son un ritmo; proyectar ahí daba números absurdos.
    render(<TripPaceCard pace={pace({ elapsed_nights: 2 })} />);
    expect(screen.queryByText("Proyección del viaje")).toBeNull();
  });

  it("antes de arrancar muestra lo comprometido, no un run-rate", () => {
    render(<TripPaceCard pace={pace({ status: "not_started", run_rate_usd: null })} />);
    expect(screen.getByText(/\/día previsto/)).toBeTruthy();
    expect(screen.getByText(/comprometidos/)).toBeTruthy();
    expect(screen.queryByText("Proyección del viaje")).toBeNull();
  });

  it("terminado resume el total en noches", () => {
    render(<TripPaceCard pace={pace({ status: "finished" })} />);
    expect(screen.getByText(/Viaje terminado/)).toBeTruthy();
    expect(screen.queryByText("Proyección del viaje")).toBeNull();
  });
});
