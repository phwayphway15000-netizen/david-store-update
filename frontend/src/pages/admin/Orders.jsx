import { useState } from "react";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { mmk, fmtDate, SOURCES } from "@/lib/fmt";
import { PageHeader, StatusBadge, Field, inp, btnPrimary, Th, Td } from "@/components/admin/ui";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const TABS = [["", "All"], ["AWAITING_CUSTOMER_CONFIRMATION", "To confirm"], ["AWAITING_PAYMENT", "Awaiting payment"], ["PAYMENT_SUBMITTED,PAYMENT_UNDER_REVIEW", "Payment review"],
  ["PAID_AWAITING_FULFILLMENT,FULFILLMENT_IN_PROGRESS", "Delivery pending"], ["DELIVERED,COMPLETED", "Delivered"], ["CANCELLED,PAYMENT_REJECTED,REFUND_PENDING,REFUNDED", "Other"]];

function NewOrder({ open, setOpen }) {
  const nav = useNavigate();
  const { data } = useQuery({ queryKey: ["order-products"], enabled: open, queryFn: () => api.get("/products", { params: { limit: 48, in_stock: true } }).then((r) => r.data.items) });
  const [f, setF] = useState({ source: "DIRECT_MESSENGER", product_id: "", variant_id: "", customer_name: "", customer_contact: "", messenger_ref: "", note: "" });
  const p = (data || []).find((x) => x.id === f.product_id);
  const u = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const submit = async (e) => {
    e.preventDefault();
    try { const { data: o } = await api.post("/admin/orders", f); toast.success(`Order ${o.ref} created`); nav(`/admin/orders/${o.id}`); } catch (er) { toast.error(errMsg(er)); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>New order (customer service)</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="space-y-3" data-testid="new-order-form">
          <Field label="Source"><select data-testid="new-order-source" className={inp} value={f.source} onChange={(e) => u("source", e.target.value)}><option value="DIRECT_MESSENGER">Direct Messenger</option><option value="ADMIN_MANUAL">Admin manual</option></select></Field>
          <Field label="Product"><select data-testid="new-order-product" required className={inp} value={f.product_id} onChange={(e) => setF({ ...f, product_id: e.target.value, variant_id: "" })}><option value="">Choose…</option>{(data || []).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>
          {p && <Field label="Plan"><select data-testid="new-order-variant" required className={inp} value={f.variant_id} onChange={(e) => u("variant_id", e.target.value)}><option value="">Choose…</option>{p.variants.filter((v) => v.available).map((v) => <option key={v.id} value={v.id}>{v.name} — {mmk(v.effective_price_mmk)}</option>)}</select></Field>}
          <Field label="Customer name"><input data-testid="new-order-name" required className={inp} value={f.customer_name} onChange={(e) => u("customer_name", e.target.value)} /></Field>
          <Field label="Customer contact (Messenger name / phone)"><input data-testid="new-order-contact" className={inp} value={f.customer_contact} onChange={(e) => u("customer_contact", e.target.value)} /></Field>
          <Field label="Messenger conversation ref"><input className={inp} value={f.messenger_ref} onChange={(e) => u("messenger_ref", e.target.value)} /></Field>
          <Field label="Note"><textarea className={inp + " h-20 py-2"} value={f.note} onChange={(e) => u("note", e.target.value)} /></Field>
          <button className={btnPrimary + " w-full"} data-testid="new-order-submit">Create order</button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function Orders() {
  const [sp, setSp] = useSearchParams();
  const [q, setQ] = useState("");
  const [source, setSource] = useState("");
  const [mine, setMine] = useState(false);
  const [open, setOpen] = useState(false);
  const status = sp.get("status") || "";
  const { data = [], isLoading } = useQuery({ queryKey: ["orders", status, q, source, mine], queryFn: () => api.get("/admin/orders", { params: { status, q, source, assignee: mine ? "me" : "" } }).then((r) => r.data), refetchInterval: 20000 });
  return (
    <div>
      <PageHeader title="Unified order inbox" sub="Telegram, Messenger and manual orders in one place. Search by order reference to match Messenger conversations.">
        <button className={btnPrimary} onClick={() => setOpen(true)} data-testid="new-order-btn"><Plus className="h-4 w-4" />New order</button>
      </PageHeader>
      <div className="flex gap-1 overflow-x-auto no-scrollbar mb-4 border-b">
        {TABS.map(([v, l]) => <button key={l} data-testid={`orders-tab-${l.toLowerCase().replace(/\s/g, "-")}`} onClick={() => setSp(v ? { status: v } : {})} className={`px-3 h-10 text-sm whitespace-nowrap border-b-2 -mb-px ${status === v ? "border-blue-600 text-blue-600 font-semibold" : "border-transparent text-muted-foreground"}`}>{l}</button>)}
      </div>
      <div className="flex flex-wrap gap-2 mb-4">
        <input data-testid="orders-search-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Order ref, customer, product…" className={inp + " max-w-xs"} />
        <select data-testid="orders-source-filter" value={source} onChange={(e) => setSource(e.target.value)} className={inp + " max-w-[220px]"}><option value="">All sources</option>{SOURCES.map((s) => <option key={s}>{s}</option>)}</select>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} data-testid="orders-mine-toggle" />Assigned to me</label>
      </div>
      <div className="rounded-xl border bg-card overflow-x-auto">
        <table className="w-full min-w-[860px]">
          <thead className="border-b bg-slate-50 dark:bg-slate-900"><tr><Th>Order</Th><Th>Product</Th><Th>Customer</Th><Th>Source</Th><Th>Total</Th><Th>Status</Th><Th>Created</Th></tr></thead>
          <tbody className="divide-y">
            {isLoading && <tr><Td>Loading…</Td></tr>}
            {data.map((o) => (
              <tr key={o.id} className="hover:bg-slate-50 dark:hover:bg-slate-900" data-testid={`order-row-${o.ref}`}>
                <Td><Link to={`/admin/orders/${o.id}`} className="font-mono font-semibold text-blue-600">{o.ref}</Link></Td>
                <Td>{o.items[0].product_name}<p className="text-xs text-muted-foreground">{o.items[0].variant_name}</p></Td>
                <Td>{o.customer_name || "—"}<p className="text-xs text-muted-foreground">{o.customer_contact || o.channel}</p></Td>
                <Td className="text-[11px] font-mono">{o.source}</Td><Td className="font-semibold">{mmk(o.total_mmk)}</Td>
                <Td><StatusBadge s={o.status} /></Td><Td className="text-xs">{fmtDate(o.created_at)}</Td>
              </tr>
            ))}
          </tbody>
        </table>
        {!isLoading && !data.length && <p className="p-8 text-center text-sm text-muted-foreground" data-testid="orders-empty">No orders here.</p>}
      </div>
      <NewOrder open={open} setOpen={setOpen} />
    </div>
  );
}
