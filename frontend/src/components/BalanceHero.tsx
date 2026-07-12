import { Check, Handshake } from "lucide-react";

import Card from "@/components/ui/Card";
import { formatUsd } from "@/lib/format";
import type { Balance } from "@/types";

export default function BalanceHero({ balance, names, onSettle }: {
  balance: Balance; names: Record<number, string>; onSettle: () => void;
}) {
  const settled =
    !balance.debtor_id || balance.amount_usd === "0" || balance.amount_usd === "0.00";

  if (settled) {
    return (
      <Card className="flex items-center gap-4 p-5">
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-success-bg text-success">
          <Check size={24} strokeWidth={2.5} aria-hidden="true" />
        </span>
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-ink-3">Balance</p>
          <p className="text-lg font-bold text-success">Están a mano</p>
        </div>
      </Card>
    );
  }

  return (
    <Card className="relative overflow-hidden p-5 text-white hero-gradient soft-hero">
      <div className="hero-texture absolute inset-0" aria-hidden="true" />
      <div className="relative">
        <p className="text-xs font-medium uppercase tracking-wide text-white/70">Balance</p>
        <p className="mt-1.5 text-sm text-white/90">
          <span className="font-bold text-white">{names[balance.debtor_id!] ?? "Alguien"}</span>{" "}
          le debe a{" "}
          <span className="font-bold text-white">{names[balance.creditor_id!] ?? "el otro"}</span>
        </p>
        <p className="mt-1 font-display text-5xl leading-none font-tabular">
          {formatUsd(balance.amount_usd)}
        </p>
        <button
          onClick={onSettle}
          className="mt-4 inline-flex min-h-[40px] cursor-pointer items-center gap-2 rounded-lg bg-white/15 px-4 text-sm font-semibold text-white backdrop-blur-sm transition-colors hover:bg-white/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
        >
          <Handshake size={17} strokeWidth={2} aria-hidden="true" />
          Saldar
        </button>
      </div>
    </Card>
  );
}
