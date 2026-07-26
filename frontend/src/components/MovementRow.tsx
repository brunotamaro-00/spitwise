import { Handshake, Pencil, Trash2 } from "lucide-react";

import Flag from "@/components/Flag";
import { cashbackLabel, netAmount } from "@/lib/cashback";
import { categoryIcon } from "@/lib/categoryIcons";
import { categoryBg, categoryColor } from "@/lib/chartTheme";
import { formatAmount, formatUsd } from "@/lib/format";
import { myShare } from "@/lib/share";
import type { Category, Movement } from "@/types";

const SPLIT_LABEL: Record<string, string> = {
  shared: "Compartido",
  payer_only: "Solo pagador",
  other_only: "Solo del otro",
};

export default function MovementRow({ mv, myId, category, flag, onOpen, onEdit, onDelete, readOnly = false, preferShare = false }: {
  mv: Movement;
  myId?: number;
  category?: Category;
  flag?: string | null;
  /** Tocar la fila abre el detalle (bottom sheet): el target táctil es toda la fila. */
  onOpen?: (m: Movement) => void;
  onEdit?: (m: Movement) => void;
  onDelete?: (m: Movement) => void;
  readOnly?: boolean;
  /** En vistas personales (Ciudades), el primary es "tu parte". */
  preferShare?: boolean;
}) {
  const isSettlement = mv.type === "settlement";
  const cbLabel = isSettlement ? null : cashbackLabel(mv);
  const share = myId != null ? myShare(mv, myId) : 0;
  const Icon = isSettlement ? Handshake : categoryIcon(category?.name);
  const color = isSettlement ? "var(--color-ink-3)" : categoryColor(category?.name ?? null);
  const bg = isSettlement ? "var(--color-surface-2)" : categoryBg(category?.name ?? null);
  const showSharePrimary = preferShare && !isSettlement && myId != null;

  const body = (
    <>
      <span
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
        style={{ background: bg, color }}
        aria-hidden="true"
      >
        <Icon size={17} strokeWidth={2} />
      </span>

      <div className="min-w-0 flex-1">
        {/* Los badges van FUERA del truncate y con shrink-0: adentro del <p>
            desaparecían justo en las descripciones largas (las cuotas siempre lo
            son, por el sufijo "(i/n)"), que es donde más importa verlos. */}
        <div className="flex min-w-0 items-baseline gap-1.5">
          <p className="min-w-0 truncate font-semibold text-ink">
            {mv.description || (isSettlement ? "Pago (saldo)" : "Sin descripción")}
          </p>
          {(mv.status === "pending" || mv.status === "awaiting") && (
            <span className="shrink-0 rounded-full bg-accent-amber-bg px-1.5 py-px text-[10px] font-bold uppercase tracking-wide text-accent-amber">
              {mv.status === "awaiting" ? "Por confirmar" : "Pendiente"}
            </span>
          )}
          {cbLabel && (
            <span
              className="shrink-0 rounded-full bg-accent-teal-bg px-1.5 py-px text-[10px] font-bold uppercase tracking-wide text-accent-teal"
              title={`Cashback ${cbLabel}`}
            >
              CB {cbLabel}
            </span>
          )}
        </div>
        <p className="mt-0.5 truncate text-xs text-ink-3">
          {mv.city_name ? (
            <>
              {flag && <Flag flag={flag} className="mr-1 text-[11px]" />}
              {mv.city_name} ·{" "}
            </>
          ) : null}
          {isSettlement ? "Saldo" : SPLIT_LABEL[mv.split] ?? mv.split}
        </p>
      </div>

      <div className="shrink-0 text-right">
        <p className="font-tabular font-bold text-ink">
          {formatUsd(showSharePrimary ? String(share) : mv.amount_usd)}
        </p>
        {mv.currency !== "USD" && (
          <p className="font-tabular text-xs text-ink-3">
            {mv.currency} {formatAmount(String(netAmount(mv)))}
            {mv.fx_source === "fallback" && (
              <span className="ml-1 font-bold text-danger" title="Tasa aproximada (fallback)">≈</span>
            )}
          </p>
        )}
        {showSharePrimary ? (
          <p className="font-tabular text-[11px] text-ink-faint">ticket {formatUsd(mv.amount_usd)}</p>
        ) : (
          !isSettlement && myId != null && (
            <p className="font-tabular text-[11px] text-ink-faint">tu parte {formatUsd(String(share))}</p>
          )
        )}
      </div>
    </>
  );

  return (
    <div className="flex items-center gap-1 border-b border-border last:border-b-0">
      {onOpen ? (
        <button
          onClick={() => onOpen(mv)}
          aria-label={`Ver detalle de ${mv.description || "movimiento"}`}
          className="-mx-2 flex min-w-0 flex-1 cursor-pointer items-center gap-3 rounded-lg px-2 py-3 text-left transition-colors hover:bg-surface-2/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brick/40"
        >
          {body}
        </button>
      ) : (
        <div className="flex min-w-0 flex-1 items-center gap-3 py-3">{body}</div>
      )}

      {/* Acciones inline solo en desktop; en mobile viven en el sheet de detalle. */}
      {!readOnly && (
        <div className="-mr-2 hidden shrink-0 items-center lg:flex">
          <button
            aria-label={`Editar ${mv.description || "movimiento"}`}
            className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-md text-ink-faint/50 transition-colors hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
            onClick={() => onEdit?.(mv)}
          >
            <Pencil size={14} strokeWidth={1.75} aria-hidden="true" />
          </button>
          <button
            aria-label={`Borrar ${mv.description || "movimiento"}`}
            className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-md text-ink-faint/50 transition-colors hover:bg-danger-bg hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger/40"
            onClick={() => onDelete?.(mv)}
          >
            <Trash2 size={14} strokeWidth={1.75} aria-hidden="true" />
          </button>
        </div>
      )}
    </div>
  );
}
