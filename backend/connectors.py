import asyncio
import json
import math
from datetime import timedelta
from pathlib import Path
from typing import List, Literal, Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, now, now_iso, new_id, encrypt, decrypt, mask, require, actor_of, audit, logger, slugify
from catalog import recompute
import suppliers as S

router = APIRouter(prefix="/api/admin/supplier-integrations")
PRESETS = json.loads((Path(__file__).parent / "supplier_presets.json").read_text())
STATUSES = ["NOT_CONNECTED", "CONNECTED", "SYNCING", "SYNC_FAILED", "AUTH_FAILED", "CONFIGURATION_ERROR", "NEEDS_REVIEW", "DISABLED"]
REVIEW = {"BlackHatWorld": ("CONFIGURATION_ERROR", "SECURITY_REVIEW_REQUIRED: endpoint uses plain HTTP. Credentials are never sent over HTTP; an approved HTTPS endpoint is required."),
          "Prmast": ("NEEDS_REVIEW", "A previous sync was redirected. Redirects are never followed with credentials; confirm the correct HTTPS endpoint with the supplier."),
          "Samayra": ("NEEDS_REVIEW", "A previous sync returned HTTP 404 for the documented products route. Confirm the route with the supplier.")}


class SupplierError(ValueError):
    def __init__(self, code, msg):
        super().__init__(f"{code}: {msg}")
        self.code = code


def preset_key(name):
    return slugify(name).rsplit("-", 1)[0]


async def install_presets():
    for p in PRESETS["suppliers"]:
        key = preset_key(p["name"])
        await db.supplier_definitions.update_one({"key": key}, {"$set": {"key": key, "version": PRESETS["preset_version"],
                                                 "schema_version": PRESETS["schema_version"], "definition": p, "updated_at": now_iso()}}, upsert=True)
        c, a = p["connector"], p["authentication"]
        cfg = {"name": p["name"], "base_url": p["base_url"], "docs_url": p.get("documentation_url"), "products_endpoint": c["products_endpoint"],
               "items_path": c.get("response_list_key") or "", "auth_type": a["type"], "auth_location": a["location"],
               "auth_header_name": a["name"], "auth_prefix": a.get("prefix") or "", "field_mappings": c["field_mappings"],
               "query_params": c.get("query_params") or {}, "pagination": c.get("pagination") or {}, "rate_limit_rpm": c.get("rate_limit_rpm") or 30,
               "https_required": c.get("https_required", True), "follow_redirects": False, "preset_version": PRESETS["preset_version"],
               "bot_username": p.get("bot_username"), "allowed_host": urlparse(p["base_url"]).hostname}
        existing = await db.suppliers.find_one({"preset_key": key}, {"_id": 0, "id": 1})
        if existing:
            await db.suppliers.update_one({"preset_key": key}, {"$set": cfg})
            continue
        status, note = REVIEW.get(p["name"], ("NOT_CONNECTED", None))
        await db.suppliers.insert_one({"id": new_id(), "preset_key": key, **cfg, "credential_enc": None, "connection_status": status,
                                       "review_note": note, "active": True, "sync_interval_minutes": p.get("sync_interval_minutes") or 30,
                                       "health": "unknown", "last_sync_at": None, "last_success_at": None, "last_test": None,
                                       "created_at": now_iso(), "deleted_at": None, "sync_lock_until": None})


def build_auth(s, key):
    """Returns (headers, params) with the key in the preset's configured location."""
    headers, params = {"Accept": "application/json", "User-Agent": "DavidStore-SupplierSync/1.0"}, dict(s.get("query_params") or {})
    if s.get("auth_location") == "query":
        params[s["auth_header_name"]] = key
    else:
        headers[s["auth_header_name"]] = f"{s.get('auth_prefix') or ''}{key}"
    return headers, params


def extract_list(data, key):
    if key:
        items = S.get_path(data, key)
    elif isinstance(data, list):
        items = data
    else:
        items = next((data[k] for k in ("products", "data", "items", "services", "results") if isinstance(data, dict) and isinstance(data.get(k), list)), None)
    if not isinstance(items, list):
        raise SupplierError("MALFORMED_RESPONSE", f"response list '{key or '(root)'}' not found")
    return items


