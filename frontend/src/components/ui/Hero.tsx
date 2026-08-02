import { cn } from "@/lib/cn";

import Card from "./Card";

/* Intent: el bloque focal de una página — el número al que el usuario vino.
   Superficie de marca (gradiente ladrillo + trail de puntitos + sheen) usada
   una sola vez por vista: dos heros compitiendo es no haber decidido el foco.
   Antes esta receta vivía copiada 4 veces (Dashboard, Budget ×2, Cities). */

const PADDING = {
  lg: "p-6 lg:p-7",
  md: "p-5",
} as const;

/** Superficie hero. `eyebrow` = kicker uppercase arriba (admite nodos: bandera
 *  + texto). `loading` mantiene el shell con placeholders sobre el gradiente —
 *  nunca mostrar un dato falso (el "USD 0" de Cities era un bug, no un estado). */
export default function Hero({
  eyebrow,
  loading = false,
  padding = "lg",
  className,
  children,
}: {
  eyebrow?: React.ReactNode;
  loading?: boolean;
  padding?: keyof typeof PADDING;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Card
      className={cn(
        "relative overflow-hidden text-white hero-gradient soft-hero",
        PADDING[padding],
        className,
      )}
    >
      <div className="spit-dots absolute inset-0" aria-hidden="true" />
      <div className="hero-sheen absolute inset-0" aria-hidden="true" />
      <div className="relative">
        {eyebrow && (
          <p className="flex items-center gap-2 text-meta font-semibold uppercase tracking-eyebrow text-white/70">
            {eyebrow}
          </p>
        )}
        {loading ? (
          <div aria-busy="true">
            <span role="status" className="sr-only">Cargando…</span>
            <div className="animate-skeleton mt-2 h-12 w-44 rounded-lg bg-white/20" />
            <div className="animate-skeleton mt-3 h-4 w-56 rounded bg-white/15" />
          </div>
        ) : (
          children
        )}
      </div>
    </Card>
  );
}
