import type { LucideIcon } from "lucide-react";

/** Estado vacío: chip circular con ícono + título + descripción muted. */
export default function EmptyState({ icon: Icon, title, description }: {
  icon: LucideIcon;
  title: string;
  description?: string;
}) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full border border-border bg-surface-2 text-ink-3">
        <Icon size={22} strokeWidth={1.5} aria-hidden="true" />
      </span>
      <p className="font-semibold text-ink">{title}</p>
      {description && <p className="max-w-[26ch] text-sm text-ink-3">{description}</p>}
    </div>
  );
}
