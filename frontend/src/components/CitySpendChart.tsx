import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import Card from "@/components/ui/Card";
import { Label } from "@/components/ui/Field";
import { formatUsd, parseMoney } from "@/lib/format";
import { TICK, cityColor } from "@/lib/chartTheme";
import type { CitySpend } from "@/types";

type Row = { name: string; usd: number; total: string; color: string };

function CityTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="rounded-xl border border-border bg-surface px-3 py-2 soft-pop">
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full" style={{ background: r.color }} />
        <span className="text-sm font-semibold text-ink">{r.name}</span>
      </div>
      <div className="mt-0.5 font-tabular text-sm text-ink-2">{formatUsd(r.total)}</div>
    </div>
  );
}

function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

export default function CitySpendChart({
  data,
  title = "Gasto por ciudad",
}: {
  data: CitySpend[];
  title?: string;
}) {
  const rows: Row[] = data.map((c, i) => ({
    name: c.city_name || c.stop_slug || "Sin ciudad",
    usd: parseMoney(c.total_usd),
    total: c.total_usd,
    color: cityColor(i),
  }));
  if (rows.length === 0) return null;
  const many = rows.length > 5;

  return (
    <Card className="p-5">
      <Label className="mb-4 block">{title}</Label>
      <div style={{ height: Math.max(rows.length * 30, 200) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={rows}
            layout="vertical"
            margin={{ top: 4, right: 56, bottom: 0, left: 4 }}
            barCategoryGap={rows.length > 8 ? "18%" : "28%"}
          >
            <XAxis type="number" hide />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ ...TICK, fontSize: many ? 11 : 12 }}
              tickLine={false}
              axisLine={false}
              width={96}
              tickFormatter={(v: string) => truncate(v, 14)}
            />
            <Tooltip cursor={{ fill: "var(--color-surface-2)", opacity: 0.5 }} content={<CityTooltip />} />
            <Bar dataKey="usd" radius={[6, 6, 6, 6]} maxBarSize={26}>
              {rows.map((r) => (
                <Cell key={r.name} fill={r.color} />
              ))}
              <LabelList
                dataKey="total"
                position="right"
                formatter={(v: unknown) => formatUsd(String(v))}
                style={{ fill: "var(--color-ink-2)", fontSize: 11, fontWeight: 700 }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
