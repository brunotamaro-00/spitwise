import { formatDayHeader, formatUsd } from "@/lib/format";

/** Header de un grupo de movimientos por día: fecha a la izquierda, total del
 *  día a la derecha. Va sobre canvas (afuera del Card), por eso ink-3.
 *  Vivía duplicado literal entre /movimientos y /ciudades. */
export default function DayHeader({
  date,
  totalUsd,
  as: Tag = "h2",
}: {
  date: string;
  totalUsd: number;
  as?: "h2" | "h3";
}) {
  return (
    <Tag className="mb-1.5 flex items-baseline justify-between gap-2 px-1">
      <span className="text-meta font-semibold uppercase tracking-caps text-ink-3">
        {formatDayHeader(date)}
      </span>
      <span className="font-tabular text-meta font-semibold text-ink-3">
        {formatUsd(String(totalUsd))}
      </span>
    </Tag>
  );
}
