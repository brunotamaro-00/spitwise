import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

import Card from "./Card";

const TINTS = {
  brick: "bg-brick-bg text-brick",
  blue: "bg-accent-blue-bg text-accent-blue",
  teal: "bg-accent-teal-bg text-accent-teal",
  amber: "bg-accent-amber-bg text-accent-amber",
} as const;

/** Indicador compacto: ícono tintado + valor display + label.
 *  `badge` es un slot opcional (p.ej. el delta vs promedio) que va arriba a la
 *  derecha, en la línea del ícono, sin robarle un renglón a la grilla. */
export default function Kpi({ icon: Icon, tint, label, value, badge }: {
  icon: LucideIcon;
  tint: keyof typeof TINTS;
  label: string;
  value: string;
  badge?: ReactNode;
}) {
  return (
    <Card className="flex flex-col gap-2 p-4">
      <div className="flex items-start justify-between gap-1">
        <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${TINTS[tint]}`}>
          <Icon size={16} strokeWidth={2} aria-hidden="true" />
        </span>
        {badge}
      </div>
      {/* Sin `truncate` en el valor: un monto que se corta con ellipsis esconde
          plata en silencio. A 402px la columna deja 83px, y a text-lg
          "USD 1.234" ya medía 81px — text-base en mobile da aire real. */}
      <div className="min-w-0">
        <p className="font-display text-base leading-none tracking-tight text-ink font-tabular lg:text-lg">
          {value}
        </p>
        <p className="mt-1 whitespace-nowrap text-xs font-medium text-ink-3">{label}</p>
      </div>
    </Card>
  );
}
