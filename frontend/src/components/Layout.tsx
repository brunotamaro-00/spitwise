import { LayoutDashboard, ListOrdered, LogOut } from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { logout } from "@/api/auth";

export default function Layout() {
  const nav = useNavigate();
  return (
    <div className="mx-auto min-h-dvh max-w-2xl pb-24">
      <header className="sticky top-0 z-10 flex items-center justify-between border-b-2 border-ink bg-canvas px-4 py-3">
        <span className="font-display text-2xl uppercase leading-none text-brick">Botardo</span>
        <button
          aria-label="Cerrar sesión"
          className="flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-[4px] text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
          onClick={() => { logout(); nav("/login"); }}
        >
          <LogOut size={18} strokeWidth={1.5} aria-hidden="true" />
        </button>
      </header>
      <main className="p-4">
        <Outlet />
      </main>
      <nav
        aria-label="Navegación principal"
        className="fixed inset-x-0 bottom-0 z-10 border-t-2 border-ink bg-canvas pb-[env(safe-area-inset-bottom)]"
      >
        <div className="mx-auto flex max-w-2xl">
          {[
            { to: "/", label: "Dashboard", Icon: LayoutDashboard },
            { to: "/movimientos", label: "Movimientos", Icon: ListOrdered },
          ].map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              end
              className={({ isActive }) =>
                `flex min-h-[56px] flex-1 cursor-pointer flex-col items-center justify-center gap-1 text-[11px] font-extrabold uppercase tracking-[0.08em] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brick/40 ${
                  isActive ? "text-brick" : "text-ink-3 hover:text-ink"
                }`
              }
            >
              <Icon size={20} strokeWidth={1.5} aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
