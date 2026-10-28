import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Trash2, Plus, ImagePlus } from "lucide-react";
import { api, errMsg, imgUrl } from "@/lib/api";
import { mmk, fmtDate } from "@/lib/fmt";
import { PageHeader, Field, Card, inp, btnPrimary, btnGhost } from "@/components/admin/ui";

const blankVariant = () => ({ name: "1 Month", duration: "1 month", price_mmk: 0, promo_price_mmk: null, promo_start: null, promo_end: null, stock_status: "in_stock", stock_qty: null, stock_override: null, price_locked: true, active: true });
const blank = { name: "", name_my: "", brand_id: "", category_id: "", short_description: "", short_description_my: "", description: "", description_my: "", product_type: "subscription", activation_method: "", eligibility: "", warranty: "", delivery_time: "", images: [], featured: false, hot: false, status: "draft", variants: [blankVariant()] };
const toLocal = (s) => (s ? s.slice(0, 16) : "");
const fromLocal = (s) => (s ? new Date(s).toISOString() : null);

function VariantRow({ v, i, set, remove }) {
  const u = (k, val) => set(i, { ...v, [k]: val });
  const num = (x) => (x === "" || x == null ? null : Number(x));
  return (
    <div className="rounded-xl border p-4 grid gap-3 md:grid-cols-4" data-testid={`variant-row-${i}`}>
      <Field label="Plan name"><input data-testid={`variant-name-${i}`} className={inp} value={v.name} onChange={(e) => u("name", e.target.value)} /></Field>
      <Field label="Duration"><input data-testid={`variant-duration-${i}`} className={inp} value={v.duration || ""} onChange={(e) => u("duration", e.target.value)} /></Field>
      <Field label="Selling price (MMK)"><input data-testid={`variant-price-${i}`} type="number" min="0" className={inp} value={v.price_mmk} onChange={(e) => u("price_mmk", Number(e.target.value))} /></Field>
      <Field label="Promo price (MMK)"><input data-testid={`variant-promo-${i}`} type="number" min="0" className={inp} value={v.promo_price_mmk ?? ""} onChange={(e) => u("promo_price_mmk", num(e.target.value))} /></Field>
      <Field label="Promo start"><input type="datetime-local" className={inp} value={toLocal(v.promo_start)} onChange={(e) => u("promo_start", fromLocal(e.target.value))} /></Field>
      <Field label="Promo end"><input type="datetime-local" className={inp} value={toLocal(v.promo_end)} onChange={(e) => u("promo_end", fromLocal(e.target.value))} /></Field>
      <Field label="Manual stock">
        <select data-testid={`variant-stock-${i}`} className={inp} value={v.stock_status} onChange={(e) => u("stock_status", e.target.value)}><option value="in_stock">In stock</option><option value="limited">Limited (qty)</option><option value="out_of_stock">Out of stock</option></select>
      </Field>
      <Field label="Qty (limited)"><input type="number" min="0" className={inp} value={v.stock_qty ?? ""} onChange={(e) => u("stock_qty", num(e.target.value))} /></Field>
      <Field label="Admin stock override" hint="Wins over supplier & manual stock">
        <select data-testid={`variant-override-${i}`} className={inp} value={v.stock_override || ""} onChange={(e) => u("stock_override", e.target.value || null)}><option value="">No override</option><option value="in_stock">Force in stock</option><option value="out_of_stock">Force out of stock</option></select>
      </Field>
      <div className="md:col-span-2 text-xs text-muted-foreground self-end space-y-0.5">
        {v.supplier_product_id ? <>
          <p>Supplier ref: <span className="font-mono">{v.supplier_product_id}</span></p>
          <p>Supplier cost: <b>{v.supplier_cost == null ? "—" : v.supplier_currency && v.supplier_currency !== "MMK" ? `${v.supplier_cost} ${v.supplier_currency}` : mmk(v.supplier_cost)}</b> · Supplier stock: <b>{v.supplier_stock ?? "—"}</b></p>
          <p>Last synced: {fmtDate(v.last_synced_at)} (snapshot, not real-time)</p>
        </> : <p>Manual plan (no supplier mapping)</p>}
      </div>
      <div className="flex items-end gap-4 text-sm">
        <label className="flex items-center gap-1.5"><input type="checkbox" data-testid={`variant-locked-${i}`} checked={v.price_locked} onChange={(e) => u("price_locked", e.target.checked)} />Price locked</label>
        <label className="flex items-center gap-1.5"><input type="checkbox" checked={v.active} onChange={(e) => u("active", e.target.checked)} />Active</label>
        <button type="button" onClick={() => remove(i)} className="ml-auto text-rose-600" data-testid={`variant-remove-${i}`} aria-label="Remove plan"><Trash2 className="h-4 w-4" /></button>
      </div>
    </div>
  );
}

