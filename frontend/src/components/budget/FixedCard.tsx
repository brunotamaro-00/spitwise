import { BedDouble, Plane } from "lucide-react";

import Card from "@/components/ui/Card";
import SectionHeader from "@/components/ui/SectionHeader";
import { formatUsd, isZeroMoney } from "@/lib/format";
import type { BudgetAnalysis } from "@/types";

/** Los comprometidos que quedan afuera del plan de vivir. */
export default function FixedCard({ b }: { b: BudgetAnalysis }) {
  const f = b.fixed;
  const rows = [
    { icon: BedDouble, label: "Alojamiento", hint: "reservas del itinerario", usd: f.lodging_usd },
    { icon: Plane, label: "Generales", hint: "vuelos, pases, seguros", usd: f.general_usd },
  ];

  return (
    <Card className="p-5">
      <SectionHeader>Fijos</SectionHeader>
      <p className="mt-0.5 text-meta font-medium text-ink-3">
        Fuera del plan de vivir: ya están comprometidos.
      </p>
      <div className="mt-3 flex flex-col">
        {rows.map(({ icon: Icon, label, hint, usd }) => (
          <div
            key={label}
            className="flex items-center gap-3 border-b border-border py-2.5 last:border-0"
          >
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-2 text-ink-3">
              <Icon size={16} strokeWidth={2} aria-hidden="true" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-semibold text-ink-2">{label}</span>
              <span className="block text-meta font-medium text-ink-faint">{hint}</span>
            </span>
            <span className="shrink-0 font-tabular text-sm font-bold text-ink">
              {formatUsd(usd, "whole")}
            </span>
          </div>
        ))}
      </div>
      {f.per_night_usd && !isZeroMoney(f.per_night_usd) && (
        <p className="mt-3 text-meta font-medium text-ink-3">
          Alojamiento ={" "}
          <span className="font-tabular">{formatUsd(f.per_night_usd, "whole")}</span> por noche.
        </p>
      )}
    </Card>
  );
}
