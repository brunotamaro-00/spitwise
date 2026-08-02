import { Plus } from "lucide-react";

import BandBadge from "@/components/BandBadge";
import BudgetBandBar from "@/components/BudgetBandBar";
import Flag from "@/components/Flag";
import Badge from "@/components/ui/Badge";
import { formatUsd, isZeroMoney } from "@/lib/format";
import type { CityBudget } from "@/types";

import { bandText } from "./bandText";

/** Fila de una parada: nombre + plan + ritmo real + veredicto contra la banda.
 *  Toda la fila es el target (edita el plan de esa ciudad). */
export default function CityRow({ c, onEdit }: { c: CityBudget; onEdit: () => void }) {
  const future = c.status === "future";
  const hasPlan = c.target_min_usd != null && c.target_max_usd != null;
  // En una futura el "valor" es el plan: todavía no hay ritmo que mostrar.
  const value = future ? null : c.living_per_day_usd;
  const plan = bandText(c.target_min_usd, c.target_max_usd);

  return (
    <button
      type="button"
      onClick={onEdit}
      aria-label={`Editar el plan de ${c.city_name}`}
      className="focus-ring-inset flex w-full min-h-[56px] cursor-pointer flex-col gap-1.5 border-b border-border py-3 text-left transition-[background-color,transform] last:border-0 hover:bg-surface-2/60 active:scale-[0.99]"
    >
      <div className="flex w-full items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-1.5 text-sm font-bold text-ink">
            {c.country_flag && <Flag flag={c.country_flag} className="shrink-0 text-sm leading-none" />}
            <span className="min-w-0 truncate">{c.city_name}</span>
            {c.status === "current" && (
              <Badge tone="brick" size="sm" caps className="shrink-0">
                hoy
              </Badge>
            )}
          </p>
          <p className="mt-0.5 text-meta font-medium text-ink-3">
            {c.nights} noche{c.nights === 1 ? "" : "s"}
            {plan ? <> · plan <span className="font-tabular">{plan}</span></> : <> · sin plan</>}
            {c.note && <> · {c.note}</>}
          </p>
        </div>

        <div className="flex shrink-0 flex-col items-end gap-1">
          {!hasPlan ? (
            <Badge tone="brick">
              <Plus size={11} strokeWidth={2.5} aria-hidden="true" />
              definir
            </Badge>
          ) : value && !isZeroMoney(value) ? (
            <span className="font-tabular text-sm font-bold text-ink">
              {formatUsd(value, "whole")}
              <span className="font-sans text-meta font-medium text-ink-3">/día</span>
            </span>
          ) : (
            <span className="text-meta font-medium text-ink-faint">
              {future ? "por venir" : "—"}
            </span>
          )}
          <BandBadge position={c.band_position} edgeDeltaPct={c.edge_delta_pct} />
        </div>
      </div>

      {/* La barra es lo que se escanea: con 27 filas, nadie lee 27 números. */}
      {hasPlan && (
        <BudgetBandBar
          min={c.target_min_usd!}
          max={c.target_max_usd!}
          value={value}
          position={c.band_position}
          label={c.city_name}
        />
      )}
    </button>
  );
}
