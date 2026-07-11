import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { createMovement } from "@/api/movements";
import { listUsers } from "@/api/users";
import { capitalize } from "@/lib/format";

const field =
  "min-h-[44px] rounded-[4px] border-2 border-border bg-surface px-3 font-semibold focus:border-border-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-brick/40";
const label = "text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-3";

/** Registra un settlement: quién paga le transfiere USD X al otro. */
export default function SettleDialog({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const firstRef = useRef<HTMLInputElement>(null);
  const { data: users = [] } = useQuery({ queryKey: ["users"], queryFn: listUsers, staleTime: Infinity });
  const [amount, setAmount] = useState("");
  const [paidBy, setPaidBy] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    firstRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const save = useMutation({
    mutationFn: () =>
      createMovement({
        type: "settlement",
        amount,
        currency: "USD",
        paid_by: Number(paidBy || users[0]?.id),
        description: "saldo",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["balance"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["movements"] });
      onClose();
    },
    onError: () => setErr("No se pudo registrar el pago."),
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!amount || Number.isNaN(Number(amount)) || Number(amount) <= 0) {
      setErr("Ingresá un monto válido en USD.");
      return;
    }
    save.mutate();
  }

  // Portal al body: evita que un ancestro con transform re-ancle el `fixed`.
  return createPortal(
    <div className="fixed inset-0 z-20 flex items-end justify-center bg-ink/40 sm:items-center" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Saldar deuda"
        className="max-h-[92dvh] w-full max-w-sm animate-fade-in overflow-y-auto rounded-t-[8px] border-2 border-ink bg-canvas p-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] sm:max-h-[85dvh] sm:rounded-[4px] sm:hard-shadow-ink"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-2xl uppercase text-ink">Saldar</h2>
          <button
            aria-label="Cerrar"
            className="flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-[4px] text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
            onClick={onClose}
          >
            <X size={20} strokeWidth={1.5} aria-hidden="true" />
          </button>
        </div>
        <form onSubmit={submit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className={label}>Quién paga</span>
            <select className={`${field} cursor-pointer`} value={paidBy} onChange={(e) => setPaidBy(e.target.value)}>
              {users.map((u) => (
                <option key={u.id} value={u.id}>{capitalize(u.username)}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className={label}>Monto (USD)</span>
            <input ref={firstRef} className={field} inputMode="decimal" placeholder="100.00"
                   value={amount} onChange={(e) => setAmount(e.target.value)} />
          </label>
          {err && <p role="alert" className="text-sm font-semibold text-danger">{err}</p>}
          <button
            disabled={save.isPending}
            className="mt-1 min-h-[48px] cursor-pointer rounded-[2px] bg-ink font-display text-lg uppercase tracking-wide text-surface hard-shadow-ink transition-transform hover:brightness-110 active:translate-x-[3px] active:translate-y-[3px] active:shadow-none disabled:opacity-60"
          >
            {save.isPending ? "Registrando…" : "Registrar pago"}
          </button>
        </form>
      </div>
    </div>,
    document.body,
  );
}
