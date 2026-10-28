import hashlib
import secrets
from datetime import timedelta

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from core import db, now, now_iso, new_id, put_object, APP_NAME, audit, logger
from catalog import effective_price
import orders as O
import tg_api
from tg_api import esc, send, notify_owner, owner_id

OWNER_CMDS = {"/admin", "/pending", "/orders", "/paymentreview", "/deliverypending", "/order", "/stats"}
STATUS_MM = {"AWAITING_PAYMENT": "ငွေပေးချေရန်စောင့်ဆိုင်းနေသည်", "PAYMENT_SUBMITTED": "ငွေလွှဲအထောက်အထား ပို့ပြီး",
             "PAYMENT_UNDER_REVIEW": "စစ်ဆေးနေသည်", "PAYMENT_REJECTED": "အတည်မပြုနိုင်ပါ",
             "PAID_AWAITING_FULFILLMENT": "ငွေရပြီး၊ ပို့ဆောင်ရန်ပြင်ဆင်နေသည်", "FULFILLMENT_IN_PROGRESS": "ပို့ဆောင်နေသည်",
             "DELIVERED": "ပို့ဆောင်ပြီး", "COMPLETED": "ပြီးဆုံး", "CANCELLED": "ပယ်ဖျက်ပြီး"}


def is_owner(uid):
    return bool(owner_id()) and str(uid) == owner_id()


def owner_actor(frm):
    return {"type": "telegram_owner", "id": str(frm["id"]), "name": frm.get("username") or frm.get("first_name")}


def mmk(n):
    return f"{int(n or 0):,} MMK"


def token_hash(t):
    return hashlib.sha256(t.encode()).hexdigest()


async def create_intent(product_id, variant_id, source="website"):
    token = secrets.token_urlsafe(24)
    intent = {"id": secrets.token_urlsafe(8), "token_hash": token_hash(token), "product_id": product_id,
              "variant_id": variant_id, "status": "ACTIVE", "channel": "telegram", "source": source,
              "created_at": now_iso(), "expires_at": (now() + timedelta(minutes=30)).isoformat()}
    await db.checkout_intents.insert_one(intent)
    return token, intent


def order_summary(o, admin=False):
    it = o["items"][0]
    lines = [f"🧾 <b>{o['ref']}</b>", f"{esc(it.get('brand_name') or '')} {esc(it['product_name'])}",
             f"Plan: {esc(it['variant_name'])} {('· ' + esc(it['duration'])) if it.get('duration') else ''}",
             f"Price: <b>{mmk(o['total_mmk'])}</b>", f"Status: <b>{o['status']}</b>"]
    if not admin and o["status"] in STATUS_MM:
        lines.append(STATUS_MM[o["status"]])
    if admin:
        lines.append(f"Source: {o['source']} · Customer: {esc(o.get('customer_name') or o.get('channel_id') or '-')}")
    return "\n".join(lines)


def admin_buttons(o):
    r, s = o["ref"], o["status"]
    rows = [[("👁 View", f"a:view:{r}")]]
    if s in {"PAYMENT_SUBMITTED", "PAYMENT_UNDER_REVIEW"}:
        rows.append([("✅ Approve", f"a:approve:{r}"), ("❌ Reject", f"a:reject:{r}")])
        rows.append([("📎 Request evidence", f"a:moreev:{r}")])
    if s == "PAID_AWAITING_FULFILLMENT":
        rows.append([("⏳ Mark delivery pending", f"a:dpend:{r}")])
    if s in {"PAID_AWAITING_FULFILLMENT", "FULFILLMENT_IN_PROGRESS"}:
        rows.append([("🚚 Send Delivery", f"a:deliver:{r}")])
    if s == "DELIVERED":
        rows.append([("🏁 Complete", f"a:complete:{r}")])
    if s in O.TRANSITIONS and "CANCELLED" in O.TRANSITIONS[s]:
        rows.append([("🛑 Cancel", f"a:cancel:{r}")])
    return rows


