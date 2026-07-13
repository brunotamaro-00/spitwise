import { cn } from "@/lib/cn";

/** Wordmark de Spitwise: Anton en tinta con un "trail" de puntitos terracota
 *  saliendo del final de la palabra — el escupitajo de la llama del logo.
 *  Escala con el font-size del contenedor (todo en em). */
export function Wordmark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "relative inline-block whitespace-nowrap pr-[0.45em] font-display leading-none text-ink",
        className,
      )}
    >
      Spitwise
      <span aria-hidden="true">
        <span className="absolute bottom-[0.34em] right-[0.28em] h-[0.11em] w-[0.11em] rounded-full bg-brick" />
        <span className="absolute bottom-[0.55em] right-[0.14em] h-[0.085em] w-[0.085em] rounded-full bg-brick/70" />
        <span className="absolute bottom-[0.74em] right-[0.02em] h-[0.06em] w-[0.06em] rounded-full bg-brick/40" />
      </span>
    </span>
  );
}

/** Título de página editorial: Anton grande + trail de puntitos de marca. */
export function PageTitle({ children }: { children: React.ReactNode }) {
  return (
    <h1 className="flex items-baseline gap-2.5 font-display text-[1.9rem] leading-none tracking-wide text-ink">
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
