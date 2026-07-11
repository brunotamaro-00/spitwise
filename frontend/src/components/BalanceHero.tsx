import { Check, Handshake } from "lucide-react";

import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { Label } from "@/components/ui/Field";
import { formatUsd } from "@/lib/format";
import type { Balance } from "@/types";

export default function BalanceHero({ balance, names, onSettle }: {
  balance: Balance; names: Record<number, string>; onSettle: () => void;
}) {
  const settled =
    !balance.debtor_id || balance.amount_usd === "0" || balance.amount_usd === "0.00";
  return (
    <Card className="p-5">
      <Label>Balance</Label>
      {settled ? (
        <p className="mt-2 flex items-center gap-2 text-lg font-bold text-success">
          <Check size={20} strokeWidth={2} aria-hidden="true" />
          Están a mano
        </p>
      ) : (
        <>
          <p className="mt-1.5 text-ink-2">
            <span className="font-semibold text-ink">{names[balance.debtor_id!] ?? "Alguien"}</span>{" "}
            le debe a{" "}
            <span className="font-semibold text-ink">{names[balance.creditor_id!] ?? "el otro"}</span>
          </p>
          <p className="mt-1 font-display text-5xl leading-none text-brick font-tabular">
            {formatUsd(balance.amount_usd)}
          </p>
          <Button variant="secondary" size="sm" className="mt-4" onClick={onSettle}>
            <Handshake size={17} strokeWidth={1.75} aria-hidden="true" />
            Saldar
          </Button>
        </>
      )}
    </Card>
  );
}
