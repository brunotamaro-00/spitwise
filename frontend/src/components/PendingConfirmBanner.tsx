import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellRing, Check, RefreshCcw } from "lucide-react";
import { useState } from "react";

import { confirmMovement } from "@/api/movements";
import { listUsers } from "@/api/users";
import Button from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { capitalize, formatShortDate, formatUsd } from "@/lib/format";
import type { Movement } from "@/types";

/** Aviso de gastos futuros que llegaron a su fecha y esperan confirmación
 *  manual del pagador. Aparece desde 1 día antes de la fecha de pago y sale al
 *  confirmar. Cada ítem: confirmar tal cual o cambiar quién pagó antes de dar OK. */
export default function PendingConfirmBanner({ items }: { items: Movement[] }) {
  if (items.length === 0) return null;
  return (
    <div className="animate-fade-in mb-3 rounded-xl border border-accent-amber/30 bg-accent-amber-bg/60 p-3">
      <div className="mb-2 flex items-center gap-2 px-1">
        <BellRing size={16} strokeWidth={2.25} className="text-accent-amber" aria-hidden="true" />
        <p className="text-sm font-semibold text-ink">
          {items.length === 1 ? "Un gasto llegó a su fecha" : `${items.length} gastos llegaron a su fecha`}
          <span className="ml-1 font-normal text-ink-3">· confirmá quién pagó</span>
        </p>
      </div>
      <div className="flex flex-col gap-2">
        {items.map((m) => <PendingRow key={m.id} mv={m} />)}
      </div>
    </div>
  );
}

function PendingRow({ mv }: { mv: Movement }) {
  const qc = useQueryClient();
  const toast = useToast();
  const { data: users = [] } = useQuery({ queryKey: ["users"], queryFn: listUsers, staleTime: Infinity });
  // Pagador elegido para confirmar; arranca en quién quedó cargado por default.
  const [paidBy, setPaidBy] = useState<number>(mv.paid_by);

  const confirm = useMutation({
    mutationFn: () => confirmMovement(mv.id, paidBy !== mv.paid_by ? paidBy : undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["movements"] });
      qc.invalidateQueries({ queryKey: ["balance"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["city"] });
      toast("success", "Gasto confirmado");
    },
    onError: () => toast("error", "No se pudo confirmar. Probá de nuevo."),
  });

  const payerName = capitalize(users.find((u) => u.id === paidBy)?.username ?? "");

  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="flex items-baseline justify-between gap-2">
        <p className="min-w-0 truncate text-sm font-semibold text-ink">
          {mv.description || "Gasto"}
        </p>
        <span className="font-tabular shrink-0 text-sm font-semibold text-ink">
          {formatUsd(mv.amount_usd)}
        </span>
      </div>
      {mv.payment_date && (
        <p className="mt-0.5 text-xs text-ink-3">
          {mv.city_name ? `${mv.city_name} · ` : ""}fecha de pago {formatShortDate(mv.payment_date)}
        </p>
      )}
      <div className="mt-2.5 flex items-center gap-2">
        {/* Toggle de pagador: quién pagó realmente este gasto. */}
        <div className="flex flex-1 overflow-hidden rounded-lg border border-border">
          {users.map((u) => {
            const active = u.id === paidBy;
            return (
              <button
                key={u.id}
                type="button"
                onClick={() => setPaidBy(u.id)}
                aria-pressed={active}
                className={`flex-1 cursor-pointer px-2 py-2 text-sm font-semibold transition-colors ${
                  active ? "bg-brick-bg text-brick" : "bg-surface text-ink-3 hover:bg-surface-2"
                }`}
              >
                {capitalize(u.username)}
              </button>
            );
          })}
        </div>
        <Button
          size="sm"
          onClick={() => confirm.mutate()}
          disabled={confirm.isPending}
          aria-label={`Confirmar gasto, pagó ${payerName}`}
        >
          {confirm.isPending ? (
            <RefreshCcw size={15} strokeWidth={2.25} className="animate-spin" aria-hidden="true" />
          ) : (
            <Check size={16} strokeWidth={2.5} aria-hidden="true" />
          )}
          Confirmar
        </Button>
      </div>
    </div>
  );
}
