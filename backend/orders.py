from pymongo import ReturnDocument

from core import db, now, now_iso, new_id, encrypt, audit
from catalog import effective_price, variant_available
import tg_api

STATES = ["CHECKOUT_STARTED", "AWAITING_CUSTOMER_CONFIRMATION", "AWAITING_PAYMENT", "PAYMENT_SUBMITTED",
          "PAYMENT_UNDER_REVIEW", "PAYMENT_REJECTED", "PAID_AWAITING_FULFILLMENT", "FULFILLMENT_IN_PROGRESS",
          "DELIVERED", "COMPLETED", "CANCELLED", "REFUND_PENDING", "REFUNDED"]

TRANSITIONS = {
    "CHECKOUT_STARTED": {"AWAITING_CUSTOMER_CONFIRMATION", "AWAITING_PAYMENT", "CANCELLED"},
    "AWAITING_CUSTOMER_CONFIRMATION": {"AWAITING_PAYMENT", "CANCELLED"},
    "AWAITING_PAYMENT": {"PAYMENT_SUBMITTED", "CANCELLED"},
    "PAYMENT_SUBMITTED": {"PAYMENT_UNDER_REVIEW", "PAID_AWAITING_FULFILLMENT", "PAYMENT_REJECTED", "AWAITING_PAYMENT", "CANCELLED"},
    "PAYMENT_UNDER_REVIEW": {"PAID_AWAITING_FULFILLMENT", "PAYMENT_REJECTED", "AWAITING_PAYMENT", "CANCELLED"},
    "PAYMENT_REJECTED": {"PAYMENT_SUBMITTED", "AWAITING_PAYMENT", "CANCELLED"},
    "PAID_AWAITING_FULFILLMENT": {"FULFILLMENT_IN_PROGRESS", "DELIVERED", "REFUND_PENDING"},
    "FULFILLMENT_IN_PROGRESS": {"DELIVERED", "PAID_AWAITING_FULFILLMENT", "REFUND_PENDING"},
    "DELIVERED": {"COMPLETED", "REFUND_PENDING"},
    "COMPLETED": {"REFUND_PENDING"},
    "REFUND_PENDING": {"REFUNDED"},
    "CANCELLED": set(),
    "REFUNDED": set(),
}
APPROVAL_TARGETS = {"PAID_AWAITING_FULFILLMENT", "PAYMENT_REJECTED", "REFUND_PENDING", "REFUNDED"}
DELIVERY_TARGETS = {"FULFILLMENT_IN_PROGRESS", "DELIVERED", "COMPLETED"}


class OrderError(Exception):
    pass


def payment_status(s):
    return {"AWAITING_PAYMENT": "pending", "PAYMENT_SUBMITTED": "submitted", "PAYMENT_UNDER_REVIEW": "under_review",
            "PAYMENT_REJECTED": "rejected", "REFUND_PENDING": "refund_pending", "REFUNDED": "refunded"}.get(
        s, "verified" if s in {"PAID_AWAITING_FULFILLMENT", "FULFILLMENT_IN_PROGRESS", "DELIVERED", "COMPLETED"}
        else "not_started")


def delivery_status(s):
    return {"PAID_AWAITING_FULFILLMENT": "pending", "FULFILLMENT_IN_PROGRESS": "in_progress",
            "DELIVERED": "delivered", "COMPLETED": "delivered"}.get(s, "not_started")


async def next_ref():
    year = now().year
    c = await db.counters.find_one_and_update({"_id": f"order-{year}"}, {"$inc": {"seq": 1}}, upsert=True,
                                              return_document=ReturnDocument.AFTER)
    return f"DAV-{year}-{c['seq']:06d}"


async def add_event(order_id, frm, to, actor, action, note=None):
    await db.order_events.insert_one({"id": new_id(), "order_id": order_id, "from_status": frm, "to_status": to,
                                      "actor": actor, "action": action, "note": note, "created_at": now_iso()})


async def get_customer(channel, external_id, name=None, username=None):
    ident = await db.customer_channel_identities.find_one({"channel": channel, "external_id": str(external_id)}, {"_id": 0})
    if ident:
        return ident["customer_id"]
    cid = new_id()
    await db.customers.insert_one({"id": cid, "name": name or "", "created_at": now_iso()})
    await db.customer_channel_identities.insert_one({"id": new_id(), "customer_id": cid, "channel": channel,
                                                     "external_id": str(external_id), "username": username,
                                                     "created_at": now_iso()})
    return cid


async def load_product_variant(product_id, variant_id, require_published=True):
    q = {"id": product_id, "deleted_at": None}
    if require_published:
        q["status"] = "published"
    p = await db.products.find_one(q, {"_id": 0})
    if not p:
        raise OrderError("Product not found or not available")
    v = next((x for x in p.get("variants", []) if x["id"] == variant_id and x.get("active", True)), None)
    if not v:
        raise OrderError("Selected plan not found")
    if not variant_available(v):
        raise OrderError("This plan is currently out of stock")
    return p, v


