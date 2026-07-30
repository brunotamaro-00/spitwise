export function parseMoney(s: string): number {
  return Number(s);
}

export function capitalize(s: string): string {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}

/** Número con formato argentino: punto de miles, coma decimal, con `decimals`
 *  decimales fijos. */
function formatNumber(n: number, decimals: number): string {
  return n.toLocaleString("es-AR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** ¿El monto es cero a efectos de mostrar? (tolerante a "0", "0.00", "-0"). */
export function isZeroMoney(s: string | null | undefined): boolean {
  if (s == null || s === "") return true;
  const n = Number(s);
  return Number.isNaN(n) || Math.abs(n) < 0.005;
}

/** Precisión monetaria según el rol de la cifra.
 *
 *  `cents` (default) es el estándar de plata: filas, sheet de detalle, balance,
 *  totales por día — donde los centavos son el dato.
 *
 *  `whole` es para las cifras grandes (hero, KPI, chips de ciudad, ritmo,
 *  centro del donut): ahí el decimal es ruido y además no entra. Medido con
 *  Anton a 60px en un viewport de 402px, "USD 12.345,6" son 330,6px contra
 *  322px disponibles — el hero se partía en dos líneas pasando los 10.000.
 *  Sin decimales, "USD 123.456" mide 316,8px y entra. */
export type MoneyPrecision = "cents" | "whole";

const DECIMALS: Record<MoneyPrecision, number> = { cents: 2, whole: 0 };

export function formatUsd(s: string, precision: MoneyPrecision = "cents"): string {
  return `USD ${formatNumber(parseMoney(s), DECIMALS[precision])}`;
}

/** Monto en moneda original para las filas: "20,00", "20,50", "1.234,56". */
export function formatAmount(s: string, precision: MoneyPrecision = "cents"): string {
  return formatNumber(parseMoney(s), DECIMALS[precision]);
}

/** Número sin ceros de relleno: "2", "2,5", "1.234,56". Para etiquetas cortas
 *  donde el decimal fijo es ruido (badge de cashback: "2%", no "2,00%"). */
export function formatCompact(s: string): string {
  return parseMoney(s).toLocaleString("es-AR", { maximumFractionDigits: 2 });
}

/** Valor inicial del input al editar: entero => "20"; decimal => "20,50". */
export function toInputValue(s: string | null | undefined): string {
  if (s == null || s === "") return "";
  const n = Number(s);
  if (Number.isNaN(n)) return String(s);
  return Number.isInteger(n) ? String(n) : String(n).replace(".", ",");
}

/** Hoy en formato ISO (yyyy-mm-dd) en la zona horaria LOCAL del dispositivo.
 *  Nunca usar toISOString().slice(0,10): eso es UTC y después de medianoche
 *  local imputa el gasto al día equivocado. */
export function todayLocal(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const da = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${da}`;
}

/** Fecha corta "dd/mm" sin corrimiento de zona horaria (estándar de la app). */
export function formatShortDate(iso: string): string {
  const [, m, d] = iso.split("-");
  return m && d ? `${d}/${m}` : iso;
}

/** Encabezado de día: día de semana + fecha dd/mm ("vie 06/08"),
 *  sin corrimiento de zona horaria. */
export function formatDayHeader(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  const weekday = new Date(y, m - 1, d).toLocaleDateString("es-AR", { weekday: "short" });
  return `${weekday} ${formatShortDate(iso)}`;
}

/** Filtra la entrada de un campo de monto: solo dígitos, coma y punto.
 *  Impide tipear letras u otros símbolos, y limita a 2 decimales después de
 *  la coma (el separador decimal inequívoco en es-AR). */
export function sanitizeAmountInput(s: string): string {
  const t = s.replace(/[^\d.,]/g, "");
  const comma = t.lastIndexOf(",");
  if (comma === -1) return t;
  const decimals = t.slice(comma + 1).replace(/[.,]/g, "");
  return t.slice(0, comma + 1) + decimals.slice(0, 2);
}

/** Normaliza lo tipeado por el usuario a decimal con punto para el backend.
 *  Acepta coma decimal ("20,50") y miles con punto ("1.234,50"). */
export function normalizeAmountInput(s: string): string {
  const t = s.trim();
  if (t.includes(",")) return t.replace(/\./g, "").replace(",", ".");
  return t;
}