async def set_session(chat_id, mode, order_id=None):
    await db.telegram_sessions.update_one({"chat_id": str(chat_id)},
                                          {"$set": {"mode": mode, "order_id": order_id, "updated_at": now_iso()}}, upsert=True)


async def handle_update(upd):
    try:
        await db.telegram_events.insert_one({"update_id": upd.get("update_id"), "received_at": now_iso(),
                                             "kind": "callback" if "callback_query" in upd else "message"})
    except DuplicateKeyError:
        return "duplicate"
    try:
        if "callback_query" in upd:
            await on_callback(upd["callback_query"])
        elif "message" in upd:
            await on_message(upd["message"])
    except O.OrderError as e:
        chat = (upd.get("message") or upd.get("callback_query", {}).get("message") or {}).get("chat", {}).get("id")
        if chat:
            await send(chat, f"⚠️ {esc(str(e))}")
    return "ok"


async def on_message(msg):
    chat_id = str(msg["chat"]["id"])
    frm = msg.get("from", {})
    text = (msg.get("text") or "").strip()
    if msg["chat"].get("type") != "private":
        return
    cmd = text.split()[0].split("@")[0].lower() if text.startswith("/") else None
    if cmd == "/start":
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            return await resolve_intent(parts[1].strip(), chat_id, frm)
        return await welcome(chat_id, frm)
    if cmd in OWNER_CMDS and is_owner(frm.get("id")):
        return await owner_command(cmd, text, chat_id)
    if cmd == "/admin":
        return await send(chat_id, "⛔ This command is restricted.")
    if cmd == "/products":
        return await list_products(chat_id)
    if cmd == "/orders":
        return await my_orders(chat_id)
    if cmd in {"/help", "/support"}:
        return await help_msg(chat_id)
    session = await db.telegram_sessions.find_one({"chat_id": chat_id}, {"_id": 0}) or {}
    if session.get("mode") == "await_delivery" and is_owner(frm.get("id")) and text:
        o = await db.orders.find_one({"id": session["order_id"]}, {"_id": 0})
        await set_session(chat_id, None)
        res = await O.deliver(o["id"], "delivery", text, owner_actor(frm))
        return await send(chat_id, f"Delivery result for {o['ref']}: <b>{res['result']}</b>", admin_buttons(res["order"]))
    if session.get("mode") == "await_reject" and is_owner(frm.get("id")) and text:
        await set_session(chat_id, None)
        o, _ = await O.reject_payment(session["order_id"], owner_actor(frm), text[:300])
        return await send(chat_id, f"Rejected {o['ref']}.", admin_buttons(o))
    if session.get("mode") == "await_evidence":
        return await receive_evidence(msg, chat_id, session["order_id"])
    await send(chat_id, "Use /products to browse, /orders to see your orders, /help for help.")


async def welcome(chat_id, frm):
    s = await db.settings.find_one({"id": "global"}, {"_id": 0}) or {}
    await send(chat_id, f"👋 မင်္ဂလာပါ! Welcome to <b>{esc(s.get('brand_name', 'AI Tools By David Digital Store'))}</b>.\n\n"
                        "/products – Browse products\n/orders – My orders\n/support – Contact support\n\n"
                        "🔒 We will never ask for your passwords or OTP codes.")


async def help_msg(chat_id):
    s = await db.settings.find_one({"id": "global"}, {"_id": 0}) or {}
    c = s.get("contacts", {})
    await send(chat_id, "🆘 <b>Support</b>\n" + "\n".join(f"{k.title()}: {esc(v)}" for k, v in c.items() if v)
               + "\n\nReply here with your Order ID and question. Never share passwords or OTP codes.")


