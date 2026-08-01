import { parseMoney } from "@/lib/format";
import type { BandPosition, CurrentCityBudget, TripCushion } from "@/types";

/** Qué dice el bloque focal de la ciudad en curso.
 *
 *  El caso `over` NO muestra el "por día" negativo: "podés gastar USD -103 por
 *  día" no es una frase. Muestra el excedente total, que es el dato que sirve
 *  para decidir cuánto aflojar en la próxima parada. */
export type BudgetVerdict =
  | { kind: "no_target" }
  | { kind: "margin"; amountUsd: string; days: number }
  | { kind: "over"; amountUsd: string };

export function currentVerdict(c: CurrentCityBudget): BudgetVerdict {
  if (c.target_daily_usd == null || c.remaining_daily_usd == null) {
    return { kind: "no_target" };
  }
  const daily = parseMoney(c.remaining_daily_usd);
  if (daily < 0) {
    const over = Math.abs(parseMoney(c.remaining_budget_usd ?? "0"));
    return { kind: "over", amountUsd: String(over) };
  }
  return { kind: "margin", amountUsd: c.remaining_daily_usd, days: c.remaining_days };
}

/* ------------------------------------------------------------ la banda --- */

/** Tono semántico de una posición en la banda.
 *
 *  `neutral` para "en plan" a propósito: estar adentro del rango no es un
 *  logro que haya que celebrar en verde, es lo esperado. El único tono que
 *  llama la atención es el ámbar de pasarse — y **nunca** es rojo: esto es
 *  contexto para decidir el almuerzo, no una alarma. */
export type BandTone = "teal" | "neutral" | "amber";

export function bandTone(position: BandPosition | null | undefined): BandTone {
  if (position === "under") return "teal";
  if (position === "over") return "amber";
  return "neutral";
}

/** Texto del veredicto. Afuera del rango lleva el % contra el borde que se
 *  violó; adentro no lleva número porque no hay desvío que reportar. */
export function bandLabel(
  position: BandPosition | null | undefined,
  edgeDeltaPct: number | null | undefined,
): string | null {
  if (position == null) return null;
  if (position === "in") return "en plan";
  if (position === "under") return "ahorrando";
  const pct = edgeDeltaPct == null ? null : Math.round(edgeDeltaPct);
  return pct == null || pct === 0 ? "pasado" : `+${pct}%`;
}

/** Fracciones 0..1 de la barra: dónde empieza y termina la zona del plan,
 *  dónde cae el objetivo y hasta dónde llega el gasto real.
 *
 *  La escala deja aire arriba del techo para que la zona del plan no ocupe
 *  toda la barra (sin margen no se ve que se puede pasar), y se estira si el
 *  gasto real se fue por encima. */
export function bandGeometry(min: number, max: number, value: number | null) {
  const scale = Math.max(max * 1.25, (value ?? 0) * 1.08, min * 1.25, 1);
  const pct = (n: number) => Math.min(Math.max((n / scale) * 100, 0), 100);
  return {
    bandStart: pct(min),
    bandWidth: pct(max) - pct(min),
    center: pct((min + max) / 2),
    value: value == null ? null : pct(value),
  };
}

/* ------------------------------------------------------------ colchón ---- */

/** Lectura del colchón del viaje. `ahead` = vienen gastando menos que el plan.
 *
 *  El signo no se esconde: ir arriba del plan es justo el momento en que la
 *  página tiene que servir para algo, y para eso está `neededUsd` (a cuánto
 *  por día hay que ir en lo que queda para cerrar en plan). */
export type CushionRead =
  | { kind: "none" }
  | {
      kind: "ahead" | "behind";
      amountUsd: string;
      neededUsd: string | null;
      remainingNights: number;
    };

export function cushionRead(c: TripCushion): CushionRead {
  if (c.cushion_usd == null || c.covered_nights === 0) return { kind: "none" };
  const value = parseMoney(c.cushion_usd);
  return {
    kind: value < 0 ? "behind" : "ahead",
    amountUsd: String(Math.abs(value)),
    neededUsd: c.needed_daily_usd,
    remainingNights: c.remaining_nights,
  };
}

/* ---------------------------------------------------------- proyección --- */

/** Dónde cae la proyección del viaje respecto del plan.
 *
 *  Con un plan que es rango, "terminan USD 922 arriba" es una media verdad si
 *  esos 922 los pone por encima del **centro** pero la proyección sigue adentro
 *  de la banda: ahí no hay nada que ajustar, y decirlo como desvío entrena a
 *  ignorar la página. `inside` existe justo para eso; afuera, el monto se mide
 *  contra el borde que se pasa, igual que en cada ciudad. */
export type ProjectionRead =
  | { kind: "none" }
  | { kind: "inside" }
  | { kind: "over" | "under"; amountUsd: string };

export function projectionRead(p: {
  projected_living_usd: string | null;
  living_budget_min_usd: string | null;
  living_budget_max_usd: string | null;
}): ProjectionRead {
  if (
    p.projected_living_usd == null ||
    p.living_budget_min_usd == null ||
    p.living_budget_max_usd == null
  ) {
    return { kind: "none" };
  }
  const value = parseMoney(p.projected_living_usd);
  const lo = parseMoney(p.living_budget_min_usd);
  const hi = parseMoney(p.living_budget_max_usd);
  if (value > hi) return { kind: "over", amountUsd: String(value - hi) };
  if (value < lo) return { kind: "under", amountUsd: String(lo - value) };
  return { kind: "inside" };
}

/* ----------------------------------------------------------- cobertura --- */

/** Línea de cobertura. Va SIEMPRE al lado de la varianza: un presupuesto
 *  parcial comparado contra una proyección de noches completas es mentir. */
export function coverageLine(
  covered: number,
  total: number,
  uncoveredNames: string[],
): { complete: boolean; text: string } {
  if (total === 0) return { complete: false, text: "Todavía no hay itinerario" };
  if (covered === 0) {
    return { complete: false, text: "Ninguna parada tiene plan todavía" };
  }
  if (covered >= total) {
    return { complete: true, text: `Las ${total} noches del viaje tienen plan` };
  }
  const faltan = total - covered;
  const noches = `${faltan} noche${faltan === 1 ? "" : "s"} de ${total}`;
  // Sin nombres (el hero del plan no los tiene a mano) el prefijo quedaba
  // colgando en un "Sin plan: · 3 noches de 108".
  if (uncoveredNames.length === 0) {
    return { complete: false, text: `${noches} sin plan` };
  }
  const nombres = uncoveredNames.slice(0, 3).join(", ");
  const resto = uncoveredNames.length > 3 ? ` y ${uncoveredNames.length - 3} más` : "";
  return { complete: false, text: `Sin plan: ${nombres}${resto} · ${noches}` };
}

/** Texto del progreso de la parada en curso. Días, no cuenta regresiva del viaje. */
export function stayProgress(lived: number, total: number): string {
  return `día ${lived} de ${total}`;
}
