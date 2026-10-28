import { useState, useRef } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, Upload } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { mmk } from "@/lib/fmt";
import { PageHeader, inp, btnPrimary, btnGhost, Th, Td } from "@/components/admin/ui";

const STATUS_CLS = { published: "bg-emerald-50 text-emerald-700", draft: "bg-slate-100 text-slate-600", unpublished: "bg-amber-50 text-amber-700", archived: "bg-stone-100 text-stone-500" };

export default function Products() {
  const [sp, setSp] = useSearchParams();
  const [q, setQ] = useState("");
  const [sel, setSel] = useState([]);
  const [action, setAction] = useState("publish");
  const [value, setValue] = useState("");
  const fileRef = useRef();
  const qc = useQueryClient();
  const status = sp.get("status") || "";
  const { data: items = [], isLoading } = useQuery({ queryKey: ["admin-products", q, status], queryFn: () => api.get("/admin/products", { params: { q, status } }).then((r) => r.data) });
  const { data: cats = [] } = useQuery({ queryKey: ["admin-categories"], queryFn: () => api.get("/admin/categories").then((r) => r.data) });
  const refresh = () => qc.invalidateQueries({ queryKey: ["admin-products"] });
  const runBulk = async () => {
    try {
      const { data } = await api.post("/admin/products/bulk", { ids: sel, action, value: value || null });
      toast.success(`Updated ${data.updated} products`); setSel([]); refresh();
    } catch (e) { toast.error(errMsg(e)); }
  };
  const importFile = async (e) => {
    const f = e.target.files[0]; if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    try {
      const { data } = await api.post("/admin/products/import", fd);
      toast.success(`Imported ${data.created} products as drafts${data.errors.length ? `, ${data.errors.length} rows failed` : ""}`);
      data.errors.slice(0, 3).forEach((er) => toast.error(`Row ${er.row}: ${er.error}`)); refresh();
    } catch (er) { toast.error(errMsg(er)); }
    e.target.value = "";
  };
  const toggle = (id) => setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  return (
    <div>
      <PageHeader title="Products" sub="CSV/XLSX columns: name, brand, category, plan, duration, price_mmk, description, stock_status">
        <input ref={fileRef} type="file" accept=".csv,.xlsx" className="hidden" onChange={importFile} data-testid="import-file-input" />
        <button className={btnGhost} onClick={() => fileRef.current.click()} data-testid="import-products-btn"><Upload className="h-4 w-4" />Import CSV/XLSX</button>
        <Link to="/admin/products/new" className={btnPrimary} data-testid="new-product-btn"><Plus className="h-4 w-4" />New product</Link>
      </PageHeader>
      <div className="flex flex-wrap gap-2 mb-4">
        <input data-testid="products-search-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…" className={inp + " max-w-xs"} />
        <select data-testid="products-status-filter" value={status} onChange={(e) => setSp(e.target.value ? { status: e.target.value } : {})} className={inp + " max-w-[160px]"}>
          {["", "published", "draft", "unpublished", "archived"].map((s) => <option key={s} value={s}>{s || "All statuses"}</option>)}
        </select>
      </div>
      {sel.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border bg-blue-50 dark:bg-blue-950/40 p-3" data-testid="bulk-bar">
          <span className="text-sm font-medium">{sel.length} selected</span>
          <select data-testid="bulk-action-select" value={action} onChange={(e) => { setAction(e.target.value); setValue(""); }} className={inp + " max-w-[200px]"}>
            {["publish", "unpublish", "archive", "feature", "unfeature", "hot", "unhot", "set_category", "price_adjust_percent"].map((a) => <option key={a}>{a}</option>)}
          </select>
          {action === "set_category" && <select data-testid="bulk-value-category" value={value} onChange={(e) => setValue(e.target.value)} className={inp + " max-w-[200px]"}><option value="">Choose…</option>{cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>}
          {action === "price_adjust_percent" && <input data-testid="bulk-value-percent" value={value} onChange={(e) => setValue(e.target.value)} placeholder="e.g. 10 or -5" className={inp + " max-w-[140px]"} />}
          <button className={btnPrimary} onClick={runBulk} data-testid="bulk-apply-btn">Apply</button>
        </div>
      )}
      <div className="rounded-xl border bg-card overflow-x-auto">
        <table className="w-full min-w-[820px]">
          <thead className="border-b bg-slate-50 dark:bg-slate-900"><tr><Th><input type="checkbox" data-testid="select-all-products" checked={sel.length === items.length && items.length > 0} onChange={(e) => setSel(e.target.checked ? items.map((p) => p.id) : [])} /></Th><Th>Product</Th><Th>Brand</Th><Th>Source</Th><Th>From</Th><Th>Stock</Th><Th>Status</Th><Th>Flags</Th></tr></thead>
          <tbody className="divide-y">
            {isLoading && <tr><Td>Loading…</Td></tr>}
            {items.map((p) => (
              <tr key={p.id} className="hover:bg-slate-50 dark:hover:bg-slate-900" data-testid={`product-row-${p.id}`}>
                <Td><input type="checkbox" checked={sel.includes(p.id)} onChange={() => toggle(p.id)} data-testid={`select-product-${p.id}`} /></Td>
                <Td><Link to={`/admin/products/${p.id}`} className="font-medium text-blue-600 hover:underline">{p.name}</Link><p className="text-xs text-muted-foreground">{p.category_name} · {p.variants.length} plan(s)</p></Td>
                <Td>{p.brand_name || "—"}</Td>
                <Td><span className="text-[11px] font-mono">{p.source_type}</span></Td>
                <Td>{mmk(p.min_price)}</Td>
                <Td>{p.available ? (p.low_stock ? <span className="text-amber-600">Low</span> : <span className="text-emerald-600">Available</span>) : <span className="text-rose-600">Out</span>}</Td>
                <Td><span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${STATUS_CLS[p.status]}`}>{p.status}</span></Td>
                <Td className="text-xs">{[p.featured && "featured", p.hot && "hot", p.on_promo && "promo", p.is_sample && "sample"].filter(Boolean).join(", ")}</Td>
              </tr>
            ))}
          </tbody>
        </table>
        {!isLoading && !items.length && <p className="p-8 text-center text-sm text-muted-foreground">No products.</p>}
      </div>
    </div>
  );
}
