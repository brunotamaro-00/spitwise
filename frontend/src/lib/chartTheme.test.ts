import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { ACCENT, CATEGORY_META, FALLBACK_SERIES, GRID, TICK } from "./chartTheme";

// Relativo al root del proyecto (cwd de Vitest): import.meta.url acá no es file://.
const css = readFileSync("src/index.css", "utf8");

/** Anti-drift: chartTheme referencia tokens por var() — los hex viven SOLO en
 *  index.css. Este test convierte en fallo de CI los dos modos de romperlo:
 *  (a) renombrar un token en index.css sin actualizar la referencia (el var()
 *  colgado renderiza transparente en silencio), y (b) volver a duplicar un hex
 *  acá (el drift original: FALLBACK_SERIES quedó en un ink-3 viejo). */

const defined = [...css.matchAll(/--color-[\w-]+(?=\s*:)/g)].map((m) => m[0]);

const values = [
  ACCENT,
  FALLBACK_SERIES,
  GRID,
  TICK.fill,
  ...Object.values(CATEGORY_META).flatMap((m) => [m.color, m.bg]),
];

describe("chartTheme ↔ index.css", () => {
  it("cada var() referenciado existe como token", () => {
    // Guarda del propio test: si el ?raw no trae el CSS, esto falla primero.
    expect(defined.length).toBeGreaterThan(10);
    for (const v of values) {
      const refs = [...v.matchAll(/var\((--color-[\w-]+)\)/g)].map((m) => m[1]);
      expect(refs.length, `"${v}" no referencia ningún token`).toBeGreaterThan(0);
      for (const token of refs) {
        expect(defined, `${token} no existe en index.css`).toContain(token);
      }
    }
  });

  it("ningún color vive como hex duplicado", () => {
    for (const v of values) {
      expect(v).not.toMatch(/#[0-9a-fA-F]{3,8}/);
    }
  });
});
