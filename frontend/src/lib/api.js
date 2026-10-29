import axios from "axios";

export const BACKEND = process.env.REACT_APP_BACKEND_URL;
export const api = axios.create({ baseURL: `${BACKEND}/api`, withCredentials: true });

let refreshing = null;
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const cfg = error.config || {};
    if (error.response?.status === 401 && !cfg._retry && !cfg.url?.startsWith("/auth/") && !cfg.url?.startsWith("/reseller/")) {
      cfg._retry = true;
      refreshing = refreshing || api.post("/auth/refresh").finally(() => { refreshing = null; });
      try {
        await refreshing;
        return api(cfg);
      } catch {
        return Promise.reject(error);
      }
    }
    return Promise.reject(error);
  }
);

export function errMsg(e) {
  const d = e?.response?.data?.detail;
  if (d == null) return e?.message || "Something went wrong. Please try again.";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => (x && typeof x.msg === "string" ? `${(x.loc || []).slice(-1)[0] || ""} ${x.msg}` : JSON.stringify(x))).join(" ");
  return d.msg || String(d);
}

export const imgUrl = (u) => (u && u.startsWith("/api") ? `${BACKEND}${u}` : u || "");
