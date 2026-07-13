import { useQuery } from "@tanstack/react-query";
import { LayoutDashboard, ListOrdered, LogOut, Map, Plus } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { logout } from "@/api/auth";
import { getMe } from "@/api/users";
import AddMovementDialog from "@/components/AddMovementDialog";
import { capitalize } from "@/lib/format";

const TABS = [
  { to: "/", label: "Dashboard", Icon: LayoutDashboard },
  { to: "/ciudades", label: "Ciudades", Icon: Map },
  { to: "/movimientos", label: "Movimientos", Icon: ListOrdered },
];

export default function Layout() {
  const nav = useNavigate();
  const [adding, setAdding] = useState(false);
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe, staleTime: Infinity });

  const avatar = me && (
    <span className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-2 text-sm font-bold text-ink-2">
      {capitalize(me.username).slice(0, 1)}
    </span>
  );
  const logoutBtn = (
    <button
      aria-label="Cerrar sesión"
      className="flex min-h-[40px] min-w-[40px] cursor-pointer items-center justify-center rounded-lg text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
      onClick={() => { logout(); nav("/login"); }}
    >
      <LogOut size={18} strokeWidth={1.75} aria-hidden="true" />
    </button>
  );

  return (
    <div className="min-h-dvh lg:flex">
      {/* Sidebar (desktop) */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 flex-col border-r border-border bg-surface px-4 py-6 lg:flex">
        <div className="flex items-center gap-2.5 px-2">
          <img src="/logo.png" alt="" width={34} height={34} className="rounded-full" />
          <div>
            <span className="block font-display text-2xl leading-none text-brick">Spitwise</span>
            <p className="mt-0.5 text-xs text-ink-3">Europa 2026</p>
          </div>
        </div>
        <nav aria-label="Navegación principal" className="mt-8 flex flex-col gap-1">
          {TABS.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex min-h-[44px] items-center gap-3 rounded-lg px-3 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/30 ${
                  isActive ? "bg-brick-bg text-brick" : "text-ink-2 hover:bg-surface-2 hover:text-ink"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={20} strokeWidth={isActive ? 2.25 : 1.75} aria-hidden="true" />
                  {label}
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
        <span className="flex items-center gap-2">
          <img src="/logo.png" alt="" width={26} height={26} className="rounded-full" />
          <span className="font-display text-xl leading-none text-brick">Spitwise</span>
        </span>
        <div className="flex items-center gap-2">
          {avatar}
          {logoutBtn}
        </div>
      </header>

      {/* Contenido */}
      <div className="flex-1 lg:pl-60">
        <main className="mx-auto max-w-lg p-4 pb-24 lg:max-w-5xl lg:p-8 lg:pb-8">
          <Outlet />
        </main>
      </div>

      {/* FAB global: cargar gasto desde cualquier página. */}
      <button
        onClick={() => setAdding(true)}
        aria-label="Agregar movimiento"
        className="fixed bottom-[calc(env(safe-area-inset-bottom)+4.75rem)] right-4 z-30 flex h-14 w-14 cursor-pointer items-center justify-center rounded-full bg-brick text-white soft-pop transition-[background-color,transform] hover:bg-brick-hover active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40 lg:bottom-8 lg:right-8"
      >
        <Plus size={26} strokeWidth={2} aria-hidden="true" />
      </button>

      {/* Bottom nav (mobile) */}
      <nav
        aria-label="Navegación principal"
        className="fixed inset-x-0 bottom-0 z-10 border-t border-border bg-surface/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-md lg:hidden"
      >
        <div className="mx-auto flex max-w-lg">
          {TABS.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
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