async def request_page(s, headers, params):
    url = s["base_url"].rstrip("/") + "/" + s["products_endpoint"].lstrip("/")
    host = urlparse(url).hostname
    if urlparse(url).scheme != "https":
        raise SupplierError("CONFIGURATION_ERROR", "endpoint is not HTTPS; credentials were not sent")
    if host != s.get("allowed_host"):
        raise SupplierError("CONFIGURATION_ERROR", "host is not on the allowlist")
    try:
        S.check_url(url)
    except ValueError as e:
        raise SupplierError("CONFIGURATION_ERROR", str(e))
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as c:
            r = await c.get(url, headers=headers, params=params)
    except httpx.TimeoutException:
        raise SupplierError("TIMEOUT", "supplier did not respond within 20s")
    except httpx.ConnectError as e:
        msg = str(e).lower()
        if "ssl" in msg or "certificate" in msg:
            raise SupplierError("TLS_ERROR", "TLS/certificate verification failed")
        raise SupplierError("DNS_OR_CONNECT", "could not resolve or connect to supplier host")
    except httpx.HTTPError:
        raise SupplierError("NETWORK_ERROR", "request failed")
    if 300 <= r.status_code < 400:
        raise SupplierError("UNEXPECTED_REDIRECT", f"HTTP {r.status_code} redirect was not followed to protect credentials")
    codes = {401: "AUTH_FAILED", 403: "AUTH_FAILED", 404: "NOT_FOUND", 429: "RATE_LIMITED"}
    if r.status_code >= 400:
        raise SupplierError(codes.get(r.status_code, "HTTP_ERROR"), f"HTTP {r.status_code}")
    if len(r.content) > S.MAX_BYTES:
        raise SupplierError("MALFORMED_RESPONSE", "response too large")
    try:
        return r.status_code, r.json()
    except ValueError:
        raise SupplierError("MALFORMED_RESPONSE", "response is not JSON")


async def fetch_preset(s):
    key = decrypt(s.get("credential_enc"))
    if not key:
        raise SupplierError("NOT_CONNECTED", "no API key saved")
    headers, params = build_auth(s, key)
    delay = 60 / max(1, s.get("rate_limit_rpm") or 30)
    offset_mode = (s.get("pagination") or {}).get("method") == "offset"
    size = (s.get("pagination") or {}).get("page_size") or 100
    out, status = [], 200
    for page in range(20 if offset_mode else 1):
        if offset_mode:
            params.update(offset=page * size, limit=size)
        status, data = await request_page(s, headers, params)
        items = extract_list(data, s.get("items_path"))
        root_cur = data.get("currency") if isinstance(data, dict) else None
        out += [{**i, "__root_currency": root_cur} if isinstance(i, dict) else i for i in items]
        if not offset_mode or len(items) < size:
            break
        await asyncio.sleep(delay)
    return status, out


def num(x):
    try:
        f = float(x)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def tiers_to_variants(tiers):
    out = []
    for i, t in enumerate(tiers if isinstance(tiers, list) else []):
        if isinstance(t, dict):
            cost = num(next((t[k] for k in ("price", "amount", "price_usd", "cost", "unit_price") if k in t), None))
            label = next((str(t[k]) for k in ("name", "label", "duration", "plan", "months", "period", "title") if t.get(k) not in (None, "")), f"Option {i + 1}")
        else:
            cost, label = num(t), f"Option {i + 1}"
        out.append({"key": str(i), "name": label[:80], "cost": cost})
    return out


def map_value(raw, path):
    if not path:
        return None
    if path == "_id":
        return raw.get("_id")
    if path.startswith("_fixed_") and path != "_fixed_stock":
        return path[len("_fixed_"):]
    if path == "_root_currency":
        return raw.get("__root_currency")
    if path.startswith("_price_options_0_"):
        opts = raw.get("price_options") or []
        return (opts[0] or {}).get(path[len("_price_options_0_"):]) if opts and isinstance(opts[0], dict) else None
    return S.get_path(raw, path)


def price_variants(raw, path):
    if path == "_pricing_tiers_0":
        return tiers_to_variants(raw.get("pricing_tiers"))
    if path and path.startswith("_price_options_0_"):
        return tiers_to_variants(raw.get("price_options"))
    v = map_value(raw, path)
    if isinstance(v, list):
        return tiers_to_variants(v)
    if isinstance(v, dict):
        return [{"key": str(k), "name": str(k)[:80], "cost": num(x)} for k, x in v.items() if num(x) is not None]
    return [{"key": "0", "name": "Standard", "cost": num(v)}]


