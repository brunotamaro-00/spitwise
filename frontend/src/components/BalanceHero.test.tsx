import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import BalanceHero from "./BalanceHero";

describe("BalanceHero", () => {
  it("muestra deuda", () => {
    render(<BalanceHero balance={{ debtor_id: 2, creditor_id: 1, amount_usd: "320.00" }}
      names={{ 1: "Bruno", 2: "Katia" }} onSettle={() => {}} />);
    expect(screen.getByText(/Katia/)).toBeTruthy();
    expect(screen.getByText(/320\.00/)).toBeTruthy();
  });
  it("a mano cuando 0", () => {
    render(<BalanceHero balance={{ debtor_id: null, creditor_id: null, amount_usd: "0" }}
      names={{}} onSettle={() => {}} />);
    expect(screen.getByText(/a mano/i)).toBeTruthy();
  });
});
