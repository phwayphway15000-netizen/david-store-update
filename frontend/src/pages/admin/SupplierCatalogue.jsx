import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { mmk, fmtDate } from "@/lib/fmt";
import { PageHeader, Card, Field, inp, btnPrimary, btnGhost, Th, Td } from "@/components/admin/ui";

function Rates() {
  const { data, refetch } = useQuery({ queryKey: ["rates"], queryFn: () => api.get("/admin/supplier-integrations/exchange-rates").then((r) => r.data) });
  const [r, setR] = useState({ USD: "", USDT: "" });
  useEffect(() => { if (data) setR((x) => ({ ...x, ...data })); }, [data]);
  const save = async () => { try { await api.put("/admin/supplier-integrations/exchange-rates", r); toast.success("Rates saved"); refetch(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <Card className="flex flex-wrap items-end gap-3" data-testid="rates-card">
      <p className="font-semibold w-full">Exchange rates → MMK (admin-managed, not live)</p>
      {Object.keys(r).filter((k) => k !== "MMK").map((k) => <Field key={k} label={`1 ${k} =`}><input data-testid={`rate-${k}`} type="number" min="0" className={inp + " w-32"} value={r[k]} onChange={(e) => setR({ ...r, [k]: e.target.value })} /></Field>)}
      <button className={btnGhost} onClick={() => { const c = window.prompt("Currency code"); if (c) setR({ ...r, [c.toUpperCase()]: "" }); }}>Add currency</button>
      <button className={btnPrimary} onClick={save} data-testid="rates-save-btn">Save rates</button>
    </Card>
  );
}

export default function SupplierCatalogue() {
  const [sp, setSp] = useSearchParams();
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [brandF, setBrandF] = useState("");
  const [sel, setSel] = useState([]);
  const [pricing, setPricing] = useState({ strategy: "fixed_markup", value: 3000, rounding: 100 });
  const [preview, setPreview] = useState(null);
  const supplier = sp.get("supplier") || "";
  const { data: sups } = useQuery({ queryKey: ["integrations-presets"], queryFn: () => api.get("/admin/supplier-integrations").then((r) => r.data) });
  const { data, refetch } = useQuery({ queryKey: ["catalogue", supplier, q, cat, brandF], queryFn: () => api.get("/admin/supplier-integrations/catalogue", { params: { supplier, q, category: cat, brand: brandF } }).then((r) => r.data) });
  const { data: cats = [] } = useQuery({ queryKey: ["admin-categories"], queryFn: () => api.get("/admin/categories").then((r) => r.data) });
  const [catId, setCatId] = useState("");
  const names = Object.fromEntries((sups?.suppliers || []).map((s) => [s.id, s.name]));
  const body = () => ({ items: sel.map((id) => ({ supplier_product_id: id, category_id: catId || null })), pricing: { ...pricing, value: Number(pricing.value), rounding: Number(pricing.rounding) } });
  const doPreview = async () => { try { setPreview((await api.post("/admin/supplier-integrations/catalogue/preview", body())).data); } catch (e) { toast.error(errMsg(e)); } };
  const doImport = async () => {
    try { const { data: r } = await api.post("/admin/supplier-integrations/catalogue/import", body()); toast.success(`Imported ${r.created.length} as DRAFT`); r.errors.slice(0, 3).forEach((x) => toast.error(x.error)); setSel([]); setPreview(null); refetch(); } catch (e) { toast.error(errMsg(e)); }
  };
  const items = data?.items || [];
  return (
    <div className="space-y-6">
      <PageHeader title="Supplier Catalogue" sub="Supplier API → catalogue → your review → local product (DRAFT) → publish from Products. Supplier costs are never shown publicly.">
        <Link to="/admin/supplier-integrations" className={btnGhost}>Integrations</Link>
      </PageHeader>
      <Rates />
      <div className="flex flex-wrap gap-2">
        <select data-testid="cat-supplier-filter" value={supplier} onChange={(e) => setSp(e.target.value ? { supplier: e.target.value } : {})} className={inp + " max-w-[200px]"}><option value="">All suppliers</option>{(sups?.suppliers || []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
        <input data-testid="cat-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…" className={inp + " max-w-xs"} />
        <select value={cat} onChange={(e) => setCat(e.target.value)} className={inp + " max-w-[180px]"} data-testid="cat-category-filter"><option value="">All supplier categories</option>{(data?.categories || []).map((c) => <option key={c}>{c}</option>)}</select>
        <select value={brandF} onChange={(e) => setBrandF(e.target.value)} className={inp + " max-w-[160px]"}><option value="">All brands</option>{(data?.brands || []).map((c) => <option key={c}>{c}</option>)}</select>
      </div>
      {sel.length > 0 && (
        <Card className="flex flex-wrap items-end gap-3" data-testid="import-bar">
          <span className="text-sm font-medium w-full">{sel.length} selected — pricing for all plans</span>
          <Field label="Strategy"><select data-testid="pricing-strategy" className={inp} value={pricing.strategy} onChange={(e) => setPricing({ ...pricing, strategy: e.target.value })}><option value="fixed_markup">Rate + fixed MMK markup</option><option value="percent_markup">Rate + % markup</option><option value="rate_multiplier">Custom multiplier (cost × value)</option><option value="manual">Manual MMK price</option></select></Field>
          <Field label="Value"><input data-testid="pricing-value" type="number" className={inp + " w-32"} value={pricing.value} onChange={(e) => setPricing({ ...pricing, value: e.target.value })} /></Field>
          <Field label="Round up to"><select className={inp} value={pricing.rounding} onChange={(e) => setPricing({ ...pricing, rounding: e.target.value })}>{[0, 100, 500, 1000].map((v) => <option key={v} value={v}>{v || "none"}</option>)}</select></Field>
          <Field label="Local category"><select className={inp} value={catId} onChange={(e) => setCatId(e.target.value)}><option value="">—</option>{cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
          <button className={btnGhost} onClick={doPreview} data-testid="price-preview-btn">Preview prices</button>
          <button className={btnPrimary} onClick={doImport} data-testid="catalogue-import-btn">Import as draft</button>
          {preview && <table className="w-full text-xs mt-2" data-testid="price-preview"><tbody>{preview.map((p) => <tr key={p.supplier_product_id + p.variant} className="border-t"><Td>{p.variant}</Td><Td>{p.cost} {p.currency}</Td><Td>rate {p.rate ?? "—"}</Td><Td className="font-semibold">{p.price_mmk != null ? mmk(p.price_mmk) : <span className="text-rose-600">{p.error}</span>}</Td></tr>)}</tbody></table>}
        </Card>
      )}
      <div className="rounded-xl border bg-card overflow-x-auto">
        <table className="w-full min-w-[900px]">
          <thead className="border-b bg-slate-50 dark:bg-slate-900"><tr><Th></Th><Th>Product</Th><Th>Supplier</Th><Th>Plans / cost</Th><Th>Stock</Th><Th>Category</Th><Th>Synced</Th><Th>Status</Th></tr></thead>
          <tbody className="divide-y">
            {items.map((x) => (
              <tr key={x.id} data-testid={`cat-row-${x.external_id}`} className={x.linked_product_id ? "opacity-70" : ""}>
                <Td><input type="checkbox" disabled={!!x.linked_product_id} checked={sel.includes(x.id)} onChange={() => setSel((s) => (s.includes(x.id) ? s.filter((y) => y !== x.id) : [...s, x.id]))} data-testid={`cat-select-${x.external_id}`} /></Td>
                <Td><p className="font-medium">{x.name}</p><p className="text-xs text-muted-foreground line-clamp-1 max-w-xs">{x.description}</p></Td>
                <Td className="text-xs">{names[x.supplier_id]}</Td>
                <Td className="text-xs">{(x.variants || []).map((v) => <p key={v.key}>{v.name}: {v.cost ?? "?"} {x.currency}</p>)}</Td>
                <Td className="text-xs">{x.stock ?? "—"} <span className="text-muted-foreground">({x.stock_status})</span></Td>
                <Td className="text-xs">{x.category || "—"}</Td><Td className="text-xs">{fmtDate(x.last_seen_at)}</Td>
                <Td className="text-xs">{x.linked_product_id ? <Link to={`/admin/products/${x.linked_product_id}`} className="text-blue-600">Imported → edit</Link> : x.needs_review ? <span className="text-amber-700" title={(x.review_reasons || []).join(", ")}>Needs review</span> : "New"}</Td>
              </tr>
            ))}
          </tbody>
        </table>
        {!items.length && <p className="p-8 text-center text-sm text-muted-foreground" data-testid="catalogue-empty">No supplier products yet. Connect a supplier and run Sync Products.</p>}
      </div>
    </div>
  );
}
