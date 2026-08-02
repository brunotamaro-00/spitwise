import Badge from "@/components/ui/Badge";
import { bandLabel, bandLevel, levelTone } from "@/lib/budget";
import { parseMoney } from "@/lib/format";
import type { BandPosition } from "@/types";

/** Veredicto contra la banda del plan: `ahorrando` · `en plan` · `al límite` · `+9%`.
 *
 *  Es el par en palabras del `BudgetBandBar`: el color de la rampa nunca viaja
 *  solo. `band_position` (del backend) decide si HAY veredicto — null en una
 *  parada futura o sin plan —; los tres números deciden el paso de la rampa,
 *  con la misma `bandLevel` que pinta la barra. */
export default function BandBadge({
  position,
  edgeDeltaPct,
  min,
  max,
  value,
}: {
  position: BandPosition | null | undefined;
  edgeDeltaPct: number | null | undefined;
  min?: string | null;
  max?: string | null;
  value?: string | null;
}) {
  const level =
    min == null || max == null || value == null
      ? null
      : bandLevel(parseMoney(value), parseMoney(min), parseMoney(max));
  const label = bandLabel(position, edgeDeltaPct, level);
  if (label == null) return null;
  return (
    <Badge tone={levelTone(level)} tabular={position === "over"}>
      {label}
    </Badge>
  );
}
