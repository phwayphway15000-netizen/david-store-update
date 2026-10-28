import { useEffect, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { Search, Menu, Moon, Sun, Send, X } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { useCategories, useSettings } from "@/lib/hooks";
import { imgUrl } from "@/lib/api";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";

export const Logo = ({ settings }) => (
  <Link to="/" data-testid="nav-logo" className="flex items-center gap-2.5 shrink-0">
    {settings?.logo_url ? (
      <img src={imgUrl(settings.logo_url)} alt={settings.brand_name} className="h-9 w-auto" />
    ) : (
      <img src="/logo-mark.png" alt="AI Tools By David Digital Store logo" data-testid="nav-logo-img" className="h-12 w-12 object-contain drop-shadow-md" />
    )}
    <span className="leading-tight">
      <span className="block font-display font-bold text-[15px] text-[#0A1128] dark:text-white">AI Tools By David</span>
      <span className="block text-[10px] uppercase tracking-[0.18em] text-blue-600 font-bold">Digital Store</span>
    </span>
  </Link>
);

function useDark() {
  const [dark, setDark] = useState(() => localStorage.getItem("theme") === "dark");
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);
  return [dark, setDark];
}

const LangSwitch = () => {
  const { lang, setLang } = useI18n();
  return (
    <div className="flex rounded-full border p-0.5 text-xs font-bold" data-testid="lang-switch">
      {["my", "en"].map((l) => (
        <button key={l} data-testid={`lang-${l}`} onClick={() => setLang(l)}
          className={`px-2.5 py-1 rounded-full transition-colors ${lang === l ? "bg-[#0A1128] text-white dark:bg-blue-600" : "text-muted-foreground"}`}>
          {l === "my" ? "MM" : "EN"}
        </button>
      ))}
    </div>
  );
};

export default function Navbar() {
  const { t, pick } = useI18n();
  const { data: cats = [] } = useCategories();
  const { data: settings } = useSettings();
  const [dark, setDark] = useDark();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const links = [{ to: "/", label: t("home") }, { to: "/products", label: t("all_products") },
    ...cats.map((c) => ({ to: `/products?category=${c.slug}`, label: pick(c.name, c.name_my), key: c.slug })),
    { to: "/promotions", label: t("promotions") }, { to: "/support", label: t("support") }];
  const submit = (e) => { e.preventDefault(); nav(`/products?q=${encodeURIComponent(q)}`); setOpen(false); };

  return (
    <header className="sticky top-0 z-40 backdrop-blur-md bg-white/85 dark:bg-slate-950/85 border-b border-slate-200/80 dark:border-slate-800">
      <div className="container-x flex items-center gap-4 h-16">
        <Logo settings={settings} />
        <form onSubmit={submit} className="hidden md:flex flex-1 max-w-md mx-auto relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input data-testid="nav-search-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("search")}
            className="w-full h-10 rounded-full bg-slate-100 dark:bg-slate-900 pl-9 pr-4 text-sm outline-none focus:ring-2 focus:ring-blue-500" />
        </form>
        <div className="ml-auto flex items-center gap-2">
          <LangSwitch />
          <button data-testid="theme-toggle" aria-label="Toggle dark mode" onClick={() => setDark(!dark)} className="h-9 w-9 grid place-items-center rounded-full hover:bg-slate-100 dark:hover:bg-slate-800">
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
          {settings?.telegram_bot_url && (
            <a href={settings.telegram_bot_url} target="_blank" rel="noreferrer" data-testid="nav-telegram-btn"
              className="hidden sm:inline-flex items-center gap-1.5 h-9 px-4 rounded-full bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold transition-colors">
              <Send className="h-4 w-4" /> Telegram
            </a>
          )}
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
              <button data-testid="nav-mobile-menu" className="lg:hidden h-9 w-9 grid place-items-center rounded-full hover:bg-slate-100 dark:hover:bg-slate-800" aria-label="Menu"><Menu className="h-5 w-5" /></button>
            </SheetTrigger>
            <SheetContent side="right" className="w-80">
              <form onSubmit={submit} className="mt-8 mb-4">
                <input data-testid="mobile-search-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("search")}
                  className="w-full h-11 rounded-xl bg-slate-100 dark:bg-slate-900 px-4 text-sm outline-none" />
              </form>
              <nav className="flex flex-col">
                {links.map((l) => (
                  <Link key={l.to} to={l.to} onClick={() => setOpen(false)} className="py-3 border-b text-sm font-medium" data-testid={`mobile-nav-${l.key || l.to.replace(/\W/g, "") || "home"}`}>{l.label}</Link>
                ))}
              </nav>
            </SheetContent>
          </Sheet>
        </div>
      </div>
      <nav className="hidden lg:block border-t border-slate-100 dark:border-slate-800">
        <div className="container-x flex items-center gap-1 h-11 overflow-x-auto no-scrollbar">
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} end data-testid={`nav-link-${l.key || l.to.replace(/\W/g, "") || "home"}`}
              className="px-3 py-1.5 rounded-full text-[13px] font-medium whitespace-nowrap text-slate-600 dark:text-slate-300 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-slate-800 transition-colors">
              {l.label}
            </NavLink>
          ))}
        </div>
      </nav>
    </header>
  );
}

export { X };
