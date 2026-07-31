import { useQuery } from "@tanstack/react-query";
import { BedDouble, Plane, Plus, Target, TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";

import { getBudget } from "@/api/budget";
import BudgetTargetDialog from "@/components/BudgetTargetDialog";
import DeltaBadge from "@/components/DeltaBadge";
import Flag from "@/components/Flag";
import AnimatedUsd from "@/components/ui/AnimatedUsd";
import { PageTitle } from "@/components/ui/Brand";
import Card from "@/components/ui/Card";
import ErrorState from "@/components/ui/ErrorState";
import Skeleton from "@/components/ui/Skeleton";
import SkeletonReveal from "@/components/ui/SkeletonReveal";
import { coverageLine, currentVerdict, stayProgress } from "@/lib/budget";
import { formatShortDate, formatUsd, isZeroMoney, parseMoney } from "@/lib/format";
import type { BudgetAnalysis, CityBudget, CurrentCityBudget, TripPlan } from "@/types";

/* ------------------------------------------------------------------ focal */

/** Bloque focal con la ciudad en curso.
 *
 *  El número grande no es "cuánto gastaste" (mirar para atrás) sino **cuánto
 *  queda por día hasta el check-out**: si vinieron ahorrando, sube. Es la
 *  respuesta a "¿salimos a comer hoy?". */
function CurrentHero({ c }: { c: CurrentCityBudget }) {
  const verdict = currentVerdict(c);

  return (
    <Card className="relative overflow-hidden p-6 text-white hero-gradient soft-hero lg:p-7">
      <div className="spit-dots absolute inset-0" aria-hidden="true" />
      <div className="hero-sheen absolute inset-0" aria-hidden="true" />
      <div className="relative">
        <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-white/70">
          {c.country_flag && <Flag flag={c.country_flag} className="text-sm leading-none" />}
          {c.city_name} · {stayProgress(c.lived_nights, c.total_nights)}
        </p>

        {verdict.kind === "no_target" ? (
          <>
            <p className="mt-2 font-display text-5xl leading-none tracking-[-0.02em] font-tabular">
              <AnimatedUsd value={c.living_usd} />
            </p>
            <p className="mt-3 text-sm text-white/85">
              Sin presupuesto para esta parada — cargalo abajo y vas a ver si alcanza.
            </p>
          </>
        ) : (
          <>
            <p className="mt-2 font-display text-6xl leading-none tracking-[-0.02em] font-tabular lg:text-7xl">
              <AnimatedUsd value={verdict.amountUsd} />
            </p>
            <p className="mt-3 text-sm text-white/85">
              {verdict.kind === "margin" ? (
                <>
                  por día hasta el check-out ·{" "}
                  <span className="font-semibold">
                    {verdict.days} día{verdict.days === 1 ? "" : "s"}
                  </span>{" "}
                  por delante
                </>
              ) : (
                <>te pasaste del presupuesto de {c.city_name}</>
              )}
            </p>
          </>
        )}

        {c.target_daily_usd && (
          <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-white/20 pt-4 text-sm text-white/85">
            <span>
              Plan{" "}
              <span className="font-tabular font-semibold text-white">
                {formatUsd(c.target_daily_usd, "whole")}
              </span>
              /día
            </span>
            {c.living_per_day_usd && (
              <span>
                Llevás{" "}
                <span className="font-tabular font-semibold text-white">
                  {formatUsd(c.living_per_day_usd, "whole")}
                </span>
                /día
              </span>
            )}
            <DeltaBadge pct={c.delta_pct} compact />
          </div>
        )}
      </div>
    </Card>
  );
}

/** Antes de arrancar (o terminado el viaje) no hay ciudad en curso: el foco
 *  pasa a ser el plan. Es también el único momento en que revisar los targets
 *  cargados sirve de verdad, porque todavía se pueden ajustar. */
function PlanHero({ plan, finished }: { plan: TripPlan; finished: boolean }) {
  const cov = coverageLine(plan.covered_nights, plan.budget_nights, []);

  return (
    <Card className="relative overflow-hidden p-6 text-white hero-gradient soft-hero lg:p-7">
      <div className="spit-dots absolute inset-0" aria-hidden="true" />
      <div className="hero-sheen absolute inset-0" aria-hidden="true" />
      <div className="relative">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/70">
          {finished ? "El plan · viaje terminado" : "El plan"}
        </p>
        {plan.living_budget_usd ? (
          <>
            <p className="mt-2 font-display text-6xl leading-none tracking-[-0.02em] font-tabular lg:text-7xl">
              <AnimatedUsd value={plan.living_budget_usd} />
            </p>
            <p className="mt-3 text-sm text-white/85">
              vivir · {plan.budget_nights} noches ·{" "}
              <span className="font-tabular font-semibold text-white">
                {formatUsd(plan.avg_target_daily_usd ?? "0", "whole")}
              </span>
              /día promedio
            </p>
          </>
        ) : (
          <>
            <p className="mt-2 font-display text-4xl leading-none tracking-[-0.02em]">
              Sin presupuesto
            </p>
            <p className="mt-3 text-sm text-white/85">
              Cargá un objetivo por día en cada ciudad y esta pantalla te dice si van bien.
            </p>
          </>
        )}

        {plan.next_stop && (
          <div className="mt-5 flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-white/20 pt-4 text-sm text-white/85">
            <span>Arranca en</span>
            {plan.next_stop.country_flag && (
              <Flag flag={plan.next_stop.country_flag} className="text-sm leading-none" />
            )}
            <span className="font-semibold text-white">{plan.next_stop.city_name}</span>
            {plan.next_stop.arrival_date && (
              <span>· {formatShortDate(plan.next_stop.arrival_date)}</span>
            )}
            {plan.next_stop.target_daily_usd && (
              <span>
                ·{" "}
                <span className="font-tabular font-semibold text-white">
                  {formatUsd(plan.next_stop.target_daily_usd, "whole")}
                </span>
                /día
              </span>
            )}
          </div>
        )}

        {!cov.complete && plan.budget_nights > 0 && (
          <p className="mt-3 text-xs text-white/70">{cov.text}</p>
        )}
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------- por ciudad */

function CityRow({ c, onEdit }: { c: CityBudget; onEdit: () => void }) {
  const future = c.status === "future";
  const hasTarget = c.target_daily_usd != null;
  // En una futura el "valor" es el plan: todavía no hay ritmo que mostrar.
  const value = future ? c.target_daily_usd : c.living_per_day_usd;

  return (
    <button
      type="button"
      onClick={onEdit}
      aria-label={`Editar presupuesto de ${c.city_name}`}
      className="focus-ring-inset flex w-full min-h-[56px] cursor-pointer items-center gap-3 border-b border-border py-3 text-left transition-colors last:border-0 hover:bg-surface-2/60"
    >
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-1.5 text-sm font-bold text-ink">
          {c.country_flag && <Flag flag={c.country_flag} className="shrink-0 text-sm leading-none" />}
          <span className="min-w-0 truncate">{c.city_name}</span>
          {c.status === "current" && (
            <span className="shrink-0 rounded-full bg-brick-bg px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-brick-ink">
              hoy
            </span>
          )}
        </p>
        <p className="mt-0.5 text-[11px] font-medium text-ink-3">
          {c.nights} noche{c.nights === 1 ? "" : "s"}
          {/* En una futura el número de la derecha YA es el plan: repetirlo acá
              era decir dos veces lo mismo en la misma fila. */}
          {!hasTarget ? (
            <> · sin presupuesto</>
          ) : future ? (
            <> · por venir</>
          ) : (
            <> · plan <span className="font-tabular">{formatUsd(c.target_daily_usd!, "whole")}</span>/día</>
          )}
          {c.note && <> · {c.note}</>}
        </p>
      </div>

      <div className="flex shrink-0 flex-col items-end gap-1">
        {hasTarget && value && !isZeroMoney(value) ? (
          <span
            className={`font-tabular text-sm font-bold ${future ? "text-ink-3" : "text-ink"}`}
          >
            {formatUsd(value, "whole")}
            <span className="font-sans text-[11px] font-medium text-ink-3">/día</span>
          </span>
        ) : !hasTarget ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-brick-bg px-2 py-1 text-[11px] font-bold text-brick-ink">
            <Plus size={11} strokeWidth={2.5} aria-hidden="true" />
            definir
          </span>
        ) : (
          <span className="text-sm font-medium text-ink-faint">—</span>
        )}
        <DeltaBadge pct={c.delta_pct} compact />
      </div>
    </button>
  );
}

/* ------------------------------------------------------------- proyección */

function ProjectionCard({ b }: { b: BudgetAnalysis }) {
  const p = b.projection;
  const names = useMemo(() => {
    const bySlug = new Map(b.cities.map((c) => [c.stop_slug, c.city_name]));
    return p.uncovered_slugs.map((s) => bySlug.get(s) ?? s);
  }, [b.cities, p.uncovered_slugs]);
  const cov = coverageLine(p.covered_nights, p.budget_nights, names);

  const variance = p.variance_usd == null ? null : parseMoney(p.variance_usd);

  return (
    <Card className="p-5">
      <h2 className="flex items-center gap-2 text-sm font-bold text-ink">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent-teal-bg text-accent-teal">
          <TrendingUp size={15} strokeWidth={2} aria-hidden="true" />
        </span>
        Proyección del viaje
      </h2>

      {p.living_budget_usd && p.projected_living_usd ? (
        <>
          <dl className="mt-4 grid grid-cols-2 gap-3">
            <div>
              <dt className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">
                Presupuesto
              </dt>
              <dd className="font-display text-2xl leading-none text-ink font-tabular">
                {formatUsd(p.living_budget_usd, "whole")}
              </dd>
            </div>
            <div>
              <dt className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">
                Proyectado
              </dt>
              <dd className="font-display text-2xl leading-none text-ink font-tabular">
                {formatUsd(p.projected_living_usd, "whole")}
              </dd>
            </div>
          </dl>
          {variance != null && (
            <p className="mt-3 text-sm font-semibold text-ink-2">
              Al ritmo de lo que ya cerraron, terminan{" "}
              <span
                className={`font-tabular ${variance > 0 ? "text-accent-amber-ink" : "text-accent-teal-ink"}`}
              >
                {formatUsd(String(Math.abs(variance)), "whole")}{" "}
                {variance > 0 ? "arriba" : "abajo"}
              </span>{" "}
              del plan.
            </p>
          )}
        </>
      ) : (
        <p className="mt-3 text-sm font-medium text-ink-2">
          {p.living_budget_usd
            ? "Todavía no hay ninguna ciudad cerrada: la proyección aparece cuando terminen la primera parada."
            : "Cargá presupuestos por ciudad para poder proyectar el viaje."}
        </p>
      )}

      {/* La cobertura va SIEMPRE debajo de la varianza: un presupuesto parcial
          comparado contra una proyección de noches completas es mentir. */}
      <p
        className={`mt-3 border-t border-border pt-3 text-[11px] font-medium ${
          cov.complete ? "text-ink-3" : "text-accent-amber-ink"
        }`}
      >
        {cov.text}
      </p>
    </Card>
  );
}

/* ------------------------------------------------------------------ fijos */

function FixedCard({ b }: { b: BudgetAnalysis }) {
  const f = b.fixed;
  const rows = [
    { icon: BedDouble, label: "Alojamiento", hint: "reservas del itinerario", usd: f.lodging_usd },
    { icon: Plane, label: "Generales", hint: "vuelos, pases, seguros", usd: f.general_usd },
  ];

  return (
    <Card className="p-5">
      <h2 className="text-sm font-bold text-ink">Fijos</h2>
      <p className="mt-0.5 text-[11px] font-medium text-ink-3">
        Fuera del presupuesto de vivir: ya están comprometidos.
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
              <span className="block text-[11px] font-medium text-ink-faint">{hint}</span>
            </span>
            <span className="shrink-0 font-tabular text-sm font-bold text-ink">
              {formatUsd(usd, "whole")}
            </span>
          </div>
        ))}
      </div>
      {f.per_night_usd && !isZeroMoney(f.per_night_usd) && (
        <p className="mt-3 text-[11px] font-medium text-ink-3">
          Alojamiento ={" "}
          <span className="font-tabular">{formatUsd(f.per_night_usd, "whole")}</span> por noche.
        </p>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ page  */

/** ¿Estamos gastando bien? Compara el gasto diario de "vivir" (todo menos
 *  alojamiento y generales) contra un objetivo por ciudad. Sin cuentas
 *  regresivas: las paradas futuras existen, pero nadie las cuenta. */
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
            <Skeleton className="h-48" />
            <Skeleton className="h-64" />
            <Skeleton className="h-32" />
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
        <Card className="px-5 py-1">
          <div className="flex items-center gap-2 py-3">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brick-bg text-brick">
              <Target size={15} strokeWidth={2} aria-hidden="true" />
            </span>
            <h2 className="text-sm font-bold text-ink">Por ciudad</h2>
            <span className="ml-auto text-[11px] font-medium text-ink-3">
              real vs plan · por persona
            </span>
          </div>
          {cities.map((c, i) => (
            <div key={c.stop_slug}>
              {i === firstFuture && i > 0 && (
                <p className="border-b border-border bg-surface-2/50 -mx-5 px-5 py-1.5 text-[10px] font-bold uppercase tracking-[0.1em] text-ink-3">
                  Por venir
                </p>
              )}
              <CityRow c={c} onEdit={() => onEdit(c)} />
            </div>
          ))}
        </Card>
      </div>

      <div className="animate-rise-in stagger-3">
        <ProjectionCard b={b} />
      </div>

      <div className="animate-rise-in stagger-4">
        <FixedCard b={b} />
      </div>
    </div>
  );
}
