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
 *  relleno y el poste ES el número grande. Abajo, una sola frase con el ritmo
 *  al que pueden ir en lo que queda.
 *
 *  **Un número y una frase, a propósito.** La versión anterior llegó a cinco
 *  cifras (colchón, los dos extremos de la barra rotulados, el ritmo con su
 *  display grande, el plan promedio y el conteo de noches) para responder algo
 *  que se dice en un renglón. La demo pública la abre gente que entra de cero.
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
              {ahead ? "Ahorrado en lo que va del viaje" : "Gastado de más hasta hoy"}
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
            ? "Gastaron menos de lo que tenían planeado hasta hoy."
            : "Gastaron más de lo que tenían planeado hasta hoy."}
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

      {/* Una frase, no un tercer número grande. El ritmo del resto del viaje es
          contexto del colchón, no otra respuesta: con su propio display, su
          conteo de noches y el plan promedio al lado, la card pedía cinco
          números para decir una cosa. En cuerpo de texto tampoco compite con el
          hero — el único permiso grande de la página sigue siendo aquel. */}
      {needed && read.remainingNights > 0 && (
        <p className="border-t border-border bg-surface-2/60 px-5 py-3.5 text-sm font-medium text-ink-2">
          {ahead ? "Pueden gastar " : "Tienen que ir a "}
          <span className="font-tabular font-bold text-ink">
            {formatUsd(needed, "whole")}
          </span>{" "}
          por día en lo que queda del viaje
          {ahead ? "." : " para cerrar en plan."}
        </p>
      )}
    </Card>
  );
}
