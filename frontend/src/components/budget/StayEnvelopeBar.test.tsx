import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import StayEnvelopeBar from "./StayEnvelopeBar";

/** El color no puede ser el único canal: la barra tiene que decir los tres
 *  números en texto para quien no la ve. */
describe("StayEnvelopeBar", () => {
  it("describe lo gastado, el pote y el techo", () => {
    render(<StayEnvelopeBar spent={108} envelope={350} max={415} accrued={210} over={false} />);
    const aria = screen.getByRole("img").getAttribute("aria-label") ?? "";
    expect(aria).toMatch(/108/);
    expect(aria).toMatch(/350/);
    expect(aria).toMatch(/415/);
  });

  it("dibuja el hueco entre lo gastado y el poste: eso es el ahorro", () => {
    const { container } = render(
      <StayEnvelopeBar spent={108} envelope={350} max={415} accrued={210} over={false} />,
    );
    const gap = container.querySelector<HTMLElement>(".bg-white\\/35");
    // 108 y 210 sobre un eje de 415: el hueco arranca en uno y termina en otro.
    expect(parseFloat(gap!.style.left)).toBeCloseTo(26.02, 1);
    expect(parseFloat(gap!.style.width)).toBeCloseTo(24.58, 1);
  });

  it("gastando por encima del plan no hay hueco que mostrar", () => {
    const { container } = render(
      <StayEnvelopeBar spent={300} envelope={350} max={415} accrued={210} over={false} />,
    );
    expect(container.querySelector(".bg-white\\/35")).toBeNull();
  });

  /** Pasados de pote, el relleno NO se pinta todo de rojo: el tramo que entraba
   *  en el plan queda blanco y solo el exceso va en la rampa. Pintar todo decía
   *  "te pasaste" pero escondía cuánto de lo gastado sobra. */
  it("separa lo que entraba en el plan del exceso", () => {
    const { container } = render(
      <StayEnvelopeBar spent={388} envelope={350} max={415} accrued={350} over={true} />,
    );
    const white = container.querySelector<HTMLElement>(".bg-white:not([class*='/'])");
    const over = container.querySelector<HTMLElement>(".bg-heat-over");
    expect(parseFloat(white!.style.width)).toBeCloseTo(84.34, 1); // 350 de 415
    expect(parseFloat(over!.style.left)).toBeCloseTo(84.34, 1);
    expect(parseFloat(over!.style.width)).toBeCloseTo(9.16, 1);   // 38 de 415
  });

  it("el eje se estira con el gasto: pasarse nunca desborda la barra", () => {
    const { container } = render(
      <StayEnvelopeBar spent={900} envelope={350} max={415} accrued={350} over={true} />,
    );
    const widths = [...container.querySelectorAll<HTMLElement>("div[style*='width']")].map((el) =>
      parseFloat(el.style.width),
    );
    for (const w of widths) expect(w).toBeLessThanOrEqual(100);
  });
});