async def create_order(p, v, source, actor, status, customer_id=None, channel=None, channel_id=None,
                       customer_name=None, customer_contact=None, note=None, ref=None, extra=None):
    brand = await db.brands.find_one({"id": p.get("brand_id")}, {"_id": 0, "name": 1})
    price = effective_price(v)
    item = {"id": new_id(), "product_id": p["id"], "product_name": p["name"], "brand_name": (brand or {}).get("name"),
            "variant_id": v["id"], "variant_name": v.get("name"), "duration": v.get("duration"),
            "unit_price_mmk": price, "list_price_mmk": v.get("price_mmk"), "quantity": 1}
    order = {
        "id": new_id(), "ref": ref or await next_ref(), "source": source, "status": status,
        "items": [item], "price_snapshot": {"total_mmk": price, "currency": "MMK", "locked_at": now_iso()},
        "total_mmk": price, "customer_id": customer_id, "channel": channel, "channel_id": str(channel_id) if channel_id else None,
        "customer_name": customer_name, "customer_contact": customer_contact, "assignee_id": None, "notes": note,
        "payment_method_id": None, "delivery_lock": False, "created_at": now_iso(), "updated_at": now_iso(), **(extra or {}),
    }
    await db.orders.insert_one(order)
    order.pop("_id", None)
    await db.products.update_one({"id": p["id"]}, {"$inc": {"order_count": 1}})
    await add_event(order["id"], "CHECKOUT_STARTED", status, actor, "order_created", note)
    await audit(actor, "order.created", "order", order["id"], {"ref": order["ref"], "source": source, "total_mmk": price})
    return order


async def transition(order_id, to, actor, action=None, note=None, extra=None, allowed_from=None):
    """Atomic compare-and-set transition. Returns (order, changed)."""
    if to not in STATES:
        raise OrderError("Unknown status")
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise OrderError("Order not found")
    frm = order["status"]
    if frm == to:
        return order, False
    if allowed_from and frm not in allowed_from:
        raise OrderError(f"Order is {frm}; this action is not allowed")
    if to not in TRANSITIONS.get(frm, set()):
        raise OrderError(f"Invalid transition {frm} → {to}")
    upd = {"status": to, "updated_at": now_iso(), **(extra or {})}
    res = await db.orders.find_one_and_update({"id": order_id, "status": frm}, {"$set": upd}, projection={"_id": 0},
                                              return_document=ReturnDocument.AFTER)
    if not res:
        raise OrderError("Order was changed by someone else. Refresh and try again.")
    await add_event(order_id, frm, to, actor, action or "status_changed", note)
    await audit(actor, f"order.{action or 'transition'}", "order", order_id,
                {"ref": order["ref"], "from": frm, "to": to, "note": note})
    return res, True


async def approve_payment(order_id, actor, note=None):
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise OrderError("Order not found")
    if order["status"] in {"PAID_AWAITING_FULFILLMENT", "FULFILLMENT_IN_PROGRESS", "DELIVERED", "COMPLETED"}:
        return order, False
    res, changed = await transition(order_id, "PAID_AWAITING_FULFILLMENT", actor, "payment_approved", note,
                                    {"paid_at": now_iso(), "payment_verified_by": actor},
                                    allowed_from={"PAYMENT_SUBMITTED", "PAYMENT_UNDER_REVIEW"})
    if changed:
        await db.payment_reviews.insert_one({"id": new_id(), "order_id": order_id, "decision": "approved",
                                             "actor": actor, "note": note, "created_at": now_iso()})
        await db.payment_evidence.update_many({"order_id": order_id, "review_status": "pending"},
                                              {"$set": {"review_status": "accepted"}})
        if res.get("channel") == "telegram":
            await tg_api.send(res["channel_id"], f"✅ ငွေပေးချေမှု အတည်ပြုပြီးပါပြီ။\nPayment verified for order <b>{res['ref']}</b>. "
                                                  "We are preparing your delivery.")
        await tg_api.notify_owner(f"💳 Payment approved for <b>{res['ref']}</b>. Ready for delivery.",
                                  [[("🚚 Send Delivery", f"a:deliver:{res['ref']}"), ("👁 View", f"a:view:{res['ref']}")]])
    return res, changed


async def reject_payment(order_id, actor, reason):
    if not (reason or "").strip():
        raise OrderError("A rejection reason is required")
    res, changed = await transition(order_id, "PAYMENT_REJECTED", actor, "payment_rejected", reason,
                                    allowed_from={"PAYMENT_SUBMITTED", "PAYMENT_UNDER_REVIEW"})
    if changed:
        await db.payment_reviews.insert_one({"id": new_id(), "order_id": order_id, "decision": "rejected",
                                             "actor": actor, "note": reason, "created_at": now_iso()})
        await db.payment_evidence.update_many({"order_id": order_id, "review_status": "pending"},
                                              {"$set": {"review_status": "rejected"}})
        if res.get("channel") == "telegram":
            await tg_api.send(res["channel_id"], f"⚠️ Payment for <b>{res['ref']}</b> could not be verified.\n"
                                                  f"Reason: {tg_api.esc(reason or '-')}\nPlease send a new transaction reference or screenshot.")
            await db.telegram_sessions.update_one({"chat_id": res["channel_id"]}, {"$set": {"mode": "await_evidence", "order_id": res["id"]}}, upsert=True)
    return res, changed


