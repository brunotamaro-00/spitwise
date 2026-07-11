import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";

import { deleteMovement, listMovements } from "@/api/movements";
import AddMovementDialog from "@/components/AddMovementDialog";
import MovementRow from "@/components/MovementRow";
import type { Movement } from "@/types";

export default function Movements() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Movement | null>(null);
  const { data = [], isLoading } = useQuery({ queryKey: ["movements"], queryFn: listMovements });
  const del = useMutation({
    mutationFn: (m: Movement) => deleteMovement(m.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["movements"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["balance"] });
    },
  });

  function onDelete(m: Movement) {
    if (window.confirm(`¿Borrar "${m.description || m.type}" (${m.currency} ${m.amount})?`)) {
      del.mutate(m);
    }
  }

  return (
    <div className="animate-fade-in">
      <div className="mb-3 flex items-center justify-between">
        <h1 className="font-display text-3xl uppercase leading-none text-ink">Movimientos</h1>
        <button
          onClick={() => { setEditing(null); setOpen(true); }}
          className="flex min-h-[44px] cursor-pointer items-center gap-1 rounded-[2px] bg-brick px-3 font-display uppercase text-surface hard-shadow-ink transition-transform hover:brightness-105 active:translate-x-[3px] active:translate-y-[3px] active:shadow-none"
        >
          <Plus size={16} strokeWidth={2} aria-hidden="true" /> Agregar
        </button>
      </div>
      <div className="rounded-[4px] border-2 border-border bg-surface px-4 card-shadow">
        {data.map((m) => (
          <MovementRow key={m.id} mv={m}
            onEdit={(mv) => { setEditing(mv); setOpen(true); }}
            onDelete={onDelete} />
        ))}
        {!isLoading && data.length === 0 && (
          <p className="py-10 text-center text-ink-3">Sin movimientos todavía.</p>
        )}
      </div>
      {open && <AddMovementDialog editing={editing} onClose={() => setOpen(false)} />}
    </div>
  );
}
