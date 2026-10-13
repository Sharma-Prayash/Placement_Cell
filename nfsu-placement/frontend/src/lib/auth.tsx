import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";

export type Role = "admin" | "officer" | "coordinator" | "recruiter" | "student";
export interface Me {
  username: string;
  name: string;
  role: Role;
  mfa_enabled: boolean;
  coordinator_course: string | null;
  company?: string;
}

interface AuthState {
  me: Me | null;
  loading: boolean;
  refresh: () => Promise<void>;
  setMe: (m: Me | null) => void;
  signOut: () => Promise<void>;
}

const Ctx = createContext<AuthState>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    try {
      setMe(await api<Me>("/auth/me"));
    } catch {
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);
  const signOut = useCallback(async () => {
    try {
      await api("/auth/logout", { method: "POST" });
    } finally {
      setMe(null);
    }
  }, []);
  useEffect(() => {
    refresh();
  }, [refresh]);
  return <Ctx.Provider value={{ me, loading, refresh, setMe, signOut }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
export const isStaff = (r?: Role) => r === "admin" || r === "officer" || r === "coordinator";
export const homeFor = (r?: Role) => (r === "student" ? "/student" : r === "recruiter" ? "/recruiter" : isStaff(r) ? "/staff" : "/");
