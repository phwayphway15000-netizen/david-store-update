# Iteration 2 regression: refactored suppliers sync, OpenAPI read, CSV/XLSX import, order transitions,
# Telegram CALLBACKS dispatch (c:/x:/b:/pm:/a:) and duplicate update handling.
import io
import time
import uuid
import pytest
import requests
from conftest import BASE_URL, BE, SUPPLIER_BASE, SUPPLIER_KEY

API = f"{BASE_URL}/api"
WH = f"{API}/telegram/webhook"
WH_SECRET = BE["TELEGRAM_WEBHOOK_SECRET"]
CHAT = 980000000 + int(time.time()) % 100000
SUP = {"auth_type": "api_key_header", "auth_header_name": "X-API-Key", "credential": SUPPLIER_KEY,
       "products_endpoint": "/api/demo-supplier/products", "items_path": "data.items", "map_id": "sku", "map_name": "title",
       "map_price": "cost_mmk", "map_stock": "qty", "map_description": "details.summary"}


def tg(update):
    return requests.post(WH, json=update, headers={"X-Telegram-Bot-Api-Secret-Token": WH_SECRET}, timeout=30)


def uid():
    return int(time.time() * 1000) % 10**9 + uuid.uuid4().int % 10**6


def msg(text, chat=CHAT):
    return {"update_id": uid(), "message": {"message_id": 1, "chat": {"id": chat, "type": "private"},
                                            "from": {"id": chat, "first_name": "TEST_tg2", "username": "test_tg2"}, "text": text}}


def cb(data, chat=CHAT):
    return {"update_id": uid(), "callback_query": {"id": str(uid()), "data": data, "from": {"id": chat, "first_name": "TEST_tg2"},
                                                   "message": {"message_id": 1, "chat": {"id": chat, "type": "private"}}}}


# ---------- Supplier sync refactor ----------
class TestSupplierSync:
    def test_sync_import_resync(self, owner, mongo):
        s = owner.post(f"{API}/admin/suppliers", json={**SUP, "name": "TEST_Sync2", "base_url": SUPPLIER_BASE}).json()
        sid = s["id"]
        try:
            assert owner.post(f"{API}/admin/suppliers/{sid}/test").json()["ok"]
            r1 = owner.post(f"{API}/admin/suppliers/{sid}/sync", timeout=60).json()
            assert r1["status"] == "success" and r1["new_count"] == 4 and r1["duplicate_count"] == 0, r1
            sps = owner.get(f"{API}/admin/suppliers/{sid}/products").json()
            d2 = next(x for x in sps if x["external_id"] == "DEMO-2")
            imp = owner.post(f"{API}/admin/suppliers/{sid}/import", json={"items": [
                {"supplier_product_id": d2["id"], "name": "TEST_Sync2 Video", "price_mmk": 21000}]}).json()
            pid = imp["created"][0]
            # re-import same supplier product -> skipped
            assert owner.post(f"{API}/admin/suppliers/{sid}/import", json={"items": [
                {"supplier_product_id": d2["id"], "name": "TEST_Sync2 Video", "price_mmk": 21000}]}).json()["created"] == []
            # tamper stored cost + variant stock to verify the sync rewrites them
            mongo.supplier_products.update_one({"id": d2["id"]}, {"$set": {"cost": 1000}})
            mongo.products.update_one({"id": pid}, {"$set": {"variants.0.supplier_stock": 999, "variants.0.supplier_cost": 1}})
            ph_before = mongo.price_history.count_documents({"supplier_id": sid, "kind": "supplier_cost"})
            r2 = owner.post(f"{API}/admin/suppliers/{sid}/sync", timeout=60).json()
            assert r2["status"] == "success" and r2["updated_count"] == 4 and r2["new_count"] == 0 and r2["price_changes"] == 1, r2
            assert mongo.price_history.count_documents({"supplier_id": sid, "kind": "supplier_cost"}) == ph_before + 1
            v = owner.get(f"{API}/admin/products/{pid}").json()["variants"][0]
            assert v["price_mmk"] == 21000 and v["supplier_cost"] == 14000 and v["supplier_stock"] == 5, v
            # unlocked + markup -> selling price recalculated and price history written
            owner.put(f"{API}/admin/suppliers/{sid}", json={**SUP, "name": "TEST_Sync2", "base_url": SUPPLIER_BASE, "markup_percent": 100})
            mongo.products.update_one({"id": pid}, {"$set": {"variants.0.price_locked": False}})
            r3 = owner.post(f"{API}/admin/suppliers/{sid}/sync", timeout=60).json()
            assert r3["status"] == "success", r3
            v = owner.get(f"{API}/admin/products/{pid}").json()["variants"][0]
            assert v["price_mmk"] == 28000, v
            assert mongo.price_history.find_one({"product_id": pid, "kind": "selling_price", "new": 28000}) is not None
            runs = owner.get(f"{API}/admin/suppliers/{sid}/runs").json()
            assert len(runs) == 3 and all(r["status"] == "success" for r in runs)
            owner.delete(f"{API}/admin/products/{pid}")
        finally:
            owner.delete(f"{API}/admin/suppliers/{sid}")

    def test_duplicates_counted(self, owner):
        # map_id -> details.summary ("Sandbox item" for all 4) => 1 new + 3 duplicates
        s = owner.post(f"{API}/admin/suppliers", json={**SUP, "name": "TEST_Dup", "base_url": SUPPLIER_BASE, "map_id": "details.summary"}).json()
        try:
            r = owner.post(f"{API}/admin/suppliers/{s['id']}/sync", timeout=60).json()
            assert r["status"] == "success" and r["new_count"] == 1 and r["duplicate_count"] == 3, r
        finally:
            owner.delete(f"{API}/admin/suppliers/{s['id']}")

    def test_sync_failure_recorded(self, owner):
        s = owner.post(f"{API}/admin/suppliers", json={**SUP, "name": "TEST_BadKey", "base_url": SUPPLIER_BASE, "credential": "wrongkey"}).json()
        try:
            r = owner.post(f"{API}/admin/suppliers/{s['id']}/sync", timeout=90).json()
            assert r["status"] == "failed" and r["attempts"] == 3 and r["error"], r
            assert owner.get(f"{API}/admin/suppliers/{s['id']}").json()["health"] == "error"
        finally:
            owner.delete(f"{API}/admin/suppliers/{s['id']}")


