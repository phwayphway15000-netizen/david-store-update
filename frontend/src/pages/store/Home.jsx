import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Headphones, Globe, Smartphone, Send, Bot, Plug, ShieldCheck, Eye, MessagesSquare, Truck, Sparkles } from "lucide-react";
import { api, imgUrl } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useBrands, usePromotions, useSettings } from "@/lib/hooks";
import ProductCard, { CardSkeleton } from "@/components/store/ProductCard";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";

const SICON = { globe: Globe, smartphone: Smartphone, send: Send, bot: Bot, plug: Plug };

const Section = ({ eyebrow, title, action, children, id }) => (
  <section className="container-x mt-20" id={id}>
    <div className="flex items-end justify-between gap-4 mb-8">
      <div>{eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}<h2 className="text-2xl sm:text-3xl font-bold tracking-tight">{title}</h2></div>
      {action}
    </div>
    {children}
  </section>
);

function Hero({ s, promo }) {
  const { pick, t } = useI18n();
  const h = s?.hero || {};
  const title = promo ? pick(promo.title_en, promo.title_my) : pick(h.title_en, h.title_my);
  const sub = promo ? pick(promo.subtitle_en, promo.subtitle_my) : pick(h.subtitle_en, h.subtitle_my);
  const img = promo?.image_url || h.image_url;
  return (
    <section className="relative overflow-hidden bg-[#0A1128] text-white" data-testid="hero-section">
      <div className="absolute inset-0 grid-bg opacity-30" />
      <div className="absolute -top-40 -right-40 h-[520px] w-[520px] rounded-full bg-blue-600/40 blur-[120px]" />
      <div className="container-x relative py-16 sm:py-24 grid lg:grid-cols-[1.2fr_1fr] gap-12 items-center">
        <div className="fade-up">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-semibold text-blue-200"><Sparkles className="h-3.5 w-3.5" />{pick(h.badge_en, h.badge_my)}</span>
          <h1 className="mt-6 text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.3]" data-testid="hero-title">{title}</h1>
          <p className="mt-6 text-base sm:text-lg text-slate-300 max-w-xl">{sub}</p>
          <div className="mt-9 flex flex-wrap gap-3">
            <Link to={promo?.link || "/products"} data-testid="hero-explore-btn" className="h-12 px-7 rounded-full bg-blue-600 hover:bg-blue-500 font-semibold inline-flex items-center gap-2 transition-colors">{t("explore")}<ArrowRight className="h-4 w-4" /></Link>
            <Link to="/support" data-testid="hero-support-btn" className="h-12 px-7 rounded-full border border-white/25 hover:bg-white/10 font-semibold inline-flex items-center gap-2 transition-colors"><Headphones className="h-4 w-4" />{t("contact_support")}</Link>
          </div>
        </div>
        <div className="relative lg:hidden flex justify-center -mt-4 mb-2 order-first">
          <img src="/logo-mark.png" alt="" className="w-32 hero-float drop-shadow-[0_0_30px_rgba(59,130,246,0.7)]" data-testid="hero-logo-mobile" />
        </div>
        <div className="relative hidden lg:block">
          {img ? <img src={imgUrl(img)} alt="" className="rounded-3xl border border-white/10 shadow-2xl" />
            : <div className="relative h-[420px] grid place-items-center" data-testid="hero-logo">
              <div className="absolute h-80 w-80 rounded-full bg-blue-500/40 blur-[90px] animate-pulse" />
              <div className="absolute h-[380px] w-[380px] rounded-full border border-blue-400/20" />
              <div className="absolute h-[300px] w-[300px] rounded-full border border-blue-400/10" />
              <img src="/logo-mark.png" alt="AI Tools By David" className="relative w-72 xl:w-80 fade-up hero-float drop-shadow-[0_0_45px_rgba(59,130,246,0.75)]" />
            </div>}
        </div>
      </div>
    </section>
  );
}

function Promos({ items }) {
  const { pick } = useI18n();
  if (!items.length) return null;
  return (
    <div className="grid md:grid-cols-2 gap-5">
      {items.map((p) => (
        <Link key={p.id} to={p.link || "/promotions"} data-testid={`promo-banner-${p.id}`} className="relative rounded-2xl overflow-hidden min-h-[180px] p-7 bg-gradient-to-br from-blue-600 to-[#0A1128] text-white card-elev">
          {p.image_url && <img src={imgUrl(p.image_url)} alt="" className="absolute inset-0 h-full w-full object-cover opacity-40" />}
          <div className="relative"><h3 className="text-2xl font-bold">{pick(p.title_en, p.title_my)}</h3><p className="mt-2 text-sm text-blue-100 max-w-sm">{pick(p.subtitle_en, p.subtitle_my)}</p>
            {p.end_at && <p className="mt-4 text-xs text-blue-200">Ends {new Date(p.end_at).toLocaleDateString()}</p>}</div>
        </Link>
      ))}
    </div>
  );
}

