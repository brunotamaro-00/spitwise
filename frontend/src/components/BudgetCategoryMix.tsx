import { useQuery } from "@tanstack/react-query";

import { listCategories } from "@/api/categories";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import { categoryBg, categoryColor, categoryIcon } from "@/lib/chartTheme";
import { formatUsd } from "@/lib/format";
import type { CategoryMix, CurrentCityBudget } from "@/types";

const TOP = 5;

/** Umbrales del chip "×N vs lo normal".
 *
 *  Con dos días en una ciudad la mezcla es ruido: una sola cena mueve el share
 *  cincuenta puntos. Solo se compara contra categorías que pesan de verdad en
 *  el viaje y cuando la diferencia es grande, así el chip aparece poco y
 *  cuando aparece significa algo. */
const MIN_TRIP_SHARE = 4;
const MIN_RATIO_GAP = 0.35;

function mixChip(m: CategoryMix): string | null {
  if (m.ratio == null || (m.trip_share_pct ?? 0) < MIN_TRIP_SHARE) return null;
  if (Math.abs(m.ratio - 1) < MIN_RATIO_GAP) return null;
  const n = m.ratio.toFixed(1).replace(".", ",").replace(",0", "");
  return `×${n} vs lo normal`;
}

/** En qué se va el "vivir" de la parada en curso.
 *
 *  El monto crudo depende de cuántos días llevás acá; lo que dice algo es el
 *  **share**: que el café sea el 22% de lo que gastás en esta ciudad cuando en
 *  el viaje es el 9%. Por eso la barra es share de la parada y el chip compara
 *  proporciones, no plata. */
export default function BudgetCategoryMix({ c }: { c: CurrentCityBudget }) {
  const { data: categories = [] } = useQuery({
    queryKey: ["categories"],
    queryFn: listCategories,
    staleTime: Infinity,
  });
  const names = new Map(categories.map((k) => [k.id, k.name]));

  const rows = c.by_category.slice(0, TOP);
  if (rows.length === 0) return null;
  // Escala relativa al rubro más grande: con shares chicos, normalizar contra
  // 100 dejaba cinco barritas idénticas y sin información.
  const top = Math.max(...rows.map((m) => m.share_pct ?? 0), 1);

  return (
    <Card className="p-5">
      <h2 className="text-sm font-bold text-ink">En qué se te va</h2>
      <p className="mt-0.5 text-meta font-medium text-ink-3">
        Vivir en {c.city_name}, sin alojamiento · tu parte
      </p>

      <ul className="mt-3 flex flex-col gap-3">
        {rows.map((m) => {
          const name = m.category_id == null ? null : names.get(m.category_id) ?? null;
          const Icon = categoryIcon(name);
          const color = categoryColor(name);
          const chip = mixChip(m);
          return (
            <li key={m.category_id ?? "none"} className="flex items-center gap-3">
              <span
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                style={{ backgroundColor: categoryBg(name), color }}
              >
                <Icon size={15} strokeWidth={2} aria-hidden="true" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-baseline gap-2">
                  <span className="min-w-0 truncate text-sm font-semibold text-ink">
                    {name ?? "Sin categoría"}
                  </span>
                  {chip && (
                    <Badge size="sm" className="shrink-0">
                      {chip}
                    </Badge>
                  )}
                </span>
                <span
                  className="mt-1.5 block h-1.5 w-full overflow-hidden rounded-full bg-surface-2"
                  aria-hidden="true"
                >
                  <span
                    className="block h-full rounded-full"
                    style={{
                      width: `${Math.max(((m.share_pct ?? 0) / top) * 100, 3)}%`,
                      backgroundColor: color,
                    }}
                  />
                </span>
              </span>
              <span className="shrink-0 text-right">
                <span className="block font-tabular text-sm font-bold text-ink">
                  {formatUsd(m.living_usd, "whole")}
                </span>
                {m.share_pct != null && (
                  <span className="block font-tabular text-meta font-medium text-ink-3">
                    {Math.round(m.share_pct)}%
                  </span>
                )}
              </span>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
