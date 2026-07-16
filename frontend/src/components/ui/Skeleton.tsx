import { cn } from "@/lib/cn";

/** Bloque de carga: pulso suave + shimmer diagonal que recorre la superficie. */
export default function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn("skeleton-shimmer animate-skeleton relative overflow-hidden rounded-lg bg-surface-2", className)}
      aria-hidden="true"
    />
  );
}
