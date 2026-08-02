import { cn } from "@/lib/cn";

/** Wordmark de Spitwise: `spit` terracota + `wise` tinta, en minúscula y
 *  Hanken Grotesk 800 — igual que el logo entregado. Escala con el font-size
 *  del contenedor. El escupitajo (firma de marca) vive en el logo y en
 *  `SpitDivider`, no en el texto. */
export function Wordmark({ className, tone = "light" }: { className?: string; tone?: "light" | "dark" }) {
  // Sobre espresso, `wise` en tinta desaparece: usamos crema, y un terracota
  // más claro para `spit` que mantiene contraste AA.
  const spit = tone === "dark" ? "text-brick-soft" : "text-brick";
  const wise = tone === "dark" ? "text-espresso-ink" : "text-ink";
  return (
    <span
      className={cn(
        // Sin font-size propio: lo fija quien lo usa.
        "inline-block whitespace-nowrap font-sans font-extrabold lowercase leading-none tracking-[-0.035em]",
        className,
      )}
    >
      <span className={spit}>spit</span>
      <span className={wise}>wise</span>
    </span>
  );
}

/** Título de página editorial: Anton grande + trail de puntitos de marca. */
export function PageTitle({ children }: { children: React.ReactNode }) {
  return (
    <h1 className="flex items-baseline gap-2.5 font-display text-title leading-none tracking-display text-ink">
      {children}
      <SpitDivider className="translate-y-[-0.35rem]" />
    </h1>
  );
}

/** Acento decorativo de sección: tres puntitos decrecientes (firma de marca). */
export function SpitDivider({ className }: { className?: string }) {
  return (
    <span aria-hidden="true" className={cn("inline-flex items-center gap-1", className)}>
      <span className="h-1.5 w-1.5 rounded-full bg-brick/70" />
      <span className="h-1 w-1 rounded-full bg-brick/40" />
      <span className="h-0.5 w-0.5 rounded-full bg-brick/20" />
    </span>
  );
}
