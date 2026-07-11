import { Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import Card from "@/components/ui/Card";
import { Label } from "@/components/ui/Field";
import { categoryIcon } from "@/lib/categoryIcons";
import { formatUsd, parseMoney } from "@/lib/format";
import { TOOLTIP_STYLE, categoryColor } from "@/lib/chartTheme";
import type { CategorySpend } from "@/types";

export default function CategoryDonut({ data }: { data: CategorySpend[] }) {
  const rows = data.map((c) => ({
    name: c.name || "Sin categoría",
    usd: parseMoney(c.total_usd),
    total: c.total_usd,
    color: categoryColor(c.name),
    fill: categoryColor(c.name),
  }));
  if (rows.length === 0) return null;
  return (
    <Card className="p-4">
      <Label className="mb-3 block">Gasto por categoría</Label>
      <div className="h-44">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => formatUsd(String(v))} />
            <Pie data={rows} dataKey="usd" nameKey="name" innerRadius="58%" outerRadius="92%"
                 stroke="#FFFFFF" strokeWidth={2} paddingAngle={1} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-3 flex flex-col gap-1.5">
        {rows.map((r) => {
          const Icon = categoryIcon(r.name);
          return (
            <li key={r.name} className="flex items-center gap-2 text-sm">
              <span className="flex items-center justify-center" style={{ color: r.color }}>
                <Icon size={15} strokeWidth={1.75} aria-hidden="true" />
              </span>
              <span className="min-w-0 flex-1 truncate font-medium text-ink">{r.name}</span>
              <span className="font-tabular text-ink-3">{formatUsd(r.total)}</span>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
