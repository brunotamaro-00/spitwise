import type { LucideIcon } from "lucide-react";

import Card from "./Card";

const TINTS = {
  brick: "bg-brick-bg text-brick",
  blue: "bg-accent-blue-bg text-accent-blue",
  teal: "bg-accent-teal-bg text-accent-teal",
  amber: "bg-accent-amber-bg text-accent-amber",
} as const;

/** Indicador compacto: ícono tintado + valor display + label. */
export default function Kpi({ icon: Icon, tint, label, value }: {
  icon: LucideIcon;
  tint: keyof typeof TINTS;
  label: string;
  value: string;
}) {
  return (
    <Card className="flex flex-col gap-2 p-4">
      <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${TINTS[tint]}`}>
        <Icon size={16} strokeWidth={2} aria-hidden="true" />
      </span>
      <div className="min-w-0">
        <p className="truncate font-display text-lg leading-none tracking-tight text-ink font-tabular">
          {value}
        </p>
        <p className="mt-1 text-xs font-medium text-ink-3">{label}</p>
      </div>
    </Card>
  );
}