# ---------- OpenAPI read ----------
class TestOpenAPI:
    def test_openapi_errors(self, owner):
        s = owner.post(f"{API}/admin/suppliers", json={**SUP, "name": "TEST_OA", "base_url": SUPPLIER_BASE}).json()
        try:
            r = owner.post(f"{API}/admin/suppliers/{s['id']}/openapi")
            assert r.status_code == 400 and "No OpenAPI URL" in r.json()["detail"], r.text
            owner.put(f"{API}/admin/suppliers/{s['id']}", json={**SUP, "name": "TEST_OA", "base_url": SUPPLIER_BASE, "openapi_url": SUPPLIER_BASE + "/"})
            r = owner.post(f"{API}/admin/suppliers/{s['id']}/openapi")
            assert r.status_code == 400 and "JSON" in r.json()["detail"], r.text
            owner.put(f"{API}/admin/suppliers/{s['id']}", json={**SUP, "name": "TEST_OA", "base_url": SUPPLIER_BASE, "openapi_url": SUPPLIER_BASE + "/api/health"})
            r = owner.post(f"{API}/admin/suppliers/{s['id']}/openapi")
            assert r.status_code == 200 and r.json()["get_endpoints"] == [], r.text
        finally:
            owner.delete(f"{API}/admin/suppliers/{s['id']}")


