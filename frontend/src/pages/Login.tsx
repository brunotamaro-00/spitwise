import { ArrowUpRight, ChevronRight } from "lucide-react";
import { useState } from "react";
import { Navigate } from "react-router-dom";

import { isAuthenticated, login } from "@/api/auth";
import { Wordmark } from "@/components/ui/Brand";
import Button, { buttonClasses } from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";
import { usePublicConfig } from "@/lib/useConfig";

const DEFAULT_DEMO_URL = "https://demo.spitwise.lat";

export default function Login() {
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const config = usePublicConfig();
  // Mientras la config no llegó asumimos producción: mostrar el campo de más y
  // esconderlo después es preferible al salto inverso, que dejaría entrar sin
  // contraseña por un frame.
  const isDemo = config?.demo ?? false;
  const demoUrl = config?.demo_url ?? DEFAULT_DEMO_URL;

  if (isAuthenticated()) {
    return <Navigate to="/" replace />;
  }

  async function enter() {
    if (!isDemo && !password) {
      setErr("Ingresá la contraseña.");
      return;
    }
    setErr(null);
    setBusy(true);
    try {
      // Quién sos no se elige acá: `login` manda la última persona del
      // dispositivo como pista y el backend resuelve el resto (api/auth.py).
      await login(password);
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
      setBusy(false);
    }
  }

  return (
    // overflow-x-hidden y no overflow-hidden: si el viewport es más bajo que el
    // contenido (barra del navegador, tipografía agrandada), preferimos scroll
    // antes que recortar la card.
    <div className="relative flex flex-1 flex-col overflow-x-hidden">
      <div className="spit-dots-ink pointer-events-none absolute inset-0" aria-hidden="true" />

      <div className="relative mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-3.5 px-5 py-4">
        <header className="animate-rise-in espresso-panel relative overflow-hidden rounded-2xl px-5 py-5 soft-hero">
          <div className="spit-dots pointer-events-none absolute inset-0" aria-hidden="true" />
          <div className="hero-sheen pointer-events-none absolute inset-0" aria-hidden="true" />
          <div className="relative flex flex-col items-start">
            <div className="flex w-full items-center justify-between gap-3">
              <img
                src="/brand/mark-tile-192.png"
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

        {isDemo ? (
          /* En el propio deploy de demo no hay contraseña ni persona que elegir:
             una pantalla, un botón, adentro. El backend entra siempre como el
             mismo usuario (ver api/auth.py). */
          <Card className="animate-rise-in stagger-2 p-5">
            <p className="text-sm leading-snug text-ink-2">
              Estás entrando a la demo pública de Spitwise: el mismo ledger que usamos en el
              viaje, con datos inventados que se regeneran cada noche.
            </p>
            <Button
              className="mt-3.5 w-full"
              loading={busy}
              loadingLabel="Entrando…"
              onClick={() => void enter()}
            >
              Entrar a la demo
            </Button>
          </Card>
        ) : (
          <>
            {/* Casi todo el tráfico de spitwise.lat llega desde el CV, así que la
                demo es el único focal de la pantalla y la contraseña se pliega
                abajo. */}
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
                className={buttonClasses({ className: "mt-4 flex min-h-[52px] w-full" })}
              >
                Entrar a la demo
                <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
              </a>
              <p className="mt-2.5 text-center text-meta text-ink-3">
                FastAPI · SQLAlchemy 2 async · PostgreSQL · React 19
              </p>
            </Card>

            {/* El gate no compite con el CTA: vive plegado. `<details>` nativo —
                sin JS de apertura, sin estado que sincronizar. */}
            <details open={err !== null} className="group animate-rise-in stagger-3">
              <summary className="flex min-h-[44px] cursor-pointer list-none items-center justify-center gap-1 rounded-full text-meta font-extrabold uppercase tracking-eyebrow text-ink-3 transition-colors hover:text-ink-2 focus-ring [&::-webkit-details-marker]:hidden">
                <ChevronRight
                  className="h-3.5 w-3.5 transition-transform duration-150 group-open:rotate-90 motion-reduce:transition-none"
                  aria-hidden="true"
                />
                Soy Bruno o Katia
              </summary>

              <Card className="mt-2 p-5">
                <form
                  className="flex flex-col gap-3.5"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void enter();
                  }}
                >
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

                  <Button type="submit" loading={busy} loadingLabel="Entrando…">
                    Entrar
                  </Button>

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
            </details>
          </>
        )}
      </div>
    </div>
  );
}
