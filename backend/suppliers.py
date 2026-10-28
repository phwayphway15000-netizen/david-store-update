import asyncio
import ipaddress
from datetime import datetime
import json
import socket
from urllib.parse import urlparse, urljoin

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict

from core import db, now, now_iso, new_id, encrypt, decrypt, mask, require, actor_of, audit, logger, slugify
from catalog import recompute
import tg_api

router = APIRouter(prefix="/api/admin/suppliers")
MAX_BYTES = 5 * 1024 * 1024
BLOCKED_HEADERS = {"host", "content-length", "transfer-encoding", "connection", "cookie"}


class SupplierIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    base_url: str = Field(max_length=300)
    docs_url: Optional[str] = ""
    openapi_url: Optional[str] = ""
    auth_type: Literal["none", "api_key_header", "bearer", "custom_headers"] = "none"
    auth_header_name: Optional[str] = "X-API-Key"
    credential: Optional[str] = None
    custom_headers: Optional[Dict[str, str]] = None
    products_endpoint: str = "/products"
    items_path: str = ""
    map_id: str = "id"
    map_name: str = "name"
    map_price: str = "price"
    map_stock: str = "stock"
    map_description: Optional[str] = ""
    map_image: Optional[str] = ""
    map_brand: Optional[str] = ""
    sync_interval_minutes: int = Field(default=0, ge=0, le=10080)
    markup_percent: Optional[float] = Field(default=None, ge=0, le=1000)
    active: bool = True


