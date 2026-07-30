import { ArrowUpRight } from "lucide-react";
import { useState } from "react";
import { Navigate } from "react-router-dom";

import { isAuthenticated, loginAs } from "@/api/auth";
import { Wordmark } from "@/components/ui/Brand";
import Card from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";
import { usePublicConfig } from "@/lib/useConfig";

const PEOPLE = [
  { username: "bruno", label: "Bruno" },
  { username: "katia", label: "Katia" },
] as const;

const DEFAULT_DEMO_URL = "https://demo.spitwise.lat";
/** Enter en el campo de contraseña dispara el primer submit del form, así que el
 *  orden de los chips decide con quién entrás sin tocar la pantalla. */
const LAST_PERSON_KEY = "spitwise_last_person";

export default function Login() {
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const config = usePublicConfig();
  // Mientras la config no llegó asumimos producción: mostrar el campo de más y
  // esconderlo después es preferible al salto inverso, que dejaría entrar sin
  // contraseña por un frame.
  const isDemo = config?.demo ?? false;
  const demoUrl = config?.demo_url ?? DEFAULT_DEMO_URL;

  if (isAuthenticated()) {
    return <Navigate to="/" replace />;
  }

  const last = localStorage.getItem(LAST_PERSON_KEY);
  const people = last === "katia" ? [PEOPLE[1], PEOPLE[0]] : PEOPLE;

  async function choose(username: string) {
    if (!isDemo && !password) {
      setErr("Ingresá la contraseña.");
      return;
    }
    setErr(null);
    setBusy(username);
    try {
      // En demo no hay campo: el form OAuth2 rechaza un password vacío con 422,
      // así que va un placeholder que el backend ignora (demo_mode no valida).
      await loginAs(username, password || "-");
      localStorage.setItem(LAST_PERSON_KEY, username);
      // Full reload: remonta PersistQueryClient con buster del JWT nuevo.
      window.location.assign("/");
    } catch (e) {
      const status = (e as { response?: { status?: number } }).response?.status;
      setErr(
        status === 429
          ? "Demasiados intentos. Probá de nuevo en un minuto."
          : status === 401
            ? "Contraseña incorrecta."
            : "No se pudo entrar. Probá de nuevo.",
      );
      setBusy(null);
    }
  }

  return (
    <div className="relative min-h-dvh overflow-hidden">
      <div className="spit-dots-ink pointer-events-none absolute inset-0" aria-hidden="true" />

      <div className="relative mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-5 p-6">
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

        {/* Casi todo el tráfico de spitwise.lat llega desde el CV, así que la
            demo es la acción primaria y la contraseña la excepción. En el propio
            deploy de demo este bloque sobra. */}
        {!isDemo && (
          <Card className="animate-rise-in stagger-2 p-6">
            <p className="mb-2 text-[11px] font-extrabold uppercase tracking-[0.12em] text-ink-3">
              ¿Venís desde mi CV o LinkedIn?
            </p>
            <p className="text-sm leading-relaxed text-ink-2">
              Spitwise es el ledger real del viaje: por eso pide contraseña. La demo pública es
              exactamente la misma app, con datos de ejemplo.
            </p>
            <a
              href={demoUrl}
              rel="noopener"
              className="focus-ring mt-4 flex min-h-[48px] items-center justify-center gap-2 rounded-lg bg-brick px-4 text-[15px] font-semibold text-white transition-[background-color,transform] hover:bg-brick-hover active:scale-[0.98] active:bg-brick-press"
            >
              Entrar a la demo
              <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
            </a>
          </Card>
        )}

        {!isDemo && (
          <div className="flex animate-rise-in items-center gap-3 stagger-3" aria-hidden="true">
            <span className="h-px flex-1 bg-border" />
            <span className="text-[11px] font-extrabold uppercase tracking-[0.12em] text-ink-faint">
              o
            </span>
            <span className="h-px flex-1 bg-border" />
          </div>
        )}

        <Card className="animate-rise-in stagger-4 p-6">
          <form
            className="flex flex-col gap-4"
            onSubmit={(e) => {
              // El submit lo disparan los chips (cada uno manda su persona);
              // este handler solo cubre el Enter del campo de contraseña.
              e.preventDefault();
              void choose(people[0].username);
            }}
          >
            {!isDemo && (
              <Field label="Contraseña">
                <Input
                  type="password"
                  name="password"
                  autoComplete="current-password"
                  enterKeyHint="go"
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); }}
                  aria-invalid={err !== null || undefined}
                  aria-describedby={err ? "login-error" : undefined}
                />
              </Field>
            )}

            <fieldset>
              <legend className="mb-2 text-[11px] font-extrabold uppercase tracking-[0.12em] text-ink-3">
                ¿Quién sos?
              </legend>
              <div className="grid grid-cols-2 gap-3">
                {people.map(({ username, label }) => (
                  <button
                    key={username}
                    type="submit"
                    disabled={busy !== null}
                    onClick={(e) => {
                      e.preventDefault();
                      void choose(username);
                    }}
                    className="flex min-h-[64px] items-center justify-center rounded-xl border-2 border-border bg-surface-2 text-sm font-extrabold uppercase tracking-[0.08em] text-ink transition-all duration-150 hover:border-brick hover:bg-brick-bg hover:text-brick-ink active:translate-y-px disabled:opacity-50 focus-ring"
                  >
                    {busy === username ? "Entrando…" : label}
                  </button>
                ))}
              </div>
            </fieldset>

            {/* Región siempre presente: si apareciera recién con el error,
                algunos lectores de pantalla no anuncian el primero. */}
            <p
              id="login-error"
              role="alert"
              aria-live="polite"
              className="text-sm font-semibold text-danger empty:hidden"
            >
              {err}
            </p>
          </form>
        </Card>
      </div>
    </div>
  );
}
