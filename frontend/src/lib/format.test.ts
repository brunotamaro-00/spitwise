import { describe, expect, it } from "vitest";

import { formatUsd, parseMoney } from "./format";

describe("format", () => {
  it("formatUsd", () => {
    expect(formatUsd("1234.5")).toBe("USD 1,234.50");
  });
  it("parseMoney", () => {
    expect(parseMoney("50.00")).toBe(50);
  });
});
