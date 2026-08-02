import { useQuery } from "@tanstack/react-query";
import { BedDouble, PiggyBank, Plane, Plus, Target, TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";

import { getBudget } from "@/api/budget";
import BandBadge from "@/components/BandBadge";
import BudgetBandBar from "@/components/BudgetBandBar";
import BudgetCategoryMix from "@/components/BudgetCategoryMix";
import BudgetTargetDialog from "@/components/BudgetTargetDialog";
import Flag from "@/components/Flag";
import AnimatedUsd from "@/components/ui/AnimatedUsd";
import Badge from "@/components/ui/Badge";
import { PageTitle } from "@/components/ui/Brand";
import Card from "@/components/ui/Card";
import ErrorState from "@/components/ui/ErrorState";
import Skeleton from "@/components/ui/Skeleton";
import SkeletonReveal from "@/components/ui/SkeletonReveal";
import {
  coverageLine,
  currentVerdict,
  cushionRead,
  projectionRead,
  stayProgress,
} from "@/lib/budget";
import { formatAmount, formatShortDate, formatUsd, isZeroMoney } from "@/lib/format";
import type {
  BudgetAnalysis,
  CityBudget,
  CurrentCityBudget,
  TripPlan,
} from "@/types";

/** "USD 48 – 63" — el plan siempre se dice como el rango que es.
 *  La moneda va una sola vez: "USD 48 – USD 63" ocupa el doble y no aclara nada. */
function bandText(min: string | null, max: string | null): string | null {
  if (min == null || max == null) return null;
  return min === max
    ? formatUsd(min, "whole")
    : `${formatUsd(min, "whole")} – ${formatAmount(max, "whole")}`;
}

/* ------------------------------------------------------------------ focal */

/** Bloque focal con la ciudad en curso.
 *
 *  El número grande no es "cuánto gastaste" (mirar para atrás) sino **cuánto
 *  queda por día hasta el check-out**: si vinieron ahorrando, sube. Es la
 *  respuesta a "¿salimos a comer hoy?". Debajo, la banda ubica el ritmo real
 *  dentro del plan, que es lo que dice si hace falta ajustar o no. */
function CurrentHero({ c }: { c: CurrentCityBudget }) {
  const verdict = currentVerdict(c);
  const plan = bandText(c.target_min_usd, c.target_max_usd);

  return (
    <Card className="relative overflow-hidden p-6 text-white hero-gradient soft-hero lg:p-7">
      <div className="spit-dots absolute inset-0" aria-hidden="true" />
      <div className="hero-sheen absolute inset-0" aria-hidden="true" />
      <div className="relative">
        <p className="flex items-center gap-2 text-meta font-semibold uppercase tracking-eyebrow text-white/70">
          {c.country_flag && <Flag flag={c.country_flag} className="text-sm leading-none" />}
          {c.city_name} · {stayProgress(c.lived_nights, c.total_nights)}
        </p>

        {verdict.kind === "no_target" ? (
          <>
            <p className="mt-2 font-display text-5xl leading-none tracking-display font-tabular">
              <AnimatedUsd value={c.living_usd} />
            </p>
            <p className="mt-3 text-sm text-white/85">
              Sin plan para esta parada — cargalo abajo y vas a ver si alcanza.
            </p>
          </>
        ) : (
          <>
            <p className="mt-2 font-display text-6xl leading-none tracking-display font-tabular lg:text-7xl">
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
                <>te pasaste del plan de {c.city_name}</>
              )}
            </p>
          </>
        )}

        {plan && c.target_min_usd && c.target_max_usd && (
          <div className="mt-5 border-t border-white/20 pt-4">
            <div className="flex items-baseline justify-between gap-3 text-sm text-white/85">
              <span>
                Llevás{" "}
                <span className="font-tabular font-semibold text-white">
                  {formatUsd(c.living_per_day_usd ?? "0", "whole")}
                </span>
                /día
              </span>
              <BandBadge position={c.band_position} edgeDeltaPct={c.edge_delta_pct} />
            </div>
            <div className="mt-2.5">
              <BudgetBandBar
                min={c.target_min_usd}
                max={c.target_max_usd}
                value={c.living_per_day_usd}
                position={c.band_position}
                size="lg"
                variant="hero"
                label={c.city_name}
              />
            </div>
            <p className="mt-2 text-meta font-medium text-white/70">
              Plan <span className="font-tabular">{plan}</span> por día · la marca es el objetivo
            </p>
          </div>
        )}
      </div>
    </Card>
  );
}

/** Antes de arrancar (o terminado el viaje) no hay ciudad en curso: el foco
 *  pasa a ser el plan. Es también el único momento en que revisar las bandas
 *  cargadas sirve de verdad, porque todavía se pueden ajustar. */
