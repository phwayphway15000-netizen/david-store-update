import { Link } from "react-router-dom";
import { Phone, Mail, Facebook, Send, Bot } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { useSettings } from "@/lib/hooks";

export default function Footer() {
  const { t, pick } = useI18n();
  const { data: s } = useSettings();
  const c = s?.contacts || {};
  const pol = [["about", t("about")], ["privacy", t("privacy")], ["terms", t("terms")], ["refund", t("refund")],
    ["delivery", t("delivery_policy")], ["warranty", t("warranty_terms")]];
  return (
    <footer className="bg-[#0A1128] text-slate-300 mt-24" data-testid="site-footer">
      <div className="container-x py-14 grid gap-10 md:grid-cols-4">
        <div className="md:col-span-2 max-w-sm">
          <p className="font-display text-white text-xl font-bold flex items-center gap-3"><img src="/logo-mark.png" alt="logo" className="h-14 w-14 object-contain" data-testid="footer-logo" />{s?.brand_name}</p>
          <p className="mt-3 text-sm text-slate-400">{pick(s?.tagline_en, s?.tagline_my)}</p>
          <p className="mt-6 text-xs text-slate-500">{t("disclaimer")}</p>
        </div>
        <div>
          <p className="text-white font-semibold mb-4">{t("policies")}</p>
          <ul className="space-y-2 text-sm">
            {pol.map(([k, l]) => <li key={k}><Link data-testid={`footer-policy-${k}`} to={`/policies/${k}`} className="hover:text-white transition-colors">{l}</Link></li>)}
          </ul>
        </div>
        <div>
          <p className="text-white font-semibold mb-4">{t("contact")}</p>
          <ul className="space-y-3 text-sm">
            {c.phone && <li className="flex gap-2 items-center"><Phone className="h-4 w-4" /><a data-testid="footer-phone" href={`tel:${c.phone}`}>{c.phone}</a></li>}
            {c.email && <li className="flex gap-2 items-center"><Mail className="h-4 w-4" /><span data-testid="footer-email">{c.email}</span></li>}
            {c.facebook && <li className="flex gap-2 items-center"><Facebook className="h-4 w-4" /><a data-testid="footer-facebook" href={c.facebook} target="_blank" rel="noreferrer" className="hover:text-white">Facebook Page</a></li>}
            {c.telegram_channel && <li className="flex gap-2 items-center"><Send className="h-4 w-4" /><a data-testid="footer-telegram-channel" href={c.telegram_channel} target="_blank" rel="noreferrer" className="hover:text-white">Telegram Channel</a></li>}
            {s?.telegram_bot_url && <li className="flex gap-2 items-center"><Bot className="h-4 w-4" /><a data-testid="footer-telegram-bot" href={s.telegram_bot_url} target="_blank" rel="noreferrer" className="hover:text-white">Telegram Bot</a></li>}
          </ul>
        </div>
      </div>
      <div className="border-t border-white/10">
        <div className="container-x py-5 text-xs text-slate-500 flex flex-wrap justify-between gap-2">
          <span>© {new Date().getFullYear()} {s?.brand_name}</span>
          <Link to="/track" data-testid="footer-track-link" className="hover:text-white">{t("track")}</Link>
        </div>
      </div>
    </footer>
  );
}
