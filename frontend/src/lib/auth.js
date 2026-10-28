import { createContext, useContext, useEffect, useState, createElement } from "react";
import { api } from "./api";

const Ctx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  useEffect(() => {
    api.get("/auth/me").then((r) => setUser(r.data)).catch(() => setUser(false));
  }, []);
  const logout = async () => {
    await api.post("/auth/logout").catch(() => {});
    setUser(false);
  };
  const can = (p) => !!user && (user.permissions?.includes("*") || user.permissions?.includes(p));
  return createElement(Ctx.Provider, { value: { user, setUser, logout, can } }, children);
}

export const useAuth = () => useContext(Ctx);
