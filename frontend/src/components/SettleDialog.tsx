import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { createMovement } from "@/api/movements";
import { listUsers } from "@/api/users";
import Button from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import Modal from "@/components/ui/Modal";
import { capitalize, normalizeAmountInput } from "@/lib/format";

/** Registra un settlement: quién paga le transfiere USD X al otro. */
export default function SettleDialog({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const firstRef = useRef<HTMLSelectElement>(null);
  const { data: users = [] } = useQuery({ queryKey: ["users"], queryFn: listUsers, staleTime: Infinity });
  const [amount, setAmount] = useState("");
  const [paidBy, setPaidBy] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { firstRef.current?.focus(); }, []);

  const save = useMutation({
    mutationFn: () =>
      createMovement({
        type: "settlement",
        amount: normalizeAmountInput(amount),
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
    const normalized = normalizeAmountInput(amount);
    if (!normalized || Number.isNaN(Number(normalized)) || Number(normalized) <= 0) {
      setErr("Ingresá un monto válido en USD.");
      return;
    }
    save.mutate();
  }

  return (
    <Modal title="Saldar deuda" onClose={onClose} size="sm">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <Field label="Quién paga">
          <Select ref={firstRef} value={paidBy} onChange={(e) => setPaidBy(e.target.value)}>
            {users.map((u) => <option key={u.id} value={u.id}>{capitalize(u.username)}</option>)}
          </Select>
        </Field>
        <Field label="Monto (USD)">
          <Input inputMode="decimal" placeholder="100,00"
                 value={amount} onChange={(e) => setAmount(e.target.value)} />
        </Field>
        {err && <p role="alert" className="text-sm font-semibold text-danger">{err}</p>}
        <Button type="submit" disabled={save.isPending} className="mt-1">
          {save.isPending ? "Registrando…" : "Registrar pago"}
        </Button>
      </form>
    </Modal>
  );
}
