import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import BalanceHero from "./BalanceHero";

describe("BalanceHero", () => {
  it("muestra deuda", () => {
    render(<BalanceHero balance={{ debtor_id: 2, creditor_id: 1, amount_usd: "320.50" }}
      names={{ 1: "Bruno", 2: "Katia" }} onSettle={() => {}} />);
    expect(screen.getByText(/Katia/)).toBeTruthy();
    expect(screen.getByText(/320,5/)).toBeTruthy();
  });
  it("verde cuando me deben a mí (soy acreedor)", () => {
    const { container } = render(
      <BalanceHero balance={{ debtor_id: 2, creditor_id: 1, amount_usd: "9.70" }}
        names={{ 1: "Katia", 2: "Bruno" }} myId={1} onSettle={() => {}} />);
    expect(container.querySelector(".text-success")).toBeTruthy();
    expect(container.querySelector(".text-brick")).toBeNull();
  });
  it("rojo cuando yo debo (soy deudor)", () => {
    const { container } = render(
      <BalanceHero balance={{ debtor_id: 2, creditor_id: 1, amount_usd: "9.70" }}
        names={{ 1: "Katia", 2: "Bruno" }} myId={2} onSettle={() => {}} />);
    expect(container.querySelector(".text-brick")).toBeTruthy();
    expect(container.querySelector(".text-success")).toBeNull();
  });
  it("a mano cuando 0", () => {
    render(<BalanceHero balance={{ debtor_id: null, creditor_id: null, amount_usd: "0" }}
      names={{}} onSettle={() => {}} />);
    expect(screen.getByText(/a mano/i)).toBeTruthy();
  });
});
