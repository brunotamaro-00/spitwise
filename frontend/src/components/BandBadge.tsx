import { bandLabel, bandTone } from "@/lib/budget";
import type { BandPosition } from "@/types";

const TONES = {
  teal: "bg-accent-teal-bg text-accent-teal-ink",
  neutral: "bg-surface-2 text-ink-3",
  amber: "bg-accent-amber-bg text-accent-amber-ink",
} as const;

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
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-bold ${
        TONES[bandTone(position)]
      } ${position === "over" ? "font-tabular" : ""}`}
    >
      {label}
    </span>
  );
}
