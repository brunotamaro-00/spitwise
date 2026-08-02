/** Motion tokens del lado JS: espejo de los `--duration-*` / `--ease-*` de
 *  `index.css`, en las unidades que consume `motion/react` (segundos + tuplas
 *  cubic-bezier). Mantener sincronizado con el bloque "Motion tokens" del CSS.
 *
 *  Regla usage-first: se usa para transiciones de superficie (open/close, slide,
 *  fade). Los springs gestuales (drag, whileTap/whileHover) NO se tokenizan acá:
 *  no tienen equivalente en la escala y viven inline en su componente. */

/** Duraciones en segundos (el CSS las declara en ms). */
export const DURATION = {
  stagger: 0.04,
  micro: 0.08,
  quick: 0.15,
  fast: 0.25,
  medium: 0.35,
  slow: 0.4,
  verySlow: 0.5,
} as const;

/** Ease de superficie por defecto: idéntico a --ease-smooth-out.
 *  Es el cubic-bezier que ya usaba toda la app. Tuple mutable para que
 *  `motion/react` lo acepte como BezierDefinition. */
export const EASE_SMOOTH_OUT: [number, number, number, number] = [0.22, 1, 0.36, 1];

/** Springs de SUPERFICIE (no gestuales): presets nombrados para que toast,
 *  pills y layout-ids compartan física. Los springs de gesto (drag del Modal,
 *  whileTap/whileHover del FAB) siguen inline en su componente — son física de
 *  interacción, no transición de superficie, y no pertenecen a esta escala. */
export const SPRING_POP = { type: "spring", stiffness: 500, damping: 32 } as const; // entrada de toast/badge
export const SPRING_SLIDE = { type: "spring", stiffness: 480, damping: 36 } as const; // pill de nav, layoutId
