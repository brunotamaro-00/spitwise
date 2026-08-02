import clsx, { type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/** twMerge no lee index.css, así que hay que declararle las clases custom que
 *  su heurística agruparía mal:
 *  - `font-tabular` (font-variant-numeric) caería en font-family y colisionaría
 *    con `font-display`/`font-sans`.
 *  - los tamaños del ledger (`text-meta`, `text-entry`, …) caerían en el grupo
 *    de COLOR de texto y pisarían `text-white`/`text-accent-*-ink` (bug real:
 *    lo atrapó DeltaBadge.test). Declararlos como font-size los separa.
 *  Si sumás un token `--text-*` o `--tracking-*` nuevo en index.css, agregalo acá. */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "fvn-figure": ["font-tabular"],
      "font-family": [{ font: ["display", "sans"] }],
      "font-size": [{ text: ["fine", "meta", "note", "entry", "wordmark", "title", "splash"] }],
      tracking: [{ tracking: ["display", "caps", "eyebrow"] }],
    },
  },
});

/** Une clases condicionales y resuelve conflictos de utilidades Tailwind:
 *  la última gana (`cn("p-5", "p-4")` → `"p-4"`), así los overrides por
 *  `className` en los primitivos de ui/ son confiables. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