async def list_products(chat_id):
    items = await db.products.find({"status": "published", "deleted_at": None, "available": True}, {"_id": 0}) \
        .sort("order_count", -1).limit(8).to_list(8)
    if not items:
        return await send(chat_id, "No products available right now.")
    rows = []
    for p in items:
        for v in [v for v in p["variants"] if v.get("active", True)][:2]:
            rows.append([(f"{p['name'][:28]} · {v['name'][:14]} · {effective_price(v):,}", f"b:{p['id'][:8]}:{v['id'][:8]}")])
    await send(chat_id, "🛍 <b>Popular products</b> — tap to order:", rows)


async def resolve_intent(token, chat_id, frm):
    intent = await db.checkout_intents.find_one_and_update(
        {"token_hash": token_hash(token), "status": "ACTIVE", "expires_at": {"$gt": now_iso()}},
        {"$set": {"status": "RESOLVED", "chat_id": chat_id, "resolved_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not intent:
        old = await db.checkout_intents.find_one({"token_hash": token_hash(token)}, {"_id": 0})
        if old and old.get("chat_id") == chat_id and old["status"] == "RESOLVED":
            intent = old
        else:
            return await send(chat_id, "⌛ This checkout link has expired or was already used.\n"
                                       "ဤလင့်ခ် သက်တမ်းကုန်သွားပါပြီ။ Please press Buy Now again on the website.")
    await show_confirmation(chat_id, intent)


async def show_confirmation(chat_id, intent):
    p, v = await O.load_product_variant(intent["product_id"], intent["variant_id"])
    await send(chat_id, f"🛒 <b>Confirm your order</b>\n\n{esc(p['name'])}\nPlan: {esc(v['name'])}"
                        f"{(' · ' + esc(v['duration'])) if v.get('duration') else ''}\nPrice: <b>{mmk(effective_price(v))}</b>\n\n"
                        "အော်ဒါ အတည်ပြုမလား?",
               [[("✅ Confirm order", f"c:{intent['id']}"), ("✖ Cancel", f"x:{intent['id']}")]])


async def on_callback(cq):
    data = cq.get("data", "")
    frm = cq["from"]
    chat_id = str(cq["message"]["chat"]["id"])
    await tg_api.tg_call("answerCallbackQuery", callback_query_id=cq["id"])
    kind, _, rest = data.partition(":")
    if kind == "a":
        if not is_owner(frm.get("id")):
            await audit({"type": "telegram_user", "id": str(frm.get("id"))}, "telegram.unauthorized_admin_action", "order", None, {"data": data})
            return await send(chat_id, "⛔ Unauthorized.")
        action, _, ref = rest.partition(":")
        return await owner_action(action, ref, chat_id, frm)
    if kind == "b":
        pid, _, vid = rest.partition(":")
        p = await db.products.find_one({"id": {"$regex": f"^{pid}"}, "status": "published", "deleted_at": None}, {"_id": 0})
        v = next((x for x in (p or {}).get("variants", []) if x["id"].startswith(vid)), None)
        if not p or not v:
            return await send(chat_id, "Product not available.")
        _, intent = await create_intent(p["id"], v["id"], "bot")
        await db.checkout_intents.update_one({"id": intent["id"]}, {"$set": {"status": "RESOLVED", "chat_id": chat_id}})
        return await show_confirmation(chat_id, intent)
    if kind == "x":
        await db.checkout_intents.update_one({"id": rest, "chat_id": chat_id, "status": "RESOLVED"}, {"$set": {"status": "CANCELLED"}})
        return await send(chat_id, "Order cancelled. /products to browse again.")
    if kind == "c":
        intent = await db.checkout_intents.find_one_and_update(
            {"id": rest, "chat_id": chat_id, "status": "RESOLVED"}, {"$set": {"status": "CONVERTED"}},
            projection={"_id": 0}, return_document=ReturnDocument.AFTER)
        if not intent:
            return await send(chat_id, "This order was already confirmed or cancelled. Use /orders.")
        p, v = await O.load_product_variant(intent["product_id"], intent["variant_id"])
        cid = await O.get_customer("telegram", chat_id, frm.get("first_name"), frm.get("username"))
        actor = {"type": "telegram_customer", "id": chat_id, "name": frm.get("username") or frm.get("first_name")}
        o = await O.create_order(p, v, "WEBSITE_TELEGRAM",
                                 actor, "AWAITING_PAYMENT", cid, "telegram", chat_id,
                                 customer_name=frm.get("first_name"), customer_contact=f"@{frm['username']}" if frm.get("username") else None,
                                 extra={"checkout_intent_id": intent["id"]})
        await db.checkout_intents.update_one({"id": intent["id"]}, {"$set": {"order_id": o["id"]}})
        await notify_owner("🆕 New order\n" + order_summary(o, True), [[("👁 View", f"a:view:{o['ref']}")]])
        return await show_payment_methods(chat_id, o)
    if kind == "pm":
        ref, _, mid = rest.partition(":")
        o = await db.orders.find_one({"ref": ref, "channel_id": chat_id}, {"_id": 0})
        m = await db.payment_methods.find_one({"code": mid, "enabled": True}, {"_id": 0})
        if not o or not m:
            return await send(chat_id, "Payment method unavailable.")
        if o["status"] not in {"AWAITING_PAYMENT", "PAYMENT_REJECTED"}:
            return await send(chat_id, f"Order {ref} is {o['status']}.")
        await db.orders.update_one({"id": o["id"]}, {"$set": {"payment_method_id": m["id"]}})
        await set_session(chat_id, "await_evidence", o["id"])
        return await send(chat_id, f"💳 <b>{esc(m['name'])}</b>\nAccount name: <b>{esc(m['account_name'])}</b>\n"
                                   f"Number: <code>{esc(m['account_number'])}</code>\nAmount: <b>{mmk(o['total_mmk'])}</b>\n"
                                   f"Note/Remark: <code>{o['ref']}</code>\n\n{esc(m.get('instructions') or '')}\n\n"
                                   "ငွေလွှဲပြီးပါက Transaction ID (သို့) Screenshot ကို ဤနေရာသို့ ပို့ပေးပါ။\n"
                                   "After paying, send the transaction ID or a screenshot here. Your payment stays pending until our team verifies it.")


async def show_payment_methods(chat_id, o):
    methods = await db.payment_methods.find({"enabled": True}, {"_id": 0}).sort("sort", 1).to_list(20)
    head = "✅ Order created\n" + order_summary(o)
    if not methods:
        return await send(chat_id, head + "\n\nPayment methods are being set up. Our team will contact you shortly.")
    await send(chat_id, head + "\n\nငွေပေးချေမည့်နည်းလမ်း ရွေးပါ / Choose a payment method:",
               [[(m["name"], f"pm:{o['ref']}:{m['code']}")] for m in methods])


async def receive_evidence(msg, chat_id, order_id):
    o = await db.orders.find_one({"id": order_id, "channel_id": chat_id}, {"_id": 0})
    if not o or o["status"] not in {"AWAITING_PAYMENT", "PAYMENT_REJECTED", "PAYMENT_SUBMITTED", "PAYMENT_UNDER_REVIEW"}:
        await set_session(chat_id, None)
        return await send(chat_id, "No order is waiting for payment evidence. Use /orders.")
    if await db.payment_evidence.count_documents({"order_id": order_id}) >= 6:
        return await send(chat_id, "Evidence limit reached for this order. Please contact /support.")
    ev = {"id": new_id(), "order_id": order_id, "kind": None, "reference": None, "storage_path": None,
          "content_type": None, "review_status": "pending", "submitted_via": "telegram", "created_at": now_iso()}
    if msg.get("photo") or (msg.get("document") and (msg["document"].get("mime_type") or "").startswith("image/")):
        fid = msg["photo"][-1]["file_id"] if msg.get("photo") else msg["document"]["file_id"]
        data = await tg_api.download_file(fid)
        if not data:
            return await send(chat_id, "Could not receive the image. Please try again.")
        ct = (msg.get("document") or {}).get("mime_type") or "image/jpeg"
        res = await put_object(f"{APP_NAME}/private/evidence/{order_id}/{ev['id']}.jpg", data, ct)
        ev.update(kind="screenshot", storage_path=res["path"], content_type=ct, reference=(msg.get("caption") or "")[:200] or None)
    elif msg.get("text"):
        ev.update(kind="transaction_reference", reference=msg["text"][:200])
    else:
        return await send(chat_id, "Please send a transaction ID (text) or a screenshot (photo).")
    await db.payment_evidence.insert_one(ev)
    actor = {"type": "telegram_customer", "id": chat_id}
    if o["status"] in {"AWAITING_PAYMENT", "PAYMENT_REJECTED"}:
        o, _ = await O.transition(order_id, "PAYMENT_SUBMITTED", actor, "payment_evidence_submitted", ev["kind"])
    await set_session(chat_id, None)
    await send(chat_id, f"📨 Evidence received for <b>{o['ref']}</b>.\nကျွန်ုပ်တို့ စစ်ဆေးပြီး အကြောင်းပြန်ပါမည်။ "
                        "Your payment is pending manual verification.")
    await notify_owner("🔔 <b>Payment review needed</b>\n" + order_summary(o, True)
                       + f"\nEvidence: {ev['kind']}" + (f" — <code>{esc(ev['reference'])}</code>" if ev.get("reference") else "")
                       + "\n⚠️ Evidence is not proof of receipt — check your account before approving.", admin_buttons(o))


async def my_orders(chat_id):
    items = await db.orders.find({"channel_id": chat_id, "channel": "telegram"}, {"_id": 0}).sort("created_at", -1).limit(5).to_list(5)
    if not items:
        return await send(chat_id, "You have no orders yet. /products")
    for o in items:
        if o["status"] in {"AWAITING_PAYMENT", "PAYMENT_REJECTED"}:
            await show_payment_methods(chat_id, o)
        else:
            await send(chat_id, order_summary(o))


async def find_ref(ref):
    o = await db.orders.find_one({"ref": ref.strip().upper()}, {"_id": 0})
    return o


async def owner_command(cmd, text, chat_id):
    groups = {"/pending": ["AWAITING_PAYMENT", "PAYMENT_SUBMITTED", "PAYMENT_UNDER_REVIEW", "AWAITING_CUSTOMER_CONFIRMATION"],
              "/paymentreview": ["PAYMENT_SUBMITTED", "PAYMENT_UNDER_REVIEW"],
              "/deliverypending": ["PAID_AWAITING_FULFILLMENT", "FULFILLMENT_IN_PROGRESS"], "/orders": None}
    if cmd == "/admin":
        return await send(chat_id, "🛠 <b>Owner panel</b>\n/pending\n/paymentreview\n/deliverypending\n/orders\n/order &lt;order_id&gt;\n/stats")
    if cmd == "/stats":
        counts = {s: await db.orders.count_documents({"status": s}) for s in O.STATES[2:]}
        rev = await db.orders.aggregate([{"$match": {"status": "COMPLETED"}}, {"$group": {"_id": None, "t": {"$sum": "$total_mmk"}}}]).to_list(1)
        return await send(chat_id, "📊 <b>Stats</b>\n" + "\n".join(f"{k}: {v}" for k, v in counts.items() if v)
                          + f"\nRevenue (completed): <b>{mmk(rev[0]['t'] if rev else 0)}</b>")
    if cmd == "/order":
        parts = text.split()
        o = await find_ref(parts[1]) if len(parts) > 1 else None
        if not o:
            return await send(chat_id, "Usage: /order DAV-2026-000001")
        return await send(chat_id, order_summary(o, True), admin_buttons(o))
    q = {"status": {"$in": groups[cmd]}} if groups.get(cmd) else {}
    items = await db.orders.find(q, {"_id": 0}).sort("created_at", -1).limit(10).to_list(10)
    if not items:
        return await send(chat_id, "Nothing here 🎉")
    for o in items:
        await send(chat_id, order_summary(o, True), admin_buttons(o))


async def owner_action(action, ref, chat_id, frm):
    o = await find_ref(ref)
    if not o:
        return await send(chat_id, "Order not found.")
    actor = owner_actor(frm)
    if action == "view":
        if o["status"] == "PAYMENT_SUBMITTED":
            o, _ = await O.transition(o["id"], "PAYMENT_UNDER_REVIEW", actor, "review_started")
        evs = await db.payment_evidence.find({"order_id": o["id"]}, {"_id": 0}).to_list(10)
        ev_txt = "\n".join(f"• {e['kind']}: {esc(e.get('reference') or '(image)')} [{e['review_status']}]" for e in evs) or "• none"
        return await send(chat_id, order_summary(o, True) + "\n\n<b>Evidence</b>\n" + ev_txt, admin_buttons(o))
    if action == "approve":
        return await send(chat_id, f"⚠️ Confirm you have checked your account and received <b>{mmk(o['total_mmk'])}</b> for {o['ref']}?",
                          [[("✅ Yes, approve payment", f"a:approve_yes:{ref}"), ("Back", f"a:view:{ref}")]])
    if action == "approve_yes":
        o, changed = await O.approve_payment(o["id"], actor)
        return await send(chat_id, ("Approved " if changed else "Already approved ") + o["ref"], admin_buttons(o))
    if action == "reject":
        await set_session(chat_id, "await_reject", o["id"])
        return await send(chat_id, f"Type the rejection reason for {o['ref']}:")
    if action == "moreev":
        o, _ = await O.request_more_evidence(o["id"], actor)
        return await send(chat_id, f"Requested more evidence for {o['ref']}.", admin_buttons(o))
    if action == "dpend":
        o, _ = await O.transition(o["id"], "FULFILLMENT_IN_PROGRESS", actor, "fulfillment_started")
        return await send(chat_id, f"{o['ref']} marked delivery pending.", admin_buttons(o))
    if action == "deliver":
        if o["status"] not in {"PAID_AWAITING_FULFILLMENT", "FULFILLMENT_IN_PROGRESS"}:
            return await send(chat_id, f"{o['ref']} is {o['status']}; cannot deliver.")
        if o.get("channel") != "telegram":
            return await send(chat_id, f"{o['ref']} came from {o['source']}. Deliver it from the web admin (manual handoff).")
        await set_session(chat_id, "await_delivery", o["id"])
        return await send(chat_id, f"Send the delivery content (license / activation link / instructions) for {o['ref']} as your next message.")
    if action == "complete":
        o, _ = await O.complete(o["id"], actor)
        return await send(chat_id, f"{o['ref']} completed.")
    if action == "cancel":
        return await send(chat_id, f"Cancel {o['ref']}?", [[("🛑 Yes, cancel", f"a:cancel_yes:{ref}"), ("Back", f"a:view:{ref}")]])
    if action == "cancel_yes":
        o, _ = await O.transition(o["id"], "CANCELLED", actor, "cancelled")
        if o.get("channel") == "telegram":
            await send(o["channel_id"], f"Order {o['ref']} has been cancelled. Contact /support if you have questions.")
        return await send(chat_id, f"{o['ref']} cancelled.")


async def register_webhook(base_url):
    import os
    if not tg_api.configured() or not base_url:
        return False, "Bot token, bot username or PUBLIC_BASE_URL missing"
    ok, res = await tg_api.tg_call("setWebhook", url=f"{base_url.rstrip('/')}/api/telegram/webhook",
                                   secret_token=os.environ.get("TELEGRAM_WEBHOOK_SECRET"),
                                   allowed_updates=["message", "callback_query"], drop_pending_updates=False)
    await tg_api.tg_call("setMyCommands", commands=[{"command": c, "description": d} for c, d in
                         [("start", "Start"), ("products", "Browse products"), ("orders", "My orders"),
                          ("help", "Help"), ("support", "Contact support")]])
    logger.info(f"Telegram webhook registration: {ok}")
    return ok, res
