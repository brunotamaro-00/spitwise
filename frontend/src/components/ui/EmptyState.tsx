import type { LucideIcon } from "lucide-react";

/** Estado vacío con la llama de Spitwise + badge del contexto (ícono). */
export default function EmptyState({ icon: Icon, title, description }: {
  icon: LucideIcon;
  title: string;
  description?: string;
}) {
  return (
    <div className="relative flex flex-col items-center gap-3 overflow-hidden px-6 py-12 text-center">
      <div className="spit-dots-ink pointer-events-none absolute inset-0" aria-hidden="true" />
      <span className="relative flex h-16 w-16 items-center justify-center rounded-full border border-border bg-surface-2">
        <img src="/logo-sm.png" alt="" width={44} height={44} />
        <span className="absolute -bottom-1 -right-1 flex h-6 w-6 items-center justify-center rounded-full border border-border bg-surface text-ink-3 soft-card">
          <Icon size={13} strokeWidth={2} aria-hidden="true" />
        </span>
      </span>
      <p className="relative font-semibold text-ink">{title}</p>
      {description && <p className="relative max-w-[28ch] text-sm text-ink-3">{description}</p>}
    </div>
  );
}