def check_url(url):
    p = urlparse(url)
    if p.scheme != "https":
        raise ValueError("Only https:// supplier URLs are allowed")
    host = p.hostname
    if not host or host == "localhost" or host.endswith(".local") or host.endswith(".internal"):
        raise ValueError("Host not allowed")
    if p.username or p.password:
        raise ValueError("Credentials in URL are not allowed; use the authentication fields")
    if p.port not in (None, 443, 8443):
        raise ValueError("Only ports 443/8443 are allowed")
    try:
        infos = socket.getaddrinfo(host, p.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise ValueError("Host could not be resolved")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise ValueError("Private, loopback or internal network targets are not allowed")
    return url


def get_path(obj, path):
    if not path:
        return obj
    for part in path.split("."):
        if isinstance(obj, list) and part.isdigit():
            obj = obj[int(part)] if int(part) < len(obj) else None
        elif isinstance(obj, dict):
            obj = obj.get(part)
        else:
            return None
    return obj


def headers_for(s):
    h = {"Accept": "application/json", "User-Agent": "DavidStore-SupplierSync/1.0"}
    cred = decrypt(s.get("credential_enc"))
    if s["auth_type"] == "api_key_header" and cred:
        h[s.get("auth_header_name") or "X-API-Key"] = cred
    elif s["auth_type"] == "bearer" and cred:
        h["Authorization"] = f"Bearer {cred}"
    elif s["auth_type"] == "custom_headers" and s.get("custom_headers_enc"):
        for k, v in json.loads(decrypt(s["custom_headers_enc"])).items():
            if k.lower() not in BLOCKED_HEADERS:
                h[k] = v
    return h


async def safe_get(url, headers):
    check_url(url)
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as c:
        async with c.stream("GET", url, headers=headers) as r:
            body = b""
            async for chunk in r.aiter_bytes():
                body += chunk
                if len(body) > MAX_BYTES:
                    raise ValueError("Response too large")
            return r.status_code, body


async def fetch_items(s):
    url = urljoin(s["base_url"].rstrip("/") + "/", s["products_endpoint"].lstrip("/"))
    status, body = await safe_get(url, headers_for(s))
    if status >= 400:
        raise ValueError(f"Supplier responded with HTTP {status}")
    try:
        data = json.loads(body)
    except Exception:
        raise ValueError("Supplier response is not valid JSON")
    items = get_path(data, s.get("items_path") or "")
    if not isinstance(items, list):
        raise ValueError("Items path did not resolve to a list")
    return status, items


def normalize(s, raw):
    def num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None
    ext = get_path(raw, s["map_id"])
    return {"external_id": str(ext) if ext is not None else None, "name": str(get_path(raw, s["map_name"]) or "")[:200],
            "cost": num(get_path(raw, s["map_price"])), "stock": num(get_path(raw, s["map_stock"])),
            "description": str(get_path(raw, s.get("map_description")) or "")[:2000] if s.get("map_description") else "",
            "image": str(get_path(raw, s.get("map_image")) or "") if s.get("map_image") else "",
            "brand": str(get_path(raw, s.get("map_brand")) or "") if s.get("map_brand") else ""}


def public_supplier(s):
    out = {k: v for k, v in s.items() if k not in ("credential_enc", "custom_headers_enc")}
    out["credential_masked"] = mask(decrypt(s.get("credential_enc"))) if s.get("credential_enc") else ""
    out["custom_header_names"] = list(json.loads(decrypt(s["custom_headers_enc"])).keys()) if s.get("custom_headers_enc") else []
    return out


async def get_supplier(sid):
    s = await db.suppliers.find_one({"id": sid, "deleted_at": None}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Supplier not found")
    return s


async def fetch_with_retry(s, run):
    err = None
    for attempt in range(3):
        run["attempts"] = attempt + 1
        try:
            _, items = await fetch_items(s)
            return items, None
        except Exception as e:
            err = str(e)
            await asyncio.sleep(2 ** attempt)
    return None, err


async def upsert_supplier_product(s, n, raw, run, alerts):
    existing = await db.supplier_products.find_one({"supplier_id": s["id"], "external_id": n["external_id"]}, {"_id": 0})
    await db.inventory_snapshots.insert_one({"supplier_id": s["id"], "external_id": n["external_id"], "stock": n["stock"],
                                             "cost": n["cost"], "taken_at": now_iso()})
    if not existing:
        await db.supplier_products.insert_one({"id": new_id(), "supplier_id": s["id"], **n, "raw": raw if len(json.dumps(raw)) < 20000 else {},
                                               "review_status": "new", "linked_product_id": None,
                                               "first_seen_at": now_iso(), "last_seen_at": now_iso()})
        run["new_count"] += 1
        return
    if existing.get("cost") is not None and n["cost"] is not None and existing["cost"] != n["cost"]:
        run["price_changes"] += 1
        alerts.append(f"{n['name']}: {existing['cost']} → {n['cost']}")
        await db.price_history.insert_one({"id": new_id(), "kind": "supplier_cost", "supplier_id": s["id"],
                                           "external_id": n["external_id"], "old": existing["cost"], "new": n["cost"], "created_at": now_iso()})
    await db.supplier_products.update_one({"id": existing["id"]}, {"$set": {**n, "last_seen_at": now_iso()}})
    run["updated_count"] += 1


async def apply_to_variant(s, p, v, n):
    """Only supplier-owned fields change; selling price only when unlocked and a markup is configured."""
    v["supplier_cost"], v["supplier_stock"], v["last_synced_at"] = n["cost"], n["stock"], now_iso()
    if v.get("price_locked", True) or s.get("markup_percent") is None or n["cost"] is None:
        return
    newp = int(round(n["cost"] * (1 + s["markup_percent"] / 100)))
    if newp != v.get("price_mmk"):
        await db.price_history.insert_one({"id": new_id(), "kind": "selling_price", "product_id": p["id"], "variant_id": v["id"],
                                           "old": v.get("price_mmk"), "new": newp, "source": "supplier_markup", "created_at": now_iso()})
        v["price_mmk"] = newp


async def update_linked_variants(s, n):
    async for p in db.products.find({"variants.supplier_id": s["id"], "variants.supplier_product_id": n["external_id"]}, {"_id": 0}):
        for v in p["variants"]:
            if v.get("supplier_id") == s["id"] and v.get("supplier_product_id") == n["external_id"]:
                await apply_to_variant(s, p, v, n)
        recompute(p)
        await db.products.update_one({"id": p["id"]}, {"$set": {"variants": p["variants"], "min_price": p["min_price"],
                                                                 "available": p["available"], "low_stock": p["low_stock"],
                                                                 "on_promo": p["on_promo"], "last_synced_at": now_iso()}})


async def run_sync(s, actor, trigger="manual"):
    run = {"id": new_id(), "supplier_id": s["id"], "trigger": trigger, "status": "running", "started_at": now_iso(),
           "new_count": 0, "updated_count": 0, "duplicate_count": 0, "price_changes": 0, "error": None, "attempts": 0}
    await db.supplier_sync_runs.insert_one(dict(run))
    items, err = await fetch_with_retry(s, run)
    if items is None:
        run.update(status="failed", error=err, finished_at=now_iso())
        await db.supplier_sync_runs.update_one({"id": run["id"]}, {"$set": run})
        await db.suppliers.update_one({"id": s["id"]}, {"$set": {"health": "error", "last_error": err, "last_sync_at": now_iso()}})
        await tg_api.notify_owner(f"⚠️ Supplier sync failed: {tg_api.esc(s['name'])} — {tg_api.esc(err)}")
        return run
    seen, alerts = set(), []
    for raw in items[:5000]:
        n = normalize(s, raw)
        if not n["external_id"]:
            continue
        if n["external_id"] in seen:
            run["duplicate_count"] += 1
            continue
        seen.add(n["external_id"])
        await upsert_supplier_product(s, n, raw, run, alerts)
        await update_linked_variants(s, n)
    run.update(status="success", finished_at=now_iso(), item_count=len(items))
    await db.supplier_sync_runs.update_one({"id": run["id"]}, {"$set": run})
    await db.suppliers.update_one({"id": s["id"]}, {"$set": {"health": "ok", "last_error": None, "last_sync_at": now_iso()}})
    await audit(actor, "supplier.sync", "supplier", s["id"], {k: run[k] for k in ("new_count", "updated_count", "price_changes", "duplicate_count")})
    if alerts:
        await tg_api.notify_owner(f"📈 Supplier price changes ({tg_api.esc(s['name'])}):\n" + "\n".join(tg_api.esc(a) for a in alerts[:10]))
    return run


async def scheduler_loop():
    while True:
        try:
            async for s in db.suppliers.find({"active": True, "deleted_at": None, "sync_interval_minutes": {"$gt": 0}}, {"_id": 0}):
                last = s.get("last_sync_at")
                due = not last or (now() - datetime.fromisoformat(last)).total_seconds() >= s["sync_interval_minutes"] * 60
                if due:
                    await run_sync(s, {"type": "system", "id": "scheduler"}, "scheduled")
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        await asyncio.sleep(60)


def build_doc(body: SupplierIn, existing=None):
    try:
        check_url(body.base_url)
    except ValueError as e:
        raise HTTPException(400, f"Base URL rejected: {e}")
    d = body.model_dump(exclude={"credential", "custom_headers"})
    if body.credential:
        d["credential_enc"] = encrypt(body.credential)
    if body.custom_headers is not None:
        bad = [k for k in body.custom_headers if k.lower() in BLOCKED_HEADERS]
        if bad:
            raise HTTPException(400, f"Header not allowed: {bad[0]}")
        d["custom_headers_enc"] = encrypt(json.dumps(body.custom_headers)) if body.custom_headers else None
    if existing is None:
        d.update(id=new_id(), created_at=now_iso(), deleted_at=None, health="unknown", validated=False,
                 last_test=None, last_sync_at=None, credential_enc=d.get("credential_enc"))
    d["updated_at"] = now_iso()
    return d


@router.get("")
async def list_suppliers(user=Depends(require("suppliers"))):
    items = await db.suppliers.find({"deleted_at": None}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return [public_supplier(s) for s in items]


@router.post("")
async def create_supplier(body: SupplierIn, user=Depends(require("suppliers"))):
    d = build_doc(body)
    await db.suppliers.insert_one(dict(d))
    await audit(actor_of(user), "supplier.created", "supplier", d["id"], {"name": d["name"]})
    return public_supplier(d)


@router.get("/{sid}")
async def get_one(sid: str, user=Depends(require("suppliers"))):
    return public_supplier(await get_supplier(sid))


@router.put("/{sid}")
async def update_supplier(sid: str, body: SupplierIn, user=Depends(require("suppliers"))):
    await get_supplier(sid)
    d = build_doc(body, existing=True)
    await db.suppliers.update_one({"id": sid}, {"$set": {**d, "validated": False}})
    await audit(actor_of(user), "supplier.updated", "supplier", sid, {"credential_changed": bool(body.credential)})
    return public_supplier(await get_supplier(sid))


@router.delete("/{sid}")
async def delete_supplier(sid: str, user=Depends(require("suppliers"))):
    await db.suppliers.update_one({"id": sid}, {"$set": {"deleted_at": now_iso(), "active": False}})
    await audit(actor_of(user), "supplier.deleted", "supplier", sid)
    return {"ok": True}


@router.post("/{sid}/validate")
async def validate(sid: str, user=Depends(require("suppliers"))):
    s = await get_supplier(sid)
    problems = []
    try:
        check_url(s["base_url"])
    except ValueError as e:
        problems.append(f"Base URL: {e}")
    if s["auth_type"] in ("api_key_header", "bearer") and not s.get("credential_enc"):
        problems.append("Authentication selected but no credential saved")
    if s["auth_type"] == "custom_headers" and not s.get("custom_headers_enc"):
        problems.append("Custom headers auth selected but no headers saved")
    for f in ("map_id", "map_name", "map_price", "map_stock", "products_endpoint"):
        if not s.get(f):
            problems.append(f"Missing mapping: {f}")
    await db.suppliers.update_one({"id": sid}, {"$set": {"validated": not problems}})
    return {"valid": not problems, "problems": problems}


@router.post("/{sid}/test")
async def test_connection(sid: str, user=Depends(require("suppliers"))):
    s = await get_supplier(sid)
    result = {"ok": False, "at": now_iso()}
    try:
        status, items = await fetch_items(s)
        sample = normalize(s, items[0]) if items else None
        result.update(ok=True, status_code=status, item_count=len(items), sample_mapped=sample,
                      sample_keys=list(items[0].keys())[:30] if items and isinstance(items[0], dict) else [],
                      message=f"Connected. {len(items)} items found.")
    except Exception as e:
        result.update(message=str(e)[:300])
    await db.suppliers.update_one({"id": sid}, {"$set": {"last_test": result, "health": "ok" if result["ok"] else "error"}})
    await audit(actor_of(user), "supplier.tested", "supplier", sid, {"ok": result["ok"]})
    return result


@router.post("/{sid}/openapi")
async def read_openapi(sid: str, user=Depends(require("suppliers"))):
    s = await get_supplier(sid)
    if not s.get("openapi_url"):
        raise HTTPException(400, "No OpenAPI URL configured")
    spec = {}
    try:
        status, body = await safe_get(s["openapi_url"], {"Accept": "application/json"})
        spec = json.loads(body)
    except Exception as e:
        raise HTTPException(400, f"Could not read spec as JSON: {str(e)[:200]}") from e
    if not isinstance(spec, dict):
        raise HTTPException(400, "Spec must be a JSON object")
    paths = [{"path": p, "summary": (ops.get("get") or {}).get("summary", "")}
             for p, ops in (spec.get("paths") or {}).items() if isinstance(ops, dict) and "get" in ops]
    return {"title": (spec.get("info") or {}).get("title"), "get_endpoints": paths[:100],
            "note": "Pick the products endpoint and map fields manually; specs are never executed."}


@router.post("/{sid}/sync")
async def manual_sync(sid: str, user=Depends(require("suppliers"))):
    s = await get_supplier(sid)
    return await run_sync(s, actor_of(user))


@router.get("/{sid}/runs")
async def runs(sid: str, user=Depends(require("suppliers"))):
    return await db.supplier_sync_runs.find({"supplier_id": sid}, {"_id": 0}).sort("started_at", -1).limit(30).to_list(30)


@router.get("/{sid}/products")
async def supplier_products(sid: str, user=Depends(require("suppliers"))):
    return await db.supplier_products.find({"supplier_id": sid}, {"_id": 0, "raw": 0}).sort("first_seen_at", -1).to_list(1000)


class ImportItem(BaseModel):
    supplier_product_id: str
    name: str = Field(min_length=2, max_length=160)
    price_mmk: int = Field(ge=0)
    description: Optional[str] = ""
    brand_id: Optional[str] = None
    category_id: Optional[str] = None
    plan_name: str = "Standard"
    duration: str = ""
    publish: bool = False


class ImportBody(BaseModel):
    items: List[ImportItem]


@router.post("/{sid}/import")
async def import_products(sid: str, body: ImportBody, user=Depends(require("products"))):
    await get_supplier(sid)
    created = []
    for it in body.items:
        sp = await db.supplier_products.find_one({"id": it.supplier_product_id, "supplier_id": sid}, {"_id": 0})
        if not sp:
            continue
        if sp.get("linked_product_id"):
            continue
        p = {"id": new_id(), "slug": slugify(it.name), "name": it.name, "name_my": "", "brand_id": it.brand_id,
             "category_id": it.category_id, "short_description": it.description[:200], "short_description_my": "",
             "description": it.description or sp.get("description", ""), "description_my": "", "product_type": "subscription",
             "activation_method": "", "eligibility": "", "warranty": "", "delivery_time": "",
             "images": [sp["image"]] if sp.get("image", "").startswith("https://") else [],
             "featured": False, "hot": False, "status": "published" if it.publish else "draft", "source_type": "SUPPLIER_API",
             "variants": [{"id": new_id(), "name": it.plan_name, "duration": it.duration, "price_mmk": it.price_mmk,
                           "promo_price_mmk": None, "promo_start": None, "promo_end": None, "stock_status": "in_stock",
                           "stock_qty": None, "stock_override": None, "supplier_id": sid, "supplier_product_id": sp["external_id"],
                           "supplier_cost": sp.get("cost"), "supplier_stock": sp.get("stock"), "last_synced_at": now_iso(),
                           "price_locked": True, "active": True}],
             "order_count": 0, "created_at": now_iso(), "updated_at": now_iso(), "deleted_at": None}
        recompute(p)
        await db.products.insert_one(dict(p))
        await db.supplier_products.update_one({"id": sp["id"]}, {"$set": {"review_status": "imported", "linked_product_id": p["id"]}})
        created.append(p["id"])
    await audit(actor_of(user), "supplier.import", "supplier", sid, {"created": len(created)})
    return {"created": created}
