import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { ShieldAlert, Eye } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { mmk, fmtDate, statusLabel } from "@/lib/fmt";
import { PageHeader, StatusBadge, Card, Field, inp, btnPrimary, btnGhost, btnDanger } from "@/components/admin/ui";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";

function EvidenceImg({ ev }) {
  const [src, setSrc] = useState(null);
  const show = async () => {
    try { const r = await api.get(`/admin/evidence/${ev.id}/file`, { responseType: "blob" }); setSrc(URL.createObjectURL(r.data)); } catch (e) { toast.error(errMsg(e)); }
  };
  useEffect(() => () => { if (src) URL.revokeObjectURL(src); }, [src]);
  return src ? <img src={src} alt="payment evidence" className="mt-2 max-h-80 rounded-lg border" /> : <button onClick={show} className="mt-1 text-xs text-blue-600 inline-flex items-center gap-1" data-testid={`view-evidence-${ev.id}`}><Eye className="h-3 w-3" />View screenshot</button>;
}

function Confirm({ c, setC, run }) {
  return (
    <AlertDialog open={!!c} onOpenChange={(o) => !o && setC(null)}>
      <AlertDialogContent data-testid="confirm-dialog">
        <AlertDialogHeader><AlertDialogTitle>{c?.title}</AlertDialogTitle><AlertDialogDescription>{c?.desc}</AlertDialogDescription></AlertDialogHeader>
        {c?.needNote && <textarea data-testid="confirm-note-input" className={inp + " h-20 py-2"} placeholder="Reason / note" onChange={(e) => (c.note = e.target.value)} />}
        <AlertDialogFooter><AlertDialogCancel data-testid="confirm-cancel-btn">Cancel</AlertDialogCancel><AlertDialogAction data-testid="confirm-ok-btn" onClick={() => run(c.to, c.note)}>{c?.ok || "Confirm"}</AlertDialogAction></AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export default function OrderDetail() {
  const { id } = useParams();
  const { can } = useAuth();
  const { data: o, refetch } = useQuery({ queryKey: ["order", id], queryFn: () => api.get(`/admin/orders/${id}`).then((r) => r.data) });
  const { data: team = [] } = useQuery({ queryKey: ["team"], enabled: can("users.view"), queryFn: () => api.get("/admin/users").then((r) => r.data) });
  const [c, setC] = useState(null);
  const [del, setDel] = useState({ artifact_type: "instructions", content: "" });
  const [ev, setEv] = useState({ reference: "", file: null });
  const [revealed, setRevealed] = useState({});
  if (!o) return <p className="text-sm">Loading…</p>;
  const it = o.items[0];
  const run = async (to, note) => {
    try { await api.post(`/admin/orders/${o.id}/transition`, { to, note: note || "" }); toast.success(`Order → ${statusLabel(to)}`); refetch(); } catch (e) { toast.error(errMsg(e)); }
  };
  const deliver = async () => {
    try { const { data } = await api.post(`/admin/orders/${o.id}/deliver`, del); toast.success(`Delivery: ${data.result}`); setDel({ ...del, content: "" }); refetch(); } catch (e) { toast.error(errMsg(e)); }
  };
  const addEvidence = async () => {
    const fd = new FormData(); fd.append("reference", ev.reference); if (ev.file) fd.append("file", ev.file);
    try { await api.post(`/admin/orders/${o.id}/evidence`, fd); toast.success("Evidence added"); setEv({ reference: "", file: null }); refetch(); } catch (e) { toast.error(errMsg(e)); }
  };
  const reveal = async (aid) => {
    try { const { data } = await api.get(`/admin/orders/${o.id}/artifacts/${aid}`); setRevealed((r) => ({ ...r, [aid]: data.content })); } catch (e) { toast.error(errMsg(e)); }
  };
  const assign = async (uid) => { await api.post(`/admin/orders/${o.id}/assign`, { user_id: uid || null }); refetch(); toast.success("Assigned"); };
  const s = o.status;
  const review = ["PAYMENT_SUBMITTED", "PAYMENT_UNDER_REVIEW"].includes(s);
  const canDeliver = ["PAID_AWAITING_FULFILLMENT", "FULFILLMENT_IN_PROGRESS"].includes(s);
  const A = (label, to, cls, extra = {}) => o.allowed_transitions.includes(to) && (
    <button key={to + label} className={cls || btnGhost} data-testid={extra.testid || `action-${to.toLowerCase()}`} onClick={() => setC({ to, title: `${label}?`, desc: `${o.ref}: ${statusLabel(s)} → ${statusLabel(to)}`, ok: label, ...extra })}>{label}</button>
  );
  return (
    <div className="space-y-6">
      <PageHeader title={<span className="font-mono" data-testid="order-ref">{o.ref}</span>} sub={`${o.source} · created ${fmtDate(o.created_at)}`}>
        <StatusBadge s={s} />
      </PageHeader>
      <div className="grid xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 space-y-6">
          <Card className="grid sm:grid-cols-4 gap-4">
            <div className="sm:col-span-2"><p className="text-xs text-muted-foreground">Product</p><p className="font-semibold">{it.brand_name} {it.product_name}</p><p className="text-sm">{it.variant_name} {it.duration && `· ${it.duration}`}</p></div>
            <div><p className="text-xs text-muted-foreground">Price snapshot</p><p className="font-display text-xl font-bold" data-testid="order-total">{mmk(o.total_mmk)}</p><p className="text-[11px] text-muted-foreground">locked {fmtDate(o.price_snapshot?.locked_at)}</p></div>
            <div><p className="text-xs text-muted-foreground">Payment / delivery</p><p className="text-sm font-medium" data-testid="order-payment-status">{o.payment_status}</p><p className="text-sm" data-testid="order-delivery-status">{o.delivery_status}</p></div>
            <div className="sm:col-span-2"><p className="text-xs text-muted-foreground">Customer</p><p className="text-sm">{o.customer_name || "—"} {o.customer_contact && `· ${o.customer_contact}`}</p><p className="text-xs text-muted-foreground">Channel: {o.channel}{o.channel_id ? ` (${o.channel_id})` : ""}{o.messenger_ref ? ` · Messenger ref ${o.messenger_ref}` : ""}</p></div>
            <div className="sm:col-span-2"><p className="text-xs text-muted-foreground">Payment method</p><p className="text-sm">{o.payment_method?.name || "—"}</p></div>
          </Card>

          <Card>
            <p className="font-semibold mb-3">Actions</p>
            <div className="flex flex-wrap gap-2" data-testid="order-actions">
              {["CHECKOUT_STARTED", "AWAITING_CUSTOMER_CONFIRMATION"].includes(s) && A("Customer confirmed", "AWAITING_PAYMENT", btnPrimary)}
              {review && can("orders.approve") && A("Approve payment", "PAID_AWAITING_FULFILLMENT", btnPrimary, { desc: `Only approve after you have checked your ${o.payment_method?.name || "payment"} account and confirmed ${mmk(o.total_mmk)} actually arrived. Screenshots are evidence, not proof.` })}
              {review && can("orders.approve") && A("Reject payment", "PAYMENT_REJECTED", btnDanger, { needNote: true })}
              {review && A("Request more evidence", "AWAITING_PAYMENT", btnGhost, { needNote: true, testid: "action-request-evidence" })}
              {review && !can("orders.approve") && <p className="text-xs text-amber-700 flex items-center gap-1" data-testid="no-approve-permission"><ShieldAlert className="h-4 w-4" />You can't approve payments. Ask an owner/admin.</p>}
              {can("orders.deliver") && A("Mark delivery pending", "FULFILLMENT_IN_PROGRESS")}
              {can("orders.deliver") && A("Confirm manual delivery", "DELIVERED", btnGhost, { needNote: true, desc: "Use this when you handed the product over outside Telegram (e.g. Messenger)." })}
              {can("orders.deliver") && A("Complete order", "COMPLETED", btnPrimary, { desc: "Delivery artifacts will be purged from storage." })}
              {A("Cancel order", "CANCELLED", btnDanger, { needNote: true })}
              {can("orders.approve") && A("Start refund", "REFUND_PENDING", btnGhost, { needNote: true })}
              {can("orders.approve") && A("Mark refunded", "REFUNDED", btnGhost, { needNote: true })}
            </div>
          </Card>

          {canDeliver && can("orders.deliver") && (
            <Card className="space-y-3" data-testid="delivery-form">
              <p className="font-semibold">Deliver product</p>
              <p className="text-xs text-muted-foreground">{o.channel === "telegram" ? "Sent securely to the customer's verified Telegram chat. Stored encrypted; purged on completion." : "Stored encrypted. Hand it over via Messenger yourself, then press “Confirm manual delivery”."}</p>
              <select data-testid="delivery-type-select" className={inp + " max-w-xs"} value={del.artifact_type} onChange={(e) => setDel({ ...del, artifact_type: e.target.value })}>{["license", "activation_link", "instructions", "credentials", "other"].map((x) => <option key={x}>{x}</option>)}</select>
              <textarea data-testid="delivery-content-input" className={inp + " h-28 py-2"} value={del.content} onChange={(e) => setDel({ ...del, content: e.target.value })} placeholder="License key, activation link or instructions" />
              <button className={btnPrimary} disabled={!del.content} onClick={deliver} data-testid="delivery-submit-btn">Send delivery</button>
            </Card>
          )}

          <Card>
            <p className="font-semibold mb-3">Payment evidence</p>
            <ul className="space-y-3" data-testid="evidence-list">
              {o.evidence.map((e) => <li key={e.id} className="text-sm border rounded-lg p-3"><p><b>{e.kind}</b> · via {e.submitted_via} · <span className="text-muted-foreground">{e.review_status}</span> · {fmtDate(e.created_at)}</p>{e.reference && <p className="font-mono text-xs mt-1">{e.reference}</p>}{e.storage_path && <EvidenceImg ev={e} />}</li>)}
              {!o.evidence.length && <li className="text-sm text-muted-foreground">No evidence submitted.</li>}
            </ul>
            {["AWAITING_PAYMENT", "PAYMENT_REJECTED", "PAYMENT_SUBMITTED", "PAYMENT_UNDER_REVIEW"].includes(s) && (
              <div className="mt-4 flex flex-wrap gap-2 items-end">
                <Field label="Transaction reference (from Messenger)"><input data-testid="evidence-ref-input" className={inp} value={ev.reference} onChange={(e) => setEv({ ...ev, reference: e.target.value })} /></Field>
                <input type="file" accept="image/*" onChange={(e) => setEv({ ...ev, file: e.target.files[0] })} className="text-xs" data-testid="evidence-file-input" />
                <button className={btnGhost} onClick={addEvidence} data-testid="evidence-submit-btn">Add evidence</button>
              </div>
            )}
          </Card>

          {o.artifacts.length > 0 && (
            <Card><p className="font-semibold mb-3">Delivery artifacts</p>
              <ul className="space-y-2 text-sm">{o.artifacts.map((a) => <li key={a.id} className="border rounded-lg p-3"><p>{a.type} · {fmtDate(a.created_at)} {a.purged_at && "· purged"}</p>
                {a.has_content && (revealed[a.id] ? <pre className="mt-2 text-xs bg-slate-50 dark:bg-slate-900 p-2 rounded whitespace-pre-wrap" data-testid="artifact-content">{revealed[a.id]}</pre> : <button className="text-xs text-blue-600" onClick={() => reveal(a.id)} data-testid={`reveal-artifact-${a.id}`}>Reveal (audited)</button>)}</li>)}
                {o.deliveries.map((d) => <li key={d.id} className="text-xs text-muted-foreground">Delivery {d.channel}: <b>{d.status}</b></li>)}</ul></Card>
          )}
        </div>

        <div className="space-y-6">
          {can("users.view") && (
            <Card><Field label="Customer service assignee">
              <select data-testid="order-assignee-select" className={inp} value={o.assignee_id || ""} onChange={(e) => assign(e.target.value)}><option value="">Unassigned</option>{team.map((u) => <option key={u.id} value={u.id}>{u.name} ({u.role})</option>)}</select>
            </Field>{o.notes && <p className="mt-3 text-sm text-muted-foreground">Note: {o.notes}</p>}</Card>
          )}
          <Card>
            <p className="font-semibold mb-3">Audit trail</p>
            <ol className="relative border-l ml-2 space-y-4" data-testid="order-timeline">
              {o.events.map((e) => (
                <li key={e.id} className="ml-4">
                  <span className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full bg-blue-600" />
                  <p className="text-sm font-medium">{e.action.replace(/_/g, " ")}</p>
                  <p className="text-xs text-muted-foreground">{statusLabel(e.from_status)} → {statusLabel(e.to_status)}</p>
                  <p className="text-xs text-muted-foreground">{e.actor?.name || e.actor?.type} · {fmtDate(e.created_at)}</p>
                  {e.note && <p className="text-xs mt-1">“{e.note}”</p>}
                </li>
              ))}
            </ol>
          </Card>
        </div>
      </div>
      <Confirm c={c} setC={setC} run={run} />
    </div>
  );
}
