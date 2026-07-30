import { useState } from "react";
import { Navigate } from "react-router-dom";

import { isAuthenticated, loginAs } from "@/api/auth";
import { Wordmark } from "@/components/ui/Brand";
import Card from "@/components/ui/Card";

const PEOPLE = [
  { username: "bruno", label: "Bruno" },
  { username: "katia", label: "Katia" },
] as const;

export default function Login() {
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  if (isAuthenticated()) {
    return <Navigate to="/" replace />;
  }

  async function choose(username: string) {
    setErr(null);
    setBusy(username);
    try {
      await loginAs(username);
      // Full reload: remonta PersistQueryClient con buster del JWT nuevo.
      window.location.assign("/");
    } catch {
      setErr("No se pudo entrar. Probá de nuevo.");
      setBusy(null);
    }
  }

  return (
    <div className="relative min-h-dvh overflow-hidden">
      <div className="spit-dots-ink pointer-events-none absolute inset-0" aria-hidden="true" />

      <div className="relative mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-6 p-6">
        <header className="animate-rise-in espresso-panel relative overflow-hidden rounded-2xl px-6 py-7 soft-hero">
          <div className="spit-dots pointer-events-none absolute inset-0" aria-hidden="true" />
          <div className="hero-sheen pointer-events-none absolute inset-0" aria-hidden="true" />
          <div className="relative flex flex-col items-start">
            <img
              src="/brand/mark-tile.png"
              alt=""
              width={72}
              height={72}
              className="mb-4 h-[72px] w-[72px] drop-shadow-[0_6px_16px_rgba(0,0,0,0.35)]"
            />
            <h1>
              <Wordmark tone="dark" className="text-[3.25rem]" />
            </h1>
            <p className="mt-2 text-[15px] text-espresso-ink-2">
              Los gastos del viaje, divididos sin drama.
            </p>
            <span className="mt-4 inline-flex items-center rounded-full border border-espresso-border bg-white/10 px-3 py-1 text-xs font-bold uppercase tracking-[0.12em] text-espresso-ink">
              Europa 2026
            </span>
          </div>
        </header>

        <Card className="animate-rise-in stagger-2 p-6">
          <p className="mb-4 text-[11px] font-extrabold uppercase tracking-[0.12em] text-ink-3">
            ¿Quién sos?
          </p>
          <div className="grid grid-cols-2 gap-3">
            {PEOPLE.map(({ username, label }) => (
              <button
                key={username}
                type="button"
                disabled={busy !== null}
                onClick={() => { void choose(username); }}
                className="flex min-h-[64px] items-center justify-center rounded-xl border-2 border-border bg-surface-2 text-sm font-extrabold uppercase tracking-[0.08em] text-ink transition-all duration-150 hover:border-brick hover:bg-brick-bg hover:text-brick-ink active:translate-y-px disabled:opacity-50 focus-ring"
              >
                {busy === username ? "Entrando…" : label}
              </button>
            ))}
          </div>
          {err && <p role="alert" className="mt-4 text-sm font-semibold text-danger">{err}</p>}
        </Card>
      </div>
    </div>
  );
}
