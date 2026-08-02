import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/cn";

/* Intent: titular una sección o card sin competir con el dato (el valor manda,
   el título orienta). Dos tiers: el normal (text-sm bold) y `quiet` para cards
   de chart donde el gráfico es el protagonista y el título es casi un label —
   antes eso se resolvía abusando del <Label> de formularios (ui/Field). */

const ICON_TINTS = {
  brick: "bg-brick-bg text-brick",
  teal: "bg-accent-teal-bg text-accent-teal",
  amber: "bg-accent-amber-bg text-accent-amber",
  blue: "bg-accent-blue-bg text-accent-blue",
  neutral: "bg-surface-2 text-ink-3",
} as const;

/** Título de sección/card. `hint` = aclaración tenue a la derecha;
 *  `action` = link/botón a la derecha (excluyentes en la práctica).
 *  `as` fija el nivel semántico real (h2 default; h3 dentro de una sección). */
export default function SectionHeader({
  as: Tag = "h2",
  icon: Icon,
  iconTone = "brick",
  hint,
  action,
  quiet = false,
  className,
  children,
}: {
  as?: "h2" | "h3";
  icon?: LucideIcon;
  iconTone?: keyof typeof ICON_TINTS;
  hint?: React.ReactNode;
  action?: React.ReactNode;
  quiet?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      {Icon && (
        <span
          className={cn(
            "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg",
            ICON_TINTS[iconTone],
          )}
        >
          <Icon size={15} strokeWidth={2} aria-hidden="true" />
        </span>
      )}
      <Tag className={quiet ? "text-xs font-medium text-ink-3" : "text-sm font-bold text-ink"}>
        {children}
      </Tag>
      {hint && <span className="ml-auto text-meta font-medium text-ink-3">{hint}</span>}
      {action && <span className="ml-auto">{action}</span>}
    </div>
  );
}
