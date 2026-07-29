import { useState } from "react";

import Button from "@/components/ui/Button";
import Modal from "@/components/ui/Modal";
import { usePublicConfig } from "@/lib/useConfig";

/**
 * Presentación de una sola vez para el deploy público. El banner avisa que los
 * datos son inventados; esto contesta la pregunta que sigue — qué es esto, con
 * qué está hecho y por qué hay dos apps.
 *
 * Aclara que el canal de WhatsApp solo corre en producción: es la feature más
 * llamativa del proyecto y la demo no la tiene (sin credenciales de Meta el
 * webhook no podría ni validar la firma), así que mejor decirlo que dejar que
 * la busquen.
 */
const SEEN_KEY = "spitwise_demo_intro_v1";

function alreadySeen(): boolean {
  try {
    return localStorage.getItem(SEEN_KEY) === "1";
  } catch {
    // Safari en modo privado tira al tocar localStorage. Sin memoria preferimos
    // mostrarlo: es una presentación, no un consentimiento.
    return false;
  }
}

export default function DemoIntro() {
  const config = usePublicConfig();
  const [dismissed, setDismissed] = useState(alreadySeen);

  function dismiss() {
    try {
      localStorage.setItem(SEEN_KEY, "1");
    } catch {
      /* idem */
    }
    setDismissed(true);
  }

  if (!config?.demo || dismissed) return null;

  return (
    <Modal title="Spitwise · demo pública" onClose={dismiss}>
      <div className="space-y-3">
        <p className="text-sm leading-relaxed text-ink-2">
          Ledger de gastos de viaje en pareja que construí y uso en producción. FastAPI ·
          SQLAlchemy 2 async · PostgreSQL · React 19 · TanStack Query.
        </p>
        <p className="text-sm leading-relaxed text-ink-2">
          <strong className="text-ink">Todos los datos que ves son inventados</strong> y se
          regeneran cada noche. Podés cargar, editar y borrar lo que quieras.
        </p>
        <p className="text-sm leading-relaxed text-ink-2">
          En producción la carga principal es un <strong className="text-ink">bot de WhatsApp</strong>{" "}
          con un LLM que entiende &ldquo;35 euros de cena en Viena, mitad y mitad&rdquo;. Ese canal
          no está en la demo: sin credenciales de Meta el webhook no puede validar la firma.
        </p>
        {config.andiamo_url ? (
          <p className="text-sm leading-relaxed text-ink-2">
            Se integra en vivo con <strong className="text-ink">Andiamo</strong>, mi app de
            itinerario: las ciudades de acá se sincronizan desde su API. El link está arriba,
            en la barra.
          </p>
        ) : null}
        {/* Único foco del diálogo. Con un link acá adentro el foco inicial caía
            ahí y un Enter se llevaba al visitante a la otra app en vez de
            cerrar; el cross-link vive en el banner, que además queda siempre. */}
        <Button onClick={dismiss} className="w-full">
          Entrar a la demo
        </Button>
      </div>
    </Modal>
  );
}
