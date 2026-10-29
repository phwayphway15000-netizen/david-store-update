import os
from datetime import timedelta
from typing import List, Optional, Literal

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, File, Form
from pydantic import BaseModel, Field, EmailStr
from pymongo import ReturnDocument

from core import (db, now, now_iso, new_id, hash_password, verify_password, create_token, require, has_perm, actor_of,
                  audit, put_object, get_object, encrypt, decrypt, client_ip, APP_NAME, IMAGE_TYPES, JWT_ALG)
from catalog import variant_available, lookup_maps

router = APIRouter(prefix="/api")
COOKIE = "reseller_token"
STATUSES = ["PENDING_CONFIRMATION", "AWAITING_PAYMENT", "PAYMENT_SUBMITTED", "PAYMENT_REJECTED", "PAID", "DELIVERED", "REJECTED", "CANCELLED"]
ADMIN_MOVES = {
    "confirm": ({"PENDING_CONFIRMATION"}, "AWAITING_PAYMENT", "orders.approve"),
    "reject": ({"PENDING_CONFIRMATION"}, "REJECTED", "orders.approve"),
    "approve_payment": ({"PAYMENT_SUBMITTED"}, "PAID", "orders.approve"),
    "reject_payment": ({"PAYMENT_SUBMITTED"}, "PAYMENT_REJECTED", "orders.approve"),
    "cancel": ({"PENDING_CONFIRMATION", "AWAITING_PAYMENT", "PAYMENT_SUBMITTED", "PAYMENT_REJECTED"}, "CANCELLED", "orders.approve"),
}
NOTE_REQUIRED = {"reject", "reject_payment", "cancel"}
PRIVATE = {"_id": 0, "password_hash": 0}


PORTAL_HIDDEN = ("password_hash", "_id", "notes", "created_by", "deleted_at")
PROOF_TYPES = {"image/jpeg": (b"\xff\xd8\xff",), "image/png": (b"\x89PNG",), "image/webp": (b"RIFF",)}


def reseller_out(r):
    return {k: v for k, v in r.items() if k not in ("password_hash", "_id")}


def portal_out(r):
    return {k: v for k, v in r.items() if k not in PORTAL_HIDDEN}


async def current_reseller(request: Request):
    tok = request.cookies.get(COOKIE)
    try:
        payload = jwt.decode(tok or "", os.environ["JWT_SECRET"], algorithms=[JWT_ALG])
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Please sign in")
    if payload.get("type") != "reseller":
        raise HTTPException(401, "Please sign in")
    r = await db.resellers.find_one({"id": payload["sub"], "active": True, "deleted_at": None}, PRIVATE)
    if not r:
        raise HTTPException(401, "Account disabled or not found")
    return r


def reseller_actor(r):
    return {"type": "reseller", "id": r["id"], "name": r.get("business_name") or r["name"], "role": "reseller"}


async def next_ref():
    c = await db.counters.find_one_and_update({"_id": f"reseller-{now().year}"}, {"$inc": {"seq": 1}}, upsert=True,
                                              return_document=ReturnDocument.AFTER)
    return f"RS-{now().year}-{c['seq']:06d}"


