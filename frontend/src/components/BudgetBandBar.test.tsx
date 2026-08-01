import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import BudgetBandBar from "./BudgetBandBar";

/** El color no puede ser el único canal: la barra tiene que decir los tres
 *  números en texto para quien no la ve. */
describe("BudgetBandBar", () => {
  it("describe el gasto real y los dos bordes del plan", () => {
    render(
      <BudgetBandBar min="68.00" max="95.00" value="74.00" position="in" label="Londres" />,
    );
    const aria = screen.getByRole("img").getAttribute("aria-label") ?? "";
    expect(aria).toMatch(/Londres/);
    expect(aria).toMatch(/74/);
    expect(aria).toMatch(/68/);
    expect(aria).toMatch(/95/);
  });

  it("sin gasto todavía lo dice, en vez de describir un cero", () => {
    render(
      <BudgetBandBar min="40.00" max="60.00" value={null} position={null} label="Praga" />,
    );
    expect(screen.getByRole("img").getAttribute("aria-label")).toMatch(/sin gasto/);
  });

  it("el tono sigue a la posición en la banda, y nunca es rojo", () => {
    const { container } = render(
      <BudgetBandBar min="40.00" max="60.00" value="80.00" position="over" label="Roma" />,
    );
    expect(container.querySelector(".bg-accent-amber-solid")).toBeTruthy();
    expect(container.querySelector(".bg-danger")).toBeNull();
  });

  /** Una banda de ancho cero es el modelo de target único de antes, y CLAUDE.md
   *  la declara el caso de no-regresión del presupuesto. Los tres postes (piso,
   *  objetivo, techo) caen en el mismo %, así que keyearlos por posición daba
   *  tres keys idénticas: React lo reporta como error y avisa que duplicar u
   *  omitir hijos es comportamiento no soportado. */
  it("con min === max dibuja los tres postes sin keys duplicadas", () => {
    const errors: unknown[] = [];
    const spy = vi.spyOn(console, "error").mockImplementation((...a) => errors.push(a));
    const { container } = render(
      <BudgetBandBar min="80.00" max="80.00" value="80.00" position="in" label="Londres" />,
    );
    spy.mockRestore();

    expect(container.querySelectorAll(':scope > div > span[aria-hidden="true"]')).toHaveLength(3);
    expect(errors.flat().join(" ")).not.toMatch(/same key/i);
  });

  it("no renderiza nada con una banda no numérica", () => {
    const { container } = render(
      <BudgetBandBar min="" max="" value={null} position={null} label="X" />,
    );
    expect(container.innerHTML).toBe("");
  });
});
