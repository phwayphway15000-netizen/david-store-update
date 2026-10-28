import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { CheckCircle2, XCircle } from "lucide-react";
import { api, errMsg, imgUrl } from "@/lib/api";
import { PageHeader, Card, Field, inp, btnPrimary, btnGhost } from "@/components/admin/ui";

const POL = ["about", "privacy", "terms", "refund", "delivery", "warranty"];
const Ok = ({ v }) => (v ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <XCircle className="h-4 w-4 text-rose-500" />);

function Integrations() {
  const { data, refetch } = useQuery({ queryKey: ["integrations"], queryFn: () => api.get("/admin/integrations").then((r) => r.data) });
  const call = async (url, msg) => { try { await api.post(url); toast.success(msg); refetch(); } catch (e) { toast.error(errMsg(e)); } };
  if (!data) return null;
  const tg = data.telegram;
  return (
    <Card className="space-y-3" data-testid="integrations-card">
      <p className="font-semibold">Telegram bot</p>
      <ul className="text-sm space-y-1.5">
        <li className="flex items-center gap-2"><Ok v={tg.configured} />Bot token & username {tg.bot_username && `(@${tg.bot_username})`}</li>
        <li className="flex items-center gap-2"><Ok v={tg.owner_configured} />Owner Telegram user ID</li>
        <li className="flex items-center gap-2"><Ok v={!!tg.webhook?.url} />Webhook {tg.webhook?.url && <span className="text-xs font-mono break-all">{tg.webhook.url}</span>}</li>
        {tg.webhook?.last_error_message && <li className="text-xs text-rose-600">Last webhook error: {tg.webhook.last_error_message}</li>}
      </ul>
      <div className="flex flex-wrap gap-2">
        <button className={btnGhost} onClick={() => call("/admin/integrations/telegram/webhook", "Webhook registered")} data-testid="register-webhook-btn">Register webhook</button>
        <button className={btnGhost} onClick={() => call("/admin/integrations/telegram/test", "Test message sent to owner")} data-testid="test-telegram-btn">Send test message to owner</button>
      </div>
      <p className="font-semibold pt-3">Messenger</p>
      <p className="text-sm">Mode: Click-to-Messenger with copyable order reference. Official Messenger Platform API connector: <b>disabled</b>.</p>
      <p className="text-xs text-muted-foreground">To enable the official connector later you will need:</p>
      <ul className="text-xs list-disc ml-5 text-muted-foreground">{data.messenger.checklist.map((c) => <li key={c}>{c}</li>)}</ul>
    </Card>
  );
}

