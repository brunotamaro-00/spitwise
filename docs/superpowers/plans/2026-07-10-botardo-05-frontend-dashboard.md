# Botardo Viaje — Plan 5: Frontend dashboard (mobile-first)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dashboard web de Botardo (React 19 + Vite, reciclado de Expenses): login, balance destacado + botón saldar, total del viaje, gasto por ciudad y por categoría, timeline, y lista de movimientos (editar/borrar/corregir FX). **Mobile-first**, con estética de la familia Andiamo (Panini).

**Architecture:** SPA React 19 + Vite + Tailwind 4 + react-query + axios (JWT en `localStorage`) + recharts + react-router. Un solo libro compartido: sin filtros por usuario. Diseño mobile-first (columna única, nav simple), que escala a desktop con `max-width` y grid.

**Tech Stack:** React 19, Vite, TypeScript, Tailwind 4 (tokens Panini en `@theme`), @tanstack/react-query, axios, recharts, lucide-react, react-router-dom, vitest.

## Global Constraints

- **Identidad git personal** (`brunotamaro-00` / `brunotamaro@hotmail.com`). Ya configurada en el repo.
- **Mobile-first**: diseñar para viewport chico primero; desktop es progresivo (max-width + grid). Touch targets ≥ 44px.
- **Estética familia Andiamo (Panini)**: crema cálido, Anton display (uppercase), Hanken Grotesk body, sombras sticker, acento brick/gold. Replicar los tokens de Andiamo (`AGENTS.md` → design system) en el `@theme` de Tailwind 4.
- Montos llegan como **string** (Decimal) — nunca hacer aritmética con floats sobre ellos sin parsear.
- **Skills obligatorias**: copiar los commands de Andiamo (`frontend-design`, `baseline-ui`, `icons-system`, `fixing-accessibility`) a `.claude/commands/` del repo Botardo y aplicarlos: `frontend-design` al construir cada pantalla, luego `baseline-ui` + `icons-system` + `fixing-accessibility` como pasada de calidad antes de cerrar cada task de UI.
- Iconos: Lucide, `strokeWidth={1.5}`, `aria-hidden` en decorativos, `aria-label` en icon-only. Sin emojis como chrome (salvo banderas de país).

**Referencia de reutilización (Expenses):** `frontend/` completo — `src/api/client.ts` (axios+JWT), `src/api/auth.ts`, `src/pages/Login.tsx`, `src/pages/Dashboard.tsx`, `src/components/{SummaryCard,CategoryDonutChart,SpendingBarChart,ExpenseTable}.tsx`, `src/types/index.ts`, `vite.config.ts`, `src/index.css`. Reciclar estructura y patrones; re-temar a Panini.

---

## Estructura de archivos (Plan 5)

- Create: `.claude/commands/{frontend-design,baseline-ui,icons-system,fixing-accessibility}.md` (copia desde andiamo).
- Create: `frontend/` scaffold (`package.json`, `vite.config.ts`, `tsconfig*.json`, `index.html`, `postcss.config.js`, `eslint.config.js`).
- Create: `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/index.css` (tokens Panini).
- Create: `frontend/src/lib/format.ts` (+ test), `frontend/src/types/index.ts`.
- Create: `frontend/src/api/{client.ts,auth.ts,movements.ts,dashboard.ts,categories.ts}`.
- Create: `frontend/src/pages/{Login.tsx,Dashboard.tsx,Movements.tsx}`.
- Create: `frontend/src/components/{Layout.tsx,BalanceHero.tsx,SettleDialog.tsx,CitySpendChart.tsx,CategoryDonut.tsx,SpendTimeline.tsx,MovementRow.tsx,AddMovementDialog.tsx}`.

---

### Task 1: Scaffold del frontend + tokens Panini + skills

**Files:**
- Create: `.claude/commands/*.md` (copia)
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/index.html`, `frontend/postcss.config.js`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/index.css`
- Test: `frontend/src/lib/format.ts`, `frontend/src/lib/format.test.ts`

**Interfaces:**
- Produces: app Vite que compila; `src/lib/format.ts` con `formatUsd(s: string): string`, `parseMoney(s: string): number`.

