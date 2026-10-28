from core import db, now


def _active_window(start, end):
    t = now().isoformat()
    return (not start or start <= t) and (not end or end >= t)


def promo_active(v):
    p = v.get("promo_price_mmk")
    return bool(p) and p < v.get("price_mmk", 0) and _active_window(v.get("promo_start"), v.get("promo_end"))


def effective_price(v):
    return v["promo_price_mmk"] if promo_active(v) else v.get("price_mmk", 0)


def discount_percent(v):
    if not promo_active(v):
        return 0
    return int(round((v["price_mmk"] - v["promo_price_mmk"]) * 100 / v["price_mmk"]))


def variant_available(v):
    if not v.get("active", True):
        return False
    if v.get("stock_override") == "in_stock":
        return True
    if v.get("stock_override") == "out_of_stock":
        return False
    if v.get("supplier_product_id"):
        return (v.get("supplier_stock") or 0) > 0
    if v.get("stock_status") == "out_of_stock":
        return False
    if v.get("stock_status") == "limited":
        return (v.get("stock_qty") or 0) > 0
    return True


def stock_label(v):
    if not variant_available(v):
        return "out_of_stock"
    qty = v.get("supplier_stock") if v.get("supplier_product_id") and not v.get("stock_override") else v.get("stock_qty")
    if v.get("stock_status") == "limited" or (qty is not None and qty <= 3 and v.get("stock_override") != "in_stock"):
        return "low_stock"
    return "in_stock"


def recompute(product):
    """Denormalized fields used for filtering/sorting."""
    vs = [v for v in product.get("variants", []) if v.get("active", True)]
    avail = [v for v in vs if variant_available(v)]
    prices = [effective_price(v) for v in (avail or vs)]
    product["min_price"] = min(prices) if prices else 0
    product["available"] = bool(avail)
    product["on_promo"] = any(promo_active(v) for v in vs)
    product["low_stock"] = any(stock_label(v) == "low_stock" for v in vs)
    return product


def public_variant(v):
    return {
        "id": v["id"], "name": v.get("name"), "duration": v.get("duration"),
        "price_mmk": v.get("price_mmk"), "effective_price_mmk": effective_price(v),
        "promo_active": promo_active(v), "discount_percent": discount_percent(v),
        "promo_end": v.get("promo_end") if promo_active(v) else None,
        "available": variant_available(v), "stock_label": stock_label(v),
        "stock_checked_at": v.get("last_synced_at") if v.get("supplier_product_id") else None,
    }


PUBLIC_FIELDS = ["id", "slug", "name", "name_my", "short_description", "short_description_my", "description",
                 "description_my", "product_type", "activation_method", "eligibility", "warranty", "delivery_time",
                 "images", "featured", "hot", "min_price", "available", "on_promo", "brand_id", "category_id",
                 "created_at", "order_count", "is_sample"]


async def lookup_maps():
    brands = {b["id"]: b async for b in db.brands.find({"deleted_at": None}, {"_id": 0})}
    cats = {c["id"]: c async for c in db.categories.find({"deleted_at": None}, {"_id": 0})}
    return brands, cats


def public_product(p, brands, cats):
    out = {k: p.get(k) for k in PUBLIC_FIELDS}
    b, c = brands.get(p.get("brand_id")), cats.get(p.get("category_id"))
    out["brand"] = {"id": b["id"], "name": b["name"], "slug": b["slug"]} if b else None
    out["category"] = {"id": c["id"], "name": c["name"], "name_my": c.get("name_my"), "slug": c["slug"]} if c else None
    out["variants"] = [public_variant(v) for v in p.get("variants", []) if v.get("active", True)]
    out["max_discount"] = max([v["discount_percent"] for v in out["variants"]] or [0])
    return out
