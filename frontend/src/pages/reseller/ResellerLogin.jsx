import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { api, errMsg } from "@/lib/api";
import { useReseller } from "@/lib/reseller";
import { useI18n } from "@/lib/i18n";
import { inp, btnPrimary } from "@/components/admin/ui";

export default function ResellerLogin() {
  const { me, setMe } = useReseller();
  const { pick } = useI18n();
  const nav = useNavigate();
  const [f, setF] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (me) return <Navigate to="/reseller" replace />;
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError("");
    try { const { data } = await api.post("/reseller/auth/login", f); setMe(data); nav("/reseller"); } catch (er) { setError(errMsg(er)); } finally { setBusy(false); }
  };
  return (
    <div className="min-h-screen grid place-items-center p-6 bg-[#0A1128]">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 bg-white dark:bg-slate-900 rounded-2xl p-7 shadow-2xl" data-testid="reseller-login-form">
        <img src="/logo-mark.png" alt="logo" className="h-14 w-14 object-contain" />
        <div><h1 className="text-2xl font-bold">{pick("Reseller sign in", "Reseller အကောင့်ဝင်ရန်")}</h1>
          <p className="text-sm text-muted-foreground mt-1 leading-relaxed">{pick("Accounts are created by the store admin.", "အကောင့်များကို Admin မှ ဖွင့်ပေးပါသည်။")}</p></div>
        <input data-testid="reseller-email-input" type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} placeholder="Email" className={inp + " h-11"} />
        <input data-testid="reseller-password-input" type="password" required value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} placeholder="Password" className={inp + " h-11"} />
        {error && <p className="text-sm text-rose-600" data-testid="reseller-login-error">{error}</p>}
        <button data-testid="reseller-login-btn" disabled={busy} className={btnPrimary + " w-full h-11"}>{busy ? "…" : pick("Sign in", "ဝင်မည်")}</button>
      </form>
    </div>
  );
}