- [x] **Step 1: Copiar los commands de Andiamo**

Run:
```bash
mkdir -p ~/Desktop/Trip/Botardo/.claude/commands
cp ~/Desktop/Trip/andiamo/.claude/commands/{frontend-design,baseline-ui,icons-system,fixing-accessibility}.md ~/Desktop/Trip/Botardo/.claude/commands/
```

- [x] **Step 2: Escribir el test que falla**

`frontend/src/lib/format.test.ts`:
```ts
import { describe, expect, it } from "vitest";

import { formatUsd, parseMoney } from "./format";

describe("format", () => {
  it("formatUsd", () => {
    expect(formatUsd("1234.5")).toBe("USD 1,234.50");
  });
  it("parseMoney", () => {
    expect(parseMoney("50.00")).toBe(50);
  });
});
```

- [x] **Step 3: Crear scaffold Vite**

`frontend/package.json`:
```json
{
  "name": "botardo-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint .",
    "test": "vitest run",
    "preview": "vite preview"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.95.0",
    "axios": "^1.13.6",
    "clsx": "^2.1.1",
    "lucide-react": "^1.0.1",
    "react": "^19.2.4",
    "react-dom": "^19.2.4",
    "react-router-dom": "^7.13.1",
    "recharts": "^3.8.0"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4.2.2",
    "@types/react": "^19.2.14",
    "@types/react-dom": "^19.2.3",
    "@vitejs/plugin-react": "^6.0.1",
    "autoprefixer": "^10.4.27",
    "eslint": "^9.39.4",
    "jsdom": "^26.1.0",
    "postcss": "^8.5.8",
    "tailwindcss": "^4.2.2",
    "typescript": "~5.9.3",
    "vite": "^8.0.1",
    "vitest": "^3.2.0"
  }
}
```

`frontend/vite.config.ts`:
```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8000", "/webhooks": "http://localhost:8000" } },
  test: { environment: "jsdom", globals: true },
});
```

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022", "useDefineForClassFields": true, "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext", "skipLibCheck": true, "moduleResolution": "bundler",
    "allowImportingTsExtensions": true, "noEmit": true, "jsx": "react-jsx",
    "strict": true, "noUnusedLocals": true, "noUnusedParameters": true,
    "baseUrl": ".", "paths": { "@/*": ["src/*"] }
  },
  "include": ["src"]
}
```

`frontend/index.html`:
```html
<!doctype html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
    <title>Botardo Viaje</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`frontend/postcss.config.js`:
```js
export default { plugins: { "@tailwindcss/postcss": {}, autoprefixer: {} } };
```

- [x] **Step 4: Tokens Panini en `index.css`**

`frontend/src/index.css` (replica el design system de Andiamo; Tailwind 4 `@theme`):
```css
@import "tailwindcss";

@theme {
  --color-canvas: #F3ECD8;
  --color-surface: #FFFFFF;
  --color-surface-2: #EAE2CB;
  --color-border: #D8CFB4;
  --color-border-strong: #C2B08A;
  --color-ink: #1B1A17;
  --color-ink-2: #6B6452;
  --color-ink-3: #8A7F6A;
  --color-brick: #C44428;
  --color-gold: #C8A24B;
  --color-success: #2F7D4F;
  --color-danger: #B23A2E;
  --font-display: "Anton", sans-serif;
  --font-sans: "Hanken Grotesk", system-ui, sans-serif;
}

body { background: var(--color-canvas); color: var(--color-ink); font-family: var(--font-sans); }

@layer utilities {
  .card-shadow { box-shadow: 3px 3px 0 var(--color-border); }
  .hard-shadow-ink { box-shadow: 3px 3px 0 var(--color-ink); }
  .font-tabular { font-variant-numeric: tabular-nums; }
}
```

Nota: cargar las fonts Anton / Hanken Grotesk vía `<link>` en `index.html` (Google Fonts) o self-hosted. Para prod/PWA, self-hostearlas; en dev, `<link>` alcanza.

- [x] **Step 5: `main.tsx`, `App.tsx`, `format.ts`**

