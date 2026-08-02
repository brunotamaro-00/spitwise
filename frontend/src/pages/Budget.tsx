import { useQuery } from "@tanstack/react-query";
import { Target } from "lucide-react";
import { useState } from "react";

import { getBudget } from "@/api/budget";
import CityRow from "@/components/budget/CityRow";
import CurrentHero from "@/components/budget/CurrentHero";
import CushionCard from "@/components/budget/CushionCard";
import FixedCard from "@/components/budget/FixedCard";
import PlanHero from "@/components/budget/PlanHero";
import ProjectionCard from "@/components/budget/ProjectionCard";
import BudgetCategoryMix from "@/components/BudgetCategoryMix";
import BudgetTargetDialog from "@/components/BudgetTargetDialog";
import { PageTitle } from "@/components/ui/Brand";
import Card from "@/components/ui/Card";
import ErrorState from "@/components/ui/ErrorState";
import SectionHeader from "@/components/ui/SectionHeader";
import Skeleton from "@/components/ui/Skeleton";
import SkeletonReveal from "@/components/ui/SkeletonReveal";
import type { BudgetAnalysis, CityBudget } from "@/types";

/** ¿Estamos gastando bien? Compara el gasto diario de "vivir" (todo menos
 *  alojamiento y generales) contra un rango por ciudad. Sin cuentas
 *  regresivas: las paradas futuras existen, pero nadie las cuenta.
 *  Las secciones viven en components/budget/. */
export default function Budget() {
  const budget = useQuery({ queryKey: ["budget"], queryFn: getBudget });
  const [editing, setEditing] = useState<CityBudget | null>(null);

  if (budget.isError) {
    return (
      <div className="flex flex-col gap-5">
        <PageTitle>Presupuesto</PageTitle>
        <ErrorState onRetry={() => void budget.refetch()} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="animate-rise-in">
        <PageTitle>Presupuesto</PageTitle>
      </div>

      <SkeletonReveal
        ready={!!budget.data}
        skeleton={
          <div className="flex flex-col gap-5">
            <Skeleton className="h-56" />
            <Skeleton className="h-28" />
            <Skeleton className="h-64" />
          </div>
        }
      >
        {() => <BudgetBody b={budget.data!} onEdit={setEditing} />}
      </SkeletonReveal>

      {editing && (
        <BudgetTargetDialog city={editing} onClose={() => setEditing(null)} />
      )}
    </div>
  );
}

function BudgetBody({
  b,
  onEdit,
}: {
  b: BudgetAnalysis;
  onEdit: (c: CityBudget) => void;
}) {
  // Orden del itinerario, con las archivadas al final (ya viene así del backend).
  const cities = b.cities;
  // Primera parada por venir: corta la lista en dos. Sin el corte, ~25 filas
  // idénticas entierran las que tienen veredicto, que son las que importan.
  const firstFuture = cities.findIndex((c) => c.status === "future");

  return (
    <div className="flex flex-col gap-5">
      <div className="animate-rise-in stagger-1">
        {b.current ? (
          <CurrentHero c={b.current} />
        ) : (
          <PlanHero plan={b.plan} finished={b.trip_status === "finished"} />
        )}
      </div>

      <div className="animate-rise-in stagger-2">
        <CushionCard b={b} />
      </div>

      <div className="animate-rise-in stagger-3">
        <Card className="px-5 py-1">
          <SectionHeader className="py-3" icon={Target} hint="real vs plan · por persona">
            Por ciudad
          </SectionHeader>
          {cities.map((c, i) => (
            <div key={c.stop_slug}>
              {i === firstFuture && i > 0 && (
                <p className="border-b border-border bg-surface-2/50 -mx-5 px-5 py-1.5 text-fine font-bold uppercase tracking-caps text-ink-3">
                  Por venir
                </p>
              )}
              <CityRow c={c} onEdit={() => onEdit(c)} />
            </div>
          ))}
        </Card>
      </div>

      {b.current && (
        <div className="animate-rise-in stagger-4">
          <BudgetCategoryMix c={b.current} />
        </div>
      )}

      <div className="animate-rise-in stagger-5">
        <ProjectionCard b={b} />
      </div>

      <div className="animate-rise-in stagger-5">
        <FixedCard b={b} />
      </div>
    </div>
  );
}
