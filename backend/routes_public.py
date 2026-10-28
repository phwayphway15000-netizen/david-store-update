import os
import re
import hashlib
import secrets
import html as H

from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import Response, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional

from core import db, now_iso, get_object, rate_limit, client_ip, logger
from catalog import public_product, lookup_maps
import orders as O
import tg_api
import telegram_bot as TB

router = APIRouter(prefix="/api")


def base_url():
    return (os.environ.get("PUBLIC_BASE_URL") or "").rstrip("/")


async def get_settings():
    return await db.settings.find_one({"id": "global"}, {"_id": 0}) or {}


@router.get("/health")
async def health():
    return {"ok": True}


@router.get("/settings/public")
async def public_settings():
    s = await get_settings()
    s["telegram_bot_url"] = f"https://t.me/{tg_api.bot_username()}" if tg_api.bot_username() else None
    s["telegram_checkout_enabled"] = tg_api.configured()
    return s


@router.get("/brands")
async def brands():
    items = await db.brands.find({"deleted_at": None}, {"_id": 0}).sort("sort", 1).to_list(500)
    for b in items:
        b["product_count"] = await db.products.count_documents({"brand_id": b["id"], "status": "published", "deleted_at": None})
    return items


@router.get("/categories")
async def categories():
    items = await db.categories.find({"deleted_at": None}, {"_id": 0}).sort("sort", 1).to_list(200)
    for c in items:
        c["product_count"] = await db.products.count_documents({"category_id": c["id"], "status": "published", "deleted_at": None})
    return items


@router.get("/promotions")
async def promotions():
    t = now_iso()
    q = {"active": True, "deleted_at": None, "$and": [{"$or": [{"start_at": None}, {"start_at": ""}, {"start_at": {"$lte": t}}]},
                                                      {"$or": [{"end_at": None}, {"end_at": ""}, {"end_at": {"$gte": t}}]}]}
    return await db.promotions.find(q, {"_id": 0}).sort("sort", 1).to_list(50)