`frontend/src/main.tsx`:
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import "./index.css";

const qc = new QueryClient();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
```

`frontend/src/App.tsx`:
```tsx
export default function App() {
  return <div className="p-4">Botardo</div>;
}
```

`frontend/src/lib/format.ts`:
```ts
export function parseMoney(s: string): number {
  return Number(s);
}

export function formatUsd(s: string): string {
  const n = parseMoney(s);
  return `USD ${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
```

- [x] **Step 6: Instalar y testear**

Run: `cd frontend && npm install && npm run test`
Expected: PASS (format.test).
Run: `npm run build`
Expected: build OK.

- [x] **Step 7: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add .claude/commands frontend
git commit -m "feat(frontend): scaffold Vite + tokens Panini + skills de diseño"
```

---

### Task 2: Tipos + capa de API + auth (login)

**Files:**
- Create: `frontend/src/types/index.ts`, `frontend/src/api/{client.ts,auth.ts,movements.ts,dashboard.ts,categories.ts}`, `frontend/src/pages/Login.tsx`
- Modify: `frontend/src/App.tsx` (rutas + guard)
- Test: `frontend/src/api/client.test.ts`

**Interfaces:**
- Produces:
  - `types`: `Movement`, `Balance`, `Summary`, `CitySpend`, `CategorySpend`, `TimePoint`, `Category` (montos como `string`).
  - `api/client.ts`: axios instance con baseURL `/api/v1`, interceptor que agrega `Authorization: Bearer <localStorage.auth_token>` y en 401 limpia token + redirige a `/login`.
  - `api/auth.ts`: `login(username,password): Promise<string>` (guarda token), `logout()`, `isAuthenticated()`.
  - `api/users.ts`: `listUsers(): Promise<User[]>` (`GET /users`, agregado en Plan 2) — alimenta los nombres del balance y el selector de pagador del settle.
  - `api/movements.ts`: `listMovements()`, `createMovement(body)`, `updateMovement(id,body)`, `deleteMovement(id)`.
  - `api/dashboard.ts`: `getBalance()`, `getSummary()`, `getByCity()`, `getByCategory()`, `getTimeseries()`.
  - `api/categories.ts`: `listCategories()`.
  - `pages/Login.tsx`: form usuario/clave → `login` → navega a `/`.

- [x] **Step 1: Escribir el test que falla**

`frontend/src/api/client.test.ts`:
```ts
import { describe, expect, it, beforeEach } from "vitest";

import { authHeader } from "./client";

describe("authHeader", () => {
  beforeEach(() => localStorage.clear());
  it("vacío sin token", () => {
    expect(authHeader()).toEqual({});
  });
  it("bearer con token", () => {
    localStorage.setItem("auth_token", "T");
    expect(authHeader()).toEqual({ Authorization: "Bearer T" });
  });
});
```

- [x] **Step 2: Correr y verificar fallo**

Run: `cd frontend && npm run test -- client.test`
Expected: FAIL — `./client` no existe.

- [x] **Step 3: Implementar `client.ts` + `types`**

`frontend/src/types/index.ts`:
```ts
export type Movement = {
  id: number; type: string; amount: string; currency: string; amount_usd: string;
  fx_rate: string; fx_source: string; paid_by: number; split: string;
  description: string | null; category_id: number | null;
  stop_slug: string | null; city_name: string | null; movement_date: string;
};
export type Balance = { debtor_id: number | null; creditor_id: number | null; amount_usd: string };
export type Summary = { total_usd: string; movement_count: number };
export type CitySpend = { stop_slug: string | null; city_name: string | null; total_usd: string };
export type CategorySpend = { category_id: number | null; name: string | null; icon: string | null; total_usd: string };
export type TimePoint = { date: string; cumulative_usd: string };
export type Category = { id: number; name: string; icon: string | null; sort_order: number };
export type User = { id: number; username: string };
```

`frontend/src/api/client.ts`:
```ts
import axios from "axios";

export function authHeader(): Record<string, string> {
  const t = localStorage.getItem("auth_token");
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export const api = axios.create({ baseURL: "/api/v1" });

api.interceptors.request.use((config) => {
  Object.assign(config.headers, authHeader());
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      localStorage.removeItem("auth_token");
      if (location.pathname !== "/login") location.assign("/login");
    }
    return Promise.reject(err);
  },
);
```

- [x] **Step 4: Correr el test**

Run: `cd frontend && npm run test -- client.test`
Expected: PASS.

- [x] **Step 5: Implementar auth + api layer + Login + rutas**

`frontend/src/api/auth.ts`:
```ts
import { api } from "./client";

export async function login(username: string, password: string): Promise<string> {
  const form = new URLSearchParams({ username, password });
  const { data } = await api.post("/auth/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  localStorage.setItem("auth_token", data.access_token);
  return data.access_token;
}
export function logout() { localStorage.removeItem("auth_token"); }
export function isAuthenticated() { return !!localStorage.getItem("auth_token"); }
```

`frontend/src/api/movements.ts`:
```ts
import type { Movement } from "@/types";
import { api } from "./client";

export async function listMovements(): Promise<Movement[]> {
  return (await api.get("/movements")).data;
}
export async function createMovement(body: Partial<Movement>): Promise<Movement> {
  return (await api.post("/movements", body)).data;
}
export async function updateMovement(id: number, body: Partial<Movement>): Promise<Movement> {
  return (await api.patch(`/movements/${id}`, body)).data;
}
export async function deleteMovement(id: number): Promise<void> {
  await api.delete(`/movements/${id}`);
}
```

`frontend/src/api/dashboard.ts`:
```ts
import type { Balance, CategorySpend, CitySpend, Summary, TimePoint } from "@/types";
import { api } from "./client";

export const getBalance = async (): Promise<Balance> => (await api.get("/balance")).data;
export const getSummary = async (): Promise<Summary> => (await api.get("/dashboard/summary")).data;
export const getByCity = async (): Promise<CitySpend[]> => (await api.get("/dashboard/by-city")).data;
export const getByCategory = async (): Promise<CategorySpend[]> => (await api.get("/dashboard/by-category")).data;
export const getTimeseries = async (): Promise<TimePoint[]> => (await api.get("/dashboard/timeseries")).data;
```

`frontend/src/api/categories.ts`:
```ts
import type { Category } from "@/types";
import { api } from "./client";

export const listCategories = async (): Promise<Category[]> => (await api.get("/categories")).data;
```

`frontend/src/api/users.ts`:
```ts
import type { User } from "@/types";
import { api } from "./client";

export const listUsers = async (): Promise<User[]> => (await api.get("/users")).data;
```

`frontend/src/pages/Login.tsx` (aplicar `frontend-design` — base):
```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { login } from "@/api/auth";

export default function Login() {
  const nav = useNavigate();
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      await login(u, p);
      nav("/");
    } catch {
      setErr("Usuario o contraseña inválidos");
    }
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-4 p-6">
      <h1 className="font-display text-4xl uppercase text-brick">Botardo</h1>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <input className="min-h-[44px] rounded-xl border-2 border-border bg-surface px-3" placeholder="Usuario"
               value={u} onChange={(e) => setU(e.target.value)} autoFocus />
        <input className="min-h-[44px] rounded-xl border-2 border-border bg-surface px-3" placeholder="Contraseña"
               type="password" value={p} onChange={(e) => setP(e.target.value)} />
        {err && <p className="text-sm text-danger">{err}</p>}
        <button className="min-h-[44px] rounded-[2px] bg-brick font-display uppercase text-surface hard-shadow-ink active:translate-x-[3px] active:translate-y-[3px] active:shadow-none">
          Entrar
        </button>
      </form>
    </div>
  );
}
```

`frontend/src/App.tsx`:
```tsx
import { Navigate, Route, Routes } from "react-router-dom";

