import { Navigate, Route, Routes } from "react-router-dom";

import { isAuthenticated } from "@/api/auth";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import Login from "@/pages/Login";
import Movements from "@/pages/Movements";

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
