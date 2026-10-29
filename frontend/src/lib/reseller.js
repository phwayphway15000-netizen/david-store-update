import { createContext, useContext, useEffect, useState, createElement } from "react";
import { api } from "./api";

const Ctx = createContext(null);

export function ResellerProvider({ children }) {
  const [me, setMe] = useState(null);
  const [cart, setCart] = useState([]);
  useEffect(() => {
    api.get("/reseller/auth/me").then((r) => setMe(r.data)).catch(() => setMe(false));
  }, []);
  useEffect(() => {
    if (me) setCart(JSON.parse(localStorage.getItem(`rcart:${me.id}`) || "[]"));
  }, [me]);
  const saveCart = (c) => {
    setCart(c);
    if (me) localStorage.setItem(`rcart:${me.id}`, JSON.stringify(c));
  };
  const logout = async () => {
    await api.post("/reseller/auth/logout").catch(() => {});
    setMe(false);
  };
  return createElement(Ctx.Provider, { value: { me, setMe, logout, cart, saveCart } }, children);
}

export const useReseller = () => useContext(Ctx);
