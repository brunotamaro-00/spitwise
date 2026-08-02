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

/** Fija el plan de "vivir" de una parada: un RANGO USD/día por persona.
 *
 *  Rango y no número porque un presupuesto de viaje nunca es un punto: el
 *  techo es el límite (recién arriba de ahí se pasaron) y el centro, derivado,
 *  es el objetivo contra el que se miden colchón y proyección.
 *
 *  Solo invalida `["budget"]`: el plan no es un movimiento, así que no toca
 *  balance, dashboard ni la lista de gastos. */
export default function BudgetTargetDialog({ city, onClose }: {
  city: CityBudget;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const [min, setMin] = useState(
    city.target_min_usd ? toInputValue(city.target_min_usd) : "",
  );
  const [max, setMax] = useState(
    city.target_max_usd ? toInputValue(city.target_max_usd) : "",
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
        daily_min_usd: normalizeAmountInput(min),
        daily_max_usd: normalizeAmountInput(max),
        note: note.trim() || null,
      }),
    onSuccess: () => done("Plan guardado"),
    onError: (e) => setErr(errorDetail(e, "No se pudo guardar el plan.")),
  });

  const remove = useMutation({
    mutationFn: () => deleteStopBudget(city.stop_slug),
    onSuccess: () => done("Plan borrado"),
    onError: (e) => setErr(errorDetail(e, "No se pudo borrar el plan.")),
  });

  const busy = save.isPending || remove.isPending;

  const lo = Number(normalizeAmountInput(min));
  const hi = Number(normalizeAmountInput(max));
  const center = lo > 0 && hi >= lo ? (lo + hi) / 2 : null;

  function submit(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setErr(null);
    if (!(lo > 0) || !(hi > 0)) {
      setErr("Ingresá el mínimo y el máximo por día, en USD.");
      return;
    }
    if (hi < lo) {
      setErr("El máximo no puede ser menor que el mínimo.");
      return;
    }
    save.mutate();
  }

  return (
    <Modal title={city.city_name} onClose={onClose} size="sm" locked={busy}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <Field
          label="Plan por día"
          hint="USD por persona, sin alojamiento: comida, café, super, transporte, salidas y actividades. El máximo es el techo."
        >
          <div className="flex items-center gap-2">
            <Input
              inputMode="decimal"
              autoFocus
              aria-label="Mínimo por día"
              placeholder="mínimo"
              value={min}
              onChange={(e) => setMin(sanitizeAmountInput(e.target.value))}
            />
            <span aria-hidden="true" className="shrink-0 text-sm font-bold text-ink-3">
              –
            </span>
            <Input
              inputMode="decimal"
              aria-label="Máximo por día"
              placeholder="máximo"
              value={max}
              onChange={(e) => setMax(sanitizeAmountInput(e.target.value))}
            />
          </div>
        </Field>

        {center != null && (
          <p className="-mt-1 text-xs font-medium text-ink-3">
            Objetivo{" "}
            <span className="font-tabular font-semibold text-ink-2">
              USD {Math.round(center)}
            </span>
            /día — el centro del rango, contra el que se miden el colchón y la proyección.
          </p>
        )}

        <Field label="Nota" hint="Opcional: por qué ese rango.">
          <Input
            placeholder="hostel con cocina"
            maxLength={200}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </Field>

        <p className="text-xs font-medium text-ink-3">
          {city.nights} noche{city.nights === 1 ? "" : "s"}
          {city.movement_count > 0 && (
            <>
              {" · "}
              <Link
                to={`/ciudades?c=${city.stop_slug}`}
                className="focus-ring inline-flex items-center gap-1 rounded-lg font-semibold text-brick transition-colors hover:text-brick-hover"
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
