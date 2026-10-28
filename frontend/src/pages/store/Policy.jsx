import { useParams } from "react-router-dom";
import { useI18n } from "@/lib/i18n";
import { useSettings } from "@/lib/hooks";

const TITLES = { about: "about", privacy: "privacy", terms: "terms", refund: "refund", delivery: "delivery_policy", warranty: "warranty_terms" };

export default function Policy() {
  const { key } = useParams();
  const { t, pick } = useI18n();
  const { data: s } = useSettings();
  const pol = s?.policies?.[key];
  const c = s?.contacts || {};
  return (
    <div className="container-x py-12 max-w-3xl">
      <h1 className="text-4xl font-extrabold tracking-tight" data-testid="policy-title">{t(TITLES[key] || key)}</h1>
      <div className="mt-6 text-[15px] leading-relaxed whitespace-pre-line text-slate-700 dark:text-slate-300" data-testid="policy-body">{pol ? pick(pol.en, pol.my) : "—"}</div>
      <div className="mt-10 rounded-2xl border p-6 text-sm">
        <p className="font-semibold mb-2">{t("contact")}</p>
        <p>{s?.brand_name}</p>
        {c.phone && <p>Phone: {c.phone}</p>}
        {c.email && <p>Email: {c.email}</p>}
        {c.address && <p>{c.address}</p>}
      </div>
    </div>
  );
}
