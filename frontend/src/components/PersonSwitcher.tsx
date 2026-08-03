import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { lastPerson, rememberPerson, switchUser } from "@/api/auth";
import { listUsers } from "@/api/users";
import Modal from "@/components/ui/Modal";
import { capitalize } from "@/lib/format";
import { usePublicConfig } from "@/lib/useConfig";
import type { User } from "@/types";

/**
 * Quién sos, decidido adentro de la app — el login solo abre la puerta.
 *
 * Acá la persona NO es una preferencia de vista como en Andiamo: viaja en el
 * `sub` del JWT y define `paid_by`, el balance y `/auth/me`. Por eso cambiarla
 * pide un token nuevo (`POST /auth/switch`) y termina en un reload completo: el
 * `PersistQueryClient` se monta con un buster derivado del JWT, así que remontar
 * es la única forma de no arrastrar la caché de la otra persona.
 *
 * Se auto-abre una vez por dispositivo cuando todavía no hay a quién recordar
 * (`spitwise_last_person`), que es exactamente el primer login de alguien real.
 * En la demo nunca: quien llega desde el CV entra como Bruno y no le
 * preguntamos nada — pero el switcher sigue a mano, que el split por persona es
 * de lo que hay para mostrar.
 */
export default function PersonSwitcher({ me }: { me: User | undefined }) {
  const config = usePublicConfig();
  const isDemo = config?.demo ?? false;
  // El prompt inicial se decide una sola vez, al montar: si se recalculara,
  // `switchUser` (que escribe la clave) lo cerraría a mitad de la mutación.
  const [prompting, setPrompting] = useState(() => !isDemo && lastPerson() === "");
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const { data: users = [] } = useQuery({ queryKey: ["users"], queryFn: listUsers });

  const showing = open || prompting;

  function close() {
    setPrompting(false);
    setOpen(false);
    setErr(null);
  }

  function choose(username: string) {
    if (username === me?.username) {
      // Ya sos esa persona: no hace falta token nuevo ni reload. Pero sí hay que
      // recordarlo, o el prompt del primer login volvería a aparecer mañana.
      rememberPerson(username);
      close();
      return;
    }
    setErr(null);
    setBusy(username);
    void switchUser(username)
      .then(() => { window.location.assign("/"); })
      .catch(() => {
        setErr("No se pudo cambiar de persona. Probá de nuevo.");
        setBusy(null);
      });
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={`Estás como ${me ? capitalize(me.username) : "invitado"}. Cambiar de persona`}
        className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-full bg-surface-2 text-sm font-bold text-ink-2 transition-colors hover:bg-brick-bg hover:text-brick-ink focus-ring"
      >
        {me ? capitalize(me.username).slice(0, 1) : "·"}
      </button>

      {showing && (
        <Modal title="¿Quién sos?" onClose={close} locked={busy !== null} size="sm">
          <p className="mb-4 text-sm leading-snug text-ink-2">
            Define de quién son los gastos que cargás y de quién es el saldo que ves.
          </p>

          {err ? (
            <p role="alert" className="mb-3 rounded-lg bg-danger-bg px-3 py-2 text-sm font-semibold text-danger">
              {err}
            </p>
          ) : null}

          <div className="space-y-2">
            {users.map((u, i) => {
              const active = u.username === me?.username;
              return (
                <button
                  key={u.id}
                  type="button"
                  autoFocus={i === 0}
                  disabled={busy !== null}
                  onClick={() => { choose(u.username); }}
                  className={`flex w-full min-h-[52px] cursor-pointer items-center justify-between rounded-xl border-2 px-4 text-left transition-colors disabled:opacity-55 focus-ring ${
                    active
                      ? "border-brick bg-brick-bg text-brick-ink"
                      : "border-border bg-surface-2 text-ink hover:border-border-strong"
                  }`}
                >
                  <span className="text-sm font-extrabold uppercase tracking-caps">
                    {capitalize(u.username)}
                  </span>
                  {busy === u.username ? (
                    <span className="text-meta font-semibold text-ink-3">Entrando…</span>
                  ) : active ? (
                    <span className="text-meta font-semibold text-brick-ink">Sos vos</span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </Modal>
      )}
    </>
  );
}
