import { Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { formatUsd, parseMoney } from "@/lib/format";
import { TOOLTIP_STYLE, categoryColor } from "@/lib/chartTheme";
import type { CategorySpend } from "@/types";

export default function CategoryDonut({ data }: { data: CategorySpend[] }) {
  const rows = data.map((c) => ({
    name: c.name || "Sin categoría",
    icon: c.icon,
    usd: parseMoney(c.total_usd),
    total: c.total_usd,
    color: categoryColor(c.name),
    fill: categoryColor(c.name),
  }));
  if (rows.length === 0) return null;
  return (
    <section className="rounded-[4px] border-2 border-border bg-surface p-4 card-shadow">
      <h2 className="mb-3 text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-3">
        Gasto por categoría
      </h2>
      <div className="h-44">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => formatUsd(String(v))} />
            <Pie data={rows} dataKey="usd" nameKey="name" innerRadius="55%" outerRadius="90%"
                 stroke="#FFFFFF" strokeWidth={2} paddingAngle={1} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-3 flex flex-col gap-1.5">
        {rows.map((r) => (
          <li key={r.name} className="flex items-center gap-2 text-sm">
            <span aria-hidden="true" className="h-3 w-3 shrink-0 rounded-[2px]" style={{ background: r.color }} />
            <span className="min-w-0 flex-1 truncate font-semibold text-ink">
              {r.icon ? `${r.icon} ` : ""}{r.name}
            </span>
            <span className="font-tabular text-ink-2">{formatUsd(r.total)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
