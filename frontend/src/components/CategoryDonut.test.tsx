import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import CategoryDonut from "./CategoryDonut";
import type { CategorySpend } from "@/types";

/** Dos gajos que suman 10.227,40 (→ USD 10.227 enteros) mientras el summary
 *  canónico es 10.227,60 (→ USD 10.228). Sin `totalUsd` el centro mentía. */
const slices: CategorySpend[] = [
  { category_id: 1, name: "Comida", icon: null, total_usd: "6000.20" },
  { category_id: 2, name: "Alojamiento", icon: null, total_usd: "4227.20" },
];

describe("CategoryDonut", () => {
  it("el centro usa totalUsd canónico, no la suma redondeada de gajos", () => {
    render(<CategoryDonut data={slices} totalUsd="10227.60" />);
    // Hero y donut deben decir lo mismo: 10.227,60 → USD 10.228
    expect(screen.getByText("USD 10.228")).toBeTruthy();
    expect(screen.queryByText("USD 10.227")).toBeNull();
  });

  it("sin totalUsd, el centro sigue siendo la suma de categorías", () => {
    render(<CategoryDonut data={slices} />);
    expect(screen.getByText("USD 10.227")).toBeTruthy();
  });
});
