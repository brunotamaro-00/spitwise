import { Bar, BarChart, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import Card from "@/components/ui/Card";
import { Label } from "@/components/ui/Field";
import { formatAmount, formatUsd, parseMoney } from "@/lib/format";
import { ACCENT, TICK } from "@/lib/chartTheme";
import type { CitySpend } from "@/types";

type Row = { name: string; usd: number; total: string };

function CityTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="rounded-xl border border-border bg-surface px-3 py-2 soft-pop">
      <div className="text-sm font-semibold text-ink">{r.name}</div>
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
  // Una sola medida (magnitud): un solo tono. La identidad la dan las etiquetas
  // del eje, no el color — colorear por posición repinta al filtrar y no informa.
  const rows: Row[] = data.map((c) => ({
    name: c.city_name || c.stop_slug || "Sin ciudad",
    usd: parseMoney(c.total_usd),
    total: c.total_usd,
  }));
  if (rows.length === 0) return null;
  const many = rows.length > 5;
  const total = rows.reduce((acc, r) => acc + r.usd, 0);

  return (
    <Card className="flex h-full flex-col p-5">
      <Label className="mb-4 block">{title}</Label>
      {/* relative + hijo absoluto: el 100% del ResponsiveContainer necesita una
          altura definida; min-height sola no la da y el chart colapsa a 0. */}
      <div
        className="relative flex-1"
        style={{ minHeight: Math.max(rows.length * 30, 200) }}
        role="img"
        aria-label={`${title}: total ${formatUsd(total.toFixed(2))} en ${rows.length} ciudades`}
      >
        {/* Centrado con tope de altura por fila: llena la celda sin esparcir
            de más las barras cuando hay pocas ciudades. */}
        <div className="absolute inset-0 flex items-center">
        <div className="h-full w-full" style={{ maxHeight: rows.length * 64 + 12 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={rows}
            layout="vertical"
            margin={{ top: 4, right: 70, bottom: 0, left: 4 }}
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
            <Bar dataKey="usd" fill={ACCENT} radius={[6, 6, 6, 6]} maxBarSize={26} animationDuration={600}>
              {/* Solo el número: "USD" está implícito (toda la app está en USD)
                  y el prefijo hacía que el label se parta en dos líneas. */}
              <LabelList
                dataKey="total"
                position="right"
                formatter={(v: unknown) => formatAmount(String(v))}
                style={{ fill: "var(--color-ink-2)", fontSize: 11, fontWeight: 700 }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        </div>
        </div>
      </div>
    </Card>
  );
}