async def move(order_id, frm, to, actor, action, note=None, extra=None, query=None, push=None):
    res = await db.reseller_orders.find_one_and_update(
        {"id": order_id, "status": {"$in": list(frm)}, **(query or {})},
        {"$set": {"status": to, "updated_at": now_iso(), **(extra or {})},
         "$push": {"events": {"id": new_id(), "to": to, "action": action, "note": note, "actor": actor, "at": now_iso()}, **(push or {})}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not res:
        raise HTTPException(409, "This order changed or the action is not allowed in its current status. Refresh and try again.")
    await audit(actor, f"reseller_order.{action}", "reseller_order", order_id, {"ref": res["ref"], "to": to, "note": note})
    return res


def order_out(o, reveal=False):
    o = {k: v for k, v in o.items() if k != "_id"}
    o["items"] = [{**{k: v for k, v in it.items() if k != "delivery_enc"}, "delivered": bool(it.get("delivery_enc")),
                   **({"delivery": decrypt(it["delivery_enc"])} if reveal and it.get("delivery_enc") else {})} for it in o["items"]]
    return o


# ---------------- reseller auth ----------------
class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


@router.post("/reseller/auth/login")
async def login(body: LoginIn, request: Request, response: Response):
    email = body.email.lower()
    ident = f"reseller:{client_ip(request)}:{email}"
    att = await db.login_attempts.find_one({"identifier": ident}, {"_id": 0})
    if att and att.get("count", 0) >= 5 and att.get("locked_until", "") > now_iso():
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")
    r = await db.resellers.find_one({"email": email, "deleted_at": None}, {"_id": 0})
    if not r or not r.get("active") or not verify_password(body.password, r["password_hash"]):
        cnt = (att or {}).get("count", 0) % 5 + 1
        await db.login_attempts.update_one({"identifier": ident}, {"$set": {"count": cnt, "locked_until": (now() + timedelta(minutes=15)).isoformat()}}, upsert=True)
        raise HTTPException(401, "Invalid email or password")
    await db.login_attempts.delete_one({"identifier": ident})
    response.set_cookie(COOKIE, create_token(r["id"], "reseller", 60 * 12), httponly=True, secure=True, samesite="none", max_age=43200, path="/")
    await db.resellers.update_one({"id": r["id"]}, {"$set": {"last_login_at": now_iso()}})
    await audit(reseller_actor(r), "reseller.login", "reseller", r["id"])
    return portal_out(r)


@router.post("/reseller/auth/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE, path="/", secure=True, samesite="none")
    return {"ok": True}


@router.get("/reseller/auth/me")
async def me(r=Depends(current_reseller)):
    return portal_out(r)


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


@router.post("/reseller/auth/change-password")
async def change_password(body: PasswordIn, r=Depends(current_reseller)):
    full = await db.resellers.find_one({"id": r["id"]}, {"_id": 0})
    if not verify_password(body.current_password, full["password_hash"]):
        raise HTTPException(400, "Current password is incorrect")
    await db.resellers.update_one({"id": r["id"]}, {"$set": {"password_hash": hash_password(body.new_password)}})
    await audit(reseller_actor(r), "reseller.password_changed", "reseller", r["id"])
    return {"ok": True}


# ---------------- reseller portal ----------------
@router.get("/reseller/catalog")
async def catalog(r=Depends(current_reseller)):
    bm, _ = await lookup_maps()
    out = []
    async for p in db.products.find({"status": "published", "deleted_at": None, "variants": {"$elemMatch": {"reseller_price_mmk": {"$ne": None}}}}, {"_id": 0}).sort("name", 1):
        vs = [{"id": v["id"], "name": v.get("name"), "duration": v.get("duration"), "reseller_price_mmk": v["reseller_price_mmk"],
               "retail_price_mmk": v.get("price_mmk"), "available": variant_available(v)}
              for v in p.get("variants", []) if v.get("active", True) and v.get("reseller_price_mmk") is not None]
        if vs:
            out.append({"id": p["id"], "name": p["name"], "name_my": p.get("name_my"), "image": (p.get("images") or [None])[0],
                        "brand": (bm.get(p.get("brand_id")) or {}).get("name"), "variants": vs})
    return out


@router.get("/reseller/payment-methods")
async def payment_methods(r=Depends(current_reseller)):
    return await db.payment_methods.find({"enabled": True}, {"_id": 0, "id": 1, "name": 1, "account_name": 1, "account_number": 1, "instructions": 1}).sort("sort", 1).to_list(20)


class CartItem(BaseModel):
    product_id: str = Field(max_length=64)
    variant_id: str = Field(max_length=64)
    quantity: int = Field(ge=1, le=100)


class OrderIn(BaseModel):
    items: List[CartItem] = Field(min_length=1, max_length=30)
    note: Optional[str] = Field(default="", max_length=1000)


async def build_item(it: CartItem):
    p = await db.products.find_one({"id": it.product_id, "status": "published", "deleted_at": None}, {"_id": 0})
    v = next((x for x in (p or {}).get("variants", []) if x["id"] == it.variant_id and x.get("active", True)), None)
    if not p or not v or v.get("reseller_price_mmk") is None:
        raise HTTPException(400, "A product in your cart is no longer available to resellers")
    if not variant_available(v):
        raise HTTPException(400, f"{p['name']} — {v.get('name')} is out of stock")
    if v.get("stock_status") == "limited" and not v.get("stock_override") and (v.get("stock_qty") or 0) < it.quantity:
        raise HTTPException(400, f"Only {v.get('stock_qty') or 0} left of {p['name']} — {v.get('name')}")
    price = int(v["reseller_price_mmk"])
    return {"id": new_id(), "product_id": p["id"], "product_name": p["name"], "variant_id": v["id"], "variant_name": v.get("name"),
            "duration": v.get("duration"), "unit_price_mmk": price, "quantity": it.quantity, "line_total_mmk": price * it.quantity}


@router.post("/reseller/orders")
async def create_order(body: OrderIn, r=Depends(current_reseller)):
    keys = [(i.product_id, i.variant_id) for i in body.items]
    if len(set(keys)) != len(keys):
        raise HTTPException(400, "Each plan can appear only once; change its quantity instead")
    items = [await build_item(i) for i in body.items]
    total = sum(i["line_total_mmk"] for i in items)
    actor = reseller_actor(r)
    o = {"id": new_id(), "ref": await next_ref(), "reseller_id": r["id"], "reseller_name": r["name"], "business_name": r.get("business_name"),
         "items": items, "total_mmk": total, "currency": "MMK", "note": body.note or "", "status": "PENDING_CONFIRMATION",
         "events": [{"id": new_id(), "to": "PENDING_CONFIRMATION", "action": "created", "note": body.note or None, "actor": actor, "at": now_iso()}],
         "evidence": [], "created_at": now_iso(), "updated_at": now_iso()}
    await db.reseller_orders.insert_one(dict(o))
    await audit(actor, "reseller_order.created", "reseller_order", o["id"], {"ref": o["ref"], "total_mmk": total})
    return order_out(o)


@router.get("/reseller/orders")
async def my_orders(r=Depends(current_reseller)):
    return [order_out(o) for o in await db.reseller_orders.find({"reseller_id": r["id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)]


async def own_order(oid, r):
    o = await db.reseller_orders.find_one({"id": oid, "reseller_id": r["id"]}, {"_id": 0})
    if not o:
        raise HTTPException(404, "Order not found")
    return o


@router.get("/reseller/orders/{oid}")
async def my_order(oid: str, r=Depends(current_reseller)):
    return order_out(await own_order(oid, r), reveal=True)


@router.post("/reseller/orders/{oid}/cancel")
async def my_cancel(oid: str, r=Depends(current_reseller)):
    await own_order(oid, r)
    return order_out(await move(oid, {"PENDING_CONFIRMATION", "AWAITING_PAYMENT"}, "CANCELLED", reseller_actor(r), "cancelled_by_reseller",
                                query={"reseller_id": r["id"]}))


@router.post("/reseller/orders/{oid}/payment")
async def submit_payment(oid: str, reference: str = Form(""), payment_method_id: str = Form(""), file: UploadFile = File(...),
                         r=Depends(current_reseller)):
    o = await own_order(oid, r)
    if o["status"] not in {"AWAITING_PAYMENT", "PAYMENT_REJECTED"}:
        raise HTTPException(400, "Payment can only be sent after the admin confirms your order")
    ct = file.content_type or ""
    data = await file.read()
    if ct not in PROOF_TYPES or not data.startswith(PROOF_TYPES[ct]):
        raise HTTPException(400, "Please upload a JPG, PNG or WEBP screenshot")
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(400, "Image is too large (max 8 MB)")
    eid = new_id()
    res = await put_object(f"{APP_NAME}/private/reseller-evidence/{o['id']}/{eid}.{IMAGE_TYPES[ct]}", data, ct)
    ev = {"id": eid, "reference": reference[:200] or None, "payment_method_id": payment_method_id[:64] or None,
          "storage_path": res["path"], "content_type": ct, "review_status": "pending", "created_at": now_iso()}
    return order_out(await move(o["id"], {"AWAITING_PAYMENT", "PAYMENT_REJECTED"}, "PAYMENT_SUBMITTED", reseller_actor(r),
                                "payment_submitted", ev["reference"], query={"reseller_id": r["id"]}, push={"evidence": ev}))


async def evidence_bytes(o, eid):
    ev = next((e for e in o.get("evidence", []) if e["id"] == eid), None)
    if not ev:
        raise HTTPException(404, "Not found")
    data, ct = await get_object(ev["storage_path"])
    return Response(content=data, media_type=ev.get("content_type") or ct, headers={"Cache-Control": "private, no-store"})


@router.get("/reseller/orders/{oid}/evidence/{eid}")
async def my_evidence(oid: str, eid: str, r=Depends(current_reseller)):
    return await evidence_bytes(await own_order(oid, r), eid)


# ---------------- admin: reseller accounts ----------------
class ResellerIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=80)
    business_name: Optional[str] = Field(default="", max_length=120)
    phone: Optional[str] = Field(default="", max_length=40)
    notes: Optional[str] = Field(default="", max_length=1000)
    password: Optional[str] = Field(default=None, min_length=8, max_length=200)
    active: bool = True


@router.get("/admin/resellers")
async def list_resellers(user=Depends(require("resellers"))):
    rs = await db.resellers.find({"deleted_at": None}, PRIVATE).sort("created_at", -1).to_list(1000)
    stats = {s["_id"]: s for s in await db.reseller_orders.aggregate([{"$group": {"_id": "$reseller_id", "orders": {"$sum": 1},
             "spent": {"$sum": {"$cond": [{"$in": ["$status", ["PAID", "DELIVERED"]]}, "$total_mmk", 0]}}}}]).to_list(1000)}
    return [{**r, "orders": stats.get(r["id"], {}).get("orders", 0), "spent_mmk": stats.get(r["id"], {}).get("spent", 0)} for r in rs]


@router.post("/admin/resellers")
async def create_reseller(body: ResellerIn, user=Depends(require("resellers"))):
    if not body.password:
        raise HTTPException(400, "Password required (min 8 characters)")
    email = body.email.lower()
    if await db.resellers.find_one({"email": email, "deleted_at": None}) or await db.users.find_one({"email": email, "deleted_at": None}):
        raise HTTPException(400, "This email is already used")
    r = {"id": new_id(), **body.model_dump(exclude={"password"}), "email": email, "password_hash": hash_password(body.password),
         "created_by": user["id"], "created_at": now_iso(), "last_login_at": None, "deleted_at": None}
    await db.resellers.insert_one(dict(r))
    await audit(actor_of(user), "reseller.created", "reseller", r["id"], {"email": email})
    return reseller_out(r)


@router.put("/admin/resellers/{rid}")
async def update_reseller(rid: str, body: ResellerIn, user=Depends(require("resellers"))):
    upd = body.model_dump(exclude={"password", "email"})
    if body.password:
        upd["password_hash"] = hash_password(body.password)
    res = await db.resellers.find_one_and_update({"id": rid, "deleted_at": None}, {"$set": upd}, projection=PRIVATE, return_document=ReturnDocument.AFTER)
    if not res:
        raise HTTPException(404, "Reseller not found")
    await audit(actor_of(user), "reseller.updated", "reseller", rid, {"active": body.active, "password_reset": bool(body.password)})
    return res


@router.delete("/admin/resellers/{rid}")
async def delete_reseller(rid: str, user=Depends(require("resellers"))):
    r = await db.resellers.update_one({"id": rid, "deleted_at": None}, {"$set": {"deleted_at": now_iso(), "active": False}})
    if not r.matched_count:
        raise HTTPException(404, "Reseller not found")
    await audit(actor_of(user), "reseller.deleted", "reseller", rid)
    return {"ok": True}


# ---------------- admin: reseller orders ----------------
@router.get("/admin/reseller-orders")
async def admin_orders(status: str = "", reseller_id: str = "", user=Depends(require("orders"))):
    q = {}
    if status:
        q["status"] = {"$in": status.split(",")}
    if reseller_id:
        q["reseller_id"] = reseller_id
    items = await db.reseller_orders.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    counts = {c["_id"]: c["n"] for c in await db.reseller_orders.aggregate([{"$group": {"_id": "$status", "n": {"$sum": 1}}}]).to_list(20)}
    return {"items": [order_out(o) for o in items], "counts": counts}


async def get_admin_order(oid):
    o = await db.reseller_orders.find_one({"id": oid}, {"_id": 0})
    if not o:
        raise HTTPException(404, "Order not found")
    return o


@router.get("/admin/reseller-orders/{oid}")
async def admin_order(oid: str, user=Depends(require("orders"))):
    o = await get_admin_order(oid)
    out = order_out(o, reveal=has_perm(user, "orders.deliver"))
    out["reseller"] = await db.resellers.find_one({"id": o["reseller_id"]}, {"_id": 0, "name": 1, "business_name": 1, "email": 1, "phone": 1})
    pms = {p["id"]: p["name"] for p in await db.payment_methods.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(50)}
    for e in out["evidence"]:
        e["payment_method"] = pms.get(e.get("payment_method_id"))
    return out


class ActionIn(BaseModel):
    action: Literal["confirm", "reject", "approve_payment", "reject_payment", "cancel"]
    note: Optional[str] = Field(default="", max_length=1000)


@router.post("/admin/reseller-orders/{oid}/action")
async def admin_action(oid: str, body: ActionIn, user=Depends(require("orders"))):
    frm, to, perm = ADMIN_MOVES[body.action]
    if not has_perm(user, perm):
        raise HTTPException(403, "You are not allowed to confirm orders or check payments")
    if body.action in NOTE_REQUIRED and not (body.note or "").strip():
        raise HTTPException(400, "Please write a reason")
    extra = {"paid_at": now_iso()} if to == "PAID" else {}
    res = await move(oid, frm, to, actor_of(user), body.action, body.note or None, extra)
    if body.action in ("approve_payment", "reject_payment"):
        res["evidence"] = [{**e, "review_status": "accepted" if to == "PAID" else "rejected"} if e["review_status"] == "pending" else e for e in res["evidence"]]
        await db.reseller_orders.update_one({"id": oid}, {"$set": {"evidence": res["evidence"]}})
    return order_out(res, reveal=has_perm(user, "orders.deliver"))


class DeliverItem(BaseModel):
    item_id: str = Field(max_length=64)
    content: str = Field(default="", max_length=4000)


class DeliverIn(BaseModel):
    items: List[DeliverItem] = Field(min_length=1)
    note: Optional[str] = Field(default="", max_length=1000)


@router.post("/admin/reseller-orders/{oid}/deliver")
async def admin_deliver(oid: str, body: DeliverIn, user=Depends(require("orders.deliver"))):
    o = await get_admin_order(oid)
    if o["status"] != "PAID":
        raise HTTPException(400, "Payment must be approved before delivery")
    given = {d.item_id: d.content.strip() for d in body.items if d.content.strip()}
    if set(given) != {i["id"] for i in o["items"]}:
        raise HTTPException(400, "Enter delivery details for every item")
    items = [{**i, "delivery_enc": encrypt(given[i["id"]]), "delivered_at": now_iso()} for i in o["items"]]
    res = await move(oid, {"PAID"}, "DELIVERED", actor_of(user), "delivered", body.note or None, {"items": items, "delivered_at": now_iso()})
    return order_out(res, reveal=True)


@router.get("/admin/reseller-orders/{oid}/evidence/{eid}")
async def admin_evidence(oid: str, eid: str, user=Depends(require("orders"))):
    resp = await evidence_bytes(await get_admin_order(oid), eid)
    await audit(actor_of(user), "reseller_evidence.viewed", "reseller_order", oid, {"evidence_id": eid})
    return resp
