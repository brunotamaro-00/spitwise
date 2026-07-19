import { useQuery } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";

import { listUsers } from "@/api/users";
import Flag from "@/components/Flag";
import Button from "@/components/ui/Button";
import Modal from "@/components/ui/Modal";
import { categoryIcon } from "@/lib/categoryIcons";
import { categoryBg, categoryColor } from "@/lib/chartTheme";
import { capitalize, formatAmount, formatDayHeader, formatUsd } from "@/lib/format";
import { createdDayKey } from "@/lib/groupByDay";
import { myShare } from "@/lib/share";
import type { Category, Movement } from "@/types";

const SPLIT_LABEL: Record<string, string> = {
  shared: "Compartido 50/50",
  payer_only: "Solo del pagador",
  other_only: "Solo del otro",
};

const FX_LABEL: Record<string, string> = {
  manual: "tasa manual",
  fallback: "tasa aproximada",
};

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border py-2.5 last:border-b-0">
      <dt className="shrink-0 text-[13px] font-semibold text-ink-3">{label}</dt>
      <dd className="min-w-0 truncate text-right text-[15px] font-semibold text-ink">{children}</dd>
    </div>
  );
}

/** Detalle de un movimiento en bottom sheet: toda la ficha (FX incluido) y
 *  acciones con targets táctiles reales — la fila de la lista queda liviana. */
export default function MovementSheet({ mv, category, flag, myId, onEdit, onDelete, onClose }: {
  mv: Movement;
  category?: Category;
  flag?: string | null;
  myId?: number;
  onEdit?: (m: Movement) => void;
  onDelete?: (m: Movement) => void;
  onClose: () => void;
}) {
  const { data: users = [] } = useQuery({ queryKey: ["users"], queryFn: listUsers, staleTime: Infinity });
  const isSettlement = mv.type === "settlement";
  const payer = users.find((u) => u.id === mv.paid_by);
  const Icon = categoryIcon(isSettlement ? undefined : category?.name);
  const share = myId != null ? myShare(mv, myId) : null;
  const fxNote = FX_LABEL[mv.fx_source];

  return (
    <Modal title={mv.description || (isSettlement ? "Pago (saldo)" : "Movimiento")} onClose={onClose}>
      <div className="flex items-start gap-4">
        <span
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full"
          style={{
            background: isSettlement ? "var(--color-surface-2)" : categoryBg(category?.name ?? null),
            color: isSettlement ? "var(--color-ink-3)" : categoryColor(category?.name ?? null),
          }}
          aria-hidden="true"
        >
          <Icon size={20} strokeWidth={2} />
        </span>
        <div className="min-w-0">
          <p className="font-display text-4xl leading-none tracking-[-0.02em] text-ink font-tabular">{formatUsd(mv.amount_usd)}</p>
          {mv.currency !== "USD" && (
            <p className="mt-1.5 font-tabular text-sm text-ink-3">
              {/* El TC necesita sus decimales reales (1,0850), no el formato de 1 decimal. */}
              {mv.currency} {formatAmount(mv.amount)} · TC{" "}
              {Number(mv.fx_rate).toLocaleString("es-AR", { maximumFractionDigits: 4 })}
              {fxNote && <span className="ml-1 font-semibold text-danger">({fxNote})</span>}
            </p>
          )}
        </div>
      </div>

      <dl className="mt-4">
        {!isSettlement && <Row label="Categoría">{category?.name ?? "Sin categoría"}</Row>}
        <Row label="Cargado">{capitalize(formatDayHeader(createdDayKey(mv)))}</Row>
        {!isSettlement && mv.payment_date && (
          <Row label={mv.status === "pending" ? "Se paga" : "Pagado"}>
            {capitalize(formatDayHeader(mv.payment_date))}
            {mv.status === "pending" && (
              <span className="ml-1.5 font-semibold text-accent-amber">· TC provisorio</span>
            )}
          </Row>
        )}
        {!isSettlement && (
          <Row label="Ciudad">
            {mv.city_name ? (
              <span className="inline-flex items-center gap-1.5">
                {flag && <Flag flag={flag} className="text-sm" />}
                {mv.city_name}
              </span>
            ) : (
              "General"
            )}
          </Row>
        )}
        <Row label={isSettlement ? "Pagó (transferencia)" : "Pagó"}>
          {payer ? capitalize(payer.username) : "—"}
        </Row>
        {!isSettlement && <Row label="División">{SPLIT_LABEL[mv.split] ?? mv.split}</Row>}
        {!isSettlement && share != null && <Row label="Tu parte">{formatUsd(String(share))}</Row>}
      </dl>

      {(onEdit || onDelete) && (
        <div className="mt-5 flex gap-2">
          {onDelete && (
            <Button variant="danger" className="flex-1" onClick={() => onDelete(mv)}>
              <Trash2 size={16} strokeWidth={2} aria-hidden="true" />
              Borrar
            </Button>
          )}
          {onEdit && (
            <Button variant="secondary" className="flex-1" onClick={() => onEdit(mv)}>
              <Pencil size={16} strokeWidth={2} aria-hidden="true" />
              Editar
            </Button>
          )}
        </div>
      )}
    </Modal>
  );
}
