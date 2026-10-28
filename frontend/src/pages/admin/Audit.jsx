import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/fmt";
import { PageHeader, inp, Th, Td } from "@/components/admin/ui";

export default function Audit() {
  const [type, setType] = useState("");
  const { data = [] } = useQuery({ queryKey: ["audit", type], queryFn: () => api.get("/admin/audit", { params: { entity_type: type } }).then((r) => r.data) });
  return (
    <div>
      <PageHeader title="Audit log" sub="Every important change with actor, timestamp and details.">
        <select data-testid="audit-type-filter" value={type} onChange={(e) => setType(e.target.value)} className={inp + " w-44"}>
          {["", "order", "product", "supplier", "user", "settings", "payment_method", "promotion", "integration", "brand", "category"].map((t) => <option key={t} value={t}>{t || "All"}</option>)}
        </select>
      </PageHeader>
      <div className="rounded-xl border bg-card overflow-x-auto">
        <table className="w-full min-w-[800px]"><thead className="border-b"><tr><Th>When</Th><Th>Actor</Th><Th>Action</Th><Th>Entity</Th><Th>Details</Th></tr></thead>
          <tbody className="divide-y" data-testid="audit-table">{data.map((a) => (
            <tr key={a.id}><Td className="text-xs whitespace-nowrap">{fmtDate(a.created_at)}</Td><Td className="text-xs">{a.actor?.name || a.actor?.id} <span className="text-muted-foreground">({a.actor?.type})</span></Td>
              <Td className="font-mono text-xs">{a.action}</Td><Td className="text-xs">{a.entity_type}</Td><Td className="text-xs font-mono max-w-md truncate">{JSON.stringify(a.details)}</Td></tr>))}</tbody></table>
      </div>
    </div>
  );
}
