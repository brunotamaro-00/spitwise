import { PiggyBank } from "lucide-react";

import AnimatedUsd from "@/components/ui/AnimatedUsd";
import Card from "@/components/ui/Card";
import { cushionRead } from "@/lib/budget";
import { formatUsd } from "@/lib/format";
import type { BudgetAnalysis } from "@/types";

/** La palanca de control: cuánto llevan ahorrado y a cuánto por día pueden ir
 *  en lo que queda. Es la respuesta a "en la próxima ciudad nos ajustamos".
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

  return (
    <Card className="p-5">
      <div className="flex items-start gap-3">
        <span
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${
            ahead ? "bg-accent-teal-bg text-accent-teal" : "bg-accent-amber-bg text-accent-amber"
          }`}
        >
          <PiggyBank size={18} strokeWidth={2} aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-meta font-semibold uppercase tracking-caps text-ink-3">
            {ahead ? "Colchón del viaje" : "Arriba del plan"}
          </p>
          <p
            className={`mt-0.5 font-display text-3xl leading-none tracking-display font-tabular ${
              ahead ? "text-accent-teal-ink" : "text-accent-amber-ink"
            }`}
          >
            {ahead ? "+" : "−"}
            <AnimatedUsd value={read.amountUsd} />
          </p>
          <p className="mt-1.5 text-sm font-medium text-ink-2">
            {ahead
              ? "de lo que el plan ya había separado para estos días."
              : "de más contra lo que el plan preveía hasta hoy."}
          </p>
        </div>
      </div>

      {needed && read.remainingNights > 0 && (
        <div className="mt-4 flex items-baseline justify-between gap-3 border-t border-border pt-3">
          <span className="text-sm font-medium text-ink-2">
            {ahead ? "Podés gastar" : "Para cerrar en plan"}
          </span>
          <span className="text-right">
            <span className="font-tabular text-lg font-bold text-ink">
              {formatUsd(needed, "whole")}
              <span className="font-sans text-meta font-medium text-ink-3">/día</span>
            </span>
            <span className="block text-meta font-medium text-ink-3">
              en las {read.remainingNights} noches que quedan
              {avg && <> · plan {formatUsd(avg, "whole")}</>}
            </span>
          </span>
        </div>
      )}
    </Card>
  );
}