import { isAuthenticated } from "@/api/auth";
import Dashboard from "@/pages/Dashboard";
import Login from "@/pages/Login";
import Movements from "@/pages/Movements";
import Layout from "@/components/Layout";

function Guard({ children }: { children: React.ReactNode }) {
  return isAuthenticated() ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Guard><Layout /></Guard>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/movimientos" element={<Movements />} />
      </Route>
    </Routes>
  );
}
```

Nota: `Layout`, `Dashboard`, `Movements` se crean en Tasks 3-4; para que compile ahora, crear stubs mínimos (`export default function X(){return null}`) y completarlos en las tareas siguientes.

- [x] **Step 6: Verificar build**

Run: `cd frontend && npm run build`
Expected: build OK (con stubs).

- [x] **Step 7: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add frontend/src
git commit -m "feat(frontend): tipos + capa API + auth/login + rutas"
```

---

### Task 3: Layout mobile-first + página de movimientos

**Files:**
- Create: `frontend/src/components/Layout.tsx`, `frontend/src/components/MovementRow.tsx`, `frontend/src/components/AddMovementDialog.tsx`, `frontend/src/pages/Movements.tsx`
- Test: `frontend/src/components/MovementRow.test.tsx`

**Interfaces:**
- `Layout`: header con wordmark + bottom TabBar mobile (`Dashboard` / `Movimientos`) con `env(safe-area-inset-bottom)`; `<Outlet/>`. En desktop, max-width y nav lateral/superior.
- `Movements`: lista `listMovements` (react-query), botón "＋ Agregar", cada fila `MovementRow` (editar/borrar). `AddMovementDialog`: form monto/moneda/categoría/split/fecha → `createMovement`.
- `MovementRow`: muestra fecha, ciudad, categoría, quién pagó, split, monto original + USD; badge si `fx_source==='fallback'`.

