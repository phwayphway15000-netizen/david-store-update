import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader, Card, Field, inp, btnPrimary } from "@/components/admin/ui";

function Method({ m, editable, onSaved }) {
  const [f, setF] = useState(m);
  const u = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const save = async () => {
    try { await api.put(`/admin/payment-methods/${m.id}`, f); toast.success(`${f.name} saved`); onSaved(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Card className="space-y-3" data-testid={`pm-card-${m.code}`}>
      <div className="flex justify-between items-center"><p className="font-semibold">{m.name}</p><span className={`text-xs font-semibold ${m.enabled ? "text-emerald-600" : "text-slate-500"}`}>{m.enabled ? "Enabled" : "Disabled"}</span></div>
      <Field label="Recipient account name"><input data-testid={`pm-account-name-${m.code}`} disabled={!editable} className={inp} value={f.account_name} onChange={(e) => u("account_name", e.target.value)} /></Field>
      <Field label="Recipient number"><input data-testid={`pm-account-number-${m.code}`} disabled={!editable} className={inp} value={f.account_number} onChange={(e) => u("account_number", e.target.value)} /></Field>
      <Field label="Instructions shown to customers"><textarea disabled={!editable} className={inp + " h-20 py-2"} value={f.instructions} onChange={(e) => u("instructions", e.target.value)} /></Field>
      {editable && <div className="flex items-center justify-between"><label className="flex items-center gap-2 text-sm"><input type="checkbox" data-testid={`pm-enabled-${m.code}`} checked={f.enabled} onChange={(e) => u("enabled", e.target.checked)} />Enabled</label>
        <button className={btnPrimary} onClick={save} data-testid={`pm-save-${m.code}`}>Save</button></div>}
    </Card>
  );
}

export default function PaymentMethods() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data = [] } = useQuery({ queryKey: ["pm"], queryFn: () => api.get("/admin/payment-methods").then((r) => r.data) });
  const [name, setName] = useState("");
  const owner = user.role === "owner";
  const add = async () => {
    try { await api.post("/admin/payment-methods", { name }); setName(""); qc.invalidateQueries({ queryKey: ["pm"] }); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div>
      <PageHeader title="Manual payment methods" sub="Methods stay disabled until the Owner enters real recipient details. Customers see these in the Telegram bot.">
        {owner && <><input data-testid="pm-new-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Other method name" className={inp + " w-48"} /><button className={btnPrimary} disabled={!name} onClick={add} data-testid="pm-add-btn">Add method</button></>}
      </PageHeader>
      {!owner && <p className="mb-4 text-sm text-amber-700">Only the Owner can edit payment recipients.</p>}
      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">{data.map((m) => <Method key={m.id + m.enabled} m={m} editable={owner} onSaved={() => qc.invalidateQueries({ queryKey: ["pm"] })} />)}</div>
    </div>
  );
}