def normalize_preset(s, raw):
    fm = s["field_mappings"]
    ext = map_value(raw, fm.get("external_product_id"))
    variants = price_variants(raw, fm.get("price"))
    qty = num(map_value(raw, fm.get("stock_quantity")))
    st = map_value(raw, fm.get("stock_status")) if fm.get("stock_status") != "_fixed_stock" else None
    if st is False:
        qty = 0
    reasons = [r for r, bad in (("missing external id", ext is None), ("missing name", not map_value(raw, fm.get("name"))),
                                ("price not mappable", not variants or any(v["cost"] is None for v in variants))) if bad]
    img = map_value(raw, fm.get("product_url"))
    return {"external_id": str(ext) if ext is not None else None, "name": str(map_value(raw, fm.get("name")) or "")[:200],
            "description": str(map_value(raw, fm.get("description")) or "")[:4000], "cost": variants[0]["cost"] if variants else None,
            "currency": str(map_value(raw, fm.get("currency")) or "").upper() or None, "stock": qty,
            "stock_status": "out_of_stock" if qty == 0 else ("in_stock" if qty or fm.get("stock_status") == "_fixed_stock" else "unknown"),
            "category": str(map_value(raw, fm.get("category")) or "") or None, "brand": str(map_value(raw, fm.get("brand")) or "") or None,
            "image": img if isinstance(img, str) and img.startswith("https://") else "",
            "warranty": str(map_value(raw, fm.get("warranty")) or "") or None, "delivery": str(st)[:80] if isinstance(st, str) else None,
            "variants": variants, "needs_review": bool(reasons), "review_reasons": reasons, "last_synced_at": now_iso()}


def card(s, counts):
    return {k: s.get(k) for k in ("id", "name", "preset_key", "docs_url", "base_url", "connection_status", "review_note", "last_success_at",
                                  "last_sync_at", "last_error", "last_test", "sync_interval_minutes", "active", "bot_username", "auth_location")} | {
        "has_key": bool(s.get("credential_enc")), "key_masked": mask(decrypt(s.get("credential_enc"))) if s.get("credential_enc") else "",
        "product_count": counts.get(s["id"], 0)}