function PlanHero({ plan, finished }: { plan: TripPlan; finished: boolean }) {
  const cov = coverageLine(plan.covered_nights, plan.budget_nights, []);
  const total = bandText(plan.living_budget_min_usd, plan.living_budget_max_usd);

  return (
    <Card className="relative overflow-hidden p-6 text-white hero-gradient soft-hero lg:p-7">
      <div className="spit-dots absolute inset-0" aria-hidden="true" />
      <div className="hero-sheen absolute inset-0" aria-hidden="true" />
      <div className="relative">
        <p className="text-meta font-semibold uppercase tracking-eyebrow text-white/70">
          {finished ? "El plan · viaje terminado" : "El plan"}
        </p>
        {total ? (
          <>
            <p className="mt-2 font-display text-4xl leading-none tracking-display font-tabular lg:text-5xl">
              {total}
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
            <p className="mt-2 font-display text-4xl leading-none tracking-display">
              Sin plan
            </p>
            <p className="mt-3 text-sm text-white/85">
              Cargá un rango por día en cada ciudad y esta pantalla te dice si van bien.
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
            {bandText(plan.next_stop.target_min_usd, plan.next_stop.target_max_usd) && (
              <span>
                ·{" "}
                <span className="font-tabular font-semibold text-white">
                  {bandText(plan.next_stop.target_min_usd, plan.next_stop.target_max_usd)}
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

/* ------------------------------------------------------- colchón + ritmo */

/** La palanca de control: cuánto llevan ahorrado y a cuánto por día pueden ir
 *  en lo que queda. Es la respuesta a "en la próxima ciudad nos ajustamos".
 *
 *  Solo con el viaje en curso. Antes de arrancar el colchón es cero por
 *  construcción (no se vivió ninguna noche) y el ritmo necesario ya descuenta
 *  todo lo prepago contra el plan entero, así que la card mostraría un número
 *  bajo y alarmante que no significa nada: el plan lo cuenta el hero. */
function CushionCard({ b }: { b: BudgetAnalysis }) {
  const read = cushionRead(b.cushion);
  if (b.trip_status !== "in_progress" || read.kind === "none") return null;

  const ahead = read.kind === "ahead";
  const needed = read.neededUsd;
  const avg = b.cushion.avg_target_daily_usd;

  return (
    <Card className="p-5">
      <div className="flex items-start gap-3">
        <span
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${
            ahead ? "bg-accent-teal-bg text-accent-teal" : "bg-accent-amber-bg text-accent-amber"
          }`}
        >
          <PiggyBank size={18} strokeWidth={2} aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-meta font-semibold uppercase tracking-caps text-ink-3">
            {ahead ? "Colchón del viaje" : "Arriba del plan"}
          </p>
          <p
            className={`mt-0.5 font-display text-3xl leading-none tracking-display font-tabular ${
              ahead ? "text-accent-teal-ink" : "text-accent-amber-ink"
            }`}
          >
            {ahead ? "+" : "−"}
            <AnimatedUsd value={read.amountUsd} />
          </p>
          <p className="mt-1.5 text-sm font-medium text-ink-2">
            {ahead
              ? "de lo que el plan ya había separado para estos días."
              : "de más contra lo que el plan preveía hasta hoy."}
          </p>
        </div>
      </div>

      {needed && read.remainingNights > 0 && (
        <div className="mt-4 flex items-baseline justify-between gap-3 border-t border-border pt-3">
          <span className="text-sm font-medium text-ink-2">
            {ahead ? "Podés gastar" : "Para cerrar en plan"}
          </span>
          <span className="text-right">
            <span className="font-tabular text-lg font-bold text-ink">
              {formatUsd(needed, "whole")}
              <span className="font-sans text-meta font-medium text-ink-3">/día</span>
            </span>
            <span className="block text-meta font-medium text-ink-3">
              en las {read.remainingNights} noches que quedan
              {avg && <> · plan {formatUsd(avg, "whole")}</>}
            </span>
          </span>
        </div>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------- por ciudad */

function CityRow({ c, onEdit }: { c: CityBudget; onEdit: () => void }) {
  const future = c.status === "future";
  const hasPlan = c.target_min_usd != null && c.target_max_usd != null;
  // En una futura el "valor" es el plan: todavía no hay ritmo que mostrar.
  const value = future ? null : c.living_per_day_usd;
  const plan = bandText(c.target_min_usd, c.target_max_usd);

  return (
    <button
      type="button"
      onClick={onEdit}
      aria-label={`Editar el plan de ${c.city_name}`}
      className="focus-ring-inset flex w-full min-h-[56px] cursor-pointer flex-col gap-1.5 border-b border-border py-3 text-left transition-[background-color,transform] last:border-0 hover:bg-surface-2/60 active:scale-[0.99]"
    >
      <div className="flex w-full items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-1.5 text-sm font-bold text-ink">
            {c.country_flag && <Flag flag={c.country_flag} className="shrink-0 text-sm leading-none" />}
            <span className="min-w-0 truncate">{c.city_name}</span>
            {c.status === "current" && (
              <Badge tone="brick" size="sm" caps className="shrink-0">
                hoy
              </Badge>
            )}
          </p>
          <p className="mt-0.5 text-meta font-medium text-ink-3">
            {c.nights} noche{c.nights === 1 ? "" : "s"}
            {plan ? <> · plan <span className="font-tabular">{plan}</span></> : <> · sin plan</>}
            {c.note && <> · {c.note}</>}
          </p>
        </div>

        <div className="flex shrink-0 flex-col items-end gap-1">
          {!hasPlan ? (
            <Badge tone="brick">
              <Plus size={11} strokeWidth={2.5} aria-hidden="true" />
              definir
            </Badge>
          ) : value && !isZeroMoney(value) ? (
            <span className="font-tabular text-sm font-bold text-ink">
              {formatUsd(value, "whole")}
              <span className="font-sans text-meta font-medium text-ink-3">/día</span>
            </span>
          ) : (
            <span className="text-meta font-medium text-ink-faint">
              {future ? "por venir" : "—"}
            </span>
          )}
          <BandBadge position={c.band_position} edgeDeltaPct={c.edge_delta_pct} />
        </div>
      </div>

      {/* La barra es lo que se escanea: con 27 filas, nadie lee 27 números. */}
      {hasPlan && (
        <BudgetBandBar
          min={c.target_min_usd!}
          max={c.target_max_usd!}
          value={value}
          position={c.band_position}
          label={c.city_name}
        />
      )}
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
  const total = bandText(p.living_budget_min_usd, p.living_budget_max_usd);
  const read = projectionRead(p);

  return (
    <Card className="p-5">
      <h2 className="flex items-center gap-2 text-sm font-bold text-ink">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent-teal-bg text-accent-teal">
          <TrendingUp size={15} strokeWidth={2} aria-hidden="true" />
        </span>
        Proyección del viaje
      </h2>

      {total && p.projected_living_usd ? (
        <>
          <dl className="mt-4 grid grid-cols-2 gap-3">
            <div>
              <dt className="text-meta font-semibold uppercase tracking-wide text-ink-3">
                Plan
              </dt>
              <dd className="font-display text-xl leading-none text-ink font-tabular">
                {total}
              </dd>
            </div>
            <div>
              <dt className="text-meta font-semibold uppercase tracking-wide text-ink-3">
                Proyectado
              </dt>
              <dd className="font-display text-xl leading-none text-ink font-tabular">
                {formatUsd(p.projected_living_usd, "whole")}
              </dd>
            </div>
          </dl>
          <p className="mt-3 text-sm font-semibold text-ink-2">
            Al ritmo de lo que ya cerraron,{" "}
            {read.kind === "inside" ? (
              <span className="text-accent-teal-ink">terminan dentro del plan.</span>
            ) : read.kind === "none" ? null : (
              <>
                terminan{" "}
                <span
                  className={`font-tabular ${
                    read.kind === "over" ? "text-accent-amber-ink" : "text-accent-teal-ink"
                  }`}
                >
                  {formatUsd(read.amountUsd, "whole")}{" "}
                  {read.kind === "over" ? "arriba del techo" : "abajo del piso"}
                </span>
                .
              </>
            )}
          </p>
        </>
      ) : (
        <p className="mt-3 text-sm font-medium text-ink-2">
          {total
            ? "Todavía no hay ninguna ciudad cerrada: la proyección aparece cuando terminen la primera parada."
            : "Cargá planes por ciudad para poder proyectar el viaje."}
        </p>
      )}

      {/* La cobertura va SIEMPRE debajo de la varianza: un presupuesto parcial
          comparado contra una proyección de noches completas es mentir. */}
      <p
        className={`mt-3 border-t border-border pt-3 text-meta font-medium ${
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

/* ------------------------------------------------------------------ page  */

/** ¿Estamos gastando bien? Compara el gasto diario de "vivir" (todo menos
 *  alojamiento y generales) contra un rango por ciudad. Sin cuentas
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
          <div className="flex items-center gap-2 py-3">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brick-bg text-brick">
              <Target size={15} strokeWidth={2} aria-hidden="true" />
            </span>
            <h2 className="text-sm font-bold text-ink">Por ciudad</h2>
            <span className="ml-auto text-meta font-medium text-ink-3">
              real vs plan · por persona
            </span>
          </div>
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
