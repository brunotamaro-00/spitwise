import { describe, expect, it } from "vitest";

import {
  formatAmount,
  formatDayHeader,
  formatShortDate,
  formatUsd,
  isZeroMoney,
  normalizeAmountInput,
  parseMoney,
  sanitizeAmountInput,
  toInputValue,
} from "./format";

describe("format", () => {
  it("formatUsd usa coma decimal, punto de miles y siempre 1 decimal", () => {
    expect(formatUsd("1234.5")).toBe("USD 1.234,5");
    expect(formatUsd("174.33")).toBe("USD 174,3");
    expect(formatUsd("20.55")).toBe("USD 20,6");
  });
  it("formatUsd de un entero también muestra 1 decimal (estándar único)", () => {
    expect(formatUsd("20")).toBe("USD 20,0");
    expect(formatUsd("370")).toBe("USD 370,0");
  });
  it("formatAmount siempre con 1 decimal", () => {
    expect(formatAmount("20.00")).toBe("20,0");
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
  it("sanitizeAmountInput filtra símbolos y limita a 2 decimales tras la coma", () => {
    expect(sanitizeAmountInput("20a,5!0")).toBe("20,50");
    expect(sanitizeAmountInput("20,505")).toBe("20,50");
    expect(sanitizeAmountInput("1.234,509")).toBe("1.234,50");
    expect(sanitizeAmountInput("1234")).toBe("1234");
  });
  it("isZeroMoney", () => {
    expect(isZeroMoney("0")).toBe(true);
    expect(isZeroMoney("0.00")).toBe(true);
    expect(isZeroMoney("")).toBe(true);
    expect(isZeroMoney(null)).toBe(true);
    expect(isZeroMoney("0.01")).toBe(false);
    expect(isZeroMoney("12.5")).toBe(false);
  });
  it("parseMoney", () => {
    expect(parseMoney("50.00")).toBe(50);
  });
  it("fechas en dd/mm sin corrimiento de zona horaria", () => {
    expect(formatShortDate("2026-08-06")).toBe("06/08");
    expect(formatDayHeader("2026-08-06")).toMatch(/^\w+\.? 06\/08$/);
  });
});
