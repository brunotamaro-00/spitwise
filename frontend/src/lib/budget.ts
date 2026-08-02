import type { BadgeTone } from "@/components/ui/Badge";
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

/** El 100% de cualquier barra de $/día: USD 100 por día y por persona.
 *
 *  **Escala fija, no relativa a cada plan.** Antes cada barra se escalaba
 *  contra su propia banda, así que una parada de plan 68–95 gastando 81 y otra
 *  de plan 20–30 gastando 25 dibujaban el relleno a la misma altura: la lista
 *  se veía prolija y no decía nada. Con un eje común, la altura del relleno ES
 *  el gasto y las 27 filas se escanean de un saque. USD 100/día es el techo
 *  natural del viaje (la banda más cara del plan queda holgada adentro) y un
 *  número redondo que se puede tener en la cabeza mientras se scrollea. */
export const BAR_MAX_USD = 100;

/** Los cinco pasos del ritmo contra el plan. `edge` (pegado al techo) existe
 *  porque adentro de una banda ancha no es lo mismo estar en el piso que a un
 *  café de pasarse, y esa distinción es la que evita la sorpresa. */
export type BandLevel = "save" | "plan" | "edge" | "over" | "far";

/** Dentro de la banda: a partir de qué fracción del rango ya es "al límite". */
const EDGE_AT = 0.75;
/** Arriba del techo: hasta qué desvío es "pasado" y no "muy pasado". */
const FAR_AT = 0.25;

/** El nivel del ritmo real dentro (o fuera) de la banda. **Única fuente** del
 *  color en toda la página: barra, badge y card de proyección leen de acá.
 *
 *  Una banda de ancho cero (`min === max`, el caso de no-regresión del modelo
 *  de target único) da `t = 0` ⇒ `plan`, nunca `edge`. */
export function bandLevel(
  value: number | null,
  min: number,
  max: number,
): BandLevel | null {
  if (value == null || !Number.isFinite(value)) return null;
  if (value < min) return "save";
  if (value <= max) {
    const t = max > min ? (value - min) / (max - min) : 0;
    return t > EDGE_AT ? "edge" : "plan";
  }
  // Fuera de la escala de la barra se trata como "muy pasado" pase lo que
  // pase: si el relleno ya no puede crecer, el color tiene que hacerse cargo.
  return value >= BAR_MAX_USD || value / max - 1 > FAR_AT ? "far" : "over";
}

/** Tono de `Badge` de cada paso. Sí, hay rojo: pasarse fuerte del plan es la
 *  única cosa que esta página necesita que se vea desde lejos. */
export function levelTone(level: BandLevel | null | undefined): BadgeTone {
  switch (level) {
    case "save":
      return "teal";
    case "plan":
      return "green";
    case "edge":
      return "amber";
    case "over":
      return "orange";
    case "far":
      return "red";
    default:
      return "neutral";
  }
}

/** Texto del veredicto. Afuera del rango lleva el % contra el borde que se
 *  violó; adentro no lleva número porque no hay desvío que reportar — salvo
 *  `edge`, que avisa sin número porque todavía no hay desvío. */
export function bandLabel(
  position: BandPosition | null | undefined,
  edgeDeltaPct: number | null | undefined,
  level?: BandLevel | null,
): string | null {
  if (position == null) return null;
  if (position === "under") return "ahorrando";
  if (position === "in") return level === "edge" ? "al límite" : "en plan";
  const pct = edgeDeltaPct == null ? null : Math.round(edgeDeltaPct);
  return pct == null || pct === 0 ? "pasado" : `+${pct}%`;
}

/** Porcentajes 0..100 de la barra sobre el eje fijo de `BAR_MAX_USD`: dónde
 *  empieza y termina la zona del plan, dónde cae el objetivo y hasta dónde
 *  llega el gasto real.
 *
 *  `overCap` = el gasto se salió del eje (la barra no puede crecer más y el
 *  extremo tiene que decirlo). `bandClipped` = el plan mismo se sale del eje;
 *  hoy no pasa con ninguna parada, pero la barra no puede dibujar un techo que
 *  no está ahí. */
export function bandGeometry(min: number, max: number, value: number | null) {
  const pct = (n: number) => Math.min(Math.max((n / BAR_MAX_USD) * 100, 0), 100);
  return {
    bandStart: pct(min),
    bandWidth: pct(max) - pct(min),
    center: pct((min + max) / 2),
    value: value == null ? null : pct(value),
    overCap: value != null && value >= BAR_MAX_USD,
    bandClipped: max > BAR_MAX_USD,
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
