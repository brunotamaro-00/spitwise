import { describe, expect, it } from "vitest";

import type { Movement } from "@/types";
import { needsConfirmation } from "./share";

const base: Movement = {
  id: 1, type: "expense", amount: "100", currency: "USD", amount_usd: "100",
  fx_rate: "1", fx_source: "manual", paid_by: 1, split: "shared",
  description: "hostel (2/2)", category_id: 1, stop_slug: "viena", city_name: "Viena",
  payment_date: null, status: "confirmed",
  cashback_kind: null, cashback_value: null, created_at: "2026-07-01T12:00:00Z",
};

// Fecha del VIAJE (TripPace.as_of), no del dispositivo.
const TODAY = "2026-07-21";

describe("needsConfirmation", () => {
  it("un confirmado normal no necesita confirmación", () => {
    expect(needsConfirmation(base, TODAY)).toBe(false);
  });

  it("awaiting siempre necesita confirmación", () => {
    expect(needsConfirmation({ ...base, status: "awaiting", payment_date: "2026-07-14" }, TODAY)).toBe(true);
  });

  it("pending con fecha a 1 día entra (caso 'desde 1 día antes')", () => {
    expect(needsConfirmation({ ...base, status: "pending", payment_date: "2026-07-22" }, TODAY)).toBe(true);
  });

  it("pending que vence hoy también entra", () => {
    expect(needsConfirmation({ ...base, status: "pending", payment_date: "2026-07-21" }, TODAY)).toBe(true);
  });

  it("pending a más de 1 día todavía no entra", () => {
    expect(needsConfirmation({ ...base, status: "pending", payment_date: "2026-07-23" }, TODAY)).toBe(false);
  });

  it("settlements nunca entran", () => {
    expect(needsConfirmation({ ...base, type: "settlement", status: "awaiting" }, TODAY)).toBe(false);
  });
});
