import { Navigate, Route, Routes } from "react-router-dom";

import { isAuthenticated } from "@/api/auth";
import DemoBanner from "@/components/DemoBanner";
import DemoIntro from "@/components/DemoIntro";
import Layout from "@/components/Layout";
import { ToastProvider } from "@/components/ui/Toast";
import Budget from "@/pages/Budget";
import Cities from "@/pages/Cities";
import Dashboard from "@/pages/Dashboard";
import Login from "@/pages/Login";
import Movements from "@/pages/Movements";
import NotFound from "@/pages/NotFound";
import Preview from "@/pages/Preview";

function Guard({ children }: { children: React.ReactNode }) {
  return isAuthenticated() ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <ToastProvider>
      <DemoBanner />
      <DemoIntro />
      <Routes>
        <Route path="/login" element={<Login />} />
        {/* Kitchen-sink del sistema de diseño: solo en dev, sin auth ni Layout
            (ver .interface-design/system.md). Vite elimina la rama en el build. */}
        {import.meta.env.DEV && <Route path="/preview" element={<Preview />} />}
        <Route element={<Guard><Layout /></Guard>}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/presupuesto" element={<Budget />} />
          {/* /viaje se reemplazó por /presupuesto; la PWA instalada puede
              tener la ruta vieja en un marcador o en el manifest. */}
          <Route path="/viaje" element={<Navigate to="/presupuesto" replace />} />
          <Route path="/ciudades" element={<Cities />} />
          <Route path="/movimientos" element={<Movements />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </ToastProvider>
  );
}
