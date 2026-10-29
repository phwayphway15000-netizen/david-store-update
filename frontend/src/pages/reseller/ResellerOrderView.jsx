import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Copy } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { mmk, fmtDate } from "@/lib/fmt";
import { useI18n } from "@/lib/i18n";
import { StatusBadge, Card, Field, inp, btnPrimary, btnGhost } from "@/components/admin/ui";

const HINT = {
  PENDING_CONFIRMATION: ["Waiting for the admin to confirm your order.", "Admin မှ အော်ဒါကို အတည်ပြုရန် စောင့်ဆိုင်းနေပါသည်။"],
  AWAITING_PAYMENT: ["Confirmed. Please pay and upload your payment screenshot.", "အတည်ပြုပြီးပါပြီ။ ငွေလွှဲပြီး Screenshot တင်ပေးပါ။"],
  PAYMENT_SUBMITTED: ["Payment sent. The admin is checking it.", "ငွေလွှဲမှုကို Admin မှ စစ်ဆေးနေပါသည်။"],
  PAYMENT_REJECTED: ["Payment could not be verified. Please upload a new screenshot.", "ငွေလွှဲမှု မအောင်မြင်ပါ။ Screenshot အသစ် တင်ပေးပါ။"],
  PAID: ["Payment verified. Your items are being prepared.", "ငွေလက်ခံရရှိပြီး ပစ္စည်းများ ပြင်ဆင်နေပါသည်။"],
  DELIVERED: ["Delivered. Your details are below.", "ပို့ဆောင်ပြီးပါပြီ။ အသေးစိတ်ကို အောက်တွင် ကြည့်ပါ။"],
  REJECTED: ["The admin declined this order.", "Admin မှ ဤအော်ဒါကို ပယ်ချခဲ့ပါသည်။"],
  CANCELLED: ["This order was cancelled.", "ဤအော်ဒါကို ပယ်ဖျက်ပြီးပါပြီ။"],
};

function PayForm({ o, done }) {
  const { pick } = useI18n();
  const { data: pms = [] } = useQuery({ queryKey: ["reseller-pms"], queryFn: () => api.get("/reseller/payment-methods").then((r) => r.data) });
  const [f, setF] = useState({ reference: "", payment_method_id: "", file: null });
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    if (!f.file) return toast.error(pick("Please choose a screenshot", "Screenshot ရွေးပါ"));
    const fd = new FormData();
    fd.append("file", f.file); fd.append("reference", f.reference); fd.append("payment_method_id", f.payment_method_id);
    setBusy(true);
    try { await api.post(`/reseller/orders/${o.id}/payment`, fd); toast.success(pick("Payment sent for checking", "ငွေလွှဲ အထောက်အထား ပို့ပြီးပါပြီ")); done(); } catch (er) { toast.error(errMsg(er)); } finally { setBusy(false); }
  };
  return (
    <Card data-testid="reseller-pay-card">
      <p className="font-semibold mb-1">{pick("Pay", "ငွေပေးချေရန်")} {mmk(o.total_mmk)}</p>
      <div className="space-y-2 my-3">{pms.map((p) => (
        <div key={p.id} className="rounded-lg border p-3 text-sm" data-testid={`reseller-pm-${p.id}`}><p className="font-semibold">{p.name}</p><p>{p.account_name} · <span className="font-mono">{p.account_number}</span></p>{p.instructions && <p className="text-xs text-muted-foreground mt-1">{p.instructions}</p>}</div>))}
        {!pms.length && <p className="text-xs text-muted-foreground">{pick("Ask the admin for payment details.", "ငွေလွှဲရန် အချက်အလက်ကို Admin ထံ မေးပါ။")}</p>}</div>
      <form onSubmit={submit} className="space-y-3">
        {pms.length > 0 && <Field label={pick("Paid with", "ငွေလွှဲသည့်နည်း")}><select className={inp} value={f.payment_method_id} onChange={(e) => setF({ ...f, payment_method_id: e.target.value })} data-testid="reseller-pay-method"><option value="">—</option>{pms.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field>}
        <Field label={pick("Transaction ID (optional)", "Transaction ID (မဖြည့်လည်းရ)")}><input className={inp} maxLength={200} value={f.reference} onChange={(e) => setF({ ...f, reference: e.target.value })} data-testid="reseller-pay-ref" /></Field>
        <Field label={pick("Payment screenshot", "ငွေလွှဲ Screenshot")}><input type="file" accept="image/png,image/jpeg,image/webp" required onChange={(e) => setF({ ...f, file: e.target.files[0] || null })} className="text-sm" data-testid="reseller-pay-file" /></Field>
        <button disabled={busy} className={btnPrimary + " w-full"} data-testid="reseller-pay-submit">{busy ? "…" : pick("Send payment proof", "အထောက်အထား ပို့မည်")}</button>
      </form>
    </Card>
  );
}

