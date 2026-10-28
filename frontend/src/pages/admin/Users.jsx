import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader, Card, Field, inp, btnPrimary, Th, Td } from "@/components/admin/ui";

const blank = { email: "", name: "", role: "customer_service", password: "", can_approve_payments: false, active: true };

export default function Users() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data = [] } = useQuery({ queryKey: ["team"], queryFn: () => api.get("/admin/users").then((r) => r.data) });
  const [f, setF] = useState(blank);
  const owner = user.role === "owner";
  const u = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const save = async (e) => {
    e.preventDefault();
    const body = { ...f, password: f.password || null };
    try { f.id ? await api.put(`/admin/users/${f.id}`, body) : await api.post("/admin/users", body); setF(blank); qc.invalidateQueries({ queryKey: ["team"] }); toast.success("Saved"); } catch (er) { toast.error(errMsg(er)); }
  };
  return (
    <div>
      <PageHeader title="Team & roles" sub="Owner > Admin > Product Manager > Customer Service. Customer service can't approve payments unless granted." />
      <div className="grid xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 rounded-xl border bg-card overflow-x-auto">
          <table className="w-full min-w-[600px]"><thead className="border-b"><tr><Th>Name</Th><Th>Email</Th><Th>Role</Th><Th>Approve payments</Th><Th>Status</Th></tr></thead>
            <tbody className="divide-y">{data.map((x) => (
              <tr key={x.id} className={owner ? "cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-900" : ""} onClick={() => owner && setF({ ...x, password: "" })} data-testid={`user-row-${x.email}`}>
                <Td>{x.name}</Td><Td>{x.email}</Td><Td className="capitalize">{x.role.replace("_", " ")}</Td><Td>{x.permissions.includes("*") || x.permissions.includes("orders.approve") ? "Yes" : "No"}</Td><Td>{x.active ? "Active" : "Disabled"}</Td>
              </tr>))}</tbody></table>
        </div>
        {owner && (
          <Card>
            <form onSubmit={save} className="space-y-3" data-testid="user-form">
              <p className="font-semibold">{f.id ? "Edit member" : "Add member"}</p>
              <Field label="Email"><input data-testid="user-email-input" type="email" required disabled={!!f.id} className={inp} value={f.email} onChange={(e) => u("email", e.target.value)} /></Field>
              <Field label="Name"><input data-testid="user-name-input" required className={inp} value={f.name} onChange={(e) => u("name", e.target.value)} /></Field>
              <Field label="Role"><select data-testid="user-role-select" className={inp} value={f.role} onChange={(e) => u("role", e.target.value)}>{["owner", "admin", "product_manager", "customer_service"].map((r) => <option key={r} value={r}>{r.replace("_", " ")}</option>)}</select></Field>
              <Field label={f.id ? "New password (optional)" : "Password (min 8)"}><input data-testid="user-password-input" type="password" autoComplete="new-password" required={!f.id} minLength={8} className={inp} value={f.password} onChange={(e) => u("password", e.target.value)} /></Field>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" data-testid="user-approve-toggle" checked={f.can_approve_payments} onChange={(e) => u("can_approve_payments", e.target.checked)} />Allow payment approval</label>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.active} onChange={(e) => u("active", e.target.checked)} />Active</label>
              <div className="flex gap-2"><button className={btnPrimary} data-testid="user-save-btn">Save</button>{f.id && <button type="button" className="text-sm" onClick={() => setF(blank)}>Cancel</button>}</div>
            </form>
          </Card>
        )}
      </div>
    </div>
  );
}
