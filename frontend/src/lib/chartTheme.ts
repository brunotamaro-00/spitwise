// Paleta categórica validada (scripts/validate_palette.js de la skill dataviz:
// banda de luminosidad, piso de croma, separación CVD adyacente y contraste ≥3:1
// sobre superficie blanca — todos PASS). El color sigue a la categoría (orden
// fijo del catálogo), nunca al ranking.
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
export const GRID = "#EEF0F3"; // surface-2: grilla muy tenue
export const TICK = { fill: "#868B93", fontSize: 11 } as const; // ink-3

export const TOOLTIP_STYLE = {
  background: "#FFFFFF",
  border: "1px solid #E3E6EA",
  borderRadius: 10,
  boxShadow: "0 4px 16px rgb(23 24 26 / 0.10), 0 2px 6px rgb(23 24 26 / 0.06)",
  fontSize: 12,
  fontWeight: 600,
  color: "#191A1C",
} as const;

export function categoryColor(name: string | null): string {
  return (name && CATEGORY_COLORS[name]) || FALLBACK_SERIES;
}
