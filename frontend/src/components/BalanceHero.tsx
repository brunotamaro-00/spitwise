import { Handshake } from "lucide-react";

import { formatUsd } from "@/lib/format";
import type { Balance } from "@/types";

export default function BalanceHero({ balance, names, onSettle }: {
  balance: Balance; names: Record<number, string>; onSettle: () => void;
}) {
  const settled =
    !balance.debtor_id || balance.amount_usd === "0" || balance.amount_usd === "0.00";
  return (
    <section className="rounded-[4px] border-2 border-ink bg-surface p-5 hard-shadow-ink">
      <p className="text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-3">Balance</p>
      {settled ? (
        <p className="mt-2 font-display text-3xl uppercase leading-none text-success">
          Están a mano
        </p>
      ) : (
        <>
          <p className="mt-2 text-ink-2">
            <span className="font-bold text-ink">{names[balance.debtor_id!] ?? "Alguien"}</span>{" "}
            le debe a{" "}
            <span className="font-bold text-ink">{names[balance.creditor_id!] ?? "el otro"}</span>
          </p>
          <p className="mt-1 font-display text-5xl uppercase leading-none text-brick font-tabular">
            {formatUsd(balance.amount_usd)}
          </p>
          <button
            onClick={onSettle}
            className="mt-4 flex min-h-[44px] cursor-pointer items-center gap-2 rounded-[2px] bg-ink px-4 font-display uppercase text-surface hard-shadow-ink transition-transform hover:brightness-110 active:translate-x-[3px] active:translate-y-[3px] active:shadow-none"
          >
            <Handshake size={18} strokeWidth={1.5} aria-hidden="true" />
            Saldar
          </button>
        </>
      )}
    </section>
  );
}
