import { cn } from "@/lib/cn";

/** Bloque de carga con pulso suave. */
export default function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-skeleton rounded-lg bg-surface-2", className)} aria-hidden="true" />;
}
