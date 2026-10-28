import { NavLink, Navigate, Outlet, Link, useLocation } from "react-router-dom";
import { useMemo, useState } from "react";
import { LayoutDashboard, Package, Tags, PlugZap, Inbox, Megaphone, Wallet, Users, Settings, ScrollText, LogOut, Menu, Store, Boxes } from "lucide-react";
import { useAuth } from "@/lib/auth";

const NAV = [
  ["", "Dashboard", LayoutDashboard, "dashboard"], ["orders", "Orders", Inbox, "orders"], ["products", "Products", Package, "products"],
  ["catalog", "Brands & Categories", Tags, "catalog"], ["supplier-integrations", "Supplier Integrations", PlugZap, "suppliers"], ["supplier-catalogue", "Supplier Catalogue", Boxes, "suppliers"], ["suppliers", "Custom suppliers", PlugZap, "suppliers"], ["promotions", "Promotions", Megaphone, "promotions"],
  ["payment-methods", "Payment methods", Wallet, "orders"], ["users", "Team", Users, "users.view"], ["settings", "Settings", Settings, "settings"],
  ["audit", "Audit log", ScrollText, "audit"],
];

export default function AdminLayout() {
  const { user, logout, can } = useAuth();
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const navItems = useMemo(() => NAV.filter((n) => can(n[3])), [user]); // eslint-disable-line react-hooks/exhaustive-deps
  if (user === null) return <div className="min-h-screen grid place-items-center text-sm text-muted-foreground">Loading…</div>;
  if (!user) return <Navigate to="/admin/login" replace />;
  const seg = pathname.split("/")[2] || "";
  const route = NAV.find((n) => n[0] === seg);
  const allowed = !route || can(route[3]);
  const side = (
    <aside className="w-64 shrink-0 bg-[#0A1128] text-slate-300 flex flex-col h-full">
      <Link to="/admin" className="px-5 h-16 flex items-center gap-2 border-b border-white/10">
        <img src="/logo-mark.png" alt="logo" className="h-10 w-10 object-contain" />
        <span className="text-white font-semibold text-sm">Store Operations</span>
      </Link>
      <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
        {navItems.map(([to, label, I]) => (
          <NavLink key={to} to={`/admin${to ? "/" + to : ""}`} end={!to} onClick={() => setOpen(false)} data-testid={`admin-nav-${to || "dashboard"}`}
            className={({ isActive }) => `flex items-center gap-3 px-3 h-10 rounded-lg text-sm transition-colors ${isActive ? "bg-blue-600 text-white" : "hover:bg-white/5"}`}>
            <I className="h-4 w-4" />{label}
          </NavLink>
        ))}
      </nav>
      <div className="p-4 border-t border-white/10 text-xs">
        <p className="text-white font-medium truncate" data-testid="admin-user-email">{user.email}</p>
        <p className="text-slate-400 capitalize" data-testid="admin-user-role">{user.role.replace("_", " ")}</p>
        <div className="mt-3 flex gap-2">
          <Link to="/" className="flex-1 h-8 rounded-md bg-white/5 hover:bg-white/10 inline-flex items-center justify-center gap-1"><Store className="h-3.5 w-3.5" />Store</Link>
          <button onClick={logout} data-testid="admin-logout-btn" className="flex-1 h-8 rounded-md bg-white/5 hover:bg-white/10 inline-flex items-center justify-center gap-1"><LogOut className="h-3.5 w-3.5" />Logout</button>
        </div>
      </div>
    </aside>
  );
  return (
    <div className="min-h-screen flex bg-slate-50 dark:bg-slate-950">
      <div className="hidden lg:block sticky top-0 h-screen">{side}</div>
      {open && <div className="fixed inset-0 z-50 flex lg:hidden"><div className="h-full">{side}</div><div className="flex-1 bg-black/40" onClick={() => setOpen(false)} /></div>}
      <div className="flex-1 min-w-0">
        <div className="lg:hidden h-14 px-4 flex items-center border-b bg-white dark:bg-slate-900">
          <button onClick={() => setOpen(true)} data-testid="admin-mobile-menu" aria-label="Menu"><Menu className="h-5 w-5" /></button>
          <span className="ml-3 font-semibold text-sm">Store Operations</span>
        </div>
        <main className="p-4 sm:p-8 max-w-[1400px]">{allowed ? <Outlet /> : <p className="text-sm text-amber-700" data-testid="no-permission">You don't have permission to view this page.</p>}</main>
      </div>
    </div>
  );
}
