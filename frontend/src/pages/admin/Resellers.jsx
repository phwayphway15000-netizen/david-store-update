import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { mmk, fmtDate } from "@/lib/fmt";
import { PageHeader, Card, Field, inp, btnPrimary, btnGhost, Th, Td } from "@/components/admin/ui";

const blank = { email: "", name: "", business_name: "", phone: "", notes: "", password: "", active: true };

export default function Resellers() {
  const qc = useQueryClient();
  const { data = [] } = useQuery({ queryKey: ["resellers"], queryFn: () => api.get("/admin/resellers").then((r) => r.data) });
  const [f, setF] = useState(blank);
  const u = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const save = async (e) => {
    e.preventDefault();
    const body = { email: f.email, name: f.name, business_name: f.business_name, phone: f.phone, notes: f.notes, active: f.active, password: f.password || null };
    try { f.id ? await api.put(`/admin/resellers/${f.id}`, body) : await api.post("/admin/resellers", body); setF(blank); qc.invalidateQueries({ queryKey: ["resellers"] }); toast.success("Saved"); } catch (er) { toast.error(errMsg(er)); }
  };
  return (
    <div>
      <PageHeader title="Resellers" sub={`Create reseller logins. Resellers sign in at ${window.location.origin}/reseller and see only the plans that have a reseller price.`} />
      <div className="grid xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 rounded-xl border bg-card overflow-x-auto">
          <table className="w-full min-w-[640px]"><thead className="border-b"><tr><Th>Name</Th><Th>Email</Th><Th>Phone</Th><Th>Orders</Th><Th>Paid total</Th><Th>Last login</Th><Th>Status</Th></tr></thead>
            <tbody className="divide-y">{data.map((x) => (
              <tr key={x.id} className="cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-900" onClick={() => setF({ ...blank, ...x, password: "" })} data-testid={`reseller-row-${x.email}`}>
                <Td><p className="font-medium">{x.name}</p>{x.business_name && <p className="text-xs text-muted-foreground">{x.business_name}</p>}</Td><Td>{x.email}</Td><Td>{x.phone || "—"}</Td><Td>{x.orders}</Td><Td>{mmk(x.spent_mmk)}</Td><Td>{fmtDate(x.last_login_at)}</Td><Td>{x.active ? "Active" : "Disabled"}</Td>
              </tr>))}
              {!data.length && <tr><Td className="text-muted-foreground">No resellers yet.</Td></tr>}</tbody></table>
        </div>
        <Card>
          <form onSubmit={save} className="space-y-3" data-testid="reseller-form">
            <p className="font-semibold">{f.id ? "Edit reseller" : "Add reseller"}</p>
            <Field label="Email (login)"><input data-testid="reseller-form-email" type="email" required disabled={!!f.id} className={inp} value={f.email} onChange={(e) => u("email", e.target.value)} /></Field>
            <Field label="Name"><input data-testid="reseller-form-name" required className={inp} value={f.name} onChange={(e) => u("name", e.target.value)} /></Field>
            <Field label="Business / shop name"><input data-testid="reseller-form-business" className={inp} value={f.business_name} onChange={(e) => u("business_name", e.target.value)} /></Field>
            <Field label="Phone"><input data-testid="reseller-form-phone" className={inp} value={f.phone} onChange={(e) => u("phone", e.target.value)} /></Field>
            <Field label={f.id ? "New password (optional)" : "Password (min 8)"}><input data-testid="reseller-form-password" type="password" autoComplete="new-password" required={!f.id} minLength={8} className={inp} value={f.password} onChange={(e) => u("password", e.target.value)} /></Field>
            <Field label="Private notes"><textarea className={inp + " h-16 py-2"} value={f.notes} onChange={(e) => u("notes", e.target.value)} data-testid="reseller-form-notes" /></Field>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" data-testid="reseller-form-active" checked={f.active} onChange={(e) => u("active", e.target.checked)} />Active (can sign in and order)</label>
            <div className="flex gap-2"><button className={btnPrimary} data-testid="reseller-form-save">Save</button>{f.id && <button type="button" className={btnGhost} onClick={() => setF(blank)}>Cancel</button>}</div>
          </form>
        </Card>
      </div>
    </div>
  );
}
