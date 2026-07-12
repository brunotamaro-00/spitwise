import { Handshake, Pencil, Trash2 } from "lucide-react";

import { categoryIcon } from "@/lib/categoryIcons";
import { categoryColor } from "@/lib/chartTheme";
import { formatAmount, formatUsd } from "@/lib/format";
import { myShare } from "@/lib/share";
import type { Category, Movement } from "@/types";

const SPLIT_LABEL: Record<string, string> = {
  shared: "Compartido",
  payer_only: "Solo pagador",
  other_only: "Solo del otro",
};

export default function MovementRow({ mv, myId, category, onEdit, onDelete, readOnly = false }: {
  mv: Movement;
  myId?: number;
  category?: Category;
  onEdit?: (m: Movement) => void;
  onDelete?: (m: Movement) => void;
  readOnly?: boolean;
}) {
  const isSettlement = mv.type === "settlement";
  const share = myId != null ? myShare(mv, myId) : 0;
  const Icon = isSettlement ? Handshake : categoryIcon(category?.name);
  const color = isSettlement ? "#8A7F6A" : categoryColor(category?.name ?? null);

  return (
    <div className="flex items-center gap-3 border-b border-border py-3 last:border-b-0">
      <span
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
        style={{ background: `${color}1A`, color }}
        aria-hidden="true"
      >
        <Icon size={17} strokeWidth={2} />
      </span>

      <div className="min-w-0 flex-1">
        <p className="truncate font-semibold text-ink">
          {mv.description || (isSettlement ? "Pago (saldo)" : "Sin descripción")}
        </p>
        <p className="mt-0.5 truncate text-xs text-ink-3">
          {mv.city_name ? `${mv.city_name} · ` : ""}
          {isSettlement ? "Saldo" : SPLIT_LABEL[mv.split] ?? mv.split}
        </p>
      </div>

      <div className="shrink-0 text-right">
        <p className="font-tabular font-bold text-ink">{formatUsd(mv.amount_usd)}</p>
        <p className="font-tabular text-xs text-ink-3">
          {mv.currency} {formatAmount(mv.amount)}
          {mv.fx_source === "fallback" && (
            <span className="ml-1 font-bold text-danger" title="Tasa aproximada (fallback)">≈</span>
          )}
        </p>
        {!isSettlement && myId != null && (
          <p className="font-tabular text-[11px] text-ink-faint">tu parte {formatUsd(String(share))}</p>
        )}
      </div>

      {!readOnly && (
        <div className="flex shrink-0 items-center">
          <button
            aria-label={`Editar ${mv.description || "movimiento"}`}
            className="flex min-h-[40px] min-w-[40px] cursor-pointer items-center justify-center rounded-lg text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
            onClick={() => onEdit?.(mv)}
          >
            <Pencil size={17} strokeWidth={1.75} aria-hidden="true" />
          </button>
          <button
            aria-label={`Borrar ${mv.description || "movimiento"}`}
            className="flex min-h-[40px] min-w-[40px] cursor-pointer items-center justify-center rounded-lg text-ink-faint transition-colors hover:bg-danger-bg hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger/40"
            onClick={() => onDelete?.(mv)}
          >
            <Trash2 size={17} strokeWidth={1.75} aria-hidden="true" />
          </button>
        </div>
      )}
    </div>
  );
}
