import { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { isStaff, Role, useAuth } from "./lib/auth";
import Activate from "./pages/Activate";
import Bulletin from "./pages/Bulletin";
import Home from "./pages/Home";
import Login from "./pages/Login";
import Recruit from "./pages/Recruit";
import Recruiter from "./pages/Recruiter";
import Staff from "./pages/Staff";
import Student from "./pages/Student";

/** Client-side guard for navigation only. Real enforcement happens on the server for every request. */
function Guard({ allow, children }: { allow: (r?: Role) => boolean; children: ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return <p className="muted">Loading…</p>;
  if (!me) return <Navigate to="/login" replace />;
  return allow(me.role) ? <>{children}</> : <Navigate to="/" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="login" element={<Login />} />
        <Route path="activate" element={<Activate />} />
        <Route path="recruit" element={<Recruit />} />
        <Route path="bulletin" element={<Guard allow={(r) => !!r}><Bulletin /></Guard>} />
        <Route path="student" element={<Guard allow={(r) => r === "student"}><Student /></Guard>} />
        <Route path="recruiter" element={<Guard allow={(r) => r === "recruiter"}><Recruiter /></Guard>} />
        <Route path="staff/*" element={<Guard allow={isStaff}><Staff /></Guard>} />
        <Route path="*" element={<p>That page does not exist. <a href="/">Go to the overview</a>.</p>} />
      </Route>
    </Routes>
  );
}
