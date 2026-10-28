import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { PlugZap, ExternalLink, RefreshCw, KeyRound } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { fmtDate } from "@/lib/fmt";
import { PageHeader, Card, inp, btnPrimary, btnGhost, btnDanger } from "@/components/admin/ui";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const STATUS_CLS = { CONNECTED: "bg-emerald-50 text-emerald-700 border-emerald-300", NOT_CONNECTED: "bg-slate-100 text-slate-600 border-slate-300",
  SYNCING: "bg-blue-50 text-blue-700 border-blue-300 animate-pulse", SYNC_FAILED: "bg-rose-50 text-rose-700 border-rose-300", AUTH_FAILED: "bg-rose-50 text-rose-700 border-rose-300",
  CONFIGURATION_ERROR: "bg-orange-50 text-orange-700 border-orange-300", NEEDS_REVIEW: "bg-amber-50 text-amber-700 border-amber-300", DISABLED: "bg-stone-100 text-stone-500 border-stone-300" };

const Metric = ({ label, value, testid }) => <Card data-testid={testid} className="!p-4"><p className="text-xs text-muted-foreground">{label}</p><p className="text-2xl font-bold font-display">{value}</p></Card>;

function ConnectDialog({ s, onClose, onDone }) {
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const go = async (e) => {
    e.preventDefault(); setBusy(true);
    try { const { data } = await api.post(`/admin/supplier-integrations/${s.id}/connect`, { api_key: key }); setRes(data); setKey(""); onDone(); } catch (er) { toast.error(errMsg(er)); } finally { setBusy(false); }
  };
  return (
    <Dialog open={!!s} onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="connect-dialog">
        <DialogHeader><DialogTitle>Connect {s?.name}</DialogTitle></DialogHeader>
        <form onSubmit={go} className="space-y-3">
          <p className="text-sm">Supplier: <b>{s?.name}</b> <span className="text-xs text-muted-foreground">(key sent as {s?.auth_location === "query" ? "query parameter" : "header"}, preset)</span></p>
          {s?.review_note && <p className="text-xs text-amber-700">{s.review_note}</p>}
          <input data-testid="connect-api-key-input" type="password" autoComplete="new-password" required minLength={4} value={key} onChange={(e) => setKey(e.target.value)} placeholder={s?.has_key ? `Replace saved key ${s.key_masked}` : "API key"} className={inp} />
          <div className="flex gap-2"><button className={btnPrimary} disabled={busy} data-testid="connect-test-btn">{busy ? "Testing…" : "Connect & Test"}</button><button type="button" className={btnGhost} onClick={onClose}>Cancel</button></div>
        </form>
        {res && (
          <div data-testid="connect-result" className={`rounded-lg border p-3 text-sm ${res.ok ? "border-emerald-300 bg-emerald-50/60" : "border-rose-300 bg-rose-50/60"}`}>
            <p className="font-bold">{res.connection_status}</p>
            {res.ok ? <><p>API authentication: Verified</p><p>Products returned: <b>{res.products_returned}</b></p><p>Product mapping: {res.mapping}</p></> : <p>{res.message}</p>}
            <p className="text-xs text-muted-foreground">Last checked: {fmtDate(res.at)}</p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function SupplierCard({ s, onConnect, refetch }) {
  const [busy, setBusy] = useState("");
  const act = async (k, method, url, body) => {
    setBusy(k);
    try { const { data } = await api[method](url, body); if (k === "sync") toast[data.status === "success" ? "success" : "error"](data.status === "success" ? `Synced: ${data.new_count} new, ${data.updated_count} updated` : data.error); else toast.success("Done"); refetch(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };
  const base = `/admin/supplier-integrations/${s.id}`;
  return (
    <Card className="flex flex-col gap-3" data-testid={`integration-card-${s.preset_key}`}>
      <div className="flex items-start gap-3">
        <span className="h-10 w-10 rounded-lg bg-blue-50 text-blue-600 grid place-items-center shrink-0"><PlugZap className="h-5 w-5" /></span>
        <div className="min-w-0 flex-1"><p className="font-semibold truncate">{s.name}</p>{s.docs_url && <a href={s.docs_url} target="_blank" rel="noreferrer" className="text-xs text-blue-600 inline-flex items-center gap-1">API docs <ExternalLink className="h-3 w-3" /></a>}</div>
        <span data-testid={`integration-status-${s.preset_key}`} className={`text-[10px] font-bold border px-2 py-0.5 rounded-full ${STATUS_CLS[s.connection_status]}`}>{s.connection_status}</span>
      </div>
      <div className="text-xs text-muted-foreground space-y-0.5">
        <p>Key: {s.has_key ? s.key_masked : "not set"} · Products: <b>{s.product_count}</b></p>
        <p>Last successful sync: {s.last_success_at ? fmtDate(s.last_success_at) : "never"}</p>
        {s.last_test?.message && !s.last_test.ok && <p className="text-rose-600">{s.last_test.message}</p>}
        {s.review_note && <p className="text-amber-700">{s.review_note}</p>}
      </div>
      <div className="flex flex-wrap gap-2 mt-auto">
        <button className={btnPrimary + " !h-8 !px-3 text-xs"} onClick={() => onConnect(s)} data-testid={`connect-btn-${s.preset_key}`}><KeyRound className="h-3.5 w-3.5" />{s.has_key ? "Replace key" : "Connect"}</button>
        {s.has_key && <>
          <button className={btnGhost + " !h-8 !px-3 text-xs"} disabled={!!busy} onClick={() => act("sync", "post", `${base}/sync`)} data-testid={`sync-btn-${s.preset_key}`}><RefreshCw className={`h-3.5 w-3.5 ${busy === "sync" ? "animate-spin" : ""}`} />Sync Products</button>
          <Link to={`/admin/supplier-catalogue?supplier=${s.id}`} className={btnGhost + " !h-8 !px-3 text-xs"} data-testid={`catalogue-link-${s.preset_key}`}>Catalogue</Link>
          <button className={btnDanger + " !h-8 !px-3 text-xs"} disabled={!!busy} onClick={() => window.confirm(`Revoke ${s.name} key?`) && act("revoke", "post", `${base}/revoke`)} data-testid={`revoke-btn-${s.preset_key}`}>Revoke</button>
        </>}
        <select aria-label="Sync interval" data-testid={`interval-${s.preset_key}`} value={s.active ? s.sync_interval_minutes : 0} onChange={(e) => act("set", "put", `${base}/settings`, { sync_interval_minutes: Math.max(5, +e.target.value || s.sync_interval_minutes), active: +e.target.value !== 0 })} className="h-8 rounded-lg border bg-background text-xs px-2">
          {[[0, "Disabled"], [15, "Every 15 min"], [30, "Every 30 min"], [60, "Hourly"], [360, "Every 6h"], [1440, "Daily"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>
    </Card>
  );
}

export default function SupplierIntegrations() {
  const { data, refetch } = useQuery({ queryKey: ["integrations-presets"], queryFn: () => api.get("/admin/supplier-integrations").then((r) => r.data), refetchInterval: 15000 });
  const [sel, setSel] = useState(null);
  const [busy, setBusy] = useState(false);
  const syncAll = async () => {
    setBusy(true);
    try { const { data: r } = await api.post("/admin/supplier-integrations/sync-all"); toast.success(`Sync finished for ${r.length} supplier(s)`); refetch(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  if (!data) return <p className="text-sm">Loading…</p>;
  const m = data.metrics;
  return (
    <div>
      <PageHeader title="Supplier Integrations" sub="Pick a supplier, enter only its API key, then Connect & Test. Keys are encrypted server-side and never shown again.">
        <Link to="/admin/supplier-catalogue" className={btnGhost} data-testid="open-catalogue-btn">Supplier Catalogue</Link>
        <button className={btnPrimary} disabled={busy} onClick={syncAll} data-testid="sync-all-btn">{busy ? "Syncing…" : "Sync all connected"}</button>
      </PageHeader>
      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-3 mb-6">
        <Metric testid="m-total" label="Configured" value={m.total} /><Metric testid="m-connected" label="Connected" value={m.connected} /><Metric testid="m-attention" label="Need attention" value={m.attention} />
        <Metric testid="m-imported" label="Imported products" value={m.imported_products} /><Metric label="Published" value={m.published} /><Metric label="Unpublished" value={m.unpublished} />
        <Metric label="Price changes (7d)" value={m.price_changes_7d} /><Metric label="Stock changes (7d)" value={m.stock_changes_7d} />
      </div>
      <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4" data-testid="integration-grid">
        {data.suppliers.map((s) => <SupplierCard key={s.id} s={s} onConnect={setSel} refetch={refetch} />)}
      </div>
      {m.recent_failures.length > 0 && (
        <Card className="mt-6"><p className="font-semibold mb-2">Recent sync failures</p>
          <ul className="text-sm divide-y" data-testid="recent-failures">{m.recent_failures.map((f) => <li key={f.id} className="py-2"><b>{f.supplier_name}</b> · {fmtDate(f.started_at)} · attempts {f.attempts} · <span className="text-rose-600">{f.error}</span></li>)}</ul></Card>
      )}
      <ConnectDialog s={sel} onClose={() => setSel(null)} onDone={refetch} />
    </div>
  );
}
