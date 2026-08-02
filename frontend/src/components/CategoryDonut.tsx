import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import Card from "@/components/ui/Card";
import SectionHeader from "@/components/ui/SectionHeader";
import { categoryBg, categoryColor, categoryIcon } from "@/lib/chartTheme";
import { formatUsd, parseMoney } from "@/lib/format";
import { DURATION } from "@/lib/motion";
import type { CategorySpend } from "@/types";

type Row = { name: string; usd: number; total: string; color: string; pct: number };

function DonutTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="relative z-20 rounded-xl border border-border bg-surface px-3 py-2 soft-pop">
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full" style={{ background: r.color }} />
        <span className="text-sm font-semibold text-ink">{r.name}</span>
      </div>
      <div className="mt-0.5 font-tabular text-sm text-ink-2">
        {formatUsd(r.total)} · {r.pct.toFixed(0)}%
      </div>
    </div>
  );
}

export default function CategoryDonut({
  data,
  title = "Gasto por categoría",
  subtitle,
  /** Total canónico (p. ej. `summary.total_usd` del hero). Sin esto, el centro
   *  redondea la suma de categorías a dólares enteros por separado del hero y
   *  pueden diferir en USD 1 (mitades de centavo del split + round por gajo). */
  totalUsd,
  /** En /ciudades: desktop pone el detalle a la derecha; mobile lo apila
   *  debajo del donut (como antes). */
  sideBySide = false,
}: {
  data: CategorySpend[];
  title?: string;
  subtitle?: string;
  totalUsd?: string;
  sideBySide?: boolean;
}) {
  // Denominador de %: lo que está en el gráfico. El rótulo del centro usa
  // `totalUsd` cuando viene del mismo summary que el hero.
  const slicesTotal = data.reduce((acc, c) => acc + parseMoney(c.total_usd), 0);
  const displayTotal = totalUsd ?? slicesTotal.toFixed(2);
  const rows: Row[] = data.map((c) => {
    const usd = parseMoney(c.total_usd);
    return {
      name: c.name || "Sin categoría",
      usd,
      total: c.total_usd,
      color: categoryColor(c.name),
      pct: slicesTotal > 0 ? (usd / slicesTotal) * 100 : 0,
    };
  });
  if (rows.length === 0) return null;

  return (
    <Card className="flex h-full flex-col p-5">
      <SectionHeader quiet className="mb-4" hint={subtitle}>
        {title}
      </SectionHeader>
      <div
        className={
          sideBySide
            ? "flex flex-col gap-4 lg:flex-row lg:items-center lg:gap-8"
            : "flex flex-col gap-4"
        }
      >
        <div
          className={
            sideBySide
              ? "relative mx-auto h-56 w-full max-w-xs shrink-0 lg:mx-0 lg:w-[14rem]"
              : "relative h-56"
          }
          role="img"
          aria-label={`${title}: total ${formatUsd(displayTotal)} en ${rows.length} categorías`}
        >
          {/* Total detrás del chart para que el tooltip quede por encima */}
          <div className="pointer-events-none absolute inset-0 z-0 flex flex-col items-center justify-center">
            <span className="text-meta font-medium uppercase tracking-wide text-ink-3">Total</span>
            <span className="font-display text-2xl leading-none text-ink font-tabular">
              {formatUsd(displayTotal, "whole")}
            </span>
          </div>
          <div className="relative z-10 h-full w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Tooltip content={<DonutTooltip />} wrapperStyle={{ zIndex: 20 }} />
                <Pie
                  data={rows}
                  dataKey="usd"
                  nameKey="name"
                  innerRadius="62%"
                  outerRadius="94%"
                  paddingAngle={rows.length > 1 ? 2 : 0}
                  stroke="var(--color-surface)"
                  strokeWidth={3}
                  startAngle={90}
                  endAngle={-270}
                  animationDuration={DURATION.verySlow * 1000}
                >
                  {rows.map((r) => (
                    <Cell key={r.name} fill={r.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <ul
          className={`flex min-w-0 flex-col gap-3 ${
            sideBySide ? "lg:flex-1" : ""
          }`}
        >
          {rows.map((r) => {
            const Icon = categoryIcon(r.name);
            return (
              <li key={r.name} className="flex items-center gap-3 text-sm">
                <span
                  className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg"
                  style={{ background: categoryBg(r.name), color: r.color }}
                >
                  <Icon size={15} strokeWidth={2} aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="truncate font-semibold text-ink">{r.name}</span>
                    <span className="font-tabular text-ink-2">{formatUsd(r.total)}</span>
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
                      <span
                        className="block h-full rounded-full"
                        style={{ width: `${Math.max(r.pct, 2)}%`, background: r.color }}
                      />
                    </span>
                    <span className="w-9 shrink-0 text-right font-tabular text-xs text-ink-3">
                      {r.pct.toFixed(0)}%
                    </span>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </Card>
  );
}