async def get_preset_supplier(sid):
    s = await db.suppliers.find_one({"id": sid, "preset_key": {"$ne": None}, "deleted_at": None}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Supplier integration not found")
    return s


def status_for_error(err):
    code = (err or "").split(":")[0]
    return {"AUTH_FAILED": "AUTH_FAILED", "CONFIGURATION_ERROR": "CONFIGURATION_ERROR", "UNEXPECTED_REDIRECT": "NEEDS_REVIEW",
            "NOT_FOUND": "NEEDS_REVIEW"}.get(code, "SYNC_FAILED")


async def locked_sync(s, actor, trigger="manual"):
    lock = await db.suppliers.find_one_and_update(
        {"id": s["id"], "$or": [{"sync_lock_until": None}, {"sync_lock_until": {"$lt": now_iso()}}]},
        {"$set": {"sync_lock_until": (now() + timedelta(minutes=10)).isoformat(), "connection_status": "SYNCING"}})
    if not lock:
        raise HTTPException(409, "A sync for this supplier is already running")
    try:
        run = await S.run_sync(s, actor, trigger)
    finally:
        await db.suppliers.update_one({"id": s["id"]}, {"$set": {"sync_lock_until": None}})
    ok = run["status"] == "success"
    await db.suppliers.update_one({"id": s["id"]}, {"$set": {"connection_status": "CONNECTED" if ok else status_for_error(run.get("error")),
                                                             **({"last_success_at": now_iso()} if ok else {})}})
    return run


async def scheduler_loop():
    while True:
        try:
            async for s in db.suppliers.find({"preset_key": {"$ne": None}, "active": True, "deleted_at": None, "credential_enc": {"$ne": None},
                                              "connection_status": {"$in": ["CONNECTED", "SYNC_FAILED"]}}, {"_id": 0}):
                last = s.get("last_sync_at")
                from datetime import datetime
                if not last or (now() - datetime.fromisoformat(last)).total_seconds() >= (s.get("sync_interval_minutes") or 30) * 60:
                    try:
                        await locked_sync(s, {"type": "system", "id": "scheduler"}, "scheduled")
                    except HTTPException:
                        pass
        except Exception as e:
            logger.error(f"Preset scheduler error: {type(e).__name__}")
        await asyncio.sleep(60)


@router.get("")
async def overview(user=Depends(require("suppliers"))):
    sups = await db.suppliers.find({"preset_key": {"$ne": None}, "deleted_at": None}, {"_id": 0}).sort("name", 1).to_list(100)
    ids = [s["id"] for s in sups]
    counts = {r["_id"]: r["n"] for r in await db.supplier_products.aggregate([{"$match": {"supplier_id": {"$in": ids}}}, {"$group": {"_id": "$supplier_id", "n": {"$sum": 1}}}]).to_list(100)}
    since = (now() - timedelta(days=7)).isoformat()
    linked = {"source_type": "SUPPLIER_API", "deleted_at": None, "variants.supplier_id": {"$in": ids}}
    metrics = {"total": len(sups), "connected": sum(s["connection_status"] == "CONNECTED" for s in sups),
               "attention": sum(s["connection_status"] in ("SYNC_FAILED", "AUTH_FAILED", "CONFIGURATION_ERROR", "NEEDS_REVIEW") for s in sups),
               "imported_products": sum(counts.values()),
               "published": await db.products.count_documents({**linked, "status": "published"}),
               "unpublished": await db.products.count_documents({**linked, "status": {"$ne": "published"}}),
               "price_changes_7d": await db.price_history.count_documents({"kind": "supplier_cost", "supplier_id": {"$in": ids}, "created_at": {"$gte": since}}),
               "stock_changes_7d": sum(r.get("stock_changes", 0) for r in await db.supplier_sync_runs.find({"supplier_id": {"$in": ids}, "started_at": {"$gte": since}}, {"_id": 0, "stock_changes": 1}).to_list(5000)),
               "recent_failures": await db.supplier_sync_runs.find({"supplier_id": {"$in": ids}, "status": "failed"}, {"_id": 0}).sort("started_at", -1).limit(8).to_list(8)}
    names = {s["id"]: s["name"] for s in sups}
    for f in metrics["recent_failures"]:
        f["supplier_name"] = names.get(f["supplier_id"])
    return {"metrics": metrics, "suppliers": [card(s, counts) for s in sups]}


class ConnectIn(BaseModel):
    api_key: str = Field(min_length=4, max_length=500)


async def run_test(s):
    if s["connection_status"] == "DISABLED":
        raise HTTPException(400, "Integration is disabled")
    res = {"at": now_iso(), "ok": False}
    try:
        status, items = await fetch_preset(s)
        sample = [normalize_preset(s, i) for i in items[:5] if isinstance(i, dict)]
        bad = [x for x in sample if x["needs_review"]]
        res.update(ok=True, status_code=status, products_returned=len(items), auth="verified",
                   mapping="validated" if sample and not bad else ("needs review" if sample else "no products returned"),
                   sample=[{k: x[k] for k in ("external_id", "name", "cost", "currency", "stock", "variants", "review_reasons")} for x in sample[:3]])
        new_status = "CONNECTED" if sample and not bad else "NEEDS_REVIEW" if bad else "CONNECTED"
    except SupplierError as e:
        res.update(error_code=e.code, message=str(e))
        new_status = status_for_error(str(e))
    await db.suppliers.update_one({"id": s["id"]}, {"$set": {"last_test": res, "connection_status": new_status, "health": "ok" if res["ok"] else "error"}})
    return {**res, "connection_status": new_status, "supplier": s["name"]}


@router.post("/{sid}/connect")
async def connect(sid: str, body: ConnectIn, user=Depends(require("suppliers"))):
    s = await get_preset_supplier(sid)
    await db.suppliers.update_one({"id": sid}, {"$set": {"credential_enc": encrypt(body.api_key.strip()), "credential_updated_at": now_iso()}})
    await audit(actor_of(user), "supplier.credential_saved", "supplier", sid, {"name": s["name"]})
    return await run_test(await get_preset_supplier(sid))


@router.post("/{sid}/test")
async def test(sid: str, user=Depends(require("suppliers"))):
    return await run_test(await get_preset_supplier(sid))


@router.post("/{sid}/revoke")
async def revoke(sid: str, user=Depends(require("suppliers"))):
    s = await get_preset_supplier(sid)
    await db.suppliers.update_one({"id": sid}, {"$set": {"credential_enc": None, "connection_status": REVIEW.get(s["name"], ("NOT_CONNECTED",))[0], "last_test": None}})
    await audit(actor_of(user), "supplier.credential_revoked", "supplier", sid, {"name": s["name"]})
    return {"ok": True}


@router.post("/{sid}/sync")
async def sync_one(sid: str, user=Depends(require("suppliers"))):
    s = await get_preset_supplier(sid)
    if not s.get("credential_enc"):
        raise HTTPException(400, "Connect this supplier with an API key first")
    return await locked_sync(s, actor_of(user))


@router.post("/sync-all")
async def sync_all(user=Depends(require("suppliers"))):
    out = []
    async for s in db.suppliers.find({"preset_key": {"$ne": None}, "deleted_at": None, "active": True, "credential_enc": {"$ne": None},
                                      "connection_status": {"$nin": ["DISABLED", "CONFIGURATION_ERROR"]}}, {"_id": 0}):
        try:
            r = await locked_sync(s, actor_of(user))
            out.append({"supplier": s["name"], "status": r["status"], "error": r.get("error")})
        except HTTPException as e:
            out.append({"supplier": s["name"], "status": "skipped", "error": e.detail})
    return out


class SettingsIn(BaseModel):
    sync_interval_minutes: int = Field(ge=5, le=10080)
    active: bool


@router.put("/{sid}/settings")
async def settings(sid: str, body: SettingsIn, user=Depends(require("suppliers"))):
    s = await get_preset_supplier(sid)
    upd = body.model_dump()
    if not body.active:
        upd["connection_status"] = "DISABLED"
    elif s["connection_status"] == "DISABLED":
        upd["connection_status"] = "CONNECTED" if s.get("credential_enc") else "NOT_CONNECTED"
    await db.suppliers.update_one({"id": sid}, {"$set": upd})
    await audit(actor_of(user), "supplier.settings", "supplier", sid, upd)
    return {"ok": True}


@router.get("/exchange-rates")
async def get_rates(user=Depends(require("suppliers"))):
    return (await db.settings.find_one({"id": "global"}, {"_id": 0, "exchange_rates": 1}) or {}).get("exchange_rates") or {"MMK": 1}


@router.put("/exchange-rates")
async def put_rates(body: dict, user=Depends(require("suppliers"))):
    rates = {str(k).upper()[:6]: float(v) for k, v in body.items() if num(v) is not None and float(v) > 0}
    rates["MMK"] = 1
    await db.settings.update_one({"id": "global"}, {"$set": {"exchange_rates": rates}})
    await audit(actor_of(user), "settings.exchange_rates", "settings", "global", rates)
    return rates


class PricingIn(BaseModel):
    strategy: Literal["manual", "fixed_markup", "percent_markup", "rate_multiplier"] = "percent_markup"
    value: float = 0
    rounding: Literal[0, 100, 500, 1000] = 100


def compute_price(cost, currency, rates, p: PricingIn):
    if p.strategy == "manual":
        return int(p.value)
    if cost is None:
        raise ValueError("supplier cost missing")
    if p.strategy == "rate_multiplier":
        mmk = cost * p.value
    else:
        rate = rates.get((currency or "MMK").upper())
        if not rate:
            raise ValueError(f"no exchange rate set for {currency}")
        mmk = cost * rate
        mmk = mmk + p.value if p.strategy == "fixed_markup" else mmk * (1 + p.value / 100)
    return int(math.ceil(mmk / p.rounding) * p.rounding) if p.rounding else int(round(mmk))


@router.get("/catalogue")
async def catalogue(q: str = "", supplier: str = "", category: str = "", brand: str = "", user=Depends(require("suppliers"))):
    import re
    ids = [s["id"] async for s in db.suppliers.find({"preset_key": {"$ne": None}}, {"_id": 0, "id": 1})]
    query = {"supplier_id": supplier if supplier in ids else {"$in": ids}}
    if q:
        query["name"] = {"$regex": re.escape(q), "$options": "i"}
    if category:
        query["category"] = category
    if brand:
        query["brand"] = brand
    items = await db.supplier_products.find(query, {"_id": 0, "raw": 0}).sort("name", 1).limit(1000).to_list(1000)
    return {"items": items, "categories": sorted({i["category"] for i in items if i.get("category")}),
            "brands": sorted({i["brand"] for i in items if i.get("brand")})}


class ImportItem(BaseModel):
    supplier_product_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    brand_id: Optional[str] = None
    category_id: Optional[str] = None
    activation_method: Optional[str] = ""
    warranty: Optional[str] = ""
    manual_prices: Optional[dict] = None


class ImportBody(BaseModel):
    items: List[ImportItem] = Field(min_length=1, max_length=200)
    pricing: PricingIn


@router.post("/catalogue/preview")
async def preview(body: ImportBody, user=Depends(require("suppliers"))):
    rates = await get_rates(user)
    out = []
    for it in body.items:
        sp = await db.supplier_products.find_one({"id": it.supplier_product_id}, {"_id": 0, "raw": 0})
        for v in (sp or {}).get("variants") or []:
            try:
                price = compute_price(v["cost"], sp.get("currency"), rates, body.pricing)
                err = None
            except ValueError as e:
                price, err = None, str(e)
            out.append({"supplier_product_id": it.supplier_product_id, "variant": v["name"], "cost": v["cost"], "currency": sp.get("currency"),
                        "rate": rates.get((sp.get("currency") or "MMK").upper()), "price_mmk": price, "error": err})
    return out


@router.post("/catalogue/import")
async def import_items(body: ImportBody, user=Depends(require("products"))):
    rates = await get_rates(user)
    created, errors = [], []
    for it in body.items:
        sp = await db.supplier_products.find_one({"id": it.supplier_product_id}, {"_id": 0, "raw": 0})
        if not sp or sp.get("linked_product_id"):
            errors.append({"id": it.supplier_product_id, "error": "not found or already imported"})
            continue
        try:
            variants = [{"id": new_id(), "name": v["name"], "duration": "", "price_mmk": int((it.manual_prices or {}).get(v["key"]) or compute_price(v["cost"], sp.get("currency"), rates, body.pricing)),
                         "promo_price_mmk": None, "promo_start": None, "promo_end": None, "stock_status": "in_stock", "stock_qty": None,
                         "stock_override": None, "supplier_id": sp["supplier_id"], "supplier_product_id": sp["external_id"], "supplier_variant_key": v["key"],
                         "supplier_cost": v["cost"], "supplier_currency": sp.get("currency"), "supplier_stock": sp.get("stock") if sp.get("stock") is not None else 999,
                         "last_synced_at": sp.get("last_synced_at"), "price_locked": True, "active": True} for v in sp.get("variants") or []]
        except ValueError as e:
            errors.append({"id": it.supplier_product_id, "error": str(e)})
            continue
        if not variants:
            errors.append({"id": it.supplier_product_id, "error": "no variants"})
            continue
        name = it.name or sp["name"]
        p = {"id": new_id(), "slug": slugify(name), "name": name, "name_my": "", "brand_id": it.brand_id, "category_id": it.category_id,
             "short_description": (it.description or sp.get("description") or "")[:200], "short_description_my": "",
             "description": it.description or sp.get("description") or "", "description_my": "", "product_type": "subscription",
             "activation_method": it.activation_method or "", "eligibility": "", "warranty": it.warranty or sp.get("warranty") or "",
             "delivery_time": "", "images": [sp["image"]] if sp.get("image") else [], "featured": False, "hot": False, "status": "draft",
             "source_type": "SUPPLIER_API", "variants": variants, "order_count": 0, "created_at": now_iso(), "updated_at": now_iso(), "deleted_at": None}
        recompute(p)
        await db.products.insert_one(dict(p))
        await db.supplier_products.update_one({"id": sp["id"]}, {"$set": {"review_status": "imported", "linked_product_id": p["id"]}})
        created.append(p["id"])
    await audit(actor_of(user), "supplier.catalogue_import", "product", None, {"created": len(created), "errors": len(errors)})
    return {"created": created, "errors": errors}


class ResetIn(BaseModel):
    field: Literal["description", "image", "name"]


@router.post("/catalogue/{spid}/reset")
async def reset_field(spid: str, body: ResetIn, user=Depends(require("products"))):
    sp = await db.supplier_products.find_one({"id": spid}, {"_id": 0})
    if not sp or not sp.get("linked_product_id"):
        raise HTTPException(404, "No linked product")
    val = {"description": {"description": sp.get("description") or ""}, "name": {"name": sp["name"]},
           "image": {"images": [sp["image"]] if sp.get("image") else []}}[body.field]
    await db.products.update_one({"id": sp["linked_product_id"]}, {"$set": val})
    await audit(actor_of(user), "product.reset_to_supplier", "product", sp["linked_product_id"], {"field": body.field})
    return {"ok": True}
