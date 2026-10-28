import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { fmtDate } from "@/lib/fmt";
import { PageHeader, Card, inp, btnPrimary, Th, Td } from "@/components/admin/ui";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export default function Suppliers() {
  const nav = useNavigate();
  const { data = [] } = useQuery({ queryKey: ["suppliers"], queryFn: () => api.get("/admin/suppliers").then((r) => r.data) });
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [base, setBase] = useState("https://");
  const create = async (e) => {
    e.preventDefault();
    try {
      const { data: s } = await api.post("/admin/suppliers", { name, base_url: base });
      nav(`/admin/suppliers/${s.id}`);
    } catch (er) { toast.error(errMsg(er)); }
  };
  return (
    <div>
      <PageHeader title="Supplier integrations" sub="Connect supplier REST APIs. Credentials are encrypted server-side and never sent to browsers.">
        <button className={btnPrimary} onClick={() => setOpen(true)} data-testid="new-supplier-btn"><Plus className="h-4 w-4" />Add supplier</button>
      </PageHeader>
      <div className="rounded-xl border bg-card overflow-x-auto">
        <table className="w-full min-w-[700px]">
          <thead className="border-b bg-slate-50 dark:bg-slate-900"><tr><Th>Name</Th><Th>Base URL</Th><Th>Auth</Th><Th>Health</Th><Th>Schedule</Th><Th>Last sync</Th></tr></thead>
          <tbody className="divide-y">
            {data.map((s) => (
              <tr key={s.id} data-testid={`supplier-row-${s.id}`}>
                <Td><Link to={`/admin/suppliers/${s.id}`} className="text-blue-600 font-medium">{s.name}</Link>{!s.active && <span className="ml-2 text-xs text-muted-foreground">inactive</span>}</Td>
                <Td className="font-mono text-xs">{s.base_url}</Td><Td>{s.auth_type}</Td>
                <Td><span className={s.health === "ok" ? "text-emerald-600" : s.health === "error" ? "text-rose-600" : "text-slate-500"}>{s.health}</span></Td>
                <Td>{s.sync_interval_minutes ? `every ${s.sync_interval_minutes} min` : "manual"}</Td><Td>{fmtDate(s.last_sync_at)}</Td>
              </tr>
            ))}
          </tbody>
        </table>
        {!data.length && <p className="p-8 text-center text-sm text-muted-foreground">No suppliers yet.</p>}
      </div>
      <Card className="mt-6 text-sm text-muted-foreground">
        Safety rules: only <b>https</b> URLs on public hosts are allowed (private, loopback and internal addresses are rejected), redirects are not followed, responses are capped at 5MB, and supplier documentation/specs are only read as data — never executed.
      </Card>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add supplier</DialogTitle></DialogHeader>
          <form onSubmit={create} className="space-y-3">
            <input data-testid="supplier-name-input" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Supplier name" className={inp} />
            <input data-testid="supplier-baseurl-input" required value={base} onChange={(e) => setBase(e.target.value)} placeholder="https://api.supplier.com" className={inp} />
            <button className={btnPrimary + " w-full"} data-testid="supplier-create-btn">Create & configure</button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