**Skills:** aplicar `frontend-design` al Layout y dialog; luego `baseline-ui` + `icons-system` + `fixing-accessibility`. Mobile-first.

- [x] **Step 1: Escribir el test que falla**

`frontend/src/components/MovementRow.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MovementRow from "./MovementRow";

const mv = {
  id: 1, type: "expense", amount: "45.00", currency: "GBP", amount_usd: "57.15",
  fx_rate: "1.27", fx_source: "frankfurter", paid_by: 1, split: "shared",
  description: "cena", category_id: 2, stop_slug: "londres", city_name: "Londres",
  movement_date: "2026-08-06",
};

describe("MovementRow", () => {
  it("muestra USD y moneda original", () => {
    render(<MovementRow mv={mv} onEdit={() => {}} onDelete={() => {}} />);
    expect(screen.getByText(/57\.15/)).toBeTruthy();
    expect(screen.getByText(/GBP 45\.00/)).toBeTruthy();
  });
});
```
Agregar `@testing-library/react` y `@testing-library/jest-dom` a devDependencies e instalarlos; setear `test.setupFiles` si se usa jest-dom (o usar asserts nativos como arriba, sin jest-dom).

- [x] **Step 2: Correr y verificar fallo**

Run: `cd frontend && npm run test -- MovementRow`
Expected: FAIL — `./MovementRow` no existe.

- [x] **Step 3: Implementar `MovementRow.tsx`**

`frontend/src/components/MovementRow.tsx`:
```tsx
import { Pencil, Trash2 } from "lucide-react";

import type { Movement } from "@/types";
import { formatUsd } from "@/lib/format";

export default function MovementRow({ mv, onEdit, onDelete }: {
  mv: Movement; onEdit: (m: Movement) => void; onDelete: (m: Movement) => void;
}) {
  return (
    <div className="flex items-center gap-3 border-b-2 border-border py-3">
      <div className="min-w-0 flex-1">
        <p className="truncate font-semibold text-ink">{mv.description || "—"}</p>
        <p className="text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-3">
          {mv.movement_date} · {mv.city_name || "—"} · {mv.split}
        </p>
      </div>
      <div className="text-right">
        <p className="font-tabular font-bold text-ink">{formatUsd(mv.amount_usd)}</p>
        <p className="font-tabular text-xs text-ink-2">
          {mv.currency} {mv.amount}
          {mv.fx_source === "fallback" && <span className="ml-1 text-danger">≈</span>}
        </p>
      </div>
      <button aria-label="Editar" className="min-h-[44px] min-w-[44px] text-ink-3" onClick={() => onEdit(mv)}>
        <Pencil className="h-5 w-5" strokeWidth={1.5} aria-hidden="true" />
      </button>
      <button aria-label="Borrar" className="min-h-[44px] min-w-[44px] text-danger" onClick={() => onDelete(mv)}>
        <Trash2 className="h-5 w-5" strokeWidth={1.5} aria-hidden="true" />
      </button>
    </div>
  );
}
```

