import { describe, expect, it } from "vitest";

import {
  formatAmount,
  formatDayHeader,
  formatShortDate,
  formatUsd,
  isValidAmountInput,
  isZeroMoney,
  normalizeAmountInput,
  parseMoney,
  sanitizeAmountInput,
  toInputValue,
} from "./format";

describe("format", () => {
  it("formatUsd usa coma decimal, punto de miles y centavos por default", () => {
    expect(formatUsd("1234.5")).toBe("USD 1.234,50");
    expect(formatUsd("174.33")).toBe("USD 174,33");
    expect(formatUsd("20.55")).toBe("USD 20,55");
    expect(formatUsd("20")).toBe("USD 20,00");
  });
  // Las cifras de titular (hero, KPI, chips) van sin decimales: el centavo es
  // ruido a 60px y además no entraba en el ancho de un iPhone.
  it("formatUsd 'whole' redondea a dólares enteros", () => {
    expect(formatUsd("12345.6", "whole")).toBe("USD 12.346");
    expect(formatUsd("105.30", "whole")).toBe("USD 105");
    expect(formatUsd("370", "whole")).toBe("USD 370");
  });
  it("formatAmount con centavos, y 'whole' cuando se lo pide", () => {
    expect(formatAmount("20.00")).toBe("20,00");
    expect(formatAmount("20.50")).toBe("20,50");
    expect(formatAmount("1234.56")).toBe("1.234,56");
    expect(formatAmount("1234.56", "whole")).toBe("1.235");
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
  // El bug que arregla: "1.500" (separador de miles de es-AR, sin coma) se
  // mandaba como 1.5 y el gasto entraba mil veces más chico, sin error visible.
  it("normalizeAmountInput lee el punto como miles solo en grupos de 3", () => {
    expect(normalizeAmountInput("1.500")).toBe("1500");
    expect(normalizeAmountInput("12.500")).toBe("12500");
    expect(normalizeAmountInput("1.234.500")).toBe("1234500");
    // Grupos que no son de 3 dígitos siguen siendo decimales (hábito en-US).
    expect(normalizeAmountInput("20.50")).toBe("20.50");
    expect(normalizeAmountInput("20.5")).toBe("20.5");
    expect(normalizeAmountInput("0.75")).toBe("0.75");
    // Con coma decimal manda la coma, pase lo que pase con los puntos.
    expect(normalizeAmountInput("1.500,25")).toBe("1500.25");
  });
  it("isValidAmountInput rechaza vacío, cero y negativos", () => {
    expect(isValidAmountInput("20,50")).toBe(true);
    expect(isValidAmountInput("1.500")).toBe(true);
    expect(isValidAmountInput("")).toBe(false);
    expect(isValidAmountInput("0")).toBe(false);
    expect(isValidAmountInput("0,00")).toBe(false);
    expect(isValidAmountInput(",")).toBe(false);
    expect(isValidAmountInput("-5")).toBe(false);
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
