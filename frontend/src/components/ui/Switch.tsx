/** Toggle switch con el acento de marca (reemplaza al checkbox nativo).
 *  Semántica `role="switch"` + `aria-checked`; el `label` es obligatorio
 *  porque el control no tiene texto propio. */
export default function Switch({ checked, onChange, label }: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={`relative h-7 w-12 shrink-0 cursor-pointer rounded-full transition-colors focus-ring ${
        checked ? "bg-brick" : "bg-border-strong"
      }`}
    >
      <span
        aria-hidden="true"
        className={`absolute left-0.5 top-0.5 h-6 w-6 rounded-full bg-white soft-card transition-transform ${
          checked ? "translate-x-5" : ""
        }`}
      />
    </button>
  );
}
