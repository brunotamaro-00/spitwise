import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MovementRow from "./MovementRow";

const mv = {
  id: 1, type: "expense", amount: "45.00", currency: "GBP", amount_usd: "57.15",
  fx_rate: "1.27", fx_source: "frankfurter", paid_by: 1, split: "shared",
  description: "cena", category_id: 2, stop_slug: "londres", city_name: "Londres",
  movement_date: "2026-08-06",
};

describe("MovementRow", () => {
  it("muestra USD y moneda original", () => {
    render(<MovementRow mv={mv} onEdit={() => {}} onDelete={() => {}} />);
    expect(screen.getByText(/57\.15/)).toBeTruthy();
    expect(screen.getByText(/GBP 45\.00/)).toBeTruthy();
  });
});
