import Button from "./Button";
import Modal from "./Modal";

/** Confirmación sobria para acciones destructivas (reemplaza window.confirm). */
export default function ConfirmDialog({
  title = "Confirmar",
  message,
  confirmLabel = "Borrar",
  onConfirm,
  onClose,
}: {
  title?: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <Modal title={title} onClose={onClose} size="sm">
      <p className="text-[15px] text-ink-2">{message}</p>
      <div className="mt-5 flex gap-2">
        <Button variant="secondary" className="flex-1" onClick={onClose}>
          Cancelar
        </Button>
        <Button
          variant="danger"
          className="flex-1"
          onClick={() => { onConfirm(); onClose(); }}
        >
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}
