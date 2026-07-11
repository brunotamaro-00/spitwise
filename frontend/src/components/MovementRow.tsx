import { Pencil, Trash2 } from "lucide-react";

import { formatUsd } from "@/lib/format";
import type { Movement } from "@/types";

const SPLIT_LABEL: Record<string, string> = {
  shared: "Compartido",
  payer_only: "Solo pagador",
  other_only: "Solo del otro",
};

export default function MovementRow({ mv, onEdit, onDelete }: {
  mv: Movement; onEdit: (m: Movement) => void; onDelete: (m: Movement) => void;
}) {
  const isSettlement = mv.type === "settlement";
  return (
    <div className="flex items-center gap-2 border-b-2 border-border py-3 last:border-b-0">
      <div className="min-w-0 flex-1">
        <p className="truncate font-semibold text-ink">
          {isSettlement ? "🤝 " : ""}
          {mv.description || (isSettlement ? "Pago (saldo)" : "—")}
        </p>
        <p className="mt-0.5 text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-3">
          {mv.movement_date}
          {mv.city_name ? ` · ${mv.city_name}` : ""}
          {!isSettlement ? ` · ${SPLIT_LABEL[mv.split] ?? mv.split}` : ""}
        </p>
      </div>
      <div className="shrink-0 text-right">
        <p className="font-tabular font-bold text-ink">{formatUsd(mv.amount_usd)}</p>
        <p className="font-tabular text-xs text-ink-2">
          {mv.currency} {mv.amount}
          {mv.fx_source === "fallback" && (
            <span className="ml-1 font-bold text-danger" title="Tasa aproximada (fallback)">≈</span>
          )}
        </p>
      </div>
      <button
        aria-label={`Editar ${mv.description || "movimiento"}`}
        className="flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-[4px] text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
        onClick={() => onEdit(mv)}
      >
        <Pencil size={18} strokeWidth={1.5} aria-hidden="true" />
      </button>
      <button
        aria-label={`Borrar ${mv.description || "movimiento"}`}
        className="flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-[4px] text-danger transition-colors hover:bg-danger/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger/40"
        onClick={() => onDelete(mv)}
      >
        <Trash2 size={18} strokeWidth={1.5} aria-hidden="true" />
      </button>
    </div>
  );
}
