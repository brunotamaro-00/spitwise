import Button from "./Button";
import Modal from "./Modal";

/** Confirmación sobria para acciones destructivas (reemplaza window.confirm). */
export default function ConfirmDialog({
  title = "Confirmar",
  message,
  confirmLabel = "Borrar",
  busy = false,
  error = null,
  onConfirm,
  onClose,
}: {
  title?: string;
  message: string;
  confirmLabel?: string;
  busy?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <Modal title={title} onClose={onClose} size="sm" locked={busy}>
      <p className="text-entry text-ink-2">{message}</p>
      {error && <p className="mt-2 text-sm text-danger">{error}</p>}
      <div className="mt-5 flex gap-2">
        <Button variant="secondary" className="flex-1" onClick={onClose} disabled={busy}>
          Cancelar
        </Button>
        <Button
          variant="danger"
          className="flex-1"
          loading={busy}
          loadingLabel="Borrando…"
          onClick={() => onConfirm()}
        >
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}