# ---------- CSV / XLSX import ----------
class TestImport:
    def _cleanup(self, owner, mongo, prefix):
        for d in mongo.products.find({"name": {"$regex": f"^{prefix}"}, "deleted_at": None}):
            owner.delete(f"{API}/admin/products/{d['id']}")

    def test_csv_grouping_errors_autocreate(self, owner, mongo):
        tag = uuid.uuid4().hex[:5]
        csv = ("name,brand,category,plan,duration,price_mmk,description\n"
               f"TEST_Imp {tag},TEST_Brand{tag},TEST_Cat{tag},1 Month,30 days,12000,d\n"
               f"test_imp {tag},TEST_Brand{tag},TEST_Cat{tag},1 Year,365 days,99000,d\n"
               f"TEST_Imp2 {tag},,,Basic,,abc,d\n"
               ",,,x,,100,d\n")
        r = owner.post(f"{API}/admin/products/import", files={"file": ("p.csv", csv.encode(), "text/csv")})
        assert r.status_code == 200, r.text
        d = r.json()
        try:
            assert d["created"] == 1, d
            rows = {e["row"]: e["error"] for e in d["errors"]}
            assert rows.get(4) == "price_mmk must be a number" and rows.get(5) == "name is required", d
            p = mongo.products.find_one({"name": f"TEST_Imp {tag}", "deleted_at": None})
            assert p and p["status"] == "draft" and len(p["variants"]) == 2
            b = mongo.brands.find_one({"name": f"TEST_Brand{tag}"})
            c = mongo.categories.find_one({"name": f"TEST_Cat{tag}"})
            assert b and c and p["brand_id"] == b["id"] and p["category_id"] == c["id"]
            # case-insensitive reuse of existing brand
            csv2 = f"name,brand,price_mmk\nTEST_Imp3 {tag},test_brand{tag},5000\n"
            owner.post(f"{API}/admin/products/import", files={"file": ("q.csv", csv2.encode(), "text/csv")})
            assert mongo.brands.count_documents({"name": {"$regex": f"^TEST_Brand{tag}$", "$options": "i"}}) == 1
        finally:
            self._cleanup(owner, mongo, "TEST_Imp")
            mongo.brands.delete_many({"name": {"$regex": f"^test_brand{tag}$", "$options": "i"}})
            mongo.categories.delete_many({"name": f"TEST_Cat{tag}"})

    def test_xlsx_import(self, owner, mongo):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["name", "plan", "price_mmk"])
        ws.append(["TEST_XL Prod", "Monthly", 7000])
        ws.append(["TEST_XL Prod", "Yearly", 70000.0])
        buf = io.BytesIO()
        wb.save(buf)
        r = owner.post(f"{API}/admin/products/import", files={"file": ("p.xlsx", buf.getvalue(), "application/octet-stream")})
        try:
            assert r.status_code == 200 and r.json()["created"] == 1, r.text
            p = mongo.products.find_one({"name": "TEST_XL Prod", "deleted_at": None})
            assert sorted(v["price_mmk"] for v in p["variants"]) == [7000, 70000]
        finally:
            self._cleanup(owner, mongo, "TEST_XL")

    def test_bad_extension(self, owner):
        r = owner.post(f"{API}/admin/products/import", files={"file": ("p.txt", b"a,b", "text/plain")})
        assert r.status_code == 400


# ---------- Order transitions ----------
class TestTransitions:
    def test_invalid_transitions_400(self, owner, published_variant):
        p, v = published_variant
        o = owner.post(f"{API}/admin/orders", json={"product_id": p["id"], "variant_id": v["id"], "source": "DIRECT_MESSENGER",
                                                    "customer_name": "TEST_Trans"}).json()
        oid = o["id"]
        try:
            for to in ("COMPLETED", "DELIVERED", "PAID_AWAITING_FULFILLMENT"):
                r = owner.post(f"{API}/admin/orders/{oid}/transition", json={"to": to, "note": "x"})
                assert r.status_code == 400 and r.json()["detail"], (to, r.status_code, r.text)
            r = owner.post(f"{API}/admin/orders/{oid}/deliver", json={"content": "lic"})
            assert r.status_code == 400 and r.json()["detail"], r.text
            assert owner.post(f"{API}/admin/orders/{oid}/deliver", json={"content": ""}).status_code == 422
            assert owner.post(f"{API}/admin/orders/nonexistent/transition", json={"to": "CANCELLED"}).status_code == 404
        finally:
            owner.post(f"{API}/admin/orders/{oid}/transition", json={"to": "CANCELLED", "note": "TEST cleanup"})
        # cancelled -> anything invalid
        r = owner.post(f"{API}/admin/orders/{oid}/transition", json={"to": "AWAITING_PAYMENT"})
        assert r.status_code == 400, r.text


