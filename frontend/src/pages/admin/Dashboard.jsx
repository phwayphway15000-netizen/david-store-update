import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { api } from "@/lib/api";
import { mmk, fmtDate } from "@/lib/fmt";
import { PageHeader, Card } from "@/components/admin/ui";

const Stat = ({ label, value, to, accent, testid }) => (
  <Link to={to || "#"} data-testid={testid} className="rounded-xl border bg-card p-4 hover:border-blue-400 transition-colors">
    <p className="text-xs text-muted-foreground">{label}</p>
    <p className={`mt-1 text-2xl font-bold font-display ${accent || ""}`}>{value}</p>
  </Link>
);

export default function Dashboard() {
  const [days, setDays] = useState(30);
  const { data: d } = useQuery({ queryKey: ["dash", days], queryFn: () => api.get(`/admin/dashboard?days=${days}`).then((r) => r.data) });
  const { data: integ } = useQuery({ queryKey: ["integrations"], queryFn: () => api.get("/admin/integrations").then((r) => r.data) });
  if (!d) return <p className="text-sm text-muted-foreground">Loading…</p>;
  const o = d.orders;
  const oq = (s) => `/admin/orders?status=${s}`;
  return (
    <div>
      <PageHeader title="Dashboard" sub="Revenue counts only completed orders with manually verified payment.">
        <select data-testid="dashboard-range" value={days} onChange={(e) => setDays(+e.target.value)} className="h-10 rounded-lg border bg-background px-3 text-sm">
          {[7, 30, 90, 365].map((n) => <option key={n} value={n}>Last {n} days</option>)}
        </select>
      </PageHeader>
      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-6 gap-3">
        <Stat testid="stat-revenue" label="Verified revenue" value={mmk(d.revenue_mmk)} accent="text-emerald-600" />
        <Stat testid="stat-payment-review" label="Payment review" value={o.payment_review} to={oq("PAYMENT_SUBMITTED,PAYMENT_UNDER_REVIEW")} accent="text-blue-600" />
        <Stat testid="stat-delivery-pending" label="Delivery pending" value={o.delivery_pending} to={oq("PAID_AWAITING_FULFILLMENT,FULFILLMENT_IN_PROGRESS")} accent="text-violet-600" />
        <Stat testid="stat-awaiting-payment" label="Awaiting payment" value={o.awaiting_payment} to={oq("AWAITING_PAYMENT")} accent="text-amber-600" />
        <Stat testid="stat-pending" label="Pending confirmation" value={o.pending} to={oq("AWAITING_CUSTOMER_CONFIRMATION")} />
        <Stat testid="stat-paid" label="Paid orders" value={o.paid} />
        <Stat testid="stat-completed" label="Completed" value={o.completed} to={oq("COMPLETED")} />
        <Stat testid="stat-cancelled" label="Cancelled" value={o.cancelled} to={oq("CANCELLED")} />
        <Stat testid="stat-products-total" label="Total products" value={d.products_total} to="/admin/products" />
        <Stat testid="stat-products-published" label="Published" value={d.products_published} to="/admin/products?status=published" />
        <Stat testid="stat-low-stock" label="Low / no stock" value={d.products_low_stock} to="/admin/products" accent="text-rose-600" />
        <Stat testid="stat-suppliers" label="Suppliers" value={d.suppliers.length} to="/admin/suppliers" />
      </div>
      <div className="mt-6 grid xl:grid-cols-3 gap-6">
        <Card className="xl:col-span-2">
          <p className="font-semibold mb-4">Verified revenue</p>
          {d.revenue_series.length ? <div className="h-64">
            <ResponsiveContainer><AreaChart data={d.revenue_series}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" /><XAxis dataKey="date" fontSize={11} /><YAxis fontSize={11} /><Tooltip /><Area dataKey="revenue" stroke="#2563EB" fill="#2563EB22" /></AreaChart></ResponsiveContainer>
          </div> : <p className="h-64 grid place-items-center text-sm text-muted-foreground" data-testid="revenue-empty">No completed orders in this range yet.</p>}
        </Card>
        <Card data-testid="integration-health">
          <p className="font-semibold mb-3">Integrations & sync health</p>
          <ul className="space-y-2 text-sm">
            <li className="flex justify-between"><span>Telegram bot</span><span className={integ?.telegram.configured ? "text-emerald-600" : "text-amber-600"}>{integ?.telegram.configured ? `@${integ.telegram.bot_username}` : "Not configured"}</span></li>
            <li className="flex justify-between"><span>Webhook</span><span className={integ?.telegram.webhook?.url ? "text-emerald-600" : "text-amber-600"}>{integ?.telegram.webhook?.url ? "Registered" : "Not registered"}</span></li>
            <li className="flex justify-between"><span>Messenger</span><span className="text-slate-500">Click-to-Messenger</span></li>
            {d.suppliers.map((s) => <li key={s.id} className="flex justify-between"><Link to={`/admin/suppliers/${s.id}`} className="text-blue-600">{s.name}</Link><span className={s.health === "ok" ? "text-emerald-600" : s.health === "error" ? "text-rose-600" : "text-slate-500"}>{s.health} · {s.last_sync_at ? fmtDate(s.last_sync_at) : "never synced"}</span></li>)}
          </ul>
        </Card>
      </div>
      <Card className="mt-6">
        <p className="font-semibold mb-3">Recent activity</p>
        <ul className="divide-y text-sm" data-testid="recent-activity">
          {d.recent_activity.map((a) => <li key={a.id} className="py-2 flex flex-wrap justify-between gap-2"><span><b>{a.actor?.name || a.actor?.type}</b> · {a.action}{a.details?.ref ? ` · ${a.details.ref}` : ""}</span><span className="text-xs text-muted-foreground">{fmtDate(a.created_at)}</span></li>)}
        </ul>
      </Card>
    </div>
  );
}
