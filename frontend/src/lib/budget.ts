import { parseMoney } from "@/lib/format";
import type { CurrentCityBudget } from "@/types";

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

/** Línea de cobertura. Va SIEMPRE al lado de la varianza: un presupuesto
 *  parcial comparado contra una proyección de noches completas es mentir. */
export function coverageLine(
  covered: number,
  total: number,
  uncoveredNames: string[],
): { complete: boolean; text: string } {
  if (total === 0) return { complete: false, text: "Todavía no hay itinerario" };
  if (covered === 0) {
    return { complete: false, text: "Ninguna parada tiene presupuesto todavía" };
  }
  if (covered >= total) {
    return { complete: true, text: `Las ${total} noches del viaje tienen presupuesto` };
  }
  const faltan = total - covered;
  const noches = `${faltan} noche${faltan === 1 ? "" : "s"} de ${total}`;
  // Sin nombres (el hero del plan no los tiene a mano) el prefijo quedaba
  // colgando en un "Sin presupuesto: · 3 noches de 108".
  if (uncoveredNames.length === 0) {
    return { complete: false, text: `${noches} sin presupuesto` };
  }
  const nombres = uncoveredNames.slice(0, 3).join(", ");
  const resto = uncoveredNames.length > 3 ? ` y ${uncoveredNames.length - 3} más` : "";
  return { complete: false, text: `Sin presupuesto: ${nombres}${resto} · ${noches}` };
}

/** Texto del progreso de la parada en curso. Días, no cuenta regresiva del viaje. */
export function stayProgress(lived: number, total: number): string {
  return `día ${lived} de ${total}`;
}
