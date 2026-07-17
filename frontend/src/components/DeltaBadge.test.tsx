import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import DeltaBadge from "./DeltaBadge";

describe("DeltaBadge", () => {
  it("no renderiza sin delta (ciudad futura)", () => {
    const { container } = render(<DeltaBadge pct={null} />);
    expect(container.innerHTML).toBe("");
  });
  it("ámbar por encima del promedio", () => {
    const { container } = render(<DeltaBadge pct={40.4} />);
    expect(screen.getByText(/\+40% vs promedio/)).toBeTruthy();
    expect(container.querySelector(".text-accent-amber")).toBeTruthy();
  });
  it("teal por debajo del promedio", () => {
    const { container } = render(<DeltaBadge pct={-15.2} />);
    expect(screen.getByText(/-15% vs promedio/)).toBeTruthy();
    expect(container.querySelector(".text-accent-teal")).toBeTruthy();
  });
  it("neutro dentro de ±10%", () => {
    const { container } = render(<DeltaBadge pct={4} />);
    expect(screen.getByText(/\+4% vs promedio/)).toBeTruthy();
    expect(container.querySelector(".text-accent-amber")).toBeNull();
    expect(container.querySelector(".text-accent-teal")).toBeNull();
  });
});
