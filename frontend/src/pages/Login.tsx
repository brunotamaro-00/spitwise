import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { login } from "@/api/auth";
import { Wordmark } from "@/components/ui/Brand";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";

export default function Login() {
  const nav = useNavigate();
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.SyntheticEvent<HTMLFormElement>) {
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
    <div className="relative min-h-dvh overflow-hidden">
      {/* Trail de puntitos de marca sobre el canvas, esquina superior derecha. */}
      <div className="spit-dots-ink pointer-events-none absolute inset-0" aria-hidden="true" />

      <div className="relative mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-8 p-6">
        <header className="animate-rise-in flex flex-col items-start">
          <img src="/logo.png" alt="" width={104} height={104} className="mb-5 drop-shadow-sm" />
          <h1>
            <Wordmark className="text-6xl" />
          </h1>
          <p className="mt-3 text-[15px] text-ink-2">
            Los gastos del viaje, divididos sin drama.
          </p>
          <span className="mt-3 inline-flex items-center rounded-full border border-brick-border bg-brick-bg px-3 py-1 text-xs font-bold uppercase tracking-[0.12em] text-brick">
            Europa 2026
          </span>
        </header>

        <Card className="animate-rise-in stagger-2 p-6">
          <form onSubmit={submit} className="flex flex-col gap-4">
            <Field label="Usuario">
              <Input value={u} onChange={(e) => setU(e.target.value)} autoComplete="username" autoFocus />
            </Field>
            <Field label="Contraseña">
              <Input type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" />
            </Field>
            {err && <p role="alert" className="text-sm font-semibold text-danger">{err}</p>}
            <Button type="submit" disabled={busy} className="mt-1">
              {busy ? "Entrando…" : "Entrar"}
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
