import clsx, { type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/** twMerge no lee index.css, así que hay que declararle las clases custom que
 *  su heurística agruparía mal: `font-tabular` (font-variant-numeric) caería en
 *  el grupo font-family y pisaría/perdería contra `font-display`/`font-sans`. */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "fvn-figure": ["font-tabular"],
      "font-family": [{ font: ["display", "sans"] }],
    },
  },
});

/** Une clases condicionales y resuelve conflictos de utilidades Tailwind:
 *  la última gana (`cn("p-5", "p-4")` → `"p-4"`), así los overrides por
 *  `className` en los primitivos de ui/ son confiables. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
