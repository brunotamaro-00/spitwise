import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { login } from "@/api/auth";

export default function Login() {
  const nav = useNavigate();
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await login(u, p);
      nav("/");
    } catch {
      setErr("Usuario o contraseña inválidos");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-6 p-6">
      <header className="animate-fade-in">
        <h1 className="font-display text-5xl uppercase leading-none text-brick">Botardo</h1>
        <p className="mt-1 text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-3">
          Gastos del viaje · Europa 2026
        </p>
      </header>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1">
          <span className="text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-3">Usuario</span>
          <input
            className="min-h-[44px] rounded-[4px] border-2 border-border bg-surface px-3 font-semibold focus:border-border-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
            value={u}
            onChange={(e) => setU(e.target.value)}
            autoComplete="username"
            autoFocus
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-3">Contraseña</span>
          <input
            className="min-h-[44px] rounded-[4px] border-2 border-border bg-surface px-3 font-semibold focus:border-border-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
            type="password"
            value={p}
            onChange={(e) => setP(e.target.value)}
            autoComplete="current-password"
          />
        </label>
        {err && (
          <p role="alert" className="text-sm font-semibold text-danger">
            {err}
          </p>
        )}
        <button
          disabled={busy}
          className="mt-1 min-h-[48px] cursor-pointer rounded-[2px] bg-brick font-display text-lg uppercase tracking-wide text-surface hard-shadow-ink transition-transform hover:brightness-105 active:translate-x-[3px] active:translate-y-[3px] active:shadow-none disabled:opacity-60"
        >
          {busy ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </div>
  );
}
