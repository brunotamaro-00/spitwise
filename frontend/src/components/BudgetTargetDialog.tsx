import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { errorDetail } from "@/api/client";
import { deleteStopBudget, putStopBudget } from "@/api/budget";
import Button from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import Modal from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { normalizeAmountInput, sanitizeAmountInput, toInputValue } from "@/lib/format";
import type { CityBudget } from "@/types";

/** Fija el target de "vivir" de una parada: USD/día por persona.
 *
 *  Solo invalida `["budget"]`: el target no es un movimiento, así que no toca
 *  balance, dashboard ni la lista de gastos. */
export default function BudgetTargetDialog({ city, onClose }: {
  city: CityBudget;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const [amount, setAmount] = useState(
    city.target_daily_usd ? toInputValue(city.target_daily_usd) : "",
  );
  const [note, setNote] = useState(city.note ?? "");
  const [err, setErr] = useState<string | null>(null);

  const done = (msg: string) => {
    qc.invalidateQueries({ queryKey: ["budget"] });
    toast("success", msg);
    onClose();
  };

  const save = useMutation({
    mutationFn: () =>
      putStopBudget(city.stop_slug, {
        daily_usd: normalizeAmountInput(amount),
        note: note.trim() || null,
      }),
    onSuccess: () => done("Presupuesto guardado"),
    onError: (e) => setErr(errorDetail(e, "No se pudo guardar el presupuesto.")),
  });

  const remove = useMutation({
    mutationFn: () => deleteStopBudget(city.stop_slug),
    onSuccess: () => done("Presupuesto borrado"),
    onError: (e) => setErr(errorDetail(e, "No se pudo borrar el presupuesto.")),
  });

  const busy = save.isPending || remove.isPending;

  function submit(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setErr(null);
    const normalized = normalizeAmountInput(amount);
    if (!normalized || Number.isNaN(Number(normalized)) || Number(normalized) <= 0) {
      setErr("Ingresá un monto por día en USD.");
      return;
    }
    save.mutate();
  }

  return (
    <Modal title={city.city_name} onClose={onClose} size="sm" locked={busy}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <Field
          label="Presupuesto por día"
          hint="USD por persona, sin alojamiento: comida, café, super, transporte, salidas y actividades."
        >
          <Input
            inputMode="decimal"
            autoFocus
            placeholder="0"
            value={amount}
            onChange={(e) => setAmount(sanitizeAmountInput(e.target.value))}
          />
        </Field>

        <Field label="Nota" hint="Opcional: por qué ese número.">
          <Input
            placeholder="hostel con cocina"
            maxLength={200}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </Field>

        <p className="text-[12px] font-medium text-ink-3">
          {city.nights} noche{city.nights === 1 ? "" : "s"}
          {city.movement_count > 0 && (
            <>
              {" · "}
              <Link
                to={`/ciudades?c=${city.stop_slug}`}
                className="focus-ring inline-flex items-center gap-1 rounded-md font-semibold text-brick transition-colors hover:text-brick-hover"
              >
                {city.movement_count === 1
                  ? "Ver el gasto"
                  : `Ver los ${city.movement_count} gastos`}
                <ArrowRight size={12} strokeWidth={2.25} aria-hidden="true" />
              </Link>
            </>
          )}
        </p>

        {err && <p className="text-sm font-medium text-danger">{err}</p>}

        <div className="mt-1 flex gap-2">
          <Button type="submit" disabled={busy} className="flex-1">
            {save.isPending ? "Guardando…" : "Guardar"}
          </Button>
          {city.target_daily_usd && (
            <Button
              type="button"
              variant="ghost"
              disabled={busy}
              onClick={() => remove.mutate()}
            >
              Borrar
            </Button>
          )}
        </div>
      </form>
    </Modal>
  );
}
