import { Navigate, Route, Routes } from "react-router-dom";

import { isAuthenticated } from "@/api/auth";
import Layout from "@/components/Layout";
import { ToastProvider } from "@/components/ui/Toast";
import Cities from "@/pages/Cities";
import Dashboard from "@/pages/Dashboard";
import Login from "@/pages/Login";
import Movements from "@/pages/Movements";
import Trip from "@/pages/Trip";

function Guard({ children }: { children: React.ReactNode }) {
  return isAuthenticated() ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <ToastProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<Guard><Layout /></Guard>}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/viaje" element={<Trip />} />
          <Route path="/ciudades" element={<Cities />} />
          <Route path="/movimientos" element={<Movements />} />
        </Route>
      </Routes>
    </ToastProvider>
  );
}
