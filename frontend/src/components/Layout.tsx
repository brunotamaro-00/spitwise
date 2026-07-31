import { useQuery } from "@tanstack/react-query";
import { CloudOff, LayoutDashboard, ListOrdered, LogOut, Map, Plus, RefreshCw, Target } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { logout } from "@/api/auth";
import { listMovements } from "@/api/movements";
import AddMovementDialog from "@/components/AddMovementDialog";
import { Wordmark } from "@/components/ui/Brand";
import { capitalize } from "@/lib/format";
import { DURATION, EASE_SMOOTH_OUT } from "@/lib/motion";
import { needsConfirmation } from "@/lib/share";
import { useTripToday } from "@/lib/useTripToday";
import { useMe } from "@/lib/useMe";
import { useOnline } from "@/lib/useOnline";
import { usePullToRefresh } from "@/lib/usePullToRefresh";

const TABS = [
  { to: "/", label: "Dashboard", Icon: LayoutDashboard },
  { to: "/presupuesto", label: "Presupuesto", Icon: Target },
  { to: "/ciudades", label: "Ciudades", Icon: Map },
  { to: "/movimientos", label: "Movimientos", Icon: ListOrdered },
];

export default function Layout() {
  const location = useLocation();
  const [adding, setAdding] = useState(false);
  const online = useOnline();
  const { data: me } = useMe();
  const { pull, refreshing } = usePullToRefresh();
  // Contador de gastos por confirmar → badge sutil sobre el tab Movimientos.
  // Comparte cache con /movimientos (misma queryKey).
  const { data: movements = [] } = useQuery({ queryKey: ["movements"], queryFn: listMovements });
  const tripToday = useTripToday();
  const confirmCount = movements.filter((m) => needsConfirmation(m, tripToday)).length;

  const avatar = me && (
    <span className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-2 text-sm font-bold text-ink-2">
      {capitalize(me.username).slice(0, 1)}
    </span>
  );
  const logoutBtn = (
    <button
      aria-label="Cerrar sesión"
      className="flex min-h-[40px] min-w-[40px] cursor-pointer items-center justify-center rounded-lg text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink focus-ring"
      onClick={() => { void logout().then(() => { window.location.assign("/login"); }); }}
    >
      <LogOut size={18} strokeWidth={1.75} aria-hidden="true" />
    </button>
  );

  return (
    <div className="min-h-dvh lg:flex">
      {/* Sidebar (desktop) */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 flex-col border-r border-border bg-surface px-4 py-6 lg:flex">
        <NavLink
          to="/"
          end
          aria-label="Ir al dashboard"
          className="flex items-center gap-3 rounded-lg px-2 transition-opacity hover:opacity-80 focus-ring"
        >
          <img src="/brand/mark-tile.png" alt="" width={48} height={48} className="h-12 w-12 shrink-0 object-contain drop-shadow-sm" />
          <div>
            <Wordmark className="text-[1.7rem]" />
            <p className="mt-0.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-faint">
              Europa 2026
            </p>
          </div>
        </NavLink>
        <nav aria-label="Secciones" className="mt-8 flex flex-col gap-1">
          {TABS.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex min-h-[44px] items-center gap-3 rounded-lg px-3 text-sm font-semibold transition-colors focus-ring ${
                  isActive ? "bg-brick-bg text-brick-ink" : "text-ink-2 hover:bg-surface-2 hover:text-ink"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={20} strokeWidth={isActive ? 2.25 : 1.75} aria-hidden="true" />
                  {label}
                  {to === "/movimientos" && confirmCount > 0 && (
                    <span
                      className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-accent-amber-solid px-1.5 text-[11px] font-bold text-white"
                      aria-label={`${confirmCount} por confirmar`}
                    >
                      <span aria-hidden="true">{confirmCount}</span>
                    </span>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto flex items-center justify-between border-t border-border pt-4">
          <span className="flex items-center gap-2 px-1">
            {avatar}
            {me && <span className="text-sm font-semibold text-ink-2">{capitalize(me.username)}</span>}
          </span>
          {logoutBtn}
        </div>
      </aside>

      {/* Header (mobile) */}
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-surface/80 px-4 py-3 backdrop-blur-md lg:hidden">
        <NavLink
          to="/"
          end
          aria-label="Ir al dashboard"
          className="flex items-center gap-2.5 rounded-lg transition-opacity hover:opacity-80 focus-ring"
        >
          <img src="/brand/mark-tile.png" alt="" width={40} height={40} className="h-10 w-10 shrink-0 object-contain drop-shadow-sm" />
          <Wordmark className="text-[1.8rem]" />
        </NavLink>
        <div className="flex items-center gap-2">
          {avatar}
          {logoutBtn}
        </div>
      </header>

      {/* Contenido */}
      <div className="flex-1 lg:pl-60">
        {!online && (
          <div
            role="status"
            className="flex items-center justify-center gap-2 bg-espresso px-4 py-1.5 text-xs font-semibold text-espresso-ink"
          >
            <CloudOff size={14} strokeWidth={2} aria-hidden="true" />
            Sin conexión — mostrando los últimos datos guardados
          </div>
        )}
        {/* Indicador de pull-to-refresh (solo aparece al tirar o refrescar). */}
        {(pull > 0 || refreshing) && (
          <div
            role="status"
            aria-label="Actualizando datos"
            className="flex justify-center overflow-hidden lg:hidden"
            style={{ height: refreshing ? 44 : pull * 0.4 }}
          >
            <RefreshCw
              size={18}
              strokeWidth={2}
              className={`mt-3 text-brick ${refreshing ? "animate-spin" : ""}`}
              style={refreshing ? undefined : { transform: `rotate(${pull * 2.5}deg)`, opacity: Math.min(pull / 72, 1) }}
              aria-hidden="true"
            />
          </div>
        )}
        {/* pb-40: espacio para scrollear el último ítem por encima del FAB
            (bottom nav 3.5rem + FAB 3.5rem alto a 4.75rem del borde). */}
        <main className="mx-auto max-w-lg p-4 pb-40 lg:max-w-5xl lg:p-8 lg:pb-28">
          {/* key por ruta: cada cambio de tab remonta el contenido y dispara
              las animaciones de entrada de la página. */}
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: DURATION.fast, ease: EASE_SMOOTH_OUT }}
          >
            <Outlet />
          </motion.div>
        </main>
      </div>

      {/* FAB global: cargar gasto desde cualquier página. */}
      <motion.button
        onClick={() => {
          if ("vibrate" in navigator) navigator.vibrate?.(10);
          setAdding(true);
        }}
        aria-label="Agregar movimiento"
        whileHover={{ scale: 1.06 }}
        whileTap={{ scale: 0.9 }}
        transition={{ type: "spring", stiffness: 500, damping: 26 }}
        className="brick-gradient focus-ring-inverse fixed bottom-[calc(env(safe-area-inset-bottom)+4.75rem)] right-4 z-30 flex h-14 w-14 cursor-pointer items-center justify-center rounded-full text-white soft-hero lg:bottom-8 lg:right-8"
      >
        <Plus size={26} strokeWidth={2} aria-hidden="true" />
      </motion.button>

      {/* Bottom nav (mobile) */}
      <nav
        aria-label="Navegación inferior"
        className="fixed inset-x-0 bottom-0 z-10 border-t border-border bg-surface/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-md lg:hidden"
      >
        <div className="mx-auto flex max-w-lg">
          {TABS.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex min-h-[56px] flex-1 cursor-pointer flex-col items-center justify-center gap-0.5 text-[11px] font-semibold transition-colors focus-ring-inset ${
                  isActive ? "text-brick" : "text-ink-3 hover:text-ink"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {/* Pill detrás del ícono activo: estado sólido, sin ambigüedad.
                      layoutId: el pill se desliza de un tab al otro. */}
                  <span className="relative flex h-7 w-12 items-center justify-center">
                    {isActive && (
                      <motion.span
                        layoutId="nav-pill"
                        transition={{ type: "spring", stiffness: 480, damping: 36 }}
                        className="absolute inset-0 rounded-full bg-brick-bg"
                        aria-hidden="true"
                      />
                    )}
                    <Icon size={20} strokeWidth={isActive ? 2.25 : 1.75} className="relative" aria-hidden="true" />
                    {to === "/movimientos" && confirmCount > 0 && (
                      <span
                        className="absolute right-1.5 top-0 flex h-4 min-w-4 items-center justify-center rounded-full bg-accent-amber-solid px-1 text-[10px] font-bold text-white"
                        aria-label={`${confirmCount} por confirmar`}
                      >
                        <span aria-hidden="true">{confirmCount}</span>
                      </span>
                    )}
                  </span>
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </div>
      </nav>

      {adding && <AddMovementDialog editing={null} onClose={() => setAdding(false)} />}
    </div>
  );
}
