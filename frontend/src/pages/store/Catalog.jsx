import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useInfiniteQuery } from "@tanstack/react-query";
import { SlidersHorizontal, PackageSearch } from "lucide-react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useBrands, useCategories } from "@/lib/hooks";
import ProductCard, { CardSkeleton } from "@/components/store/ProductCard";

const Select = ({ label, value, onChange, options, testid }) => (
  <label className="block">
    <span className="text-xs font-semibold text-muted-foreground">{label}</span>
    <select data-testid={testid} value={value} onChange={(e) => onChange(e.target.value)} className="mt-1 w-full h-10 rounded-lg border bg-background px-3 text-sm">
      {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  </label>
);

export default function Catalog({ promo = false }) {
  const { t, pick } = useI18n();
  const [sp, setSp] = useSearchParams();
  const { data: brands = [] } = useBrands();
  const { data: cats = [] } = useCategories();
  const [q, setQ] = useState(sp.get("q") || "");
  const [showF, setShowF] = useState(false);
  const f = { q: sp.get("q") || "", brand: sp.get("brand") || "", category: sp.get("category") || "", min_price: sp.get("min_price") || "",
    max_price: sp.get("max_price") || "", in_stock: sp.get("in_stock") === "true", sort: sp.get("sort") || "newest", promo: promo || sp.get("promo") === "true" };
  const set = (k, v) => { const n = new URLSearchParams(sp); if (v === "" || v === false) n.delete(k); else n.set(k, v); setSp(n, { replace: true }); };
  useEffect(() => { setQ(sp.get("q") || ""); }, [sp]);
  useEffect(() => { const h = setTimeout(() => { if (q !== f.q) set("q", q); }, 350); return () => clearTimeout(h); }, [q]); // eslint-disable-line

  const params = new URLSearchParams(Object.entries(f).filter(([, v]) => v !== "" && v !== false));
  const query = useInfiniteQuery({
    queryKey: ["catalog", params.toString()],
    queryFn: ({ pageParam = 1 }) => api.get(`/products?${params}&page=${pageParam}&limit=12`).then((r) => r.data),
    getNextPageParam: (last) => (last.page < last.pages ? last.page + 1 : undefined), initialPageParam: 1,
  });
  const items = query.data?.pages.flatMap((p) => p.items) || [];
  const total = query.data?.pages[0]?.total ?? 0;
  const cat = cats.find((c) => c.slug === f.category);
  const title = promo ? t("promotions") : cat ? pick(cat.name, cat.name_my) : t("all_products");

  return (
    <div className="container-x py-10">
      <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight" data-testid="catalog-title">{title}</h1>
      <p className="mt-2 text-sm text-muted-foreground" data-testid="catalog-count">{total} {t("results")}</p>
      <div className="mt-8 grid lg:grid-cols-[260px_1fr] gap-4 lg:gap-8">
        <button data-testid="toggle-filters-btn" onClick={() => setShowF(!showF)} className="lg:hidden h-10 rounded-xl border font-semibold text-sm inline-flex items-center justify-center gap-2"><SlidersHorizontal className="h-4 w-4" />Filters</button>
        <aside className={`${showF ? "block" : "hidden"} lg:block space-y-4 lg:sticky lg:top-32 self-start rounded-2xl border p-5 bg-card`} data-testid="catalog-filters">
          <p className="flex items-center gap-2 font-semibold text-sm"><SlidersHorizontal className="h-4 w-4" />Filters</p>
          <input data-testid="catalog-search-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("search")} className="w-full h-10 rounded-lg border bg-background px-3 text-sm" />
          <Select testid="filter-category" label={t("category")} value={f.category} onChange={(v) => set("category", v)} options={[["", t("all")], ...cats.map((c) => [c.slug, pick(c.name, c.name_my)])]} />
          <Select testid="filter-brand" label={t("brand")} value={f.brand} onChange={(v) => set("brand", v)} options={[["", t("all")], ...brands.map((b) => [b.slug, b.name])]} />
          <div className="grid grid-cols-2 gap-2">
            <input data-testid="filter-min-price" type="number" min="0" value={f.min_price} onChange={(e) => set("min_price", e.target.value)} placeholder={t("min")} className="h-10 rounded-lg border bg-background px-3 text-sm" />
            <input data-testid="filter-max-price" type="number" min="0" value={f.max_price} onChange={(e) => set("max_price", e.target.value)} placeholder={t("max")} className="h-10 rounded-lg border bg-background px-3 text-sm" />
          </div>
          <label className="flex items-center gap-2 text-sm"><input data-testid="filter-in-stock" type="checkbox" checked={f.in_stock} onChange={(e) => set("in_stock", e.target.checked ? "true" : "")} />{t("only_in_stock")}</label>
          {!promo && <label className="flex items-center gap-2 text-sm"><input data-testid="filter-promo" type="checkbox" checked={f.promo} onChange={(e) => set("promo", e.target.checked ? "true" : "")} />{t("only_promo")}</label>}
          <Select testid="sort-select" label={t("sort")} value={f.sort} onChange={(v) => set("sort", v)} options={[["newest", t("newest")], ["popular", t("popular_sort")], ["price_asc", t("price_asc")], ["price_desc", t("price_desc")]]} />
          <button data-testid="clear-filters-btn" onClick={() => setSp({})} className="text-sm text-blue-600 font-medium">{t("clear")}</button>
        </aside>
        <div>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5" data-testid="catalog-grid">
            {query.isLoading ? Array.from({ length: 6 }).map((_, i) => <CardSkeleton key={i} />) : items.map((p, i) => <ProductCard key={p.id} p={p} i={i % 12} />)}
          </div>
          {!query.isLoading && !items.length && (
            <div className="rounded-2xl border border-dashed p-16 text-center" data-testid="catalog-empty">
              <PackageSearch className="mx-auto h-10 w-10 text-muted-foreground" /><p className="mt-4 text-muted-foreground">{t("no_results")}</p>
            </div>
          )}
          {query.hasNextPage && (
            <div className="mt-10 text-center"><button data-testid="load-more-btn" onClick={() => query.fetchNextPage()} disabled={query.isFetchingNextPage} className="h-11 px-8 rounded-full border-2 font-semibold hover:bg-slate-50">{query.isFetchingNextPage ? "…" : t("load_more")}</button></div>
          )}
        </div>
      </div>
    </div>
  );
}
