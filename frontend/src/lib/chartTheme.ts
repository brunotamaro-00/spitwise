import {
  BedDouble,
  Bus,
  Coffee,
  HeartPulse,
  type LucideIcon,
  ShoppingBag,
  ShoppingCart,
  Tag,
  Ticket,
  UtensilsCrossed,
  WashingMachine,
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
 *  color nunca es el único canal de identidad.
 *
 *  Los colores son referencias var() a los tokens --color-accent-* de index.css
 *  (los hex viven SOLO ahí): antes estaban duplicados acá y ya driftearon una
 *  vez (FALLBACK_SERIES quedó en el ink-3 viejo cuando el token se corrigió por
 *  contraste). SVG acepta var() en fill/stroke — el stroke del donut ya lo usaba.
 *  chartTheme.test.ts verifica que cada token referenciado exista en index.css. */
export const CATEGORY_META = {
  Alojamiento: { icon: BedDouble, color: "var(--color-brick)", bg: "var(--color-brick-bg)" },
  Comida: { icon: UtensilsCrossed, color: "var(--color-accent-blue)", bg: "var(--color-accent-blue-bg)" },
  Cafetería: { icon: Coffee, color: "var(--color-accent-brown)", bg: "var(--color-accent-brown-bg)" },
  Supermercado: { icon: ShoppingCart, color: "var(--color-accent-pink)", bg: "var(--color-accent-pink-bg)" },
  Transporte: { icon: Bus, color: "var(--color-accent-amber)", bg: "var(--color-accent-amber-bg)" },
  Actividades: { icon: Ticket, color: "var(--color-accent-teal)", bg: "var(--color-accent-teal-bg)" },
  Compras: { icon: ShoppingBag, color: "var(--color-accent-plum)", bg: "var(--color-accent-plum-bg)" },
  Salidas: { icon: Wine, color: "var(--color-accent-green)", bg: "var(--color-accent-green-bg)" },
  Lavandería: { icon: WashingMachine, color: "var(--color-accent-rose)", bg: "var(--color-accent-rose-bg)" },
  Salud: { icon: HeartPulse, color: "var(--color-accent-cyan)", bg: "var(--color-accent-cyan-bg)" },
  Otros: { icon: Tag, color: "var(--color-accent-indigo)", bg: "var(--color-accent-indigo-bg)" },
} satisfies Record<string, CategoryMeta>;

export const FALLBACK_SERIES = "var(--color-ink-3)"; // sin categoría / serie apagada

export const ACCENT = "var(--color-brick)"; // brick: serie única (barras, línea)
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