export default function Home() {
  const { t, pick } = useI18n();
  const { data: s } = useSettings();
  const { data: promos = [] } = usePromotions();
  const { data: brands = [] } = useBrands();
  const popular = useQuery({ queryKey: ["products", "popular"], queryFn: () => api.get("/products?sort=popular&limit=8").then((r) => r.data) });
  const promoProducts = useQuery({ queryKey: ["products", "promo"], queryFn: () => api.get("/products?promo=true&limit=4").then((r) => r.data) });
  const hero = promos.find((p) => p.placement === "hero");
  const why = [[ShieldCheck, "why1"], [Eye, "why2"], [MessagesSquare, "why3"], [Truck, "why4"]];
  const grid = (q) => (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
      {q.isLoading ? Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />) : q.data?.items.map((p, i) => <ProductCard key={p.id} p={p} i={i} />)}
    </div>
  );
  return (
    <div>
      <Hero s={s} promo={hero} />
      {(promos.some((p) => p.placement === "featured") || promoProducts.data?.items.length > 0) && (
        <Section eyebrow={t("promotions")} title={t("featured_promos")} action={<Link to="/promotions" className="text-sm font-semibold text-blue-600" data-testid="promos-view-all">{t("view_all")} →</Link>}>
          <Promos items={promos.filter((p) => p.placement === "featured")} />
          {promoProducts.data?.items.length > 0 && <div className="mt-6">{grid(promoProducts)}</div>}
        </Section>
      )}
      <Section eyebrow="Top picks" title={t("popular")} action={<Link to="/products" className="text-sm font-semibold text-blue-600" data-testid="popular-view-all">{t("view_all")} →</Link>}>{grid(popular)}</Section>
      <Section title={t("browse_brand")}>
        <div className="flex flex-wrap gap-3">
          {brands.map((b) => (
            <Link key={b.id} to={`/products?brand=${b.slug}`} data-testid={`brand-pill-${b.slug}`} className="group inline-flex items-center gap-2.5 h-12 pl-2 pr-5 rounded-full border bg-card hover:border-blue-500 hover:shadow-md transition-all">
              <span className="h-8 w-8 rounded-full grid place-items-center text-white text-xs font-bold" style={{ background: b.color || "#2563EB" }}>{b.name[0]}</span>
              <span className="font-semibold text-sm">{b.name}</span><span className="text-xs text-muted-foreground">{b.product_count}</span>
            </Link>
          ))}
        </div>
      </Section>
      <Section eyebrow="Services" title={t("services")}>
        <p className="-mt-5 mb-8 text-muted-foreground">{t("services_sub")}</p>
        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {(s?.services || []).map((x) => { const I = SICON[x.icon] || Plug; return (
            <div key={x.key} className="rounded-2xl border bg-card p-6 card-elev" data-testid={`service-${x.key}`}>
              <span className="h-11 w-11 rounded-xl bg-blue-50 dark:bg-blue-950 text-blue-600 grid place-items-center"><I className="h-5 w-5" /></span>
              <p className="mt-5 font-semibold">{pick(x.en, x.my)}</p>
              <Link to="/support" className="mt-3 inline-block text-sm text-blue-600 font-medium">{t("ask_quote")} →</Link>
            </div>); })}
        </div>
      </Section>
      <Section title={t("why")}>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-px bg-border rounded-2xl overflow-hidden border">
          {why.map(([I, k]) => (
            <div key={k} className="bg-card p-7"><I className="h-6 w-6 text-blue-600" /><p className="mt-5 font-semibold">{t(k)}</p><p className="mt-2 text-sm text-muted-foreground">{t(k + "d")}</p></div>
          ))}
        </div>
      </Section>
      <Section eyebrow={t("help_center")} title={t("faq")} id="faq">
        <Accordion type="single" collapsible className="max-w-3xl">
          {(s?.faq || []).map((f, i) => (
            <AccordionItem key={i} value={`f${i}`}><AccordionTrigger data-testid={`faq-item-${i}`} className="text-left">{pick(f.q_en, f.q_my)}</AccordionTrigger><AccordionContent className="text-muted-foreground">{pick(f.a_en, f.a_my)}</AccordionContent></AccordionItem>
          ))}
        </Accordion>
      </Section>
    </div>
  );
}