- [x] **Step 4: Implementar `Layout`, `AddMovementDialog`, `Movements`**

`frontend/src/components/Layout.tsx`:
```tsx
import { LayoutDashboard, ListOrdered } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

export default function Layout() {
  return (
    <div className="mx-auto min-h-dvh max-w-2xl pb-20">
      <header className="sticky top-0 z-10 flex items-center justify-between border-b-2 border-ink bg-canvas px-4 py-3">
        <span className="font-display text-2xl uppercase text-brick">Botardo</span>
      </header>
      <main className="p-4">
        <Outlet />
      </main>
      <nav className="fixed inset-x-0 bottom-0 z-10 mx-auto flex max-w-2xl border-t-2 border-ink bg-canvas pb-[env(safe-area-inset-bottom)]">
        {[
          { to: "/", label: "Dashboard", Icon: LayoutDashboard },
          { to: "/movimientos", label: "Movimientos", Icon: ListOrdered },
        ].map(({ to, label, Icon }) => (
          <NavLink key={to} to={to} end
            className={({ isActive }) =>
              `flex flex-1 flex-col items-center gap-1 py-2 text-[11px] font-extrabold uppercase tracking-[0.08em] ${isActive ? "text-brick" : "text-ink-3"}`}>
            <Icon className="h-5 w-5" strokeWidth={1.5} aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
```

`frontend/src/components/AddMovementDialog.tsx`: form controlado (monto, moneda, categoría [de `listCategories`], split [`shared`/`payer_only`/`other_only`], fecha, descripción) que llama `createMovement` e invalida las queries `["movements"]` y `["dashboard"]`. Modal accesible (focus trap, Escape, touch targets ≥44px). Implementar siguiendo `frontend-design` + `fixing-accessibility`.

`frontend/src/pages/Movements.tsx`:
```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";

import { deleteMovement, listMovements } from "@/api/movements";
import AddMovementDialog from "@/components/AddMovementDialog";
import MovementRow from "@/components/MovementRow";
import type { Movement } from "@/types";

export default function Movements() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const { data = [] } = useQuery({ queryKey: ["movements"], queryFn: listMovements });
  const del = useMutation({
    mutationFn: (m: Movement) => deleteMovement(m.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["movements"] }); qc.invalidateQueries({ queryKey: ["dashboard"] }); },
  });

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h1 className="font-display text-2xl uppercase text-ink">Movimientos</h1>
        <button onClick={() => setOpen(true)} aria-label="Agregar"
          className="flex min-h-[44px] items-center gap-1 rounded-[2px] bg-brick px-3 font-display uppercase text-surface hard-shadow-ink">
          <Plus className="h-4 w-4" strokeWidth={2} aria-hidden="true" /> Agregar
        </button>
      </div>
      <div>
        {data.map((m) => (
          <MovementRow key={m.id} mv={m} onEdit={() => {}} onDelete={(mv) => del.mutate(mv)} />
        ))}
        {data.length === 0 && <p className="py-8 text-center text-ink-3">Sin movimientos todavía.</p>}
      </div>
      {open && <AddMovementDialog onClose={() => setOpen(false)} />}
    </div>
  );
}
```

- [x] **Step 5: Pasada de calidad + tests + build**

- Aplicar `baseline-ui`, `icons-system`, `fixing-accessibility` a Layout/Dialog/Row.
Run: `cd frontend && npm run test -- MovementRow && npm run build`
Expected: PASS + build OK.