# ---------- Telegram callback dispatch ----------
@pytest.fixture
def kbz(owner):
    pms = owner.get(f"{API}/admin/payment-methods").json()
    m = next(m for m in pms if "kbz" in m["name"].lower())
    base = {"name": m["name"], "instructions": m.get("instructions") or "", "sort": m.get("sort", 100)}
    r = owner.put(f"{API}/admin/payment-methods/{m['id']}", json={**base, "account_name": "TEST Acc", "account_number": "09000000000", "enabled": True})
    assert r.status_code == 200, r.text
    yield r.json()
    owner.put(f"{API}/admin/payment-methods/{m['id']}", json={**base, "account_name": "", "account_number": "", "enabled": False})


class TestTelegramCallbacks:
    def test_cancel_intent(self, anon, mongo, published_variant):
        p, v = published_variant
        tok = anon.post(f"{API}/checkout/telegram", json={"product_id": p["id"], "variant_id": v["id"]}).json()["deep_link"].split("start=")[1]
        tg(msg(f"/start {tok}"))
        it = mongo.checkout_intents.find_one({"chat_id": str(CHAT)}, sort=[("created_at", -1)])
        assert it["status"] == "RESOLVED"
        assert tg(cb(f"x:{it['id']}")).json()["result"] == "ok"
        assert mongo.checkout_intents.find_one({"id": it["id"]})["status"] == "CANCELLED"
        tg(cb(f"c:{it['id']}"))
        assert mongo.orders.count_documents({"checkout_intent_id": it["id"]}) == 0

    def test_bot_buy_confirm_paymethod_evidence(self, mongo, published_variant, kbz, owner):
        p, v = published_variant
        assert tg(cb(f"b:{p['id'][:8]}:{v['id'][:8]}")).json()["result"] == "ok"
        it = mongo.checkout_intents.find_one({"chat_id": str(CHAT), "source": "bot"}, sort=[("created_at", -1)])
        assert it and it["status"] == "RESOLVED" and it["product_id"] == p["id"] and it["variant_id"] == v["id"]
        tg(cb(f"c:{it['id']}"))
        o = mongo.orders.find_one({"checkout_intent_id": it["id"]})
        assert o and o["status"] == "AWAITING_PAYMENT" and o["channel_id"] == str(CHAT)
        try:
            # other chat cannot pick method for this order
            tg(cb(f"pm:{o['ref']}:{kbz['code']}", chat=CHAT + 7))
            assert mongo.orders.find_one({"id": o["id"]}).get("payment_method_id") is None
            assert tg(cb(f"pm:{o['ref']}:{kbz['code']}")).json()["result"] == "ok"
            assert mongo.orders.find_one({"id": o["id"]})["payment_method_id"] == kbz["id"]
            sess = mongo.telegram_sessions.find_one({"chat_id": str(CHAT)})
            assert sess["mode"] == "await_evidence" and sess["order_id"] == o["id"]
            tg(msg("TEST_TX_123456"))
            o2 = mongo.orders.find_one({"id": o["id"]})
            assert o2["status"] == "PAYMENT_SUBMITTED"
            assert mongo.payment_evidence.find_one({"order_id": o["id"], "reference": "TEST_TX_123456"})
        finally:
            owner.post(f"{API}/admin/orders/{o['id']}/transition", json={"to": "CANCELLED", "note": "TEST cleanup"})

    def test_bad_buy_and_unknown_callback(self):
        assert tg(cb("b:zzzzzzzz:zzzzzzzz")).json()["result"] == "ok"
        assert tg(cb("zz:whatever")).json()["result"] == "ok"
        assert tg(cb("pm:DAV-0000-000000:kbzpay")).json()["result"] == "ok"

    def test_unauthorized_admin_and_duplicate(self, mongo):
        u = cb("a:view:DAV-2026-000001", chat=CHAT + 3)
        assert tg(u).json()["result"] == "ok"
        assert tg(u).json()["result"] == "duplicate"
        assert mongo.audit_logs.find_one({"action": "telegram.unauthorized_admin_action", "actor.id": str(CHAT + 3)})
