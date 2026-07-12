// Paleta categórica validada (scripts/validate_palette.js de la skill dataviz:
// banda de luminosidad, piso de croma, separación CVD adyacente y contraste ≥3:1
// sobre superficie blanca — todos PASS). El color sigue a la categoría (orden
// fijo del catálogo), nunca al ranking. Estos mismos valores viven como tokens
// --color-accent-* en index.css: UI y charts comparten una sola verdad.
export const CATEGORY_COLORS: Record<string, string> = {
  Alojamiento: "#C44428",
  Comida: "#2E6FBF",
  Transporte: "#A67F2A",
  Actividades: "#0B8F80",
  Compras: "#8E3D88",
  "Bebidas/Salidas": "#55902F",
  Otros: "#7A5AC4",
};
export const FALLBACK_SERIES = "#8A7F6A"; // ink-3: sin categoría

export const ACCENT = "#C44428"; // brick: serie única (barras, línea)
export const GRID = "#EDE8E0"; // tenue, alineado a los neutros cálidos
export const TICK = { fill: "#857F74", fontSize: 12 } as const; // ink-3

// Paleta cíclica para colorear series por ciudad (deriva de los accents).
export const CITY_PALETTE = [
  "#C44428", // brick
  "#2E6FBF", // blue
  "#0B8F80", // teal
  "#A67F2A", // amber
  "#8E3D88", // plum
  "#55902F", // green
  "#7A5AC4", // indigo
] as const;

export function cityColor(index: number): string {
  return CITY_PALETTE[index % CITY_PALETTE.length];
}

export const TOOLTIP_STYLE = {
  background: "#FFFFFF",
  border: "1px solid #E6E1D8",
  borderRadius: 12,
  boxShadow: "0 8px 24px rgb(27 26 23 / 0.12), 0 2px 6px rgb(27 26 23 / 0.06)",
  padding: "8px 12px",
  fontSize: 12,
  fontWeight: 600,
  color: "#1B1A17",
} as const;

export function categoryColor(name: string | null): string {
  return (name && CATEGORY_COLORS[name]) || FALLBACK_SERIES;
}

/** Etiqueta compacta para ejes: 1400 -> "1,4k", 900 -> "900". */
export function compactUsd(v: number): string {
  if (v >= 1000) {
    const k = v / 1000;
    return `${(Number.isInteger(k) ? k : k.toFixed(1)).toString().replace(".", ",")}k`;
  }
  return String(Math.round(v));
}
