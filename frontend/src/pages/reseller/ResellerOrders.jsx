import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { mmk, fmtDate } from "@/lib/fmt";
import { useI18n } from "@/lib/i18n";
import { StatusBadge } from "@/components/admin/ui";

export default function ResellerOrders() {
  const { pick } = useI18n();
  const { data = [], isLoading } = useQuery({ queryKey: ["reseller-orders"], queryFn: () => api.get("/reseller/orders").then((r) => r.data) });
  return (
    <div>
      <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight mb-6">{pick("My orders", "ကျွန်ုပ်၏ အော်ဒါများ")}</h1>
      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {!isLoading && !data.length && <p className="text-sm text-muted-foreground" data-testid="reseller-orders-empty">{pick("No orders yet.", "အော်ဒါ မရှိသေးပါ။")}</p>}
      <div className="space-y-3">{data.map((o) => (
        <Link key={o.id} to={`/reseller/orders/${o.id}`} className="block rounded-xl border bg-card p-4 hover:border-blue-500 transition-colors" data-testid={`reseller-order-${o.ref}`}>
          <div className="flex flex-wrap items-center gap-3">
            <span className="font-mono font-semibold text-sm">{o.ref}</span><StatusBadge s={o.status} />
            <span className="ml-auto font-bold">{mmk(o.total_mmk)}</span>
          </div>
          <p className="text-xs text-muted-foreground mt-1">{o.items.length} {pick("item(s)", "မျိုး")} · {fmtDate(o.created_at)}</p>
        </Link>))}</div>
    </div>
  );
}
