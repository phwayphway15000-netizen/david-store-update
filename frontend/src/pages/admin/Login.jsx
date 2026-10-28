import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { inp, btnPrimary } from "@/components/admin/ui";

export default function Login() {
  const { user, setUser } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/admin" replace />;
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const { data } = await api.post("/auth/login", { email, password });
      setUser(data);
      nav("/admin");
    } catch (er) { setError(errMsg(er)); } finally { setBusy(false); }
  };
  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:flex bg-[#0A1128] text-white p-12 flex-col justify-between relative overflow-hidden">
        <div className="absolute inset-0 grid-bg opacity-30" />
        <p className="relative font-display font-bold text-lg">AI Tools By David · Operations</p>
        <p className="relative text-4xl font-extrabold leading-tight max-w-md">Every order verified by a human. Every action on the record.</p>
        <p className="relative text-sm text-slate-400">Authorized staff only. Activity is audit-logged.</p>
      </div>
      <div className="grid place-items-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm space-y-4" data-testid="admin-login-form">
          <h1 className="text-2xl font-bold">Sign in</h1>
          <input data-testid="login-email-input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" className={inp + " h-11"} />
          <input data-testid="login-password-input" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" className={inp + " h-11"} />
          {error && <p className="text-sm text-rose-600" data-testid="login-error">{error}</p>}
          <button data-testid="login-submit-btn" disabled={busy} className={btnPrimary + " w-full h-11"}>{busy ? "Signing in…" : "Sign in"}</button>
        </form>
      </div>
    </div>
  );
}
