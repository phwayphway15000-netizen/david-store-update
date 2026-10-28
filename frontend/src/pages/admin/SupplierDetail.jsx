import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { fmtDate, mmk } from "@/lib/fmt";
import { PageHeader, Card, Field, inp, btnPrimary, btnGhost, Th, Td } from "@/components/admin/ui";

const MAPS = [["products_endpoint", "Products endpoint", "/products"], ["items_path", "Items path in JSON", "data.items"], ["map_id", "Product ID field", "id"], ["map_name", "Name field", "name"],
  ["map_price", "Cost/price field", "price"], ["map_stock", "Stock field", "stock"], ["map_description", "Description field", ""], ["map_image", "Image URL field", ""], ["map_brand", "Brand field", ""]];

function ConfigForm({ s, onSaved }) {
  const [f, setF] = useState(s);
  const [cred, setCred] = useState("");
  const [headers, setHeaders] = useState("");
  useEffect(() => { setF(s); }, [s]);
  const u = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const save = async () => {
    const body = { ...f, credential: cred || null, markup_percent: f.markup_percent === "" || f.markup_percent == null ? null : Number(f.markup_percent), sync_interval_minutes: Number(f.sync_interval_minutes || 0) };
    if (f.auth_type === "custom_headers" && headers) {
      try { body.custom_headers = JSON.parse(headers); } catch { return toast.error("Custom headers must be valid JSON"); }
    }
    try { await api.put(`/admin/suppliers/${s.id}`, body); setCred(""); setHeaders(""); toast.success("Saved"); onSaved(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Card className="space-y-4" data-testid="supplier-config-form">
      <p className="font-semibold">1 · Connection & authentication</p>
      <div className="grid md:grid-cols-2 gap-3">
        <Field label="Name"><input className={inp} value={f.name} onChange={(e) => u("name", e.target.value)} /></Field>
        <Field label="Base URL (https only)"><input data-testid="cfg-base-url" className={inp} value={f.base_url} onChange={(e) => u("base_url", e.target.value)} /></Field>
        <Field label="API documentation URL"><input className={inp} value={f.docs_url || ""} onChange={(e) => u("docs_url", e.target.value)} /></Field>
        <Field label="OpenAPI spec URL (JSON)"><input data-testid="cfg-openapi-url" className={inp} value={f.openapi_url || ""} onChange={(e) => u("openapi_url", e.target.value)} /></Field>
        <Field label="Authentication">
          <select data-testid="cfg-auth-type" className={inp} value={f.auth_type} onChange={(e) => u("auth_type", e.target.value)}>
            <option value="none">None</option><option value="api_key_header">API key header</option><option value="bearer">Bearer token</option><option value="custom_headers">Approved custom headers</option>
          </select>
        </Field>
        {f.auth_type === "api_key_header" && <Field label="Header name"><input data-testid="cfg-auth-header" className={inp} value={f.auth_header_name || ""} onChange={(e) => u("auth_header_name", e.target.value)} /></Field>}
        {["api_key_header", "bearer"].includes(f.auth_type) && <Field label="API key / token" hint={s.credential_masked ? `Saved: ${s.credential_masked} — leave empty to keep` : "Not saved yet"}><input data-testid="cfg-credential" type="password" autoComplete="new-password" className={inp} value={cred} onChange={(e) => setCred(e.target.value)} /></Field>}
        {f.auth_type === "custom_headers" && <Field label='Headers JSON e.g. {"X-Client":"abc"}' hint={s.custom_header_names?.length ? `Saved: ${s.custom_header_names.join(", ")}` : ""}><input type="password" className={inp} value={headers} onChange={(e) => setHeaders(e.target.value)} /></Field>}
      </div>
      <p className="font-semibold pt-2">2 · Endpoint & field mapping</p>
      <div className="grid md:grid-cols-3 gap-3">
        {MAPS.map(([k, l, ph]) => <Field key={k} label={l}><input data-testid={`cfg-${k}`} className={inp} placeholder={ph} value={f[k] || ""} onChange={(e) => u(k, e.target.value)} /></Field>)}
      </div>
      <p className="font-semibold pt-2">3 · Sync & pricing</p>
      <div className="grid md:grid-cols-3 gap-3">
        <Field label="Sync every N minutes (0 = manual)"><input data-testid="cfg-interval" type="number" min="0" className={inp} value={f.sync_interval_minutes || 0} onChange={(e) => u("sync_interval_minutes", e.target.value)} /></Field>
        <Field label="Auto markup % (only unlocked prices)"><input type="number" min="0" className={inp} value={f.markup_percent ?? ""} onChange={(e) => u("markup_percent", e.target.value)} /></Field>
        <label className="flex items-center gap-2 text-sm mt-6"><input type="checkbox" checked={f.active} onChange={(e) => u("active", e.target.checked)} />Active</label>
      </div>
      <button onClick={save} className={btnPrimary} data-testid="cfg-save-btn">Save configuration</button>
    </Card>
  );
}

function ImportTable({ sid, items, brands, cats, onDone }) {
  const [rows, setRows] = useState({});
  const set = (id, k, v) => setRows((r) => ({ ...r, [id]: { ...(r[id] || {}), [k]: v } }));
  const selected = Object.entries(rows).filter(([, r]) => r.sel);
  const run = async () => {
    const payload = selected.map(([id, r]) => { const sp = items.find((x) => x.id === id); return { supplier_product_id: id, name: r.name || sp.name, price_mmk: Number(r.price ?? Math.round(sp.cost || 0)), description: r.description || sp.description || "", brand_id: r.brand || null, category_id: r.cat || null, plan_name: r.plan || "Standard", duration: r.duration || "", publish: !!r.publish }; });
    try { const { data } = await api.post(`/admin/suppliers/${sid}/import`, { items: payload }); toast.success(`Imported ${data.created.length} products`); setRows({}); onDone(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Card>
      <div className="flex justify-between items-center mb-3"><p className="font-semibold">5 · Review supplier products & import</p>
        <button disabled={!selected.length} onClick={run} className={btnPrimary} data-testid="import-selected-btn">Import {selected.length || ""} selected</button></div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1000px] text-sm">
          <thead className="border-b"><tr><Th></Th><Th>Supplier item</Th><Th>Cost</Th><Th>Stock</Th><Th>Your name</Th><Th>Selling price (MMK)</Th><Th>Brand</Th><Th>Category</Th><Th>Plan</Th><Th>Publish</Th></tr></thead>
          <tbody className="divide-y">
            {items.map((x) => { const r = rows[x.id] || {}; const done = !!x.linked_product_id; return (
              <tr key={x.id} data-testid={`supplier-product-${x.external_id}`} className={done ? "opacity-60" : ""}>
                <Td><input type="checkbox" disabled={done} checked={!!r.sel} onChange={(e) => set(x.id, "sel", e.target.checked)} data-testid={`sp-select-${x.external_id}`} /></Td>
                <Td><p className="font-medium">{x.name}</p><p className="text-xs font-mono text-muted-foreground">{x.external_id} · {x.review_status}</p>{done && <Link className="text-xs text-blue-600" to={`/admin/products/${x.linked_product_id}`}>Linked product →</Link>}</Td>
                <Td>{x.cost != null ? mmk(x.cost) : "—"}</Td><Td>{x.stock ?? "—"}</Td>
                <Td><input className={inp} disabled={done} defaultValue={x.name} onChange={(e) => set(x.id, "name", e.target.value)} /></Td>
                <Td><input data-testid={`sp-price-${x.external_id}`} type="number" className={inp} disabled={done} placeholder={String(Math.round(x.cost || 0))} onChange={(e) => set(x.id, "price", e.target.value)} /></Td>
                <Td><select className={inp} disabled={done} onChange={(e) => set(x.id, "brand", e.target.value)}><option value="">—</option>{brands.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select></Td>
                <Td><select className={inp} disabled={done} onChange={(e) => set(x.id, "cat", e.target.value)}><option value="">—</option>{cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Td>
                <Td><input className={inp} disabled={done} placeholder="Standard" onChange={(e) => set(x.id, "plan", e.target.value)} /></Td>
                <Td><input type="checkbox" disabled={done} onChange={(e) => set(x.id, "publish", e.target.checked)} data-testid={`sp-publish-${x.external_id}`} /></Td>
              </tr>); })}
          </tbody>
        </table>
        {!items.length && <p className="p-6 text-center text-sm text-muted-foreground">No supplier products yet — run a sync.</p>}
      </div>
    </Card>
  );
}

export default function SupplierDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { data: s, refetch } = useQuery({ queryKey: ["supplier", id], queryFn: () => api.get(`/admin/suppliers/${id}`).then((r) => r.data) });
  const { data: items = [], refetch: rp } = useQuery({ queryKey: ["sp", id], queryFn: () => api.get(`/admin/suppliers/${id}/products`).then((r) => r.data) });
  const { data: runs = [], refetch: rr } = useQuery({ queryKey: ["runs", id], queryFn: () => api.get(`/admin/suppliers/${id}/runs`).then((r) => r.data) });
  const { data: brands = [] } = useQuery({ queryKey: ["admin-brands"], queryFn: () => api.get("/admin/brands").then((r) => r.data) });
  const { data: cats = [] } = useQuery({ queryKey: ["admin-categories"], queryFn: () => api.get("/admin/categories").then((r) => r.data) });
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState("");
  const act = async (k, url) => {
    setBusy(k);
    try { const { data } = await api.post(url); setResult({ k, data }); refetch(); rp(); rr(); qc.invalidateQueries({ queryKey: ["admin-products"] }); } catch (e) { setResult({ k, data: { error: errMsg(e) } }); } finally { setBusy(""); }
  };
  if (!s) return <p className="text-sm">Loading…</p>;
  return (
    <div className="space-y-6">
      <PageHeader title={s.name} sub={`Health: ${s.health} · last sync ${fmtDate(s.last_sync_at)}${s.last_error ? ` · ${s.last_error}` : ""}`}>
        <button className={btnGhost} disabled={!!busy} onClick={() => act("validate", `/admin/suppliers/${id}/validate`)} data-testid="supplier-validate-btn">Validate config</button>
        <button className={btnGhost} disabled={!!busy} onClick={() => act("test", `/admin/suppliers/${id}/test`)} data-testid="supplier-test-btn">{busy === "test" ? "Testing…" : "Test connection"}</button>
        {s.openapi_url && <button className={btnGhost} disabled={!!busy} onClick={() => act("openapi", `/admin/suppliers/${id}/openapi`)} data-testid="supplier-openapi-btn">Read OpenAPI</button>}
        <button className={btnPrimary} disabled={!!busy} onClick={() => act("sync", `/admin/suppliers/${id}/sync`)} data-testid="supplier-sync-btn">{busy === "sync" ? "Syncing…" : "Sync now"}</button>
      </PageHeader>
      {result && (
        <Card data-testid="supplier-action-result" className={result.data.error || result.data.ok === false || result.data.valid === false || result.data.status === "failed" ? "border-rose-300 bg-rose-50/50 dark:bg-rose-950/20" : "border-emerald-300 bg-emerald-50/50 dark:bg-emerald-950/20"}>
          <p className="font-semibold capitalize mb-2">{result.k} result</p>
          <pre className="text-xs whitespace-pre-wrap break-all">{JSON.stringify(result.data, null, 2)}</pre>
        </Card>
      )}
      <ConfigForm s={s} onSaved={refetch} />
      <ImportTable sid={id} items={items} brands={brands} cats={cats} onDone={() => { rp(); }} />
      <Card>
        <p className="font-semibold mb-3">Sync history</p>
        <table className="w-full text-sm"><thead className="border-b"><tr><Th>Started</Th><Th>Trigger</Th><Th>Status</Th><Th>New</Th><Th>Updated</Th><Th>Duplicates</Th><Th>Price changes</Th><Th>Attempts</Th><Th>Error</Th></tr></thead>
          <tbody className="divide-y" data-testid="sync-history">{runs.map((r) => <tr key={r.id}><Td>{fmtDate(r.started_at)}</Td><Td>{r.trigger}</Td><Td className={r.status === "success" ? "text-emerald-600" : "text-rose-600"}>{r.status}</Td><Td>{r.new_count}</Td><Td>{r.updated_count}</Td><Td>{r.duplicate_count}</Td><Td>{r.price_changes}</Td><Td>{r.attempts}</Td><Td className="text-xs">{r.error}</Td></tr>)}</tbody></table>
      </Card>
    </div>
  );
}
