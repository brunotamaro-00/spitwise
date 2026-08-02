import { ArrowUpRight } from "lucide-react";
import { useState } from "react";
import { Navigate } from "react-router-dom";

import { isAuthenticated, loginAs } from "@/api/auth";
import { Wordmark } from "@/components/ui/Brand";
import { buttonClasses } from "@/components/ui/Button";
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
    // overflow-x-hidden y no overflow-hidden: si el viewport es más bajo que el
    // contenido (barra del navegador, tipografía agrandada), preferimos scroll
    // antes que recortar los chips de persona.
    <div className="relative flex flex-1 flex-col overflow-x-hidden">
      <div className="spit-dots-ink pointer-events-none absolute inset-0" aria-hidden="true" />

      <div className="relative mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-3.5 px-5 py-4">
        {/* El hero es decoración: con tres bloques en la pantalla se queda con
            lo justo (marca, qué es, viaje) para que todo entre sin scroll. */}
        <header className="animate-rise-in espresso-panel relative overflow-hidden rounded-2xl px-5 py-5 soft-hero">
          <div className="spit-dots pointer-events-none absolute inset-0" aria-hidden="true" />
          <div className="hero-sheen pointer-events-none absolute inset-0" aria-hidden="true" />
          <div className="relative flex flex-col items-start">
            <div className="flex w-full items-center justify-between gap-3">
              <img
                src="/brand/mark-tile.png"
                alt=""
                width={56}
                height={56}
                className="h-14 w-14 drop-shadow-[0_6px_16px_rgb(28_15_5/0.5)]"
              />
              <span className="inline-flex items-center rounded-full border border-espresso-border bg-white/10 px-3 py-1 text-meta font-bold uppercase tracking-eyebrow text-espresso-ink">
                Europa 2026
              </span>
            </div>
            <h1 className="mt-3">
              <Wordmark tone="dark" className="text-splash" />
            </h1>
            <p className="mt-1 text-sm text-espresso-ink-2">
              Los gastos del viaje, divididos sin drama.
            </p>
          </div>
        </header>

        {/* Casi todo el tráfico de spitwise.lat llega desde el CV, así que la
            demo es la acción primaria y la contraseña la excepción. En el propio
            deploy de demo este bloque sobra. */}
        {!isDemo && (
          <Card className="animate-rise-in stagger-2 p-5">
            <p className="mb-1.5 text-meta font-extrabold uppercase tracking-eyebrow text-ink-3">
              ¿Venís desde mi CV o LinkedIn?
            </p>
            <p className="text-sm leading-snug text-ink-2">
              Este es el ledger real del viaje: por eso pide contraseña. La demo pública es la
              misma app, con datos de ejemplo.
            </p>
            <a
              href={demoUrl}
              rel="noopener"
              className={buttonClasses({ className: "mt-3.5 flex min-h-[46px] w-full" })}
            >
              Entrar a la demo
              <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
            </a>
          </Card>
        )}

        {!isDemo && (
          <div className="flex animate-rise-in items-center gap-3 stagger-3" aria-hidden="true">
            <span className="h-px flex-1 bg-border" />
            <span className="text-meta font-extrabold uppercase tracking-eyebrow text-ink-faint">
              o
            </span>
            <span className="h-px flex-1 bg-border" />
          </div>
        )}

        <Card className="animate-rise-in stagger-4 p-5">
          <form
            className="flex flex-col gap-3.5"
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
              <legend className="mb-1.5 text-meta font-extrabold uppercase tracking-eyebrow text-ink-3">
                ¿Quién sos?
              </legend>
              <div className="grid grid-cols-2 gap-2.5">
                {people.map(({ username, label }) => (
                  <button
                    key={username}
                    type="submit"
                    disabled={busy !== null}
                    onClick={(e) => {
                      e.preventDefault();
                      void choose(username);
                    }}
                    className="flex min-h-[56px] items-center justify-center rounded-xl border-2 border-border bg-surface-2 text-sm font-extrabold uppercase tracking-caps text-ink transition-[border-color,background-color,color,transform] hover:border-brick hover:bg-brick-bg hover:text-brick-ink active:translate-y-px disabled:opacity-50 focus-ring"
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
