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
export const GRID = "#D8CFB4"; // border token: grilla recesiva
export const TICK = { fill: "#6B6452", fontSize: 11 } as const;

export const TOOLTIP_STYLE = {
  background: "#FFFFFF",
  border: "2px solid #1B1A17",
  borderRadius: 4,
  boxShadow: "3px 3px 0 #D8CFB4",
  fontSize: 12,
  fontWeight: 600,
  color: "#1B1A17",
} as const;

export function categoryColor(name: string | null): string {
  return (name && CATEGORY_COLORS[name]) || FALLBACK_SERIES;
}
