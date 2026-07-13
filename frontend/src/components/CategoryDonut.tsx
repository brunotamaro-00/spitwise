import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import Card from "@/components/ui/Card";
import { Label } from "@/components/ui/Field";
import { categoryIcon } from "@/lib/categoryIcons";
import { formatUsd, parseMoney } from "@/lib/format";
import { categoryBg, categoryColor } from "@/lib/chartTheme";
import type { CategorySpend } from "@/types";

type Row = { name: string; usd: number; total: string; color: string; pct: number };

function DonutTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="rounded-xl border border-border bg-surface px-3 py-2 soft-pop">
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
}: {
  data: CategorySpend[];
  title?: string;
  subtitle?: string;
}) {
  const total = data.reduce((acc, c) => acc + parseMoney(c.total_usd), 0);
  const rows: Row[] = data.map((c) => {
    const usd = parseMoney(c.total_usd);
    return {
      name: c.name || "Sin categoría",
      usd,
      total: c.total_usd,
      color: categoryColor(c.name),
      pct: total > 0 ? (usd / total) * 100 : 0,
    };
  });
  if (rows.length === 0) return null;

  return (
    <Card className="flex h-full flex-col p-5">
      <div className="mb-4 flex items-baseline justify-between gap-2">
        <Label className="block">{title}</Label>
        {subtitle && <span className="text-[11px] text-ink-faint">{subtitle}</span>}
      </div>
      <div
        className="relative h-56"
        role="img"
        aria-label={`${title}: total ${formatUsd(total.toFixed(2))} en ${rows.length} categorías`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Tooltip content={<DonutTooltip />} />
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
              animationDuration={650}
            >
              {rows.map((r) => (
                <Cell key={r.name} fill={r.color} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        {/* Total centrado */}
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[11px] font-medium uppercase tracking-wide text-ink-3">Total</span>
          <span className="font-display text-2xl leading-none text-ink font-tabular">
            {formatUsd(total.toFixed(2))}
          </span>
        </div>
      </div>

      <ul className="mt-4 flex flex-col gap-3">
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
    </Card>
  );
}