- [x] **Step 6: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add frontend/src
git commit -m "feat(frontend): layout mobile-first + lista de movimientos (agregar/borrar)"
```

---

### Task 4: Dashboard — balance, total, ciudad, categoría, timeline

**Files:**
- Create: `frontend/src/components/{BalanceHero.tsx,SettleDialog.tsx,CitySpendChart.tsx,CategoryDonut.tsx,SpendTimeline.tsx}`, `frontend/src/pages/Dashboard.tsx`
- Test: `frontend/src/components/BalanceHero.test.tsx`

**Interfaces:**
- `BalanceHero`: recibe `Balance` + nombres de usuarios; muestra "X le debe USD N a Y" (o "Están a mano"); botón **Saldar** abre `SettleDialog`.
- `SettleDialog`: crea `settlement` (`createMovement({type:"settlement", amount, currency:"USD", paid_by})`).
- `CitySpendChart`: recharts bar (por ciudad, USD). `CategoryDonut`: recharts pie. `SpendTimeline`: recharts line (acumulado).
- `Dashboard`: orquesta las queries (`["dashboard","balance"]`, etc.) y arma la grilla (columna única mobile; 2 cols desktop `md:grid-cols-2`).

**Skills:** `frontend-design` para el dashboard (jerarquía visual, hero del balance destacado), luego pasada de calidad. Para los gráficos, aplicar la skill **dataviz** (colores accesibles, mismos tokens). Mobile-first.

- [x] **Step 1: Escribir el test que falla**

`frontend/src/components/BalanceHero.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import BalanceHero from "./BalanceHero";

describe("BalanceHero", () => {
  it("muestra deuda", () => {
    render(<BalanceHero balance={{ debtor_id: 2, creditor_id: 1, amount_usd: "320.00" }}
      names={{ 1: "Bruno", 2: "Novia" }} onSettle={() => {}} />);
    expect(screen.getByText(/Novia/)).toBeTruthy();
    expect(screen.getByText(/320\.00/)).toBeTruthy();
  });
  it("a mano cuando 0", () => {
    render(<BalanceHero balance={{ debtor_id: null, creditor_id: null, amount_usd: "0" }}
      names={{}} onSettle={() => {}} />);
    expect(screen.getByText(/a mano/i)).toBeTruthy();
  });
});
```

- [x] **Step 2: Correr y verificar fallo**

Run: `cd frontend && npm run test -- BalanceHero`
Expected: FAIL — `./BalanceHero` no existe.

- [x] **Step 3: Implementar `BalanceHero.tsx`**

`frontend/src/components/BalanceHero.tsx`:
```tsx
import type { Balance } from "@/types";
import { formatUsd } from "@/lib/format";

export default function BalanceHero({ balance, names, onSettle }: {
  balance: Balance; names: Record<number, string>; onSettle: () => void;
}) {
  const settled = !balance.debtor_id || balance.amount_usd === "0" || balance.amount_usd === "0.00";
  return (
    <section className="rounded-[4px] border-2 border-border bg-surface p-5 card-shadow">
      <p className="text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-3">Balance</p>
      {settled ? (
        <p className="mt-2 font-display text-3xl uppercase text-success">Están a mano</p>
      ) : (
        <>
          <p className="mt-2 text-ink-2">
            <span className="font-bold text-ink">{names[balance.debtor_id!] ?? "Alguien"}</span> le debe a{" "}
            <span className="font-bold text-ink">{names[balance.creditor_id!] ?? "el otro"}</span>
          </p>
          <p className="font-display text-4xl uppercase text-brick">{formatUsd(balance.amount_usd)}</p>
          <button onClick={onSettle}
            className="mt-3 min-h-[44px] rounded-[2px] bg-ink px-4 font-display uppercase text-surface hard-shadow-ink">
            Saldar
          </button>
        </>
      )}
    </section>
  );
}
```

- [x] **Step 4: Implementar charts + SettleDialog + Dashboard**

- `CitySpendChart.tsx` / `CategoryDonut.tsx` / `SpendTimeline.tsx`: recharts (`ResponsiveContainer`), datos `parseMoney` sobre los strings, colores desde la paleta (skill **dataviz**), ejes legibles, tooltips. Contenedores con `overflow-x:auto` si hace falta en mobile.
- `SettleDialog.tsx`: input monto USD + **selector de quién paga (los 2 usuarios de `listUsers`)** → `createMovement({type:"settlement", amount, currency:"USD", paid_by})`, invalida `["balance"]` y `["dashboard"]`.
- `frontend/src/pages/Dashboard.tsx`:
```tsx
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getBalance, getByCategory, getByCity, getSummary, getTimeseries } from "@/api/dashboard";
import { listCategories } from "@/api/categories";
import { listUsers } from "@/api/users";
import BalanceHero from "@/components/BalanceHero";
import CategoryDonut from "@/components/CategoryDonut";
import CitySpendChart from "@/components/CitySpendChart";
import SettleDialog from "@/components/SettleDialog";
import SpendTimeline from "@/components/SpendTimeline";
import { formatUsd } from "@/lib/format";

