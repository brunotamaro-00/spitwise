import { describe, expect, it } from "vitest";

import { formatAmount, formatUsd, normalizeAmountInput, parseMoney, toInputValue } from "./format";

describe("format", () => {
  it("formatUsd usa coma decimal, punto de miles y 1 decimal", () => {
    expect(formatUsd("1234.5")).toBe("USD 1.234,5");
    expect(formatUsd("174.33")).toBe("USD 174,3");
  });
  it("formatUsd de un entero no muestra decimales", () => {
    expect(formatUsd("20")).toBe("USD 20");
  });
  it("formatAmount", () => {
    expect(formatAmount("20.00")).toBe("20");
    expect(formatAmount("20.50")).toBe("20,5");
  });
  it("toInputValue", () => {
    expect(toInputValue("20.00")).toBe("20");
    expect(toInputValue("20.50")).toBe("20,5");
    expect(toInputValue("")).toBe("");
  });
  it("normalizeAmountInput", () => {
    expect(normalizeAmountInput("20,50")).toBe("20.50");
    expect(normalizeAmountInput("1.234,50")).toBe("1234.50");
    expect(normalizeAmountInput("20.50")).toBe("20.50");
  });
  it("parseMoney", () => {
    expect(parseMoney("50.00")).toBe(50);
  });
});
