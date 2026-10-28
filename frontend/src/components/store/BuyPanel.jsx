import { useState } from "react";
import { Send, MessageCircle, Headphones, Copy, Check, ShieldCheck, Facebook } from "lucide-react";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { api, errMsg, BACKEND } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { mmk } from "@/lib/fmt";
import { StockBadge } from "./ProductCard";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export default function BuyPanel({ p, settings }) {
  const { t } = useI18n();
  const first = p.variants.find((v) => v.available) || p.variants[0];
  const [vid, setVid] = useState(first?.id);
  const [busy, setBusy] = useState("");
  const [msgr, setMsgr] = useState(null);
  const [name, setName] = useState("");
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const v = p.variants.find((x) => x.id === vid) || first;

  const buyTelegram = async () => {
    setBusy("tg");
    const win = window.open("", "_blank");
    try {
      const { data } = await api.post("/checkout/telegram", { product_id: p.id, variant_id: v.id });
      if (win) win.location.href = data.deep_link; else window.location.href = data.deep_link;
    } catch (e) {
      win?.close();
      toast.error(errMsg(e));
    } finally { setBusy(""); }
  };
  const createRef = async () => {
    setBusy("ms");
    try {
      const { data } = await api.post("/checkout/messenger", { product_id: p.id, variant_id: v.id, customer_name: name });
      setMsgr(data);
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };
  const copy = async () => {
    await navigator.clipboard.writeText(msgr.summary).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };
  const share = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(`${BACKEND}/api/og/product/${p.slug}`)}`;

  return (
    <div className="rounded-2xl border bg-card p-6 card-elev !transform-none" data-testid="buy-panel">
      <p className="text-sm font-semibold mb-3">{t("choose_plan")}</p>
      <div className="grid gap-2">
        {p.variants.map((x) => (
          <button key={x.id} data-testid={`variant-option-${x.id}`} onClick={() => setVid(x.id)} disabled={!x.available}
            className={`text-left rounded-xl border-2 px-4 py-3 transition-colors flex justify-between gap-3 ${x.id === vid ? "border-blue-600 bg-blue-50/60 dark:bg-blue-950/30" : "border-transparent bg-slate-50 dark:bg-slate-900 hover:border-slate-300"} ${!x.available ? "opacity-50 cursor-not-allowed" : ""}`}>
            <span><span className="block font-semibold text-sm">{x.name}</span><span className="text-xs text-muted-foreground">{x.duration}</span></span>
            <span className="text-right"><span className="block font-display font-bold">{mmk(x.effective_price_mmk)}</span>
              {x.promo_active && <span className="text-xs text-muted-foreground line-through">{mmk(x.price_mmk)}</span>}</span>
          </button>
        ))}
      </div>
      {v && (
        <div className="mt-5 flex items-end justify-between">
          <div>
            <p className="text-xs text-muted-foreground">{t("price")}</p>
            <p className="font-display text-3xl font-extrabold text-[#0A1128] dark:text-white" data-testid="selected-price">{mmk(v.effective_price_mmk)}</p>
            {v.promo_active && <p className="text-xs text-rose-600 font-semibold">{t("save")} {v.discount_percent}% {v.promo_end ? `· ${t("ends")} ${new Date(v.promo_end).toLocaleDateString()}` : ""}</p>}
          </div>
          <StockBadge label={v.stock_label} />
        </div>
      )}
      {v?.stock_checked_at && <p className="mt-2 text-[11px] text-muted-foreground">{t("stock_checked")}: {new Date(v.stock_checked_at).toLocaleString()}</p>}
      <div className="mt-5 grid gap-2.5">
        <button data-testid="buy-telegram-btn" onClick={buyTelegram} disabled={!v?.available || busy || !settings?.telegram_checkout_enabled}
          className="h-12 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold inline-flex items-center justify-center gap-2 transition-colors active:scale-[.98]">
          <Send className="h-4 w-4" /> {busy === "tg" ? "…" : t("buy_tg")}
        </button>
        {!settings?.telegram_checkout_enabled && <p className="text-xs text-amber-700" data-testid="telegram-off-note">{t("tg_off")}</p>}
        <button data-testid="order-messenger-btn" onClick={() => { setMsgr(null); setOpen(true); }} disabled={!v?.available}
          className="h-12 rounded-xl border-2 border-[#0A1128] dark:border-slate-600 hover:bg-[#0A1128] hover:text-white disabled:opacity-50 font-semibold inline-flex items-center justify-center gap-2 transition-colors">
          <MessageCircle className="h-4 w-4" /> {t("order_msgr")}
        </button>
        <div className="flex gap-2">
          <Link to="/support" data-testid="contact-support-btn" className="flex-1 h-10 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-sm font-medium inline-flex items-center justify-center gap-2"><Headphones className="h-4 w-4" />{t("contact_support")}</Link>
          <a href={share} target="_blank" rel="noreferrer" data-testid="share-facebook-btn" className="h-10 px-4 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 inline-flex items-center" aria-label={t("share")}><Facebook className="h-4 w-4" /></a>
        </div>
      </div>
      <p className="mt-4 text-xs text-muted-foreground flex gap-1.5"><ShieldCheck className="h-4 w-4 text-emerald-600 shrink-0" />{t("no_pw")}</p>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="messenger-dialog">
          <DialogHeader><DialogTitle>{t("order_msgr")}</DialogTitle></DialogHeader>
          {!msgr ? (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">{p.name} · {v?.name} · <b>{mmk(v?.effective_price_mmk)}</b></p>
              <input data-testid="messenger-name-input" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder={t("name_optional")} className="w-full h-11 rounded-xl border px-4 text-sm bg-transparent" />
              <button data-testid="messenger-create-ref-btn" onClick={createRef} disabled={busy === "ms"} className="w-full h-11 rounded-xl bg-blue-600 text-white font-semibold">{busy === "ms" ? "…" : t("create_ref")}</button>
            </div>
          ) : (
            <div className="space-y-4">
              <pre data-testid="messenger-summary" className="whitespace-pre-wrap text-sm bg-slate-50 dark:bg-slate-900 rounded-xl p-4 font-mono">{msgr.summary}</pre>
              <p className="text-xs text-muted-foreground">{t("msgr_hint")}</p>
              <div className="grid grid-cols-2 gap-2">
                <button data-testid="messenger-copy-btn" onClick={copy} className="h-11 rounded-xl border font-semibold inline-flex items-center justify-center gap-2">{copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}{copied ? t("copied") : t("copy")}</button>
                <a data-testid="messenger-open-btn" href={msgr.messenger_url} target="_blank" rel="noreferrer" className="h-11 rounded-xl bg-blue-600 text-white font-semibold inline-flex items-center justify-center gap-2"><MessageCircle className="h-4 w-4" />{t("open_msgr")}</a>
              </div>
              <Link data-testid="messenger-track-link" to={`/track?ref=${msgr.order_ref}&token=${msgr.track_token}`} className="block text-center text-sm text-blue-600 underline">{t("track")} — {msgr.order_ref}</Link>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
