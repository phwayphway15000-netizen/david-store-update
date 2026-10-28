import { Link } from "react-router-dom";
import { useI18n } from "@/lib/i18n";
import { mmk } from "@/lib/fmt";
import { imgUrl } from "@/lib/api";

const COLORS = ["from-blue-600 to-cyan-500", "from-[#0A1128] to-blue-600", "from-sky-500 to-indigo-600", "from-slate-800 to-slate-600"];

export const BrandMark = ({ name = "?", className = "" }) => {
  const i = (name.charCodeAt(0) || 0) % COLORS.length;
  return (
    <div className={`bg-gradient-to-br ${COLORS[i]} grid place-items-center relative overflow-hidden ${className}`}>
      <div className="absolute inset-0 grid-bg opacity-40" />
      <span className="relative font-display font-extrabold text-white/95 text-4xl tracking-tight">{name}</span>
    </div>
  );
};

export const StockBadge = ({ label }) => {
  const { t } = useI18n();
  const cls = { in_stock: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300", low_stock: "bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300", out_of_stock: "bg-slate-100 text-slate-500 dark:bg-slate-800" }[label];
  return <span className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full ${cls}`}><span className="h-1.5 w-1.5 rounded-full bg-current" />{t(label)}</span>;
};

export default function ProductCard({ p, i = 0 }) {
  const { t, pick } = useI18n();
  const v = p.variants.find((x) => x.available) || p.variants[0] || {};
  return (
    <Link to={`/products/${p.slug}`} data-testid={`product-card-${p.slug}`} style={{ animationDelay: `${i * 50}ms` }}
      className="fade-up group bg-card rounded-2xl border card-elev overflow-hidden flex flex-col">
      <div className="relative aspect-[4/3] overflow-hidden bg-slate-100">
        {p.images?.[0] ? <img src={imgUrl(p.images[0])} alt={p.name} data-testid="product-card-image" className="h-full w-full object-contain group-hover:scale-105 transition-transform duration-500" />
          : <BrandMark name={p.brand?.name || p.name} className="h-full w-full group-hover:scale-105 transition-transform duration-500" />}
        <div className="absolute top-3 left-3 flex gap-1.5 flex-wrap">
          {p.max_discount > 0 && <span className="text-[11px] font-bold bg-rose-600 text-white px-2 py-0.5 rounded-full">-{p.max_discount}%</span>}
          {p.hot && <span className="text-[11px] font-bold bg-orange-500 text-white px-2 py-0.5 rounded-full">{t("hot")}</span>}
          {p.featured && <span className="text-[11px] font-bold bg-white/90 text-blue-700 px-2 py-0.5 rounded-full">{t("featured")}</span>}
          {p.is_sample && <span className="text-[11px] font-bold bg-yellow-300 text-yellow-900 px-2 py-0.5 rounded-full">{t("sample")}</span>}
        </div>
      </div>
      <div className="p-5 flex-1 flex flex-col">
        <p className="text-xs font-semibold text-blue-600">{p.brand?.name}</p>
        <h3 className="mt-1 font-semibold leading-snug line-clamp-2">{pick(p.name, p.name_my)}</h3>
        <p className="mt-1 text-xs text-muted-foreground">{v.name}{v.duration ? ` · ${v.duration}` : ""}</p>
        <div className="mt-auto pt-4 flex items-end justify-between gap-2">
          <div>
            {v.promo_active && <p className="text-xs text-muted-foreground line-through">{mmk(v.price_mmk)}</p>}
            <p className="font-display font-bold text-lg text-[#0A1128] dark:text-white" data-testid={`product-price-${p.slug}`}>{mmk(v.effective_price_mmk)}</p>
            <div className="mt-1"><StockBadge label={v.stock_label} /></div>
          </div>
          <span className="shrink-0 h-10 px-4 inline-flex items-center rounded-full bg-[#0A1128] dark:bg-blue-600 text-white text-sm font-semibold group-hover:bg-blue-600 transition-colors">{t("buy_now")}</span>
        </div>
      </div>
    </Link>
  );
}

export const CardSkeleton = () => (
  <div className="rounded-2xl border overflow-hidden animate-pulse">
    <div className="aspect-[4/3] bg-slate-100 dark:bg-slate-800" />
    <div className="p-5 space-y-3"><div className="h-3 w-16 bg-slate-100 dark:bg-slate-800 rounded" /><div className="h-4 w-3/4 bg-slate-100 dark:bg-slate-800 rounded" /><div className="h-6 w-24 bg-slate-100 dark:bg-slate-800 rounded" /></div>
  </div>
);