export default function ProductEditor() {
  const { id } = useParams();
  const isNew = id === "new";
  const nav = useNavigate();
  const [f, setF] = useState(blank);
  const [busy, setBusy] = useState(false);
  const { data: brands = [] } = useQuery({ queryKey: ["admin-brands"], queryFn: () => api.get("/admin/brands").then((r) => r.data) });
  const { data: cats = [] } = useQuery({ queryKey: ["admin-categories"], queryFn: () => api.get("/admin/categories").then((r) => r.data) });
  const { data: existing } = useQuery({ queryKey: ["admin-product", id], enabled: !isNew, queryFn: () => api.get(`/admin/products/${id}`).then((r) => r.data) });
  useEffect(() => {
    if (existing) setF(existing);
  }, [existing]);
  const u = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const setV = (i, v) => setF((x) => ({ ...x, variants: x.variants.map((y, j) => (j === i ? v : y)) }));
  const upload = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    const fd = new FormData(); fd.append("file", file);
    try { const { data } = await api.post("/admin/uploads/image", fd); u("images", [...f.images, data.url]); toast.success("Image uploaded"); } catch (er) { toast.error(errMsg(er)); }
    e.target.value = "";
  };
  const save = async () => {
    setBusy(true);
    const body = { ...f, brand_id: f.brand_id || null, category_id: f.category_id || null };
    try {
      const { data } = isNew ? await api.post("/admin/products", body) : await api.put(`/admin/products/${id}`, body);
      toast.success("Product saved");
      if (isNew) nav(`/admin/products/${data.id}`, { replace: true }); else setF(data);
    } catch (er) { toast.error(errMsg(er)); } finally { setBusy(false); }
  };
  const txt = (k, label, area) => (
    <Field label={label}>{area ? <textarea data-testid={`product-${k}-input`} rows={4} className={inp + " h-auto py-2"} value={f[k] || ""} onChange={(e) => u(k, e.target.value)} />
      : <input data-testid={`product-${k}-input`} className={inp} value={f[k] || ""} onChange={(e) => u(k, e.target.value)} />}</Field>
  );
  return (
    <div>
      <PageHeader title={isNew ? "New product" : f.name} sub={!isNew && `Source: ${f.source_type} · slug: ${f.slug}`}>
        {!isNew && f.status === "published" && <a href={`/products/${f.slug}`} target="_blank" rel="noreferrer" className={btnGhost}>View in store</a>}
        <button onClick={save} disabled={busy} className={btnPrimary} data-testid="save-product-btn">{busy ? "Saving…" : "Save product"}</button>
      </PageHeader>
      <div className="grid xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 space-y-6">
          <Card className="grid md:grid-cols-2 gap-4">
            {txt("name", "Name (English)")}{txt("name_my", "Name (Burmese)")}
            {txt("short_description", "Short description (EN)")}{txt("short_description_my", "Short description (MM)")}
            <div className="md:col-span-2">{txt("description", "Full description (EN)", true)}</div>
            <div className="md:col-span-2">{txt("description_my", "Full description (MM)", true)}</div>
            {txt("product_type", "Product type")}{txt("activation_method", "Account activation method")}
            {txt("eligibility", "Eligibility requirements")}{txt("warranty", "Warranty details")}
            {txt("delivery_time", "Delivery expectations")}
          </Card>
          <Card>
            <div className="flex justify-between items-center mb-3"><p className="font-semibold">Plans / variants</p>
              <button type="button" className={btnGhost} onClick={() => u("variants", [...f.variants, blankVariant()])} data-testid="add-variant-btn"><Plus className="h-4 w-4" />Add plan</button></div>
            <div className="space-y-3">{f.variants.map((v, i) => <VariantRow key={v.id || i} v={v} i={i} set={setV} remove={(j) => u("variants", f.variants.filter((_, k) => k !== j))} />)}</div>
          </Card>
        </div>
        <div className="space-y-6">
          <Card className="space-y-4">
            <Field label="Status"><select data-testid="product-status-select" className={inp} value={f.status} onChange={(e) => u("status", e.target.value)}>{["draft", "published", "unpublished", "archived"].map((s) => <option key={s}>{s}</option>)}</select></Field>
            <Field label="Brand"><select data-testid="product-brand-select" className={inp} value={f.brand_id || ""} onChange={(e) => u("brand_id", e.target.value)}><option value="">—</option>{brands.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select></Field>
            <Field label="Category"><select data-testid="product-category-select" className={inp} value={f.category_id || ""} onChange={(e) => u("category_id", e.target.value)}><option value="">—</option>{cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" data-testid="product-featured-toggle" checked={f.featured} onChange={(e) => u("featured", e.target.checked)} />Featured</label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" data-testid="product-hot-toggle" checked={f.hot} onChange={(e) => u("hot", e.target.checked)} />Hot</label>
          </Card>
          <Card>
            <p className="font-semibold mb-3">Images</p>
            <div className="grid grid-cols-3 gap-2">
              {f.images.map((src, i) => (
                <div key={src} className="relative group aspect-square rounded-lg overflow-hidden border bg-slate-100">
                  <img src={imgUrl(src)} alt="" className="h-full w-full object-contain" />
                  <button onClick={() => u("images", f.images.filter((_, j) => j !== i))} className="absolute top-1 right-1 bg-white/90 rounded p-1 opacity-0 group-hover:opacity-100" aria-label="Remove image"><Trash2 className="h-3 w-3 text-rose-600" /></button>
                </div>
              ))}
              <label className="aspect-square rounded-lg border-2 border-dashed grid place-items-center cursor-pointer hover:border-blue-500" data-testid="upload-image-label">
                <ImagePlus className="h-5 w-5 text-muted-foreground" /><input type="file" accept="image/*" className="hidden" onChange={upload} data-testid="upload-image-input" />
              </label>
            </div>
          </Card>
          {existing?.price_history?.length > 0 && (
            <Card><p className="font-semibold mb-2">Price history</p>
              <ul className="text-xs space-y-1">{existing.price_history.map((h) => <li key={h.id}>{fmtDate(h.created_at)} · {h.source}: {mmk(h.old)} → {mmk(h.new)}</li>)}</ul></Card>
          )}
        </div>
      </div>
    </div>
  );
}
