import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Movement } from "@/types";
import MovementRow from "./MovementRow";

const mv: Movement = {
  id: 1, type: "expense", amount: "45.00", currency: "GBP", amount_usd: "57.15",
  fx_rate: "1.27", fx_source: "frankfurter", paid_by: 1, split: "shared",
  description: "cena", category_id: 2, stop_slug: "londres", city_name: "Londres",
  payment_date: null, status: "confirmed",
  cashback_kind: null, cashback_value: null,
  created_at: "2026-08-06T12:00:00Z",
};

describe("MovementRow", () => {
  it("muestra USD y moneda original con coma decimal y centavos", () => {
    render(<MovementRow mv={mv} onEdit={() => {}} onDelete={() => {}} />);
    // Las filas van con centavos: son el dato, no una cifra de titular.
    expect(screen.getByText("USD 57,15")).toBeTruthy();
    expect(screen.getByText(/GBP 45,00/)).toBeTruthy();
  });

  it("muestra la parte del usuario logueado", () => {
    render(<MovementRow mv={mv} myId={1} onEdit={() => {}} onDelete={() => {}} />);
    // shared: mitad de 57,15 = 28,575 -> "USD 28,58"
    expect(screen.getByText(/tu parte USD 28,58/i)).toBeTruthy();
  });

  it("marca los pendientes con un pill", () => {
    const pending: Movement = { ...mv, status: "pending", payment_date: "2026-09-03" };
    render(<MovementRow mv={pending} onEdit={() => {}} onDelete={() => {}} />);
    expect(screen.getByText(/pendiente/i)).toBeTruthy();
  });
});
