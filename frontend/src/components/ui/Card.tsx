import { cn } from "@/lib/cn";

/** Superficie base: borde hairline, esquinas suaves, sombra difusa. */
export default function Card({ className, children, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-2xl border border-border bg-surface soft-card", className)}
      {...rest}
    >
      {children}
    </div>
  );
}
