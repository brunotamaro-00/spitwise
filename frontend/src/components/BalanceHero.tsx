import { Check, Handshake } from "lucide-react";

import Card from "@/components/ui/Card";
import { formatUsd, isZeroMoney } from "@/lib/format";
import type { Balance } from "@/types";

export default function BalanceHero({ balance, names, onSettle }: {
  balance: Balance; names: Record<number, string>; onSettle: () => void;
}) {
  const settled = !balance.debtor_id || isZeroMoney(balance.amount_usd);

  if (settled) {
    return (
      <Card className="relative overflow-hidden p-6">
        <div className="spit-dots-ink absolute inset-0" aria-hidden="true" />
        <div className="relative flex items-center gap-4">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-success-bg text-success">
            <Check size={24} strokeWidth={2.5} aria-hidden="true" />
          </span>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-3">Balance</p>
            <p className="font-display text-2xl leading-tight text-success">Están a mano</p>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="relative overflow-hidden p-6 text-white hero-gradient soft-hero lg:p-7">
      <div className="spit-dots absolute inset-0" aria-hidden="true" />
      <div className="relative">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/70">Balance</p>
        <p className="mt-2 text-[15px] text-white/90">
          <span className="font-bold text-white">{names[balance.debtor_id!] ?? "Alguien"}</span>{" "}
          le debe a{" "}
          <span className="font-bold text-white">{names[balance.creditor_id!] ?? "el otro"}</span>
        </p>
        <p className="mt-1.5 font-display text-6xl leading-none font-tabular lg:text-7xl">
          {formatUsd(balance.amount_usd)}
        </p>
        <button
          onClick={onSettle}
          className="mt-5 inline-flex min-h-[42px] cursor-pointer items-center gap-2 rounded-xl bg-white px-5 text-sm font-bold text-brick shadow-sm transition-[background-color,transform] hover:bg-white/90 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60"
        >
          <Handshake size={17} strokeWidth={2.25} aria-hidden="true" />
          Saldar
        </button>
      </div>
    </Card>
  );
}
