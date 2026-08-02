import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import StayEnvelopeBar from "./StayEnvelopeBar";

/** El color no puede ser el único canal: la barra tiene que decir los números
 *  en texto para quien no la ve. */
describe("StayEnvelopeBar", () => {
  it("describe lo gastado y el plan de la parada", () => {
    render(<StayEnvelopeBar spent={107} envelope={348} over={false} />);
    const aria = screen.getByRole("img").getAttribute("aria-label") ?? "";
    expect(aria).toMatch(/107/);
    expect(aria).toMatch(/348/);
  });

  /** El eje es el pote, así que el final de la barra ES el número que el pie
   *  escribe al lado. Con el techo de la banda como eje, la barra terminaba en
   *  una cifra que no estaba escrita en ningún lado. */
  it("el relleno mide la fracción gastada del plan", () => {
    const { container } = render(<StayEnvelopeBar spent={174} envelope={348} over={false} />);
    const fill = container.querySelector<HTMLElement>(".bg-white");
    expect(parseFloat(fill!.style.width)).toBeCloseTo(50, 1);
  });

  /** Pasados de pote, el relleno NO se pinta todo de rojo: el tramo que entraba
   *  en el plan queda blanco y solo el exceso va en la rampa. Pintar todo decía
   *  "te pasaste" pero escondía cuánto de lo gastado sobra. */
  it("separa lo que entraba en el plan del exceso", () => {
    const { container } = render(<StayEnvelopeBar spent={388} envelope={350} over={true} />);
    const white = container.querySelector<HTMLElement>(".bg-white");
    const over = container.querySelector<HTMLElement>(".bg-heat-over");
    expect(parseFloat(white!.style.width)).toBeCloseTo(90.21, 1); // 350 de 388
    expect(parseFloat(over!.style.left)).toBeCloseTo(90.21, 1);
    expect(parseFloat(over!.style.width)).toBeCloseTo(9.79, 1);
  });

  it("el eje se estira con el gasto: pasarse nunca desborda la barra", () => {
    const { container } = render(<StayEnvelopeBar spent={900} envelope={350} over={true} />);
    const widths = [...container.querySelectorAll<HTMLElement>("div[style*='width']")].map((el) =>
      parseFloat(el.style.width),
    );
    for (const w of widths) expect(w).toBeLessThanOrEqual(100);
  });
});
