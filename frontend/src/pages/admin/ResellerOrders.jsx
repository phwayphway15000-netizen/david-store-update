import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { mmk, fmtDate, statusLabel } from "@/lib/fmt";
import { PageHeader, StatusBadge, Th, Td } from "@/components/admin/ui";

const TABS = [["PENDING_CONFIRMATION", "To confirm"], ["PAYMENT_SUBMITTED", "Payment to check"], ["PAID", "To deliver"], ["AWAITING_PAYMENT,PAYMENT_REJECTED", "Waiting for payment"], ["", "All"]];

export default function ResellerOrders() {
  const nav = useNavigate();
  const [tab, setTab] = useState("PENDING_CONFIRMATION");
  const { data } = useQuery({ queryKey: ["admin-reseller-orders", tab], queryFn: () => api.get("/admin/reseller-orders", { params: { status: tab } }).then((r) => r.data), refetchInterval: 30000 });
  const counts = data?.counts || {};
  const n = (k) => k.split(",").reduce((s, x) => s + (x ? counts[x] || 0 : 0), 0);
  return (
    <div>
      <PageHeader title="Reseller orders" sub="Confirm each order, check the payment screenshot, then deliver." />
      <div className="flex flex-wrap gap-2 mb-4">{TABS.map(([k, label]) => (
        <button key={label} onClick={() => setTab(k)} data-testid={`reseller-tab-${label.toLowerCase().replace(/ /g, "-")}`}
          className={`h-9 px-3 rounded-lg text-sm font-medium border transition-colors ${tab === k ? "bg-blue-600 text-white border-blue-600" : "bg-card hover:bg-slate-50"}`}>
          {label}{k && n(k) > 0 && <span className="ml-1.5 text-[11px] bg-amber-400 text-slate-900 rounded-full px-1.5">{n(k)}</span>}</button>))}</div>
      <div className="rounded-xl border bg-card overflow-x-auto">
        <table className="w-full min-w-[720px]"><thead className="border-b"><tr><Th>Ref</Th><Th>Reseller</Th><Th>Items</Th><Th>Total</Th><Th>Status</Th><Th>Created</Th></tr></thead>
          <tbody className="divide-y">{(data?.items || []).map((o) => (
            <tr key={o.id} onClick={() => nav(`/admin/reseller-orders/${o.id}`)} className="cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-900" data-testid={`admin-reseller-order-${o.ref}`}>
              <Td className="font-mono font-semibold">{o.ref}</Td><Td>{o.business_name || o.reseller_name}</Td>
              <Td>{o.items.reduce((s, i) => s + i.quantity, 0)} ({o.items.length} plans)</Td><Td className="font-semibold">{mmk(o.total_mmk)}</Td><Td><StatusBadge s={o.status} /></Td><Td>{fmtDate(o.created_at)}</Td>
            </tr>))}
            {data && !data.items.length && <tr><Td className="text-muted-foreground" data-testid="admin-reseller-orders-empty">No {tab ? statusLabel(tab.split(",")[0]).toLowerCase() : ""} orders.</Td></tr>}</tbody></table>
      </div>
    </div>
  );
}
