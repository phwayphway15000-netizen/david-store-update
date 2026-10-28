import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { fmtDate } from "@/lib/fmt";
import { PageHeader, Card, Field, inp, btnPrimary } from "@/components/admin/ui";

const blank = { title_en: "", title_my: "", subtitle_en: "", subtitle_my: "", image_url: "", link: "/products", placement: "featured", start_at: null, end_at: null, active: true, sort: 100 };

export default function Promotions() {
  const qc = useQueryClient();
  const { data = [] } = useQuery({ queryKey: ["admin-promos"], queryFn: () => api.get("/admin/promotions").then((r) => r.data) });
  const [f, setF] = useState(blank);
  const u = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const refresh = () => { qc.invalidateQueries({ queryKey: ["admin-promos"] }); qc.invalidateQueries({ queryKey: ["promotions"] }); };
  const save = async (e) => {
    e.preventDefault();
    try { f.id ? await api.put(`/admin/promotions/${f.id}`, f) : await api.post("/admin/promotions", f); setF(blank); refresh(); toast.success("Saved"); } catch (er) { toast.error(errMsg(er)); }
  };
  const upload = async (e) => {
    const fd = new FormData(); fd.append("file", e.target.files[0]);
    try { const { data: d } = await api.post("/admin/uploads/image", fd); u("image_url", d.url); } catch (er) { toast.error(errMsg(er)); }
  };
  const dt = (k) => <input type="datetime-local" className={inp} value={f[k] ? f[k].slice(0, 16) : ""} onChange={(e) => u(k, e.target.value ? new Date(e.target.value).toISOString() : null)} />;
  return (
    <div>
      <PageHeader title="Promotions & banners" sub="Hero banner replaces the homepage hero; featured banners show in Featured promotions. Product discounts are set per plan in the product editor." />
      <div className="grid xl:grid-cols-2 gap-6">
        <Card>
          <form onSubmit={save} className="grid sm:grid-cols-2 gap-3" data-testid="promo-form">
            <Field label="Title (EN)"><input data-testid="promo-title-en" required className={inp} value={f.title_en} onChange={(e) => u("title_en", e.target.value)} /></Field>
            <Field label="Title (MM)"><input data-testid="promo-title-my" className={inp} value={f.title_my} onChange={(e) => u("title_my", e.target.value)} /></Field>
            <Field label="Subtitle (EN)"><input className={inp} value={f.subtitle_en} onChange={(e) => u("subtitle_en", e.target.value)} /></Field>
            <Field label="Subtitle (MM)"><input className={inp} value={f.subtitle_my} onChange={(e) => u("subtitle_my", e.target.value)} /></Field>
            <Field label="Link"><input className={inp} value={f.link} onChange={(e) => u("link", e.target.value)} /></Field>
            <Field label="Placement"><select data-testid="promo-placement" className={inp} value={f.placement} onChange={(e) => u("placement", e.target.value)}><option value="featured">Featured</option><option value="hero">Hero</option></select></Field>
            <Field label="Start (optional)">{dt("start_at")}</Field><Field label="End (optional)">{dt("end_at")}</Field>
            <Field label="Image"><input type="file" accept="image/*" onChange={upload} className="text-xs" data-testid="promo-image-input" /></Field>
            <label className="flex items-center gap-2 text-sm mt-5"><input type="checkbox" checked={f.active} onChange={(e) => u("active", e.target.checked)} />Active</label>
            <button className={btnPrimary + " sm:col-span-2"} data-testid="promo-save-btn">{f.id ? "Update" : "Create"} banner</button>
          </form>
        </Card>
        <Card>
          <ul className="divide-y">
            {data.map((p) => (
              <li key={p.id} className="py-3 flex items-center gap-3 text-sm" data-testid={`promo-item-${p.id}`}>
                <button className="text-left flex-1" onClick={() => setF(p)}><p className="font-medium">{p.title_en}</p><p className="text-xs text-muted-foreground">{p.placement} · {p.active ? "active" : "inactive"} · {p.start_at ? fmtDate(p.start_at) : "now"} → {p.end_at ? fmtDate(p.end_at) : "no end"}</p></button>
                <button onClick={async () => { await api.delete(`/admin/promotions/${p.id}`); refresh(); }} className="text-rose-600" aria-label="Delete"><Trash2 className="h-4 w-4" /></button>
              </li>
            ))}
            {!data.length && <li className="text-sm text-muted-foreground">No banners yet.</li>}
          </ul>
        </Card>
      </div>
    </div>
  );
}
