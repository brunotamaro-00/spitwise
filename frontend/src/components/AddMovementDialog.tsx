import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { listCategories } from "@/api/categories";
import { createMovement, updateMovement } from "@/api/movements";
import { getMe, listStops, listUsers } from "@/api/users";
import Button from "@/components/ui/Button";
import DatePicker from "@/components/ui/DatePicker";
import { Field, Input, Select } from "@/components/ui/Field";
import Modal from "@/components/ui/Modal";
import { capitalize, normalizeAmountInput, sanitizeAmountInput, toInputValue } from "@/lib/format";
import type { Movement } from "@/types";

const GENERAL = "__general__"; // gasto sin ciudad
const CURRENCIES = ["USD", "EUR", "GBP", "CHF", "CZK", "PLN", "HUF", "ARS"];
const SPLITS = [
  { value: "shared", label: "Compartido" },
  { value: "payer_only", label: "Solo pagador" },
  { value: "other_only", label: "Solo del otro" },
];

/** Alta y edición de movimientos. `editing` presente => PATCH parcial. */
export default function AddMovementDialog({ editing, onClose }: {
  editing?: Movement | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const firstRef = useRef<HTMLInputElement>(null);
  const { data: categories = [] } = useQuery({ queryKey: ["categories"], queryFn: listCategories, staleTime: Infinity });
  const { data: stops = [] } = useQuery({ queryKey: ["stops"], queryFn: listStops, staleTime: Infinity });
  const { data: users = [] } = useQuery({ queryKey: ["users"], queryFn: listUsers, staleTime: Infinity });
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe, staleTime: Infinity });

  const [amount, setAmount] = useState(toInputValue(editing?.amount));
  const [currency, setCurrency] = useState(editing?.currency ?? "USD");
  const [description, setDescription] = useState(editing?.description ?? "");
  const [categoryId, setCategoryId] = useState<string>(editing?.category_id?.toString() ?? "");
  const [split, setSplit] = useState(editing?.split ?? "shared");
  const [date, setDate] = useState(editing?.movement_date ?? new Date().toISOString().slice(0, 10));
  // Sin ciudad al editar (y sin parada) => se asume gasto general.
  const [stopSlug, setStopSlug] = useState<string>(
    editing?.stop_slug ?? (editing && !editing.city_name ? GENERAL : ""),
  );
  const [paidBy, setPaidBy] = useState<string>(editing?.paid_by?.toString() ?? "");
  const [err, setErr] = useState<string | null>(null);

  // Nuevo movimiento: default de pagador = usuario logueado, cuando llega `me`.
  useEffect(() => {
    if (!editing && me && !paidBy) setPaidBy(String(me.id));
  }, [editing, me, paidBy]);

  useEffect(() => { firstRef.current?.focus(); }, []);

  const save = useMutation({
    mutationFn: async () => {
      const stop = stops.find((s) => s.slug === stopSlug);
      const body: Partial<Movement> & { general?: boolean } = {
        amount: normalizeAmountInput(amount),
        currency,
        description: description || null,
        category_id: categoryId ? Number(categoryId) : null,
        split,
        movement_date: date,
        // Ciudad vacía => el backend deriva por fecha. "General" => sin ciudad.
        stop_slug: stop ? stop.slug : null,
        city_name: stop ? stop.name : null,
        general: stopSlug === GENERAL,
      };
      if (paidBy) body.paid_by = Number(paidBy);
      return editing ? updateMovement(editing.id, body) : createMovement(body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["movements"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["balance"] });
      onClose();
    },
    onError: () => setErr("No se pudo guardar. Revisá el monto."),
  });

  function submit(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setErr(null);
    if (!amount || Number.isNaN(Number(normalizeAmountInput(amount)))) {
      setErr("Ingresá un monto válido.");
      return;
    }
    save.mutate();
  }

  return (
    <Modal title={editing ? "Editar movimiento" : "Agregar movimiento"} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <div className="grid grid-cols-[1fr_auto] gap-3">
          <Field label="Monto">
            <Input ref={firstRef} inputMode="decimal" placeholder="20,00"
                   value={amount} onChange={(e) => setAmount(sanitizeAmountInput(e.target.value))} />
          </Field>
          <Field label="Moneda">
            <Select value={currency} onChange={(e) => setCurrency(e.target.value)}>
              {CURRENCIES.map((c) => <option key={c}>{c}</option>)}
            </Select>
          </Field>
        </div>
        <Field label="Descripción">
          <Input placeholder="cena, taxi, museo…"
                 value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Categoría">
            <Select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
              <option value="">—</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
          </Field>
          <Field label="Ciudad">
            <Select value={stopSlug} onChange={(e) => setStopSlug(e.target.value)}>
              <option value="">Auto (por fecha)</option>
              <option value={GENERAL}>General (sin ciudad)</option>
              {stops.map((s) => (
                <option key={s.slug} value={s.slug}>{s.country_flag ? `${s.country_flag} ` : ""}{s.name}</option>
              ))}
            </Select>
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="División">
            <Select value={split} onChange={(e) => setSplit(e.target.value)}>
              {SPLITS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </Select>
          </Field>
          <Field label="Pagó">
            <Select value={paidBy} onChange={(e) => setPaidBy(e.target.value)}>
              {users.map((u) => <option key={u.id} value={u.id}>{capitalize(u.username)}</option>)}
            </Select>
          </Field>
        </div>
        <Field label="Fecha">
          <DatePicker value={date} onChange={setDate} stops={stops} />
        </Field>
        {err && <p role="alert" className="text-sm font-semibold text-danger">{err}</p>}
        <Button type="submit" disabled={save.isPending} className="mt-1">
          {save.isPending ? "Guardando…" : "Guardar"}
        </Button>
      </form>
    </Modal>
  );
}