async def request_more_evidence(order_id, actor, note=None):
    res, changed = await transition(order_id, "AWAITING_PAYMENT", actor, "evidence_requested", note,
                                    allowed_from={"PAYMENT_SUBMITTED", "PAYMENT_UNDER_REVIEW"})
    if changed and res.get("channel") == "telegram":
        await tg_api.send(res["channel_id"], f"📎 Please send additional payment evidence for <b>{res['ref']}</b>."
                                              + (f"\n{tg_api.esc(note)}" if note else ""))
        await db.telegram_sessions.update_one({"chat_id": res["channel_id"]}, {"$set": {"mode": "await_evidence", "order_id": res["id"]}}, upsert=True)
    return res, changed


async def deliver(order_id, artifact_type, content, actor):
    """Idempotent delivery with a lock so webhook retries never double-deliver."""
    order = await db.orders.find_one_and_update(
        {"id": order_id, "status": {"$in": ["PAID_AWAITING_FULFILLMENT", "FULFILLMENT_IN_PROGRESS"]}, "delivery_lock": {"$ne": True}},
        {"$set": {"delivery_lock": True}}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not order:
        cur = await db.orders.find_one({"id": order_id}, {"_id": 0})
        if not cur:
            raise OrderError("Order not found")
        if cur["status"] in {"DELIVERED", "COMPLETED"}:
            return {"result": "already_delivered", "order": cur}
        if cur.get("delivery_lock"):
            raise OrderError("A delivery for this order is already in progress")
        raise OrderError(f"Order is {cur['status']}; payment must be approved before delivery")
    try:
        if order["status"] == "PAID_AWAITING_FULFILLMENT":
            order, _ = await transition(order_id, "FULFILLMENT_IN_PROGRESS", actor, "fulfillment_started")
        art_id = new_id()
        await db.delivery_artifacts.insert_one({"id": art_id, "order_id": order_id, "type": artifact_type,
                                                "content_enc": encrypt(content), "created_by": actor,
                                                "created_at": now_iso(), "purged_at": None})
        delivery = {"id": new_id(), "order_id": order_id, "artifact_id": art_id, "channel": order.get("channel"),
                    "status": "pending", "created_at": now_iso()}
        if order.get("channel") == "telegram" and order.get("channel_id"):
            ok, _ = await tg_api.send(order["channel_id"],
                                      f"📦 <b>Your order {order['ref']} has been delivered</b>\n"
                                      f"{tg_api.esc(order['items'][0]['product_name'])} — {tg_api.esc(order['items'][0]['variant_name'])}\n\n"
                                      f"<b>{tg_api.esc(artifact_type.title())}:</b>\n<code>{tg_api.esc(content)}</code>\n\n"
                                      "Please keep this information private.")
            delivery["status"] = "sent" if ok else "failed"
        else:
            delivery["status"] = "awaiting_manual_handoff"
        await db.deliveries.insert_one(delivery)
        await db.delivery_events.insert_one({"id": new_id(), "order_id": order_id, "delivery_id": delivery["id"],
                                             "event": delivery["status"], "actor": actor, "created_at": now_iso()})
        await audit(actor, "delivery." + delivery["status"], "order", order_id, {"ref": order["ref"], "type": artifact_type})
        if delivery["status"] == "sent":
            order, _ = await transition(order_id, "DELIVERED", actor, "delivered", "Delivered via Telegram",
                                        {"delivered_at": now_iso()})
        return {"result": delivery["status"], "order": order}
    finally:
        await db.orders.update_one({"id": order_id}, {"$set": {"delivery_lock": False}})


async def confirm_manual_delivery(order_id, actor, note):
    if not (note or "").strip():
        raise OrderError("Describe how the product was handed over (note required)")
    res, changed = await transition(order_id, "DELIVERED", actor, "delivered_manual", note or "Manual handoff confirmed",
                                    {"delivered_at": now_iso()}, allowed_from={"PAID_AWAITING_FULFILLMENT", "FULFILLMENT_IN_PROGRESS"})
    if changed:
        await db.delivery_events.insert_one({"id": new_id(), "order_id": order_id, "event": "manual_confirmed",
                                             "actor": actor, "note": note, "created_at": now_iso()})
    return res, changed


async def complete(order_id, actor, note=None):
    res, changed = await transition(order_id, "COMPLETED", actor, "completed", note, {"completed_at": now_iso()})
    if changed:
        await db.delivery_artifacts.update_many({"order_id": order_id, "purged_at": None},
                                                {"$set": {"content_enc": None, "purged_at": now_iso()}})
    return res, changed
