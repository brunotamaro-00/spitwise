import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { errorDetail } from "@/api/client";
import { createMovement } from "@/api/movements";
import { listUsers } from "@/api/users";
import Button from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import Modal from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { capitalize, normalizeAmountInput, sanitizeAmountInput, toInputValue } from "@/lib/format";
import { invalidateLedger } from "@/lib/queryClient";
import type { Balance } from "@/types";

/** Registra un settlement: quién paga le transfiere USD X al otro.
 *  Prefill: monto = total de la deuda; paga = el deudor. */
export default function SettleDialog({ balance, onClose }: {
  balance?: Balance; onClose: () => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const { data: users = [] } = useQuery({ queryKey: ["users"], queryFn: listUsers, staleTime: Infinity });
  const [amount, setAmount] = useState(balance ? toInputValue(balance.amount_usd) : "");
  const [paidBy, setPaidBy] = useState<string>(balance?.debtor_id ? String(balance.debtor_id) : "");
  const [err, setErr] = useState<string | null>(null);

  // Sin deuda (`debtor_id` null, el estado normal después de saldar) `paidBy`
  // arrancaba vacío. El <select> no tiene opción vacía, así que el browser
  // pintaba a la primera persona mientras el estado de React seguía en "": el
  // submit dependía de `users[0]` y, con `users` todavía sin resolver, mandaba
  // `paid_by: NaN` → null en JSON y un 422 que no explica nada. El default se
  // deriva una vez, cuando hay de dónde (mismo patrón que AddMovementDialog).
  useEffect(() => {
    if (!paidBy && users.length > 0) {
      setPaidBy(String(balance?.debtor_id ?? users[0].id));
    }
  }, [paidBy, users, balance?.debtor_id]);

  const save = useMutation({
    mutationFn: () =>
      createMovement({
        type: "settlement",
        amount: normalizeAmountInput(amount),
        currency: "USD",
        paid_by: Number(paidBy),
        description: "saldo",
      }),
    onSuccess: () => {
      invalidateLedger(qc);
      toast("success", "Pago registrado");
      onClose();
    },
    onError: (e) => setErr(errorDetail(e, "No se pudo registrar el pago.")),
  });

  function submit(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setErr(null);
    const normalized = normalizeAmountInput(amount);
    if (!normalized || Number.isNaN(Number(normalized)) || Number(normalized) <= 0) {
      setErr("Ingresá un monto válido en USD.");
      return;
    }
    if (!paidBy) {
      setErr("Elegí quién paga.");
      return;
    }
    save.mutate();
  }

  return (
    <Modal title="Saldar deuda" onClose={onClose} size="sm">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <Field label="Quién paga">
          <Select value={paidBy} onChange={(e) => setPaidBy(e.target.value)}>
            {users.map((u) => <option key={u.id} value={u.id}>{capitalize(u.username)}</option>)}
          </Select>
        </Field>
        <Field label="Monto (USD)">
          <Input inputMode="decimal" placeholder="100,00"
                 value={amount} onChange={(e) => setAmount(sanitizeAmountInput(e.target.value))} />
        </Field>
        {err && <p role="alert" className="text-sm font-semibold text-danger">{err}</p>}
        <Button type="submit" disabled={save.isPending} className="mt-1">
          {save.isPending ? "Registrando…" : "Registrar pago"}
        </Button>
      </form>
    </Modal>
  );
}