function ItemList({ o }) {
  const { pick } = useI18n();
  const copy = (t) => { navigator.clipboard.writeText(t); toast.success(pick("Copied", "ကူးယူပြီး")); };
  return (
    <Card className="p-0 divide-y">{o.items.map((it) => (
      <div key={it.id} className="p-4" data-testid={`reseller-item-${it.id}`}>
        <div className="flex gap-3"><p className="flex-1 text-sm font-medium">{it.product_name} — {it.variant_name} <span className="text-muted-foreground">× {it.quantity}</span></p><p className="text-sm font-semibold">{mmk(it.line_total_mmk)}</p></div>
        {it.delivery && <div className="mt-2 rounded-lg bg-emerald-50 dark:bg-emerald-950 border border-emerald-200 p-3 text-sm"><div className="flex justify-between mb-1"><span className="text-xs font-semibold text-emerald-700">{pick("Delivery details", "ပို့ဆောင်ချက်")}</span><button onClick={() => copy(it.delivery)} className="text-xs inline-flex gap-1 items-center" data-testid={`reseller-copy-${it.id}`}><Copy className="h-3 w-3" />{pick("Copy", "ကူးယူ")}</button></div><pre className="whitespace-pre-wrap break-words font-mono text-xs" data-testid={`reseller-delivery-${it.id}`}>{it.delivery}</pre></div>}
      </div>))}
      <div className="p-4 flex justify-between font-bold"><span>{pick("Total", "စုစုပေါင်း")}</span><span data-testid="reseller-order-total">{mmk(o.total_mmk)}</span></div>
    </Card>
  );
}

export default function ResellerOrderView() {
  const { id } = useParams();
  const { pick } = useI18n();
  const qc = useQueryClient();
  const { data: o, refetch } = useQuery({ queryKey: ["reseller-order", id], queryFn: () => api.get(`/reseller/orders/${id}`).then((r) => r.data) });
  if (!o) return <p className="text-sm text-muted-foreground">Loading…</p>;
  const refresh = () => { refetch(); qc.invalidateQueries({ queryKey: ["reseller-orders"] }); };
  const cancel = async () => { try { await api.post(`/reseller/orders/${o.id}/cancel`); refresh(); } catch (e) { toast.error(errMsg(e)); } };
  const last = [...(o.events || [])].reverse().find((e) => e.note && e.actor?.type !== "reseller");
  return (
    <div>
      <div className="flex flex-wrap items-center gap-3 mb-2"><h1 className="text-2xl sm:text-3xl font-extrabold font-mono" data-testid="reseller-order-ref">{o.ref}</h1><StatusBadge s={o.status} /></div>
      <p className="text-sm text-muted-foreground leading-relaxed" data-testid="reseller-order-hint">{pick(...(HINT[o.status] || ["", ""]))}</p>
      {last && ["PAYMENT_REJECTED", "REJECTED", "CANCELLED"].includes(o.status) && <p className="mt-2 text-sm text-rose-700" data-testid="reseller-order-reason">{pick("Reason", "အကြောင်းရင်း")}: {last.note}</p>}
      <p className="text-xs text-muted-foreground mt-1">{fmtDate(o.created_at)}</p>
      <div className="grid lg:grid-cols-[1fr_360px] gap-6 mt-6">
        <ItemList o={o} />
        <div className="space-y-4">
          {["AWAITING_PAYMENT", "PAYMENT_REJECTED"].includes(o.status) && <PayForm o={o} done={refresh} />}
          {["PENDING_CONFIRMATION", "AWAITING_PAYMENT"].includes(o.status) && <button onClick={cancel} className={btnGhost + " w-full text-rose-600"} data-testid="reseller-cancel-btn">{pick("Cancel order", "အော်ဒါ ပယ်ဖျက်မည်")}</button>}
        </div>
      </div>
    </div>
  );
}
