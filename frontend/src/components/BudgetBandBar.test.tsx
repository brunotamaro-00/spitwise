import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import BudgetBandBar from "./BudgetBandBar";

/** El color no puede ser el único canal: la barra tiene que decir los tres
 *  números en texto para quien no la ve. */
describe("BudgetBandBar", () => {
  it("describe el gasto real y los dos bordes del plan", () => {
    render(<BudgetBandBar min="68.00" max="95.00" value="74.00" label="Londres" />);
    const aria = screen.getByRole("img").getAttribute("aria-label") ?? "";
    expect(aria).toMatch(/Londres/);
    expect(aria).toMatch(/74/);
    expect(aria).toMatch(/68/);
    expect(aria).toMatch(/95/);
  });

  it("dice cuál es la escala: sin eso, el largo del relleno no significa nada", () => {
    render(<BudgetBandBar min="68.00" max="95.00" value="74.00" label="Londres" />);
    expect(screen.getByRole("img").getAttribute("aria-label")).toMatch(/escala/i);
  });

  it("sin gasto todavía lo dice, en vez de describir un cero", () => {
    render(<BudgetBandBar min="40.00" max="60.00" value={null} label="Praga" />);
    expect(screen.getByRole("img").getAttribute("aria-label")).toMatch(/sin gasto/);
  });

  /** La escala fija es el motivo del cambio: con planes distintos y el mismo
   *  gasto diario, el relleno tiene que medir lo mismo. Antes cada barra se
   *  escalaba contra su propia banda y la lista se veía prolija sin decir nada. */
  it("el mismo gasto llega igual de lejos aunque los planes difieran", () => {
    // El relleno sólido corta en el techo y el excedente sigue más tenue, así
    // que lo comparable es dónde TERMINA: la suma de los dos tramos.
    const reach = (min: string, max: string) => {
      const { container } = render(
        <BudgetBandBar min={min} max={max} value="81.00" label="X" />,
      );
      return [...container.querySelectorAll<HTMLElement>(".h-1")].reduce(
        (acc, el) => acc + parseFloat(el.style.width),
        0,
      );
    };
    expect(reach("68.00", "95.00")).toBeCloseTo(81);
    expect(reach("20.00", "30.00")).toBeCloseTo(81);
  });

  /** Decisión explícita, y revierte la regla vieja ("nunca rojo"): pasarse
   *  fuerte del plan es lo único de esta página que tiene que verse de lejos. */
  it("pasarse fuerte pinta el paso rojo de la rampa", () => {
    const { container } = render(
      <BudgetBandBar min="40.00" max="60.00" value="120.00" label="Roma" />,
    );
    expect(container.querySelector(".bg-heat-far")).toBeTruthy();
  });

  it("adentro del plan la rampa es verde, no roja", () => {
    const { container } = render(
      <BudgetBandBar min="40.00" max="60.00" value="45.00" label="Praga" />,
    );
    expect(container.querySelector(".bg-heat-plan")).toBeTruthy();
    expect(container.querySelector(".bg-heat-far")).toBeNull();
  });

  it("fuera del eje marca el tope: si no, USD 100 y USD 300 se ven igual", () => {
    const cap = (value: string) => {
      const { container } = render(
        <BudgetBandBar min="40.00" max="60.00" value={value} label="X" />,
      );
      return container.querySelector(".inset-y-0.right-0");
    };
    expect(cap("300.00")).toBeTruthy();
    expect(cap("90.00")).toBeNull();
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
      <BudgetBandBar min="80.00" max="80.00" value="80.00" label="Londres" />,
    );
    spy.mockRestore();

    expect(container.querySelectorAll(':scope > div > span[aria-hidden="true"]')).toHaveLength(3);
    expect(errors.flat().join(" ")).not.toMatch(/same key/i);
  });

  it("no renderiza nada con una banda no numérica", () => {
    const { container } = render(<BudgetBandBar min="" max="" value={null} label="X" />);
    expect(container.innerHTML).toBe("");
  });
});
