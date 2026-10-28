import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { ChevronRight } from "lucide-react";
import { api, imgUrl } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useSettings } from "@/lib/hooks";
import BuyPanel from "@/components/store/BuyPanel";
import { BrandMark } from "@/components/store/ProductCard";

export default function ProductDetail() {
  const { slug } = useParams();
  const { t, pick } = useI18n();
  const { data: settings } = useSettings();
  const { data: p, isLoading, isError } = useQuery({ queryKey: ["product", slug], queryFn: () => api.get(`/products/${slug}`).then((r) => r.data) });
  const [img, setImg] = useState(0);
  useEffect(() => {
    if (p) document.title = `${p.name} – AI Tools By David Digital Store`;
  }, [p]);
  if (isLoading) return <div className="container-x py-16"><div className="h-96 rounded-2xl bg-slate-100 dark:bg-slate-800 animate-pulse" /></div>;
  if (isError || !p) return <div className="container-x py-24 text-center" data-testid="product-not-found"><p className="text-lg">Product not found.</p><Link to="/products" className="text-blue-600">{t("all_products")}</Link></div>;
  const rows = [["brand", p.brand?.name], ["product_type", p.product_type], ["activation", p.activation_method], ["eligibility", p.eligibility], ["warranty", p.warranty], ["delivery", p.delivery_time]];
  return (
    <div className="container-x py-8">
      <nav className="flex items-center gap-1 text-xs text-muted-foreground mb-6">
        <Link to="/">{t("home")}</Link><ChevronRight className="h-3 w-3" /><Link to="/products">{t("all_products")}</Link>
        {p.category && (<><ChevronRight className="h-3 w-3" /><Link to={`/products?category=${p.category.slug}`}>{pick(p.category.name, p.category.name_my)}</Link></>)}
      </nav>
      <div className="grid lg:grid-cols-[1.3fr_1fr] gap-10">
        <div>
          <div className="rounded-3xl overflow-hidden border aspect-[16/10]">
            {p.images?.length ? <img src={imgUrl(p.images[img])} alt={p.name} className="h-full w-full object-cover" data-testid="product-main-image" /> : <BrandMark name={p.brand?.name || p.name} className="h-full w-full" />}
          </div>
          {p.images?.length > 1 && <div className="mt-3 flex gap-2">{p.images.map((u, i) => <button key={u} onClick={() => setImg(i)} data-testid={`product-thumb-${i}`} className={`h-16 w-20 rounded-lg overflow-hidden border-2 ${i === img ? "border-blue-600" : "border-transparent"}`}><img src={imgUrl(u)} alt="" className="h-full w-full object-cover" /></button>)}</div>}
          <div className="mt-10">
            <p className="eyebrow">{p.brand?.name}</p>
            <h1 className="mt-2 text-3xl sm:text-4xl font-extrabold tracking-tight" data-testid="product-name">{pick(p.name, p.name_my)}</h1>
            <p className="mt-4 text-lg text-muted-foreground" data-testid="product-short-desc">{pick(p.short_description, p.short_description_my)}</p>
            <div className="mt-8 grid sm:grid-cols-2 gap-px bg-border rounded-2xl overflow-hidden border">
              {rows.map(([k, v]) => <div key={k} className="bg-card p-5"><p className="text-xs font-semibold text-muted-foreground">{t(k)}</p><p className="mt-1 text-sm font-medium" data-testid={`product-${k}`}>{v || "—"}</p></div>)}
            </div>
            <h2 className="mt-10 text-xl font-bold">{t("details")}</h2>
            <div className="mt-3 text-[15px] leading-relaxed text-slate-700 dark:text-slate-300 whitespace-pre-line" data-testid="product-description">{pick(p.description, p.description_my)}</div>
            <p className="mt-8 text-xs text-muted-foreground">{t("disclaimer")}</p>
          </div>
        </div>
        <div className="lg:sticky lg:top-32 self-start"><BuyPanel p={p} settings={settings} /></div>
      </div>
    </div>
  );
}
