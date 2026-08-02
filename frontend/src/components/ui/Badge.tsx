import { cn } from "@/lib/cn";

/* Intent: metadata compacta que etiqueta un dato (estado, veredicto, delta)
   sin robarle protagonismo. Siempre subordinado al valor que acompaña:
   tinte suave + texto -ink (los pares ya validados AA), nunca color saturado.

   `green` · `orange` · `red` son la rampa de ritmo del presupuesto (ver
   `--color-heat-*` en index.css). El rojo entró con una decisión explícita:
   en /presupuesto, pasarse fuerte del plan es lo único que tiene que verse
   desde lejos. Afuera de esa rampa la regla sigue siendo la de siempre —
   un badge informa, no alarma. */

const TONES = {
  neutral: "bg-surface-2 text-ink-3",
  teal: "bg-accent-teal-bg text-accent-teal-ink",
  green: "bg-accent-green-bg text-accent-green-ink",
  amber: "bg-accent-amber-bg text-accent-amber-ink",
  orange: "bg-heat-over-bg text-heat-over-ink",
  red: "bg-danger-bg text-danger-ink",
  brick: "bg-brick-bg text-brick-ink",
} as const;

const SIZES = {
  md: "px-2 py-0.5 text-meta",
  sm: "px-1.5 py-0.5 text-fine",
} as const;

export type BadgeTone = keyof typeof TONES;

/** Pill informativa. `caps` = etiqueta en mayúsculas (POR CONFIRMAR, HOY);
 *  `tabular` = contenido numérico (deltas, porcentajes). */
export default function Badge({
  tone = "neutral",
  size = "md",
  caps = false,
  tabular = false,
  className,
  children,
  ...rest
}: React.HTMLAttributes<HTMLSpanElement> & {
  tone?: BadgeTone;
  size?: keyof typeof SIZES;
  caps?: boolean;
  tabular?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-full font-bold",
        TONES[tone],
        SIZES[size],
        caps && "uppercase tracking-wide",
        tabular && "font-tabular",
        className,
      )}
      {...rest}
    >
      {children}
    </span>
  );
}

const COUNT_TONES = {
  amber: "bg-accent-amber-solid text-white",
  brick: "bg-brick text-white",
} as const;

const COUNT_SIZES = {
  md: "h-5 min-w-5 px-1.5 text-meta",
  sm: "h-4 min-w-4 px-1 text-fine",
} as const;

/** Punto de conteo (badge numérico de nav/filtros). El número va aria-hidden:
 *  el call site pone el `aria-label` con contexto ("3 por confirmar"). */
export function CountBadge({
  count,
  tone = "amber",
  size = "md",
  className,
  "aria-label": ariaLabel,
}: {
  count: number;
  tone?: keyof typeof COUNT_TONES;
  size?: keyof typeof COUNT_SIZES;
  className?: string;
  "aria-label"?: string;
}) {
  return (
    <span
      className={cn(
        "flex items-center justify-center rounded-full font-bold",
        COUNT_TONES[tone],
        COUNT_SIZES[size],
        className,
      )}
      aria-label={ariaLabel}
    >
      <span aria-hidden="true">{count}</span>
    </span>
  );
}
