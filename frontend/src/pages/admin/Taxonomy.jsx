import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { PageHeader, Card, inp, btnPrimary } from "@/components/admin/ui";

function List({ kind, fields }) {
  const qc = useQueryClient();
  const { data = [] } = useQuery({ queryKey: [`admin-${kind}`], queryFn: () => api.get(`/admin/${kind}`).then((r) => r.data) });
  const [f, setF] = useState({});
  const add = async (e) => {
    e.preventDefault();
    try { await api.post(`/admin/${kind}`, f); setF({}); qc.invalidateQueries({ queryKey: [`admin-${kind}`] }); toast.success("Created"); } catch (er) { toast.error(errMsg(er)); }
  };
  const del = async (id) => {
    if (!window.confirm("Delete?")) return;
    await api.delete(`/admin/${kind}/${id}`); qc.invalidateQueries({ queryKey: [`admin-${kind}`] });
  };
  return (
    <Card>
      <p className="font-semibold mb-3 capitalize">{kind}</p>
      <form onSubmit={add} className="flex flex-wrap gap-2 mb-4">
        {fields.map(([k, ph, type]) => <input key={k} data-testid={`${kind}-${k}-input`} type={type || "text"} required={k === "name"} placeholder={ph} value={f[k] || ""} onChange={(e) => setF({ ...f, [k]: e.target.value })} className={inp + " flex-1 min-w-[120px]" + (type === "color" ? " max-w-[60px] p-1" : "")} />)}
        <button className={btnPrimary} data-testid={`${kind}-add-btn`}>Add</button>
      </form>
      <ul className="divide-y">
        {data.map((x) => (
          <li key={x.id} className="py-2 flex items-center gap-3 text-sm" data-testid={`${kind}-item-${x.slug}`}>
            {x.color && <span className="h-4 w-4 rounded-full" style={{ background: x.color }} />}
            <span className="font-medium">{x.name}</span>{x.name_my && <span className="text-muted-foreground">{x.name_my}</span>}
            <span className="text-xs text-muted-foreground font-mono">{x.slug}</span>
            <button onClick={() => del(x.id)} className="ml-auto text-rose-600" aria-label="Delete" data-testid={`${kind}-delete-${x.slug}`}><Trash2 className="h-4 w-4" /></button>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export default function Taxonomy() {
  return (
    <div>
      <PageHeader title="Brands & Categories" sub="Brands are catalogue labels only — they do not imply any partnership." />
      <div className="grid lg:grid-cols-2 gap-6">
        <List kind="brands" fields={[["name", "Brand name"], ["color", "Color", "color"]]} />
        <List kind="categories" fields={[["name", "Name (EN)"], ["name_my", "Name (MM)"]]} />
      </div>
    </div>
  );
}