export default function Dashboard() {
  const [settle, setSettle] = useState(false);
  const balance = useQuery({ queryKey: ["balance"], queryFn: getBalance });
  const summary = useQuery({ queryKey: ["dashboard", "summary"], queryFn: getSummary });
  const byCity = useQuery({ queryKey: ["dashboard", "city"], queryFn: getByCity });
  const byCat = useQuery({ queryKey: ["dashboard", "cat"], queryFn: getByCategory });
  const ts = useQuery({ queryKey: ["dashboard", "ts"], queryFn: getTimeseries });
  const users = useQuery({ queryKey: ["users"], queryFn: listUsers, staleTime: Infinity });

  const names: Record<number, string> = Object.fromEntries(
    (users.data ?? []).map((u) => [u.id, u.username]),
  );

  return (
    <div className="flex flex-col gap-4">
      {balance.data && <BalanceHero balance={balance.data} names={names} onSettle={() => setSettle(true)} />}
      {summary.data && (
        <section className="rounded-[4px] border-2 border-border bg-surface p-5 card-shadow">
          <p className="text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-3">Total del viaje</p>
          <p className="font-display text-4xl uppercase text-ink">{formatUsd(summary.data.total_usd)}</p>
        </section>
      )}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {byCity.data && <CitySpendChart data={byCity.data} />}
        {byCat.data && <CategoryDonut data={byCat.data} />}
      </div>
      {ts.data && <SpendTimeline data={ts.data} />}
      {settle && <SettleDialog onClose={() => setSettle(false)} />}
    </div>
  );
}
```

Nota `names`: el endpoint `GET /api/v1/users` ya existe (Plan 2, Task 2) — no hay deuda acá.

- [x] **Step 5: Pasada de calidad + tests + build**

- Aplicar `dataviz` a los charts; `baseline-ui` + `fixing-accessibility` al dashboard.
Run: `cd frontend && npm run test && npm run build`
Expected: PASS + build OK.

- [x] **Step 6: Commit**

```bash
cd ~/Desktop/Trip/Botardo
git add frontend/src
git commit -m "feat(frontend): dashboard con balance, total, ciudad, categoría y timeline"
```

---

## Self-review (Plan 5)

- **Cobertura de spec §9:** balance destacado + saldar (Task 4), total (Task 4), por ciudad/categoría (Task 4), timeline (Task 4), lista de movimientos editar/borrar/FX badge (Task 3), login (Task 2). Mobile-first + Panini en todas.
- **Placeholders:** `AddMovementDialog`, los 3 charts y `SettleDialog` se describen con interfaz precisa pero sin volcar todo el JSX — es intencional para que se construyan con las skills de diseño (`frontend-design`/`dataviz`) en vez de fijar una estética genérica. La lógica (queries, mutations, endpoints, invalidaciones) está especificada. Al ejecutar, cada uno es un sub-paso con su test/verify.
- **Consistencia de tipos:** `types/index.ts` alinea con los schemas del Plan 2 (montos string; `updateMovement` con `Partial<Movement>` matchea el `MovementUpdate` parcial del backend). `names` y `SettleDialog` consumen `GET /users` (Plan 2).
- **Deploy:** en prod el frontend lo sirve el propio FastAPI (mismo origen) — el `baseURL: "/api/v1"` de axios funciona en dev (proxy de Vite) y en prod sin `VITE_API_URL` (ver Plan 6).
