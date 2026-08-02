import Badge from "@/components/ui/Badge";
import { bandLabel, bandTone } from "@/lib/budget";
import type { BandPosition } from "@/types";

/** Veredicto contra la banda del plan: `ahorrando` · `en plan` · `+9%`.
 *
 *  Es el par en palabras del `BudgetBandBar`: el color nunca viaja solo. Nunca
 *  rojo — pasarse del plan de una ciudad es información, no un error. Sin
 *  posición (parada futura o sin plan) no renderiza nada. */
export default function BandBadge({
  position,
  edgeDeltaPct,
}: {
  position: BandPosition | null | undefined;
  edgeDeltaPct: number | null | undefined;
}) {
  const label = bandLabel(position, edgeDeltaPct);
  if (label == null) return null;
  return (
    <Badge tone={bandTone(position)} tabular={position === "over"}>
      {label}
    </Badge>
  );
}
