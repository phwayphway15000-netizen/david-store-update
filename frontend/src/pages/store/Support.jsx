import { Phone, Mail, Facebook, Send, Bot } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { useSettings } from "@/lib/hooks";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";

export default function Support() {
  const { t, pick } = useI18n();
  const { data: s } = useSettings();
  const c = s?.contacts || {};
  const items = [[Send, "Telegram Bot", s?.telegram_bot_url, s?.telegram_bot_url], [Facebook, "Messenger / Facebook", s?.messenger_url || c.facebook, c.facebook],
    [Send, "Telegram Channel", c.telegram_channel, c.telegram_channel], [Phone, c.phone, c.phone && `tel:${c.phone}`, c.phone], [Mail, c.email, null, c.email]];
  return (
    <div className="container-x py-12">
      <p className="eyebrow">{t("help_center")}</p>
      <h1 className="mt-2 text-4xl font-extrabold tracking-tight">{t("support")}</h1>
      <p className="mt-3 text-muted-foreground max-w-xl">{t("no_pw")}</p>
      <div className="mt-10 grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {items.filter((x) => x[3]).map(([I, label, href], i) => (
          <a key={i} href={href || undefined} target="_blank" rel="noreferrer" data-testid={`support-contact-${i}`} className="rounded-2xl border bg-card p-6 card-elev flex items-center gap-4">
            <span className="h-11 w-11 rounded-xl bg-blue-50 dark:bg-blue-950 text-blue-600 grid place-items-center"><I className="h-5 w-5" /></span>
            <span className="font-semibold text-sm break-all">{label}</span>
          </a>
        ))}
      </div>
      <h2 className="mt-16 text-2xl font-bold">{t("faq")}</h2>
      <Accordion type="single" collapsible className="mt-4 max-w-3xl">
        {(s?.faq || []).map((f, i) => (
          <AccordionItem key={i} value={`f${i}`}><AccordionTrigger className="text-left" data-testid={`support-faq-${i}`}>{pick(f.q_en, f.q_my)}</AccordionTrigger><AccordionContent className="text-muted-foreground">{pick(f.a_en, f.a_my)}</AccordionContent></AccordionItem>
        ))}
      </Accordion>
    </div>
  );
}

export { Bot };
