import { useQuery } from "@tanstack/react-query";
import { LayoutDashboard, ListOrdered, LogOut, Plus } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { logout } from "@/api/auth";
import { getMe } from "@/api/users";
import AddMovementDialog from "@/components/AddMovementDialog";
import { capitalize } from "@/lib/format";

const TABS = [
  { to: "/", label: "Dashboard", Icon: LayoutDashboard },
  { to: "/movimientos", label: "Movimientos", Icon: ListOrdered },
];

export default function Layout() {
  const nav = useNavigate();
  const [adding, setAdding] = useState(false);
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe, staleTime: Infinity });

  return (
    <div className="mx-auto min-h-dvh max-w-lg pb-24">
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-surface/80 px-4 py-3 backdrop-blur-md">
        <span className="font-display text-xl leading-none text-brick">Botardo</span>
        <div className="flex items-center gap-2">
          {me && (
            <span className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-2 text-sm font-bold text-ink-2">
                {capitalize(me.username).slice(0, 1)}
              </span>
            </span>
          )}
          <button
            aria-label="Cerrar sesión"
            className="flex min-h-[40px] min-w-[40px] cursor-pointer items-center justify-center rounded-lg text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
            onClick={() => { logout(); nav("/login"); }}
          >
            <LogOut size={18} strokeWidth={1.75} aria-hidden="true" />
          </button>
        </div>
      </header>

      <main className="p-4">
        <Outlet />
      </main>

      {/* FAB global: cargar gasto desde cualquier página. `right` alinea el botón
          al borde de la columna centrada (max-w-lg = 32rem) en pantallas anchas. */}
      <button
        onClick={() => setAdding(true)}
        aria-label="Agregar movimiento"
        style={{ right: "max(1rem, calc(50vw - 16rem + 1rem))" }}
        className="fixed bottom-[calc(env(safe-area-inset-bottom)+4.75rem)] z-20 flex h-14 w-14 cursor-pointer items-center justify-center rounded-full bg-brick text-white soft-pop transition-transform hover:bg-brick-hover active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
      >
        <Plus size={26} strokeWidth={2} aria-hidden="true" />
      </button>

      <nav
        aria-label="Navegación principal"
        className="fixed inset-x-0 bottom-0 z-10 border-t border-border bg-surface/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-md"
      >
        <div className="mx-auto flex max-w-lg">
          {TABS.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              end
              className={({ isActive }) =>
                `flex min-h-[56px] flex-1 cursor-pointer flex-col items-center justify-center gap-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brick/30 ${
                  isActive ? "text-brick" : "text-ink-3 hover:text-ink"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={22} strokeWidth={isActive ? 2.25 : 1.75} aria-hidden="true" />
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
