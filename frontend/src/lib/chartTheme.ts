import {
  BedDouble,
  Bus,
  Gift,
  HeartPulse,
  type LucideIcon,
  ShoppingBag,
  ShoppingCart,
  Tag,
  Ticket,
  UtensilsCrossed,
  Wine,
} from "lucide-react";

export type CategoryMeta = {
  /** Ícono Lucide. Mismo ícono que usa Andiamo para la misma categoría. */
  icon: LucideIcon;
  /** Color de serie: sigue a la categoría (orden fijo del catálogo), nunca al ranking. */
  color: string;
  /** Fondo suave: token --color-*-bg de index.css. */
  bg: string;
};

/** Única fuente de verdad de presentación por categoría: ícono + color + fondo.
 *  Las claves espejan `backend/app/categories/catalog.py` (nombre exacto) — sumar
 *  una categoría allá es sumar una entrada acá. Los tres accessors de abajo
 *  degradan solos, así que una categoría nueva sin entrada renderiza igual
 *  (ícono Tag + gris) en vez de romper.
 *
 *  Colores: paleta categórica validada con scripts/validate_palette.js (skill
 *  dataviz), --mode light, pares adyacentes: banda de luminosidad, piso de croma
 *  y contraste ≥3:1 en PASS. La separación CVD peor caso es
 *  Salud↔Otros ΔE 6.4 (deutan), dentro de la banda 6–8 que exige encoding
 *  secundario: toda superficie que pinta color acá lo acompaña con ícono + label
 *  (leyenda del donut, chips, filas) y el donut suma tooltip por gajo, así que el
 *  color nunca es el único canal de identidad. Estos mismos valores viven como
 *  tokens --color-accent-* en index.css: UI y charts comparten una sola verdad. */
export const CATEGORY_META = {
  Alojamiento: { icon: BedDouble, color: "#C44428", bg: "var(--color-brick-bg)" },
  Comida: { icon: UtensilsCrossed, color: "#2E6FBF", bg: "var(--color-accent-blue-bg)" },
  Supermercado: { icon: ShoppingCart, color: "#C2185B", bg: "var(--color-accent-pink-bg)" },
  Transporte: { icon: Bus, color: "#A67F2A", bg: "var(--color-accent-amber-bg)" },
  Actividades: { icon: Ticket, color: "#0B8F80", bg: "var(--color-accent-teal-bg)" },
  Compras: { icon: ShoppingBag, color: "#8E3D88", bg: "var(--color-accent-plum-bg)" },
  "Bebidas/Salidas": { icon: Wine, color: "#55902F", bg: "var(--color-accent-green-bg)" },
  Regalos: { icon: Gift, color: "#96530D", bg: "var(--color-accent-brown-bg)" },
  Salud: { icon: HeartPulse, color: "#0F86B0", bg: "var(--color-accent-cyan-bg)" },
  Otros: { icon: Tag, color: "#7A5AC4", bg: "var(--color-accent-indigo-bg)" },
} satisfies Record<string, CategoryMeta>;

export const FALLBACK_SERIES = "#857F74"; // = --color-ink-3: sin categoría

export const ACCENT = "#C44428"; // brick: serie única (barras, línea)
export const GRID = "var(--color-border)"; // grilla tenue, tokenizada
export const TICK = { fill: "var(--color-ink-3)", fontSize: 12 } as const;

function meta(name: string | null | undefined): CategoryMeta | undefined {
  return name ? (CATEGORY_META as Record<string, CategoryMeta>)[name] : undefined;
}

export function categoryColor(name: string | null): string {
  return meta(name)?.color ?? FALLBACK_SERIES;
}

export function categoryBg(name: string | null): string {
  return meta(name)?.bg ?? "var(--color-surface-2)";
}

export function categoryIcon(name: string | null | undefined): LucideIcon {
  return meta(name)?.icon ?? Tag;
}

/** Etiqueta compacta para ejes: 1400 -> "1,4k", 900 -> "900". */
export function compactUsd(v: number): string {
  if (v >= 1000) {
    const k = v / 1000;
    return `${(Number.isInteger(k) ? k : k.toFixed(1)).toString().replace(".", ",")}k`;
  }
  return String(Math.round(v));
}