@router.get("/products")
async def list_products(q: str = "", brand: str = "", category: str = "", min_price: Optional[int] = None,
                        max_price: Optional[int] = None, in_stock: bool = False, promo: bool = False, featured: bool = False,
                        sort: str = "newest", page: int = Query(1, ge=1), limit: int = Query(12, ge=1, le=48)):
    query = {"status": "published", "deleted_at": None}
    if q:
        query["$or"] = [{"name": {"$regex": re.escape(q[:80]), "$options": "i"}}, {"name_my": {"$regex": re.escape(q[:80]), "$options": "i"}}]
    if brand:
        b = await db.brands.find_one({"slug": brand}, {"_id": 0, "id": 1})
        query["brand_id"] = b["id"] if b else "__none__"
    if category:
        c = await db.categories.find_one({"slug": category}, {"_id": 0, "id": 1})
        query["category_id"] = c["id"] if c else "__none__"
    if min_price is not None or max_price is not None:
        query["min_price"] = {k: v for k, v in (("$gte", min_price), ("$lte", max_price)) if v is not None}
    if in_stock:
        query["available"] = True
    if promo:
        query["on_promo"] = True
    if featured:
        query["featured"] = True
    sorts = {"newest": [("created_at", -1)], "price_asc": [("min_price", 1)], "price_desc": [("min_price", -1)],
             "popular": [("order_count", -1), ("created_at", -1)]}
    total = await db.products.count_documents(query)
    docs = await db.products.find(query, {"_id": 0}).sort(sorts.get(sort, sorts["newest"])).skip((page - 1) * limit).limit(limit).to_list(limit)
    bm, cm = await lookup_maps()
    return {"items": [public_product(p, bm, cm) for p in docs], "total": total, "page": page, "pages": max(1, -(-total // limit))}


@router.get("/products/{slug}")
async def product_detail(slug: str):
    p = await db.products.find_one({"slug": slug, "status": "published", "deleted_at": None}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Product not found")
    bm, cm = await lookup_maps()
    return public_product(p, bm, cm)


class CheckoutIn(BaseModel):
    product_id: str = Field(max_length=64)
    variant_id: str = Field(max_length=64)


class MessengerIn(CheckoutIn):
    customer_name: Optional[str] = Field(default="", max_length=80)


@router.post("/checkout/telegram")
async def checkout_telegram(body: CheckoutIn, request: Request):
    rate_limit(f"checkout:{client_ip(request)}", 15, 300)
    if not tg_api.configured():
        raise HTTPException(503, "Telegram checkout is not configured yet. Please contact support.")
    try:
        await O.load_product_variant(body.product_id, body.variant_id)
    except O.OrderError as e:
        raise HTTPException(400, str(e))
    token, intent = await TB.create_intent(body.product_id, body.variant_id)
    return {"deep_link": f"https://t.me/{tg_api.bot_username()}?start={token}", "expires_at": intent["expires_at"]}


@router.post("/checkout/messenger")
async def checkout_messenger(body: MessengerIn, request: Request):
    rate_limit(f"checkout:{client_ip(request)}", 15, 300)
    try:
        p, v = await O.load_product_variant(body.product_id, body.variant_id)
    except O.OrderError as e:
        raise HTTPException(400, str(e))
    track = secrets.token_urlsafe(12)
    actor = {"type": "website_visitor", "id": hashlib.sha256(client_ip(request).encode()).hexdigest()[:12]}
    o = await O.create_order(p, v, "WEBSITE_MESSENGER", actor, "AWAITING_CUSTOMER_CONFIRMATION", channel="messenger",
                             customer_name=(body.customer_name or "").strip() or None,
                             extra={"track_hash": hashlib.sha256(track.encode()).hexdigest()})
    s = await get_settings()
    murl = s.get("messenger_url") or s.get("contacts", {}).get("facebook") or ""
    if "m.me/" in murl:
        murl = f"{murl}{'&' if '?' in murl else '?'}ref={o['ref']}"
    it = o["items"][0]
    summary = (f"Order Reference: {o['ref']}\nProduct: {it.get('brand_name') or ''} {it['product_name']}\n"
               f"Plan: {it['variant_name']}{(' · ' + it['duration']) if it.get('duration') else ''}\nPrice: {o['total_mmk']:,} MMK")
    await tg_api.notify_owner("🆕 Messenger order reference created\n" + TB.order_summary(o, True))
    return {"order_ref": o["ref"], "track_token": track, "summary": summary, "messenger_url": murl, "total_mmk": o["total_mmk"]}


@router.get("/orders/track")
async def track(ref: str, token: str, request: Request):
    rate_limit(f"track:{client_ip(request)}", 30, 300)
    o = await db.orders.find_one({"ref": ref.strip().upper(), "track_hash": hashlib.sha256(token.encode()).hexdigest()}, {"_id": 0})
    if not o:
        raise HTTPException(404, "Order not found")
    it = o["items"][0]
    return {"ref": o["ref"], "status": o["status"], "payment_status": O.payment_status(o["status"]),
            "delivery_status": O.delivery_status(o["status"]), "product_name": it["product_name"],
            "variant_name": it["variant_name"], "total_mmk": o["total_mmk"], "created_at": o["created_at"]}


@router.get("/files/public/{path:path}")
async def public_file(path: str):
    rec = await db.files.find_one({"storage_path": path, "visibility": "public", "is_deleted": False}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "File not found")
    data, ct = await get_object(path)
    return Response(content=data, media_type=rec.get("content_type") or ct, headers={"Cache-Control": "public, max-age=86400"})


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
    if not secret or not secrets.compare_digest(request.headers.get("X-Telegram-Bot-Api-Secret-Token", ""), secret):
        raise HTTPException(403, "Invalid webhook secret")
    upd = await request.json()
    try:
        result = await TB.handle_update(upd)
    except Exception as e:
        logger.exception(f"Telegram update failed: {type(e).__name__}")
        result = "error"
    return {"ok": True, "result": result}


@router.get("/demo-supplier/products")
async def demo_supplier(request: Request):
    """Sandbox supplier API for testing the integration framework."""
    if request.headers.get("X-API-Key") != os.environ.get("DEMO_SUPPLIER_KEY"):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    items = [{"sku": f"DEMO-{i}", "title": t, "cost_mmk": c, "qty": q, "details": {"summary": d}}
             for i, (t, c, q, d) in enumerate([("Demo AI Writer Pro · 1 Month", 18000, 12, "Sandbox item"),
                                                ("Demo Video Editor Plus · 1 Month", 14000, 5, "Sandbox item"),
                                                ("Demo Voice Studio · 1 Month", 22000, 0, "Sandbox item"),
                                                ("Demo Course Pass · 1 Year", 60000, 3, "Sandbox item")], 1)]
    return {"data": {"items": items}, "meta": {"sandbox": True}}


def _abs(u):
    return f"{base_url()}{u}" if u and u.startswith("/api") else (u or "")


@router.get("/og/product/{slug}", response_class=HTMLResponse)
async def og_product(slug: str):
    p = await db.products.find_one({"slug": slug, "status": "published", "deleted_at": None}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Product not found")
    s = await get_settings()
    bm, cm = await lookup_maps()
    pp = public_product(p, bm, cm)
    e = H.escape
    title = f"{pp['name']} – {s.get('brand_name', '')}"
    desc = pp.get("short_description") or (pp.get("description") or "")[:180]
    img = _abs(pp["images"][0]) if pp.get("images") else (_abs(s.get("og_image")) or f"{base_url()}/logo-og.jpg")
    store_url = f"{base_url()}/products/{slug}"
    rows = "".join(f"<li>{e(v['name'])} {e(v.get('duration') or '')} — {v['effective_price_mmk']:,} MMK"
                   f"{' (was ' + format(v['price_mmk'], ',') + ' MMK)' if v['promo_active'] else ''} — "
                   f"{'In stock' if v['available'] else 'Out of stock'}</li>" for v in pp["variants"])
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(desc)}">
<meta property="og:type" content="product"><meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{base_url()}/api/og/product/{e(slug)}">
{f'<meta property="og:image" content="{e(img)}">' if img else ''}<meta property="product:price:amount" content="{pp['min_price']}">
<meta property="product:price:currency" content="MMK"><meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="{e(store_url)}">
<style>body{{font-family:system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px;color:#0F172A}}a.b{{display:inline-block;background:#2563EB;color:#fff;padding:12px 20px;border-radius:10px;text-decoration:none}}</style>
</head><body><p>{e(s.get('brand_name', ''))}</p><h1>{e(pp['name'])}</h1>
<p>Brand: {e((pp.get('brand') or {}).get('name', '-'))} · Category: {e((pp.get('category') or {}).get('name', '-'))}</p>
<p>{e(desc)}</p><h2>Plans</h2><ul>{rows}</ul>
<p>Delivery: {e(pp.get('delivery_time') or '-')}</p><p>Warranty: {e(pp.get('warranty') or '-')}</p>
<p><a class="b" href="{e(store_url)}">View product in store</a></p>
<p><small>Independent reseller. Not affiliated with or endorsed by the brand owner.</small></p></body></html>"""
    return HTMLResponse(page)


@router.get("/sitemap.xml")
async def sitemap():
    b = base_url()
    urls = [f"{b}/", f"{b}/products", f"{b}/promotions", f"{b}/support"] + \
           [f"{b}/policies/{k}" for k in ("privacy", "terms", "refund", "delivery", "warranty", "about")]
    async for p in db.products.find({"status": "published", "deleted_at": None}, {"_id": 0, "slug": 1}):
        urls.append(f"{b}/products/{p['slug']}")
    xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + \
          "".join(f"<url><loc>{H.escape(u)}</loc></url>" for u in urls) + "</urlset>"
    return Response(xml, media_type="application/xml")
