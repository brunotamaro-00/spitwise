import { formatAmount } from "@/lib/format";
import type { Movement } from "@/types";

/** Símbolo corto por moneda para la etiqueta de cashback fijo (fallback = ISO). */
const CURRENCY_SYMBOL: Record<string, string> = {
  USD: "$", EUR: "€", GBP: "£", CHF: "CHF", CZK: "Kč", PLN: "zł", HUF: "Ft", ARS: "$",
};

/** Neto en moneda local: bruto (mv.amount) menos el cashback. Sin cashback
 *  devuelve el bruto tal cual. Espeja app/cashback.py::net_amount. */
export function netAmount(mv: Pick<Movement, "amount" | "cashback_kind" | "cashback_value">): number {
  const gross = Number(mv.amount);
  const value = mv.cashback_value != null ? Number(mv.cashback_value) : null;
  if (!mv.cashback_kind || value == null || Number.isNaN(value)) return gross;
  const reduction = mv.cashback_kind === "pct" ? (gross * value) / 100 : value;
  const net = gross - reduction;
  return net > 0 ? net : 0;
}

/** Etiqueta corta del cashback ("2%" / "5 €") o null si el gasto no tiene. */
export function cashbackLabel(
  mv: Pick<Movement, "currency" | "cashback_kind" | "cashback_value">,
): string | null {
  const value = mv.cashback_value != null ? Number(mv.cashback_value) : null;
  if (!mv.cashback_kind || value == null || Number.isNaN(value)) return null;
  if (mv.cashback_kind === "pct") return `${formatAmount(String(value))}%`;
  return `${formatAmount(String(value))} ${CURRENCY_SYMBOL[mv.currency] ?? mv.currency}`;
}
