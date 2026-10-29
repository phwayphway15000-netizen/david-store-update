import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Minus, Plus, Trash2, Search } from "lucide-react";
import { api, errMsg, imgUrl } from "@/lib/api";
import { mmk } from "@/lib/fmt";
import { useReseller } from "@/lib/reseller";
import { useI18n } from "@/lib/i18n";
import { inp, btnPrimary, Card } from "@/components/admin/ui";

function PlanRow({ p, v, add }) {
  const { pick } = useI18n();
  return (
    <div className="flex items-center gap-3 py-2 border-t first:border-t-0" data-testid={`reseller-plan-${v.id}`}>
      <div className="flex-1 min-w-0"><p className="text-sm font-medium">{v.name}{v.duration ? ` · ${v.duration}` : ""}</p>
        <p className="text-xs text-muted-foreground">{pick("Retail", "လက်လီ")} <s>{mmk(v.retail_price_mmk)}</s></p></div>
      <p className="font-bold text-sm whitespace-nowrap">{mmk(v.reseller_price_mmk)}</p>
      <button disabled={!v.available} onClick={() => add(p, v)} data-testid={`reseller-add-${v.id}`} className="h-8 px-3 rounded-lg bg-slate-900 text-white text-xs font-semibold disabled:opacity-40 hover:bg-blue-600 transition-colors">
        {v.available ? pick("Add", "ထည့်မည်") : pick("Out of stock", "ပစ္စည်းပြတ်")}</button>
    </div>
  );
}

function Cart() {
  const { cart, saveCart } = useReseller();
  const { pick } = useI18n();
  const nav = useNavigate();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const total = cart.reduce((s, c) => s + c.price * c.quantity, 0);
  const setQty = (k, q) => saveCart(cart.map((c) => (c.variant_id === k ? { ...c, quantity: Math.max(1, Math.min(100, q)) } : c)));
  const place = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/reseller/orders", { items: cart.map(({ product_id, variant_id, quantity }) => ({ product_id, variant_id, quantity })), note });
      saveCart([]); toast.success(pick("Order sent to admin for confirmation", "အော်ဒါကို Admin ထံ ပို့ပြီးပါပြီ")); nav(`/reseller/orders/${data.id}`);
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <Card className="lg:sticky lg:top-24" data-testid="reseller-cart">
      <p className="font-semibold mb-3">{pick("Cart", "ခြင်းတောင်း")}</p>
      {!cart.length && <p className="text-sm text-muted-foreground" data-testid="reseller-cart-empty">{pick("Add plans to start an order.", "Plan များ ထည့်ပြီး မှာယူပါ။")}</p>}
      <div className="space-y-3">{cart.map((c) => (
        <div key={c.variant_id} className="text-sm" data-testid={`cart-line-${c.variant_id}`}>
          <p className="font-medium leading-snug">{c.product_name} — {c.variant_name}</p>
          <div className="mt-1 flex items-center gap-2">
            <button onClick={() => setQty(c.variant_id, c.quantity - 1)} className="h-7 w-7 grid place-items-center rounded border" data-testid={`cart-dec-${c.variant_id}`} aria-label="Decrease"><Minus className="h-3 w-3" /></button>
            <input type="number" min="1" max="100" value={c.quantity} onChange={(e) => setQty(c.variant_id, Number(e.target.value) || 1)} className="h-7 w-14 rounded border text-center" data-testid={`cart-qty-${c.variant_id}`} />
            <button onClick={() => setQty(c.variant_id, c.quantity + 1)} className="h-7 w-7 grid place-items-center rounded border" data-testid={`cart-inc-${c.variant_id}`} aria-label="Increase"><Plus className="h-3 w-3" /></button>
            <span className="ml-auto font-semibold">{mmk(c.price * c.quantity)}</span>
            <button onClick={() => saveCart(cart.filter((x) => x.variant_id !== c.variant_id))} className="text-rose-600" data-testid={`cart-remove-${c.variant_id}`} aria-label="Remove"><Trash2 className="h-4 w-4" /></button>
          </div>
        </div>))}</div>
      {cart.length > 0 && <>
        <textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} placeholder={pick("Note for admin (optional)", "Admin အတွက် မှတ်ချက် (မဖြည့်လည်းရ)")} className={inp + " h-20 py-2 mt-4"} data-testid="reseller-order-note" />
        <div className="flex justify-between items-center mt-4"><span className="text-sm">{pick("Total", "စုစုပေါင်း")}</span><span className="text-xl font-extrabold" data-testid="reseller-cart-total">{mmk(total)}</span></div>
        <button onClick={place} disabled={busy} className={btnPrimary + " w-full mt-3"} data-testid="reseller-place-order-btn">{busy ? "…" : pick("Send order to admin", "အော်ဒါ တင်မည်")}</button>
        <p className="text-[11px] text-muted-foreground mt-2 leading-relaxed">{pick("Pay after the admin confirms your order.", "Admin အတည်ပြုပြီးမှ ငွေပေးချေပါ။")}</p>
      </>}
    </Card>
  );
}

export default function ResellerShop() {
  const { cart, saveCart } = useReseller();
  const { pick } = useI18n();
  const [q, setQ] = useState("");
  const { data = [], isLoading } = useQuery({ queryKey: ["reseller-catalog"], queryFn: () => api.get("/reseller/catalog").then((r) => r.data) });
  const list = useMemo(() => data.filter((p) => `${p.name} ${p.brand || ""}`.toLowerCase().includes(q.toLowerCase())), [data, q]);
  const add = (p, v) => {
    const ex = cart.find((c) => c.variant_id === v.id);
    saveCart(ex ? cart.map((c) => (c.variant_id === v.id ? { ...c, quantity: Math.min(100, c.quantity + 1) } : c))
      : [...cart, { product_id: p.id, variant_id: v.id, product_name: p.name, variant_name: v.name, price: v.reseller_price_mmk, quantity: 1 }]);
    toast.success(pick("Added to cart", "ခြင်းတောင်းထဲ ထည့်ပြီး"));
  };
  return (
    <div>
      <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight">{pick("Reseller prices", "Reseller စျေးနှုန်းများ")}</h1>
      <div className="grid lg:grid-cols-[1fr_340px] gap-6 mt-6">
        <div>
          <div className="relative mb-4"><Search className="h-4 w-4 absolute left-3 top-3 text-muted-foreground" /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder={pick("Search products…", "ပစ္စည်း ရှာရန်…")} className={inp + " pl-9"} data-testid="reseller-search" /></div>
          {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {!isLoading && !list.length && <p className="text-sm text-muted-foreground" data-testid="reseller-catalog-empty">{pick("No reseller products yet.", "Reseller ပစ္စည်း မရှိသေးပါ။")}</p>}
          <div className="grid sm:grid-cols-2 gap-4">{list.map((p) => (
            <Card key={p.id} className="p-4" data-testid={`reseller-product-${p.id}`}>
              <div className="flex gap-3 mb-2">
                {p.image && <img src={imgUrl(p.image)} alt="" className="h-14 w-14 rounded-lg object-contain bg-slate-100" />}
                <div><p className="text-xs text-blue-600 font-semibold">{p.brand}</p><p className="font-semibold leading-snug">{p.name}</p></div>
              </div>
              {p.variants.map((v) => <PlanRow key={v.id} p={p} v={v} add={add} />)}
            </Card>))}</div>
        </div>
        <Cart />
      </div>
    </div>
  );
}
