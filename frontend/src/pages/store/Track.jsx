import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { api, errMsg } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { mmk, statusLabel, STATUS_STYLE } from "@/lib/fmt";

export default function Track() {
  const { t } = useI18n();
  const [sp] = useSearchParams();
  const [ref, setRef] = useState(sp.get("ref") || "");
  const [token, setToken] = useState(sp.get("token") || "");
  const [res, setRes] = useState(null);
  const [error, setError] = useState("");
  const lookup = useCallback(async (r, tk) => {
    setError("");
    try { setRes((await api.get("/orders/track", { params: { ref: r, token: tk } })).data); } catch (er) { setRes(null); setError(errMsg(er)); }
  }, []);
  const go = (e) => { e.preventDefault(); lookup(ref, token); };
  const qRef = sp.get("ref");
  const qToken = sp.get("token");
  useEffect(() => {
    if (qRef && qToken) lookup(qRef, qToken);
  }, [qRef, qToken, lookup]);
  return (
    <div className="container-x py-12 max-w-xl">
      <h1 className="text-4xl font-extrabold tracking-tight">{t("track")}</h1>
      <form onSubmit={go} className="mt-6 space-y-3">
        <input data-testid="track-ref-input" value={ref} onChange={(e) => setRef(e.target.value)} placeholder="DAV-2026-000001" className="w-full h-11 rounded-xl border px-4 bg-transparent" />
        <input data-testid="track-token-input" value={token} onChange={(e) => setToken(e.target.value)} placeholder="Tracking code" className="w-full h-11 rounded-xl border px-4 bg-transparent" />
        <button data-testid="track-submit-btn" className="h-11 px-6 rounded-xl bg-blue-600 text-white font-semibold">{t("track")}</button>
      </form>
      {error && <p className="mt-4 text-rose-600 text-sm" data-testid="track-error">{error}</p>}
      {res && (
        <div className="mt-8 rounded-2xl border p-6 space-y-2" data-testid="track-result">
          <p className="font-mono font-bold">{res.ref}</p>
          <p>{res.product_name} · {res.variant_name}</p>
          <p className="font-display text-xl font-bold">{mmk(res.total_mmk)}</p>
          <span className={`inline-block text-xs border px-2.5 py-1 rounded-full ${STATUS_STYLE[res.status]}`} data-testid="track-status">{statusLabel(res.status)}</span>
        </div>
      )}
    </div>
  );
}
