import { STATUS_STYLE, statusLabel } from "@/lib/fmt";

export const inp = "w-full h-10 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-blue-500";
export const btn = "inline-flex items-center justify-center gap-2 h-10 px-4 rounded-lg text-sm font-semibold transition-colors disabled:opacity-50";
export const btnPrimary = `${btn} bg-blue-600 hover:bg-blue-700 text-white`;
export const btnGhost = `${btn} border hover:bg-slate-50 dark:hover:bg-slate-800`;
export const btnDanger = `${btn} bg-rose-600 hover:bg-rose-700 text-white`;

export const PageHeader = ({ title, sub, children }) => (
  <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
    <div><h1 className="text-2xl font-bold tracking-tight" data-testid="admin-page-title">{title}</h1>{sub && <p className="text-sm text-muted-foreground mt-1">{sub}</p>}</div>
    <div className="flex flex-wrap gap-2">{children}</div>
  </div>
);

export const StatusBadge = ({ s }) => (
  <span data-testid="order-status-badge" className={`inline-flex text-[11px] font-semibold border px-2 py-0.5 rounded-full whitespace-nowrap ${STATUS_STYLE[s] || "bg-slate-100"}`}>{statusLabel(s)}</span>
);

export const Field = ({ label, children, hint }) => (
  <label className="block">
    <span className="text-xs font-semibold text-muted-foreground">{label}</span>
    <div className="mt-1">{children}</div>
    {hint && <span className="text-[11px] text-muted-foreground">{hint}</span>}
  </label>
);

export const Card = ({ children, className = "", ...rest }) => <div className={`rounded-xl border bg-card p-5 ${className}`} {...rest}>{children}</div>;

export const Th = ({ children }) => <th className="text-left text-xs font-semibold text-muted-foreground px-3 py-2.5 whitespace-nowrap">{children}</th>;
export const Td = ({ children, className = "" }) => <td className={`px-3 py-2.5 text-sm align-middle ${className}`}>{children}</td>;
