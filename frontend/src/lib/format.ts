export function parseMoney(s: string): number {
  return Number(s);
}

export function capitalize(s: string): string {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}

/** Número con formato argentino: punto de miles, coma decimal. Siempre con
 *  exactamente 1 decimal ("20,0", "306,5"): un solo estándar en toda la app. */
function formatNumber(n: number): string {
  return n.toLocaleString("es-AR", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

/** ¿El monto es cero a efectos de mostrar? (tolerante a "0", "0.00", "-0"). */
export function isZeroMoney(s: string | null | undefined): boolean {
  if (s == null || s === "") return true;
  const n = Number(s);
  return Number.isNaN(n) || Math.abs(n) < 0.005;
}

export function formatUsd(s: string): string {
  return `USD ${formatNumber(parseMoney(s))}`;
}

/** Monto en moneda original para las filas: "20", "20,50", "1.234,56". */
export function formatAmount(s: string): string {
  return formatNumber(parseMoney(s));
}

/** Valor inicial del input al editar: entero => "20"; decimal => "20,50". */
export function toInputValue(s: string | null | undefined): string {
  if (s == null || s === "") return "";
  const n = Number(s);
  if (Number.isNaN(n)) return String(s);
  return Number.isInteger(n) ? String(n) : String(n).replace(".", ",");
}

/** Encabezado de día legible sin corrimiento de zona horaria ("vie 6 ago"). */
export function formatDayHeader(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return new Date(y, m - 1, d).toLocaleDateString("es-AR", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
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
