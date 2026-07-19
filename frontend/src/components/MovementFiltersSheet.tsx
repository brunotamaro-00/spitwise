import { motion } from "motion/react";

import Flag from "@/components/Flag";
import Button from "@/components/ui/Button";
import { Field, Input, Label } from "@/components/ui/Field";
import Modal from "@/components/ui/Modal";
import { categoryIcon } from "@/lib/categoryIcons";
import { categoryBg, categoryColor } from "@/lib/chartTheme";
import type { Category } from "@/types";

export type MovementFilters = {
  onlyMine: boolean;
  city: string;
  categoryId: string;
  from: string;
  to: string;
  q: string;
};

export type CityOption = { name: string; flag: string | null };

/** Toggle switch con el acento de marca (reemplaza al checkbox nativo). */
function Switch({ checked, onChange, label }: {
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
      className={`relative h-7 w-12 shrink-0 cursor-pointer rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40 ${
        checked ? "bg-brick" : "bg-border-strong"
      }`}
    >
      <span
        aria-hidden="true"
        className={`absolute left-0.5 top-0.5 h-6 w-6 rounded-full bg-white shadow-sm transition-transform ${
          checked ? "translate-x-5" : ""
        }`}
      />
    </button>
  );
}

const chipBase =
  "flex min-h-[36px] cursor-pointer items-center gap-1.5 rounded-full border px-3 text-[13px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40";
const chipIdle = "border-border bg-surface text-ink-2 hover:bg-surface-2";

/** Bottom sheet de filtros de /movimientos: toggle "solo míos", categorías como
 *  chips con ícono (mismo lenguaje que el alta de gasto), ciudades como chips
 *  con bandera y rango de fechas. Los cambios aplican en vivo sobre la lista;
 *  "Listo" solo cierra. */
export default function MovementFiltersSheet({
  filters, categories, cities, activeCount, onChange, onClear, onClose,
}: {
  filters: MovementFilters;
  categories: Category[];
  cities: CityOption[];
  activeCount: number;
  onChange: (patch: Partial<MovementFilters>) => void;
  onClear: () => void;
  onClose: () => void;
}) {
  return (
    <Modal title="Filtros" onClose={onClose}>
      <div className="flex flex-col gap-5">
        <div className="flex items-center justify-between gap-3 rounded-xl bg-surface-2/60 p-3.5">
          <div>
            <p className="text-sm font-semibold text-ink">Solo movimientos míos</p>
            <p className="mt-0.5 text-xs text-ink-3">Oculta lo que no te involucra</p>
          </div>
          <Switch
            checked={filters.onlyMine}
            onChange={(v) => onChange({ onlyMine: v })}
            label="Solo movimientos míos"
          />
        </div>

        {categories.length > 0 && (
          <div className="flex flex-col gap-2">
            <Label>Categoría</Label>
            <div className="flex flex-wrap gap-1.5">
              {categories.map((c) => {
                const active = filters.categoryId === String(c.id);
                const Icon = categoryIcon(c.name);
                return (
                  <motion.button
                    key={c.id}
                    type="button"
                    onClick={() => onChange({ categoryId: active ? "" : String(c.id) })}
                    aria-pressed={active}
                    whileTap={{ scale: 0.94 }}
                    className={`${chipBase} ${active ? "" : chipIdle}`}
                    style={active ? {
                      background: categoryBg(c.name),
                      color: categoryColor(c.name),
                      borderColor: categoryColor(c.name),
                    } : undefined}
                  >
                    <Icon size={13} strokeWidth={2} aria-hidden="true" />
                    {c.name}
                  </motion.button>
                );
              })}
            </div>
          </div>
        )}

        {cities.length > 0 && (
          <div className="flex flex-col gap-2">
            <Label>Ciudad</Label>
            <div className="flex flex-wrap gap-1.5">
              {cities.map((c) => {
                const active = filters.city === c.name;
                return (
                  <motion.button
                    key={c.name}
                    type="button"
                    onClick={() => onChange({ city: active ? "" : c.name })}
                    aria-pressed={active}
                    whileTap={{ scale: 0.94 }}
                    className={`${chipBase} ${active ? "border-brick bg-brick-bg text-brick" : chipIdle}`}
                  >
                    {c.flag && <Flag flag={c.flag} className="text-sm leading-none" />}
                    {c.name}
                  </motion.button>
                );
              })}
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <Field label="Desde">
            <Input type="date" value={filters.from} onChange={(e) => onChange({ from: e.target.value })} />
          </Field>
          <Field label="Hasta">
            <Input type="date" value={filters.to} onChange={(e) => onChange({ to: e.target.value })} />
          </Field>
        </div>
      </div>

      <div className="mt-6 flex gap-2">
        <Button variant="secondary" className="flex-1" onClick={onClear} disabled={activeCount === 0}>
          Limpiar
        </Button>
        <Button className="flex-1" onClick={onClose}>
          Listo
        </Button>
      </div>
    </Modal>
  );
}
