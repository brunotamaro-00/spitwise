import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { login } from "@/api/auth";
import BotardoMark from "@/components/BotardoMark";
import Button from "@/components/ui/Button";
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
    <div className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-6 p-6">
      <header className="animate-fade-in">
        <BotardoMark size={72} className="mb-4" />
        <h1 className="font-display text-5xl leading-none text-brick">Botardo</h1>
        <p className="mt-2 text-sm text-ink-3">Gastos del viaje · Europa 2026</p>
      </header>
      <form onSubmit={submit} className="flex flex-col gap-3">
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
    </div>
  );
}
