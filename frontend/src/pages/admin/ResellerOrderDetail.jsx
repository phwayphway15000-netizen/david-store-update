import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Eye } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { mmk, fmtDate, statusLabel } from "@/lib/fmt";
import { PageHeader, StatusBadge, Card, inp, btnPrimary, btnGhost, btnDanger } from "@/components/admin/ui";

function Evidence({ oid, ev }) {
  const [src, setSrc] = useState(null);
  useEffect(() => () => { if (src) URL.revokeObjectURL(src); }, [src]);
  const show = async () => {
    try { const r = await api.get(`/admin/reseller-orders/${oid}/evidence/${ev.id}`, { responseType: "blob" }); setSrc(URL.createObjectURL(r.data)); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="rounded-lg border p-3 text-sm" data-testid={`admin-evidence-${ev.id}`}>
      <p><b>{ev.payment_method || "Payment"}</b> · {ev.reference || "no transaction ID"} · <span className="capitalize">{ev.review_status}</span></p>
      <p className="text-xs text-muted-foreground">{fmtDate(ev.created_at)}</p>
      {src ? <a href={src} target="_blank" rel="noreferrer"><img src={src} alt="payment screenshot" className="mt-2 max-h-96 rounded-lg border object-contain" /></a>
        : <button onClick={show} className="mt-1 text-xs text-blue-600 inline-flex items-center gap-1" data-testid={`admin-view-evidence-${ev.id}`}><Eye className="h-3 w-3" />View screenshot</button>}
    </div>
  );
}

function Actions({ o, act }) {
  const [note, setNote] = useState("");
  const run = (a, needNote) => {
    if (needNote && !note.trim()) return toast.error("Please write a reason in the note box");
    act(a, note).then(() => setNote(""));
  };
  const s = o.status;
  if (!["PENDING_CONFIRMATION", "PAYMENT_SUBMITTED", "AWAITING_PAYMENT", "PAYMENT_REJECTED"].includes(s)) return null;
  return (
    <Card data-testid="admin-reseller-actions">
      <p className="font-semibold mb-2">{s === "PENDING_CONFIRMATION" ? "Confirm this order?" : s === "PAYMENT_SUBMITTED" ? "Check the payment" : "Waiting for the reseller's payment"}</p>
      <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note / reason (shown to the reseller)" className={inp + " h-20 py-2"} data-testid="admin-reseller-note" />
      <div className="flex flex-wrap gap-2 mt-3">
        {s === "PENDING_CONFIRMATION" && <><button className={btnPrimary} onClick={() => run("confirm")} data-testid="admin-confirm-order-btn">Confirm order</button><button className={btnDanger} onClick={() => run("reject", true)} data-testid="admin-reject-order-btn">Reject order</button></>}
        {s === "PAYMENT_SUBMITTED" && <><button className={btnPrimary} onClick={() => run("approve_payment")} data-testid="admin-approve-payment-btn">Payment received</button><button className={btnDanger} onClick={() => run("reject_payment", true)} data-testid="admin-reject-payment-btn">Reject payment</button></>}
        <button className={btnGhost} onClick={() => run("cancel", true)} data-testid="admin-cancel-reseller-order-btn">Cancel order</button>
      </div>
    </Card>
  );
}

function Deliver({ o, done }) {
  const [vals, setVals] = useState({});
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try { await api.post(`/admin/reseller-orders/${o.id}/deliver`, { items: o.items.map((i) => ({ item_id: i.id, content: vals[i.id] || "" })) }); toast.success("Delivered to the reseller portal"); done(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <Card data-testid="admin-reseller-deliver">
      <p className="font-semibold mb-1">Deliver items</p>
      <p className="text-xs text-muted-foreground mb-3">Paste account details, codes or links for each plan. The reseller sees them in their portal.</p>
      <div className="space-y-3">{o.items.map((i) => (
        <label key={i.id} className="block text-sm"><span className="font-medium">{i.product_name} — {i.variant_name} × {i.quantity}</span>
          <textarea className={inp + " h-24 py-2 mt-1 font-mono"} value={vals[i.id] || ""} onChange={(e) => setVals({ ...vals, [i.id]: e.target.value })} data-testid={`admin-deliver-input-${i.id}`} /></label>))}</div>
      <button disabled={busy} onClick={submit} className={btnPrimary + " mt-3 w-full"} data-testid="admin-deliver-submit">{busy ? "…" : "Deliver"}</button>
    </Card>
  );
}

export default function ResellerOrderDetail() {
  const { id } = useParams();
  const { can } = useAuth();
  const { data: o, refetch } = useQuery({ queryKey: ["admin-reseller-order", id], queryFn: () => api.get(`/admin/reseller-orders/${id}`).then((r) => r.data) });
  if (!o) return <p className="text-sm text-muted-foreground">Loading…</p>;
  const act = (action, note) => api.post(`/admin/reseller-orders/${o.id}/action`, { action, note }).then(() => { toast.success("Updated"); refetch(); }).catch((e) => toast.error(errMsg(e)));
  return (
    <div>
      <PageHeader title={<span className="font-mono" data-testid="admin-reseller-order-ref">{o.ref}</span>} sub={`${o.reseller?.business_name || o.reseller?.name || o.reseller_name} · ${o.reseller?.email || ""} · ${o.reseller?.phone || ""}`}><StatusBadge s={o.status} /></PageHeader>
      <div className="grid xl:grid-cols-[1fr_380px] gap-6">
        <div className="space-y-4">
          <Card className="p-0 divide-y">{o.items.map((i) => (
            <div key={i.id} className="p-4 text-sm"><div className="flex gap-3"><p className="flex-1">{i.product_name} — {i.variant_name} <span className="text-muted-foreground">× {i.quantity} @ {mmk(i.unit_price_mmk)}</span></p><b>{mmk(i.line_total_mmk)}</b></div>
              {i.delivery && <pre className="mt-2 whitespace-pre-wrap break-words font-mono text-xs bg-slate-50 dark:bg-slate-900 rounded p-2">{i.delivery}</pre>}</div>))}
            <div className="p-4 flex justify-between font-bold"><span>Total</span><span data-testid="admin-reseller-order-total">{mmk(o.total_mmk)}</span></div></Card>
          {o.note && <Card><p className="text-xs font-semibold text-muted-foreground">Reseller note</p><p className="text-sm mt-1 whitespace-pre-wrap">{o.note}</p></Card>}
          {o.evidence.length > 0 && <Card><p className="font-semibold mb-2">Payment proof</p><div className="space-y-2">{o.evidence.map((ev) => <Evidence key={ev.id} oid={o.id} ev={ev} />)}</div></Card>}
          <Card><p className="font-semibold mb-2">History</p><ol className="space-y-2 text-sm">{o.events.map((e) => (
            <li key={e.id}><b>{statusLabel(e.to)}</b> · {e.actor?.name} · <span className="text-muted-foreground">{fmtDate(e.at)}</span>{e.note && <p className="text-xs text-muted-foreground">{e.note}</p>}</li>))}</ol></Card>
        </div>
        <div className="space-y-4">
          {can("orders.approve") ? <Actions o={o} act={act} /> : <p className="text-sm text-amber-700">You can't confirm orders or check payments.</p>}
          {o.status === "PAID" && can("orders.deliver") && <Deliver o={o} done={refetch} />}
        </div>
      </div>
    </div>
  );
}
