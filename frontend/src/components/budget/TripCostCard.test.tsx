import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import TripCostCard from "./TripCostCard";
import type { FixedBlock, TripCost } from "@/types";

/** Este bloque es el único lugar de la app que dice cuánto sale el viaje, y todo
 *  su valor está en el copy: que el total es un estimado, que el alojamiento
 *  tiene noches sin reservar puestas a precio, y que los generales van enteros.
 *  Sin test, un refactor lo borra sin ruido. */
const fixed: FixedBlock = {
  lodging_usd: "2646.72",
  general_usd: "1888.50",
  total_usd: "4535.22",
  booked_nights: 59,
  total_nights: 108,
  per_night_usd: "44.86",
};

const base: TripCost = {
  unbooked_nights: 49,
  lodging_estimated_usd: "2198.12",
  lodging_projected_usd: "4844.84",
  living_usd: "7991.77",
  general_usd: "1888.50",
  total_usd: "14725.12",
  basis: "projected",
  lodging_is_estimated: true,
};

const cost = (over: Partial<TripCost>): TripCost => ({ ...base, ...over });

describe("TripCostCard", () => {
  it("el total manda y las tres filas dicen de qué está hecho", () => {
    render(<TripCostCard cost={base} fixed={fixed} />);
    expect(screen.getByText("costo estimado del viaje")).toBeTruthy();
    expect(screen.getByText("USD 14.725")).toBeTruthy();
    expect(screen.getByText("USD 7.992")).toBeTruthy();   // vivir
    expect(screen.getByText("USD 4.845")).toBeTruthy();   // alojamiento
    expect(screen.getByText("USD 1.889")).toBeTruthy();   // generales
    expect(screen.getByText("vuelos, pases, seguros")).toBeTruthy();
  });

  it("dice cuántas noches faltan reservar y a qué precio se estimaron", () => {
    render(<TripCostCard cost={base} fixed={fixed} />);
    expect(screen.getByText("59 de 108 noches reservadas · USD 45/noche estimado")).toBeTruthy();
  });

  it("sin ciudades cerradas no promete una proyección", () => {
    render(
      <TripCostCard
        cost={cost({ basis: "committed", lodging_is_estimated: false })}
        fixed={{ ...fixed, booked_nights: 108 }}
      />,
    );
    expect(screen.getByText("comprometido hasta hoy")).toBeTruthy();
    expect(screen.getByText("lo que llevan gastado hasta hoy")).toBeTruthy();
  });

  // El veredicto contra la banda es trabajo de /presupuesto: acá no hay color.
  it("no muestra el veredicto del plan si no se lo pasan", () => {
    render(<TripCostCard cost={base} fixed={fixed} />);
    expect(screen.queryByText(/El plan mide solo vivir/i)).toBeNull();
  });
});