export default function Settings() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["admin-settings"], queryFn: () => api.get("/admin/settings").then((r) => r.data) });
  const [f, setF] = useState(null);
  useEffect(() => { if (data) setF({ ...data, faq: (data.faq || []).map((q) => ({ ...q, _k: q._k || Math.random().toString(36).slice(2) })) }); }, [data]);
  if (!f) return <p className="text-sm">Loading…</p>;
  const u = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const nested = (k, sub, v) => setF((x) => ({ ...x, [k]: { ...x[k], [sub]: v } }));
  const save = async () => {
    try { await api.put("/admin/settings", f); toast.success("Settings saved"); qc.invalidateQueries({ queryKey: ["settings"] }); } catch (e) { toast.error(errMsg(e)); }
  };
  const uploadLogo = async (e) => {
    const fd = new FormData(); fd.append("file", e.target.files[0]);
    try { const { data: d } = await api.post("/admin/uploads/image", fd); u("logo_url", d.url); } catch (er) { toast.error(errMsg(er)); }
  };
  const faq = (i, k, v) => u("faq", f.faq.map((x, j) => (j === i ? { ...x, [k]: v } : x)));
  return (
    <div className="space-y-6">
      <PageHeader title="Settings"><button className={btnPrimary} onClick={save} data-testid="settings-save-btn">Save settings</button></PageHeader>
      <div className="grid xl:grid-cols-2 gap-6">
        <Card className="space-y-3">
          <p className="font-semibold">Brand</p>
          <Field label="Store name"><input data-testid="settings-brand-name" className={inp} value={f.brand_name} onChange={(e) => u("brand_name", e.target.value)} /></Field>
          <Field label="Logo">{f.logo_url && <img src={imgUrl(f.logo_url)} alt="" className="h-10 mb-2" />}<input type="file" accept="image/*" onChange={uploadLogo} className="text-xs" data-testid="settings-logo-input" /></Field>
          <Field label="Tagline (EN)"><input className={inp} value={f.tagline_en} onChange={(e) => u("tagline_en", e.target.value)} /></Field>
          <Field label="Tagline (MM)"><input className={inp} value={f.tagline_my} onChange={(e) => u("tagline_my", e.target.value)} /></Field>
          <p className="font-semibold pt-2">Contacts</p>
          {["phone", "email", "facebook", "telegram_channel", "address"].map((k) => <Field key={k} label={k.replace("_", " ")}><input data-testid={`settings-contact-${k}`} className={inp} value={f.contacts?.[k] || ""} onChange={(e) => nested("contacts", k, e.target.value)} /></Field>)}
          <Field label="Messenger link (m.me/yourpage recommended for ref attribution)"><input data-testid="settings-messenger-url" className={inp} value={f.messenger_url || ""} onChange={(e) => u("messenger_url", e.target.value)} /></Field>
        </Card>
        <div className="space-y-6">
          <Integrations />
          <Card className="space-y-3">
            <p className="font-semibold">Homepage hero</p>
            {["badge_en", "badge_my", "title_en", "title_my", "subtitle_en", "subtitle_my"].map((k) => <Field key={k} label={k}><input data-testid={`settings-hero-${k}`} className={inp} value={f.hero?.[k] || ""} onChange={(e) => nested("hero", k, e.target.value)} /></Field>)}
          </Card>
        </div>
      </div>
      <Card className="space-y-4">
        <p className="font-semibold">Policies</p>
        {POL.map((k) => (
          <div key={k} className="grid md:grid-cols-2 gap-3">
            <Field label={`${k} (EN)`}><textarea data-testid={`settings-policy-${k}-en`} className={inp + " h-28 py-2"} value={f.policies?.[k]?.en || ""} onChange={(e) => u("policies", { ...f.policies, [k]: { ...f.policies[k], en: e.target.value } })} /></Field>
            <Field label={`${k} (MM)`}><textarea className={inp + " h-28 py-2"} value={f.policies?.[k]?.my || ""} onChange={(e) => u("policies", { ...f.policies, [k]: { ...f.policies[k], my: e.target.value } })} /></Field>
          </div>
        ))}
      </Card>
      <Card className="space-y-4">
        <div className="flex justify-between"><p className="font-semibold">FAQ</p><button className={btnGhost} onClick={() => u("faq", [...f.faq, { _k: Math.random().toString(36).slice(2), q_en: "", q_my: "", a_en: "", a_my: "" }])} data-testid="faq-add-btn">Add question</button></div>
        {f.faq.map((q, i) => (
          <div key={q._k} className="grid md:grid-cols-2 gap-2 border-b pb-4">
            <input className={inp} placeholder="Question EN" value={q.q_en} onChange={(e) => faq(i, "q_en", e.target.value)} />
            <input className={inp} placeholder="Question MM" value={q.q_my} onChange={(e) => faq(i, "q_my", e.target.value)} />
            <textarea className={inp + " h-20 py-2"} placeholder="Answer EN" value={q.a_en} onChange={(e) => faq(i, "a_en", e.target.value)} />
            <textarea className={inp + " h-20 py-2"} placeholder="Answer MM" value={q.a_my} onChange={(e) => faq(i, "a_my", e.target.value)} />
            <button className="text-xs text-rose-600 text-left" onClick={() => u("faq", f.faq.filter((_, j) => j !== i))}>Remove</button>
          </div>
        ))}
      </Card>
    </div>
  );
}
