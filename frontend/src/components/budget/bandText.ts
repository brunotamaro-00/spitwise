import { formatAmount, formatUsd } from "@/lib/format";

/** "USD 48 – 63" — el plan siempre se dice como el rango que es.
 *  La moneda va una sola vez: "USD 48 – USD 63" ocupa el doble y no aclara nada. */
export function bandText(min: string | null, max: string | null): string | null {
  if (min == null || max == null) return null;
  return min === max
    ? formatUsd(min, "whole")
    : `${formatUsd(min, "whole")} – ${formatAmount(max, "whole")}`;
}
