import { PiggyBank } from "lucide-react";

import AnimatedUsd from "@/components/ui/AnimatedUsd";
import Card from "@/components/ui/Card";
import { cushionRead } from "@/lib/budget";
import { formatUsd, parseMoney } from "@/lib/format";
import type { BudgetAnalysis } from "@/types";

import CushionMeter from "./CushionMeter";

/** La palanca de control: cuánto llevan ahorrado y a cuánto por día pueden ir
 *  en lo que queda. Es la respuesta a "en la próxima ciudad nos ajustamos".
 *
 *  El colchón es una **resta** (lo que el plan separó − lo que gastaron), y
 *  mostrarla sola pedía fe. La barra pone los dos términos: el hueco entre el
 *  relleno y el poste ES el número grande. Abajo, en su propia superficie, la
 *  única cifra con la que se decide algo hoy — a cuánto por día pueden ir.
 *
 *  Solo con el viaje en curso. Antes de arrancar el colchón es cero por
 *  construcción (no se vivió ninguna noche) y el ritmo necesario ya descuenta
 *  todo lo prepago contra el plan entero, así que la card mostraría un número
 *  bajo y alarmante que no significa nada: el plan lo cuenta el hero. */
export default function CushionCard({ b }: { b: BudgetAnalysis }) {
  const read = cushionRead(b.cushion);
  if (b.trip_status !== "in_progress" || read.kind === "none") return null;

  const ahead = read.kind === "ahead";
  const needed = read.neededUsd;
  const avg = b.cushion.avg_target_daily_usd;
  const planned = b.cushion.budget_to_date_usd;

  return (
    <Card className="overflow-hidden">
      <div className="p-5">
        <div className="flex items-center gap-3">
          <span
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${
              ahead ? "bg-accent-teal-bg text-accent-teal" : "bg-heat-over-bg text-heat-over-ink"
            }`}
          >
            <PiggyBank size={18} strokeWidth={2} aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-meta font-semibold uppercase tracking-caps text-ink-3">
              {ahead ? "Colchón del viaje" : "Arriba del plan"}
            </p>
            <p
              className={`font-display text-3xl leading-none tracking-display font-tabular ${
                ahead ? "text-accent-teal-ink" : "text-heat-over-ink"
              }`}
            >
              {ahead ? "+" : "−"}
              <AnimatedUsd value={read.amountUsd} />
            </p>
          </div>
        </div>

        <p className="mt-3 text-sm font-medium text-ink-2">
          {ahead
            ? "de lo que el plan ya había separado para estos días."
            : "de más contra lo que el plan preveía hasta hoy."}
        </p>

        {planned && (
          <div className="mt-4">
            <CushionMeter
              spent={parseMoney(b.cushion.living_to_date_usd)}
              planned={parseMoney(planned)}
              ahead={ahead}
            />
          </div>
        )}
      </div>

      {/* Superficie propia: es la cifra con la que se decide el almuerzo de hoy,
          no una nota al pie de la de arriba. */}
      {needed && read.remainingNights > 0 && (
        <div className="flex items-end justify-between gap-3 border-t border-border bg-surface-2/60 px-5 py-4">
          <div>
            <p className="text-meta font-semibold uppercase tracking-caps text-ink-3">
              {ahead ? "Podés gastar" : "Para cerrar en plan"}
            </p>
            <p className="mt-1 font-display text-2xl leading-none tracking-display text-ink font-tabular">
              {formatUsd(needed, "whole")}
              <span className="font-sans text-meta font-medium text-ink-3">/día</span>
            </p>
          </div>
          <p className="text-right text-meta font-medium text-ink-3">
            en las {read.remainingNights} noches que quedan
            {avg && (
              <>
                <br />
                plan <span className="font-tabular">{formatUsd(avg, "whole")}</span> por día
              </>
            )}
          </p>
        </div>
      )}
    </Card>
  );
}
