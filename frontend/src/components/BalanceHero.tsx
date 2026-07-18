import { Check, Handshake } from "lucide-react";

import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import NumberPopIn from "@/components/ui/NumberPopIn";
import { formatUsd, isZeroMoney } from "@/lib/format";
import type { Balance } from "@/types";

/** Card compacta de balance: quién le debe a quién + acción de saldar.
 *  Secundaria a propósito — el protagonista del dashboard es el gasto total. */
export default function BalanceHero({ balance, names, myId, onSettle }: {
  balance: Balance; names: Record<number, string>; myId?: number; onSettle: () => void;
}) {
  const settled = !balance.debtor_id || isZeroMoney(balance.amount_usd);
  // Si soy el acreedor, me deben plata => verde. Si soy el deudor, yo debo => rojo.
  const iAmCreditor = myId != null && balance.creditor_id === myId;

  if (settled) {
    return (
      <Card className="flex items-center gap-4 p-5">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-success-bg text-success">
          <Check size={22} strokeWidth={2.5} aria-hidden="true" />
        </span>
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-3">Balance</p>
          <p className="font-display text-xl leading-tight text-success">Están a mano</p>
        </div>
      </Card>
    );
  }

  return (
    <Card className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3 p-5">
      <div className="flex min-w-0 items-center gap-3.5">
        <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full ${
          iAmCreditor ? "bg-success-bg text-success" : "bg-brick-bg text-brick"
        }`}>
          <Handshake size={20} strokeWidth={2} aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-3">Balance</p>
          <p className="truncate text-sm text-ink-2">
            <span className="font-bold text-ink">{names[balance.debtor_id!] ?? "Alguien"}</span>{" "}
            le debe a{" "}
            <span className="font-bold text-ink">{names[balance.creditor_id!] ?? "el otro"}</span>
          </p>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <NumberPopIn
          value={formatUsd(balance.amount_usd)}
          className={`font-display text-[1.7rem] leading-none font-tabular ${
            iAmCreditor ? "text-success" : "text-brick"
          }`}
        />
        <Button variant="secondary" size="sm" onClick={onSettle}>
          Saldar
        </Button>
      </div>
    </Card>
  );
}
