# Spitwise — sistema de diseño

Decisiones vigentes del frontend (`frontend/src/`). Fuente de tokens: `src/index.css`
(`@theme` = colores/tipos/radios/sombras → utilidades Tailwind v4; `:root` = gradientes
+ motion tokens). Este archivo documenta el *porqué*; los valores viven en el CSS.

## Dirección y feel

Ledger de gastos de un viaje de pareja (Bruno + Katia), mobile-first, es-AR.
**Cálido como un cuaderno de viaje, preciso como un libro contable.** Canvas off-white
cálido (#F7F5F1), marca ladrillo/terracota (#C44428) + espresso (#342112, muestreado del
tile del logo). Nada de grises fríos ni negros puros: hasta las sombras llevan tinte
espresso. Firma de marca: el "trail" de puntitos del escupitajo del logo (`.spit-dots`,
`SpitDivider`).

- **Tipografía**: Anton (display) solo para números grandes y `PageTitle`; Hanken
  Grotesk (variable) para todo lo demás. Cifras siempre con `font-tabular`.
- **Color**: 60/30/10 — neutros cálidos dominan; brick es el único acento de acción;
  los 10 acentos categóricos (validados CVD a pares adyacentes con el validador de
  dataviz) aparecen solo pegados a su categoría, siempre con ícono + label (nunca color
  como canal único).
- **Depth**: UNA estrategia — sombras suaves con tinte espresso (`.soft-card`/`.soft-pop`/
  `.soft-hero`) + bordes `--color-border` para divisiones. Prohibido: sombras negras,
  borders duros, mezclar estrategias.
- **Números**: es-AR (`1.234,5` — `render.ar_number` backend / `lib/format.ts` front).
- **Regla dura**: nunca mostrar countdowns de días del viaje (ni restantes ni
  transcurridos).

## Jerarquía

- Un focal por página: el hero de gasto (Dashboard), la ciudad en curso (Presupuesto),
  la parada seleccionada (Ciudades), la lista (Movimientos).
- Jerarquía por peso + color antes que por tamaño: metadata en `text-ink-3`,
  labels `font-semibold`, valores `font-bold`/Anton.
- Eyebrows: uppercase + tracking ancho + tamaño mínimo.

## Escalas

- **Spacing**: escala default de Tailwind (base 0.25rem). Ritmo de página `gap-5`;
  padding de card estándar `p-5` (heros `p-6 lg:p-7`, listas densas `px-5 py-1`).
- **Radios**: `lg` 0.5rem controles · `xl` 0.75rem inputs/paneles · `2xl` 1rem cards ·
  `full` chips. Regla concéntrica en anidados: outer = inner + padding.
- **Tipos**: ver tokens `--text-*` en `@theme` (F1b de la auditoría 2026-08).
- **Motion**: escala transitions.dev en `:root` (`--duration-*`, `--ease-*`,
  `--distance-*`, `--scale-*`, `--blur-*`) + espejo JS en `lib/motion.ts`. Springs
  gestuales (drag del Modal, FAB) NO se tokenizan — son física de gesto, no transición
  de superficie. Recharts y `setTimeout` derivan de la misma escala.
- **Z-scale**: ver tokens `--z-*` (F1c) — nav < banner < fab < overlay/modal < toast.

## A11y (contratos que no se negocian)

- Focus: `focus-ring` (outline 2px brick + offset; variantes `-inverse`, `-inset`,
  `-danger`, `-within`). Nunca ring translúcido.
- Contraste AA documentado token por token en `index.css` (por eso existen las
  variantes `-ink`). Texto secundario = `ink-3`; `ink-faint` SOLO placeholders sobre
  `surface`.
- Tap targets ≥44px (extender con pseudo-elemento si lo visual es menor).
- `prefers-reduced-motion` apaga todo movimiento (CSS + `useReducedMotion`).
- Inputs a 16px mínimo (evita zoom de iOS).

## Patrones de componentes

- Primitivos en `components/ui/*`; lógica de feature fuera de ui/.
- `cn()` = clsx + tailwind-merge: los overrides por `className` son confiables.
- Estados de datos: skeleton por sección (`SkeletonReveal`) + error inline por sección
  con retry + empty con acción — patrón `Slot`/`AsyncSection` (F4). Nunca un dato falso
  como placeholder (el flash "USD 0" fue bug).
- Botón primario = `ui/Button` (también para links con apariencia de botón). Cualquier
  forma pill con texto chico = `ui/Badge` (F3).
- Kitchen-sink dev-only en `/preview` (`pages/Preview.tsx`): todo primitivo nuevo se
  agrega ahí con TODOS sus estados en el mismo commit.

## Medidas de referencia

- `Button` md — min-h 44px · px-16px · radio lg · 15px/600. `sm` — 36px · px-12px.
- Bottom nav tab — min-h 56px; FAB 56×56 a `safe-area + 4.75rem`.
- Verificación visual: SIEMPRE viewport iPhone 17 (402×874 CSS px, DPR 3, mobile UA).

## Registro de auditorías

- **2026-08**: auditoría integral (plan `tranquil-stirring-stallman`). Baseline
  pre-cambios en `.playwright-mcp/baseline/`. Identidad conservada; trabajo = tokens
  tipográficos, primitivos extraídos, estados consistentes, drift de charts, motion,
  a11y, assets offline.
