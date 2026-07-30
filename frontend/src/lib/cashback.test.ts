import { describe, expect, it } from "vitest";

import { cashbackLabel, netAmount } from "./cashback";

const base = { amount: "20", currency: "EUR", cashback_kind: null, cashback_value: null };

describe("netAmount", () => {
  it("sin cashback devuelve el bruto", () => {
    expect(netAmount(base)).toBe(20);
  });

  it("pct resta el porcentaje", () => {
    expect(netAmount({ ...base, cashback_kind: "pct", cashback_value: "2" })).toBeCloseTo(19.6);
  });

  it("amount resta el monto fijo", () => {
    expect(netAmount({ ...base, cashback_kind: "amount", cashback_value: "5" })).toBe(15);
  });

  it("no baja de cero", () => {
    expect(netAmount({ amount: "5", cashback_kind: "amount", cashback_value: "9" })).toBe(0);
  });
});

describe("cashbackLabel", () => {
  it("null sin cashback", () => {
    expect(cashbackLabel(base)).toBeNull();
  });

  // Etiqueta compacta, sin ceros de relleno: en un badge de 10px "2,00%" es ruido.
  it("porcentaje", () => {
    expect(cashbackLabel({ ...base, cashback_kind: "pct", cashback_value: "2" })).toBe("2%");
    expect(cashbackLabel({ ...base, cashback_kind: "pct", cashback_value: "2.5" })).toBe("2,5%");
  });

  it("monto fijo con símbolo de moneda", () => {
    expect(cashbackLabel({ ...base, cashback_kind: "amount", cashback_value: "5" })).toBe("5 €");
  });
});
