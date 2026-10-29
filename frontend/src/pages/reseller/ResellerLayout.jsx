import { NavLink, Navigate, Outlet, Link } from "react-router-dom";
import { LogOut, ListOrdered, Store } from "lucide-react";
import { useReseller } from "@/lib/reseller";
import { useI18n } from "@/lib/i18n";

const link = ({ isActive }) => `inline-flex items-center gap-2 h-9 px-3 rounded-lg text-sm font-medium transition-colors ${isActive ? "bg-blue-600 text-white" : "hover:bg-slate-100 dark:hover:bg-slate-800"}`;

export default function ResellerLayout() {
  const { me, logout, cart } = useReseller();
  const { pick, lang, setLang } = useI18n();
  if (me === null) return <div className="min-h-screen grid place-items-center text-sm text-muted-foreground">Loading…</div>;
  if (!me) return <Navigate to="/reseller/login" replace />;
  const count = cart.reduce((s, c) => s + c.quantity, 0);
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <header className="sticky top-0 z-40 bg-white/90 dark:bg-slate-900/90 backdrop-blur border-b">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center gap-3">
          <Link to="/reseller" className="flex items-center gap-2 mr-auto" data-testid="reseller-home-link">
            <img src="/logo-mark.png" alt="logo" className="h-9 w-9 object-contain" />
            <span className="hidden sm:block font-semibold text-sm">{pick("Reseller Portal", "Reseller Portal")}</span>
          </Link>
          <NavLink to="/reseller" end className={link} data-testid="reseller-nav-shop"><Store className="h-4 w-4" /><span className="hidden sm:inline">{pick("Order", "မှာယူရန်")}</span>{count > 0 && <span className="text-[11px] bg-amber-400 text-slate-900 rounded-full px-1.5" data-testid="reseller-cart-count">{count}</span>}</NavLink>
          <NavLink to="/reseller/orders" className={link} data-testid="reseller-nav-orders"><ListOrdered className="h-4 w-4" /><span className="hidden sm:inline">{pick("My orders", "အော်ဒါများ")}</span></NavLink>
          <button onClick={() => setLang(lang === "my" ? "en" : "my")} className="h-9 px-2 text-xs font-semibold rounded-lg border" data-testid="reseller-lang-toggle">{lang === "my" ? "EN" : "MM"}</button>
          <button onClick={logout} className="h-9 w-9 grid place-items-center rounded-lg border" data-testid="reseller-logout-btn" aria-label="Logout"><LogOut className="h-4 w-4" /></button>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-4 py-6 sm:py-10">
        <p className="text-xs text-muted-foreground mb-1" data-testid="reseller-name">{me.business_name || me.name}</p>
        <Outlet />
      </main>
    </div>
  );
}
