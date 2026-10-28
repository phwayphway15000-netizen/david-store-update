# Regression suite: AI Tools By David Digital Store (auth, storefront, checkout, telegram webhook,
# products, suppliers, payment methods, order state machine, RBAC, dashboard, SEO)
import io
import re
import time
import uuid
import hashlib
import pytest
import requests
from conftest import BASE_URL, BE, login, SUPPLIER_BASE, SUPPLIER_KEY

API = f"{BASE_URL}/api"
WH = f"{API}/telegram/webhook"
WH_SECRET = BE["TELEGRAM_WEBHOOK_SECRET"]
FAKE_CHAT = 990000000 + int(time.time()) % 100000


# ---------- Auth ----------
class TestAuth:
    def test_login_cookies_and_me(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": "chutpakoda05@gmail.com", "password": "-FkF3oEvLf-j"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["role"] == "owner" and "password_hash" not in d
        sc = r.headers.get("set-cookie", "").lower()
        assert "access_token=" in sc and "httponly" in sc and "secure" in sc
        me = s.get(f"{API}/auth/me")
        assert me.status_code == 200 and me.json()["email"] == "chutpakoda05@gmail.com"

    def test_wrong_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": "TEST_wrong_%s@example.com" % uuid.uuid4().hex[:6], "password": "nope"})
        assert r.status_code == 401
        assert "Invalid" in r.json()["detail"]

    def test_lockout_after_5(self):
        email = f"test_lock_{uuid.uuid4().hex[:6]}@example.com"
        codes = [requests.post(f"{API}/auth/login", json={"email": email, "password": "bad"}).status_code for _ in range(6)]
        assert codes[:5] == [401] * 5 and codes[5] == 429, codes

    def test_lockout_bypass_via_xff(self):
        """Lockout identifier uses first X-Forwarded-For value -> spoofable?"""
        email = f"test_xff_{uuid.uuid4().hex[:6]}@example.com"
        for _ in range(5):
            requests.post(f"{API}/auth/login", json={"email": email, "password": "bad"})
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": "bad"}, headers={"X-Forwarded-For": "8.8.4.4"})
        print("XFF spoof status:", r.status_code)
        assert r.status_code == 429, "Lockout bypassable by spoofing X-Forwarded-For"

    def test_bcrypt_hash(self, mongo):
        u = mongo.users.find_one({"email": "chutpakoda05@gmail.com"})
        assert u["password_hash"].startswith("$2b$")

    def test_unauth_admin(self):
        assert requests.get(f"{API}/admin/orders").status_code == 401


# ---------- Public storefront ----------
class TestPublic:
    def test_health_settings(self, anon):
        assert anon.get(f"{API}/health").status_code == 200
        s = anon.get(f"{API}/settings/public").json()
        assert s.get("brand_name")

    def test_catalog_filters(self, anon):
        d = anon.get(f"{API}/products", params={"limit": 48}).json()
        assert d["total"] >= 1
        empty = anon.get(f"{API}/products", params={"q": "zzznomatch"}).json()
        assert empty["total"] == 0
        promo = anon.get(f"{API}/products", params={"promo": "true", "limit": 48}).json()
        assert all(p.get("on_promo") for p in promo["items"])
        asc = anon.get(f"{API}/products", params={"sort": "price_asc", "limit": 48}).json()["items"]
        prices = [p["min_price"] for p in asc]
        assert prices == sorted(prices)
        rng = anon.get(f"{API}/products", params={"min_price": 20000, "max_price": 50000, "limit": 48}).json()["items"]
        assert all(20000 <= p["min_price"] <= 50000 for p in rng)

    def test_og_and_sitemap(self, anon, published_variant):
        p, v = published_variant
        r = anon.get(f"{API}/og/product/{p['slug']}")
        assert r.status_code == 200
        assert 'property="og:title"' in r.text and 'property="og:description"' in r.text
        assert f"{v['effective_price_mmk']:,}" in r.text
        sm = anon.get(f"{API}/sitemap.xml")
        assert sm.status_code == 200 and p["slug"] in sm.text
        assert anon.get(f"{API}/og/product/nonexistent-slug").status_code == 404

    def test_sitemap_uses_current_host(self, anon):
        sm = anon.get(f"{API}/sitemap.xml").text
        locs = re.findall(r"<loc>([^<]+)</loc>", sm)
        print("first loc:", locs[0])
        assert locs[0].startswith(BASE_URL), f"sitemap host {locs[0]} != {BASE_URL}"

    def test_robots(self, anon):
        r = anon.get(f"{BASE_URL}/robots.txt")
        assert r.status_code == 200 and "user-agent" in r.text.lower()


# ---------- Checkout ----------
class TestCheckout:
    def test_telegram_deeplink(self, anon, published_variant):
        p, v = published_variant
        r = anon.post(f"{API}/checkout/telegram", json={"product_id": p["id"], "variant_id": v["id"]})
        assert r.status_code == 200, r.text
        link = r.json()["deep_link"]
        assert re.match(r"^https://t\.me/aitoolsbydavidstore001_bot\?start=[\w-]+$", link), link

    def test_bad_variant(self, anon, published_variant):
        p, _ = published_variant
        r = anon.post(f"{API}/checkout/telegram", json={"product_id": p["id"], "variant_id": "bad"})
        assert r.status_code == 400

    def test_messenger_ref_and_track(self, anon, published_variant):
        p, v = published_variant
        r = anon.post(f"{API}/checkout/messenger", json={"product_id": p["id"], "variant_id": v["id"], "customer_name": "TEST_buyer"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert re.match(r"^DAV-\d{4}-\d{6}$", d["order_ref"])
        assert d["order_ref"] in d["summary"]
        t = anon.get(f"{API}/orders/track", params={"ref": d["order_ref"], "token": d["track_token"]})
        assert t.status_code == 200 and t.json()["status"] == "AWAITING_CUSTOMER_CONFIRMATION"
        assert anon.get(f"{API}/orders/track", params={"ref": d["order_ref"], "token": "wrong"}).status_code == 404


# ---------- Telegram webhook simulation ----------
def tg(update, secret=WH_SECRET):
    h = {"X-Telegram-Bot-Api-Secret-Token": secret} if secret else {}
    return requests.post(WH, json=update, headers=h, timeout=30)


def uid():
    return int(time.time() * 1000) % 10**9 + uuid.uuid4().int % 10**6


def msg(text, chat=FAKE_CHAT):
    return {"update_id": uid(), "message": {"message_id": 1, "chat": {"id": chat, "type": "private"},
                                            "from": {"id": chat, "first_name": "TEST_tg"}, "text": text}}


def cb(data, chat=FAKE_CHAT):
    return {"update_id": uid(), "callback_query": {"id": str(uid()), "data": data, "from": {"id": chat, "first_name": "TEST_tg"},
                                                   "message": {"message_id": 1, "chat": {"id": chat, "type": "private"}}}}


class TestTelegramWebhook:
    def test_secret_required(self):
        assert tg(msg("/start"), secret=None).status_code == 403
        assert tg(msg("/start"), secret="wrong").status_code == 403

    def test_duplicate_update(self):
        u = msg("/help")
        assert tg(u).json()["result"] == "ok"
        assert tg(u).json()["result"] == "duplicate"

    def test_start_token_confirm_creates_order(self, anon, mongo, published_variant):
        p, v = published_variant
        link = anon.post(f"{API}/checkout/telegram", json={"product_id": p["id"], "variant_id": v["id"]}).json()["deep_link"]
        token = link.split("start=")[1]
        th = hashlib.sha256(token.encode()).hexdigest()
        assert tg(msg(f"/start {token}")).json()["result"] == "ok"
        intent = mongo.checkout_intents.find_one({"chat_id": str(FAKE_CHAT), "product_id": p["id"]}, sort=[("created_at", -1)])
        assert intent and intent["status"] == "RESOLVED", intent
        # reuse by other chat -> refused (intent remains bound to first chat)
        tg(msg(f"/start {token}", chat=FAKE_CHAT + 1))
        assert mongo.checkout_intents.find_one({"id": intent["id"]})["chat_id"] == str(FAKE_CHAT)
        assert tg(cb(f"c:{intent['id']}")).json()["result"] == "ok"
        o = mongo.orders.find_one({"checkout_intent_id": intent["id"]})
        assert o and o["status"] == "AWAITING_PAYMENT" and o["source"] == "WEBSITE_TELEGRAM"
        # confirm again -> no second order
        tg(cb(f"c:{intent['id']}"))
        assert mongo.orders.count_documents({"checkout_intent_id": intent["id"]}) == 1
        pytest.tg_order_ref = o["ref"]

    def test_expired_token(self, mongo):
        r = tg(msg("/start nonexistenttoken123"))
        assert r.json()["result"] == "ok"

    def test_non_owner_admin_callback_refused(self, mongo):
        ref = getattr(pytest, "tg_order_ref", "DAV-2026-000001")
        before = mongo.orders.find_one({"ref": ref})["status"]
        assert tg(cb(f"a:approve_yes:{ref}")).json()["result"] == "ok"
        assert mongo.orders.find_one({"ref": ref})["status"] == before
        log = mongo.audit_logs.find_one({"action": "telegram.unauthorized_admin_action", "actor.id": str(FAKE_CHAT)})
        assert log is not None


# ---------- Payment methods ----------
class TestPaymentMethods:
    def test_enable_requires_account(self, owner):
        pms = owner.get(f"{API}/admin/payment-methods").json()
        kbz = next((m for m in pms if "kbz" in m["name"].lower()), None)
        assert kbz, [m["name"] for m in pms]
        base = {k: kbz.get(k) or "" for k in ("name", "instructions")}
        base["sort"] = kbz.get("sort", 100)
        r = owner.put(f"{API}/admin/payment-methods/{kbz['id']}", json={**base, "account_name": "", "account_number": "", "enabled": True})
        assert r.status_code == 400
        r = owner.put(f"{API}/admin/payment-methods/{kbz['id']}", json={**base, "account_name": "TEST Name", "account_number": "09123456789", "enabled": True})
        assert r.status_code == 200 and r.json()["enabled"] is True
        # restore original
        owner.put(f"{API}/admin/payment-methods/{kbz['id']}", json={**base, "account_name": kbz.get("account_name") or "",
                                                                     "account_number": kbz.get("account_number") or "", "enabled": kbz.get("enabled", False)})


# ---------- Products ----------
class TestProducts:
    def _payload(self, **kw):
        d = {"name": "TEST_Product " + uuid.uuid4().hex[:5], "short_description": "TEST desc", "status": "draft",
             "variants": [{"name": "1 Month", "duration": "30 days", "price_mmk": 20000, "promo_price_mmk": 15000},
                          {"name": "1 Year", "duration": "365 days", "price_mmk": 150000}]}
        d.update(kw)
        return d

    def test_promo_validation(self, owner):
        p = self._payload()
        p["variants"][0]["promo_price_mmk"] = 25000
        r = owner.post(f"{API}/admin/products", json=p)
        assert r.status_code == 400 and "lower" in r.json()["detail"]

    def test_crud_publish_bulk(self, owner, anon):
        r = owner.post(f"{API}/admin/products", json=self._payload())
        assert r.status_code == 200, r.text
        pr = r.json()
        assert len(pr["variants"]) == 2
        assert anon.get(f"{API}/products/{pr['slug']}").status_code == 404
        b = owner.post(f"{API}/admin/products/bulk", json={"ids": [pr["id"]], "action": "publish"})
        assert b.json()["updated"] == 1
        pub = anon.get(f"{API}/products/{pr['slug']}")
        assert pub.status_code == 200
        eff = sorted(v["effective_price_mmk"] for v in pub.json()["variants"])
        assert eff == [15000, 150000]
        owner.post(f"{API}/admin/products/bulk", json={"ids": [pr["id"]], "action": "feature"})
        b = owner.post(f"{API}/admin/products/bulk", json={"ids": [pr["id"]], "action": "price_adjust_percent", "value": "10"})
        assert b.status_code == 200
        g = owner.get(f"{API}/admin/products/{pr['id']}").json()
        assert g["featured"] is True
        assert sorted(v["price_mmk"] for v in g["variants"]) == [22000, 165000]
        owner.post(f"{API}/admin/products/bulk", json={"ids": [pr["id"]], "action": "unpublish"})
        assert anon.get(f"{API}/products/{pr['slug']}").status_code == 404
        assert owner.delete(f"{API}/admin/products/{pr['id']}").status_code == 200
        assert owner.get(f"{API}/admin/products/{pr['id']}").status_code == 404

    def test_csv_import_drafts(self, owner, mongo):
        csv = ("name,brand,category,plan,duration,price_mmk,description,stock_status\n"
               "TEST_CSV Alpha,ChatGPT,AI Tools,1 Month,30 days,12000,desc a,in_stock\n"
               "TEST_CSV Alpha,ChatGPT,AI Tools,1 Year,365 days,99000,desc a,in_stock\n"
               "TEST_CSV Beta,,,Basic,,5000,desc b,out_of_stock\n")
        r = owner.post(f"{API}/admin/products/import", files={"file": ("p.csv", csv.encode(), "text/csv")})
        print("import:", r.status_code, r.text[:300])
        assert r.status_code == 200
        docs = list(mongo.products.find({"name": {"$regex": "^TEST_CSV"}, "deleted_at": None}))
        assert len(docs) >= 2 and all(d["status"] == "draft" for d in docs)
        alpha = next(d for d in docs if d["name"] == "TEST_CSV Alpha")
        assert len(alpha["variants"]) == 2
        for d in docs:
            owner.delete(f"{API}/admin/products/{d['id']}")

    def test_image_upload(self, owner):
        png = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")
        r = owner.post(f"{API}/admin/uploads/image", files={"file": ("t.png", png, "image/png")})
        print("upload:", r.status_code, r.text[:200])
        assert r.status_code == 200
        url = r.json().get("url") or r.json().get("path")
        assert url
        if url.startswith("/api"):
            assert requests.get(f"{BASE_URL}{url}").status_code == 200


# ---------- Suppliers ----------
SUP = {"auth_type": "api_key_header", "auth_header_name": "X-API-Key", "credential": SUPPLIER_KEY,
       "products_endpoint": "/api/demo-supplier/products", "items_path": "data.items", "map_id": "sku", "map_name": "title",
       "map_price": "cost_mmk", "map_stock": "qty", "map_description": "details.summary"}


class TestSuppliers:
    @pytest.mark.parametrize("url", ["http://127.0.0.1", "https://localhost", "https://10.0.0.1", "https://127.0.0.1:443", "https://169.254.169.254"])
    def test_ssrf_rejected(self, owner, url):
        r = owner.post(f"{API}/admin/suppliers", json={**SUP, "name": "TEST_ssrf", "base_url": url})
        assert r.status_code == 400, (url, r.text)

    def test_full_supplier_flow(self, owner, anon, mongo):
        r = owner.post(f"{API}/admin/suppliers", json={**SUP, "name": "TEST_Sandbox", "base_url": SUPPLIER_BASE})
        assert r.status_code == 200, r.text
        s = r.json()
        sid = s["id"]
        assert "credential_enc" not in s and SUPPLIER_KEY not in str(s) and s["credential_masked"].endswith(SUPPLIER_KEY[-4:])
        lst = owner.get(f"{API}/admin/suppliers").json()
        assert SUPPLIER_KEY not in str(lst)
        assert owner.post(f"{API}/admin/suppliers/{sid}/validate").json()["valid"] is True
        t = owner.post(f"{API}/admin/suppliers/{sid}/test").json()
        assert t["ok"] and t["item_count"] == 4, t
        run = owner.post(f"{API}/admin/suppliers/{sid}/sync", timeout=60).json()
        assert run["status"] == "success" and run["new_count"] == 4, run
        sps = owner.get(f"{API}/admin/suppliers/{sid}/products").json()
        assert len(sps) == 4
        d3 = next(x for x in sps if x["external_id"] == "DEMO-3")
        assert d3["stock"] == 0
        d1 = next(x for x in sps if x["external_id"] == "DEMO-1")
        imp = owner.post(f"{API}/admin/suppliers/{sid}/import", json={"items": [
            {"supplier_product_id": d1["id"], "name": "TEST_Demo Writer", "price_mmk": 25500, "publish": True, "plan_name": "1 Month"}]})
        assert imp.status_code == 200 and len(imp.json()["created"]) == 1
        pid = imp.json()["created"][0]
        p = owner.get(f"{API}/admin/products/{pid}").json()
        assert p["status"] == "published" and p["variants"][0]["price_mmk"] == 25500
        assert anon.get(f"{API}/products/{p['slug']}").status_code == 200
        first_sync = p["variants"][0]["last_synced_at"]
        time.sleep(1.1)
        # simulate supplier cost change by tampering stored cost, then re-sync
        mongo.supplier_products.update_one({"id": d1["id"]}, {"$set": {"cost": 17000}})
        run2 = owner.post(f"{API}/admin/suppliers/{sid}/sync", timeout=60).json()
        assert run2["status"] == "success" and run2["updated_count"] == 4 and run2["price_changes"] >= 1
        p2 = owner.get(f"{API}/admin/products/{pid}").json()
        v = p2["variants"][0]
        assert v["price_mmk"] == 25500, "price_locked violated"
        assert v["supplier_cost"] == 18000 and v["supplier_stock"] == 12
        assert v["last_synced_at"] != first_sync
        runs = owner.get(f"{API}/admin/suppliers/{sid}/runs").json()
        assert len(runs) >= 2
        # cleanup
        owner.delete(f"{API}/admin/products/{pid}")
        owner.delete(f"{API}/admin/suppliers/{sid}")


# ---------- Orders state machine (web admin) ----------
class TestOrderFlow:
    def test_full_flow(self, owner, published_variant):
        p, v = published_variant
        r = owner.post(f"{API}/admin/orders", json={"product_id": p["id"], "variant_id": v["id"], "source": "DIRECT_MESSENGER",
                                                     "customer_name": "TEST_Customer", "customer_contact": "fb.com/test"})
        assert r.status_code == 200, r.text
        o = r.json()
        oid = o["id"]
        assert o["status"] == "AWAITING_PAYMENT" and o["total_mmk"] == v["effective_price_mmk"]
        # invalid
        bad = owner.post(f"{API}/admin/orders/{oid}/transition", json={"to": "DELIVERED"})
        assert bad.status_code == 400
        bad2 = owner.post(f"{API}/admin/orders/{oid}/transition", json={"to": "COMPLETED"})
        assert bad2.status_code == 400
        # approve before evidence blocked
        assert owner.post(f"{API}/admin/orders/{oid}/transition", json={"to": "PAID_AWAITING_FULFILLMENT"}).status_code == 400
        ev = owner.post(f"{API}/admin/orders/{oid}/evidence", data={"reference": "TEST_TX123"})
        assert ev.status_code == 200, ev.text
        assert owner.get(f"{API}/admin/orders/{oid}").json()["status"] == "PAYMENT_SUBMITTED"
        rej = owner.post(f"{API}/admin/orders/{oid}/transition", json={"to": "PAYMENT_REJECTED", "note": "TEST amount mismatch"})
        assert rej.status_code == 200 and rej.json()["status"] == "PAYMENT_REJECTED"
        owner.post(f"{API}/admin/orders/{oid}/evidence", data={"reference": "TEST_TX456"})
        a1 = owner.post(f"{API}/admin/orders/{oid}/transition", json={"to": "PAID_AWAITING_FULFILLMENT"})
        assert a1.status_code == 200 and a1.json()["status"] == "PAID_AWAITING_FULFILLMENT"
        a2 = owner.post(f"{API}/admin/orders/{oid}/transition", json={"to": "PAID_AWAITING_FULFILLMENT"})
        assert a2.status_code == 200 and a2.json()["status"] == "PAID_AWAITING_FULFILLMENT"
        dl = owner.post(f"{API}/admin/orders/{oid}/deliver", json={"artifact_type": "license", "content": "TEST-KEY-123"})
        assert dl.status_code == 200 and dl.json()["result"] == "awaiting_manual_handoff", dl.text
        det = owner.get(f"{API}/admin/orders/{oid}").json()
        aid = det["artifacts"][0]["id"]
        assert owner.get(f"{API}/admin/orders/{oid}/artifacts/{aid}").json()["content"] == "TEST-KEY-123"
        d = owner.post(f"{API}/admin/orders/{oid}/transition", json={"to": "DELIVERED", "note": "TEST handed"})
        assert d.json()["status"] == "DELIVERED"
        c = owner.post(f"{API}/admin/orders/{oid}/transition", json={"to": "COMPLETED"})
        assert c.json()["status"] == "COMPLETED"
        assert owner.get(f"{API}/admin/orders/{oid}/artifacts/{aid}").status_code == 410
        det = owner.get(f"{API}/admin/orders/{oid}").json()
        actions = [e["action"] for e in det["events"]]
        for a in ("order_created", "payment_rejected", "payment_approved", "delivered_manual", "completed"):
            assert a in actions, actions
        aud = owner.get(f"{API}/admin/audit", params={"entity_type": "order"}).json()
        assert any(x.get("entity_id") == oid for x in aud)

    def test_reject_requires_note(self, owner, published_variant):
        p, v = published_variant
        o = owner.post(f"{API}/admin/orders", json={"product_id": p["id"], "variant_id": v["id"], "source": "ADMIN_MANUAL",
                                                     "customer_name": "TEST_Note"}).json()
        owner.post(f"{API}/admin/orders/{o['id']}/evidence", data={"reference": "TEST_TX"})
        r = owner.post(f"{API}/admin/orders/{o['id']}/transition", json={"to": "PAYMENT_REJECTED", "note": ""})
        print("reject w/o note:", r.status_code)
        owner.post(f"{API}/admin/orders/{o['id']}/transition", json={"to": "CANCELLED", "note": "TEST cleanup"})
        assert r.status_code == 400, "Backend allows rejecting payment without a note/reason"


# ---------- Dashboard ----------
class TestDashboard:
    def test_revenue_completed_only(self, owner, mongo):
        d = owner.get(f"{API}/admin/dashboard", params={"days": 365}).json()
        since = time.strftime("%Y", time.gmtime())
        tot = sum(o["total_mmk"] for o in mongo.orders.find({"status": "COMPLETED"}))
        assert d["revenue_mmk"] == tot
        assert d["orders"]["completed"] == mongo.orders.count_documents({"status": "COMPLETED"})


# ---------- RBAC ----------
class TestRBAC:
    def _mk(self, owner, role):
        email = f"test_{role}_{uuid.uuid4().hex[:6]}@example.com"
        r = owner.post(f"{API}/admin/users", json={"email": email, "name": f"TEST {role}", "role": role, "password": "TestPass123!"})
        assert r.status_code == 200, r.text
        s, _ = login(email, "TestPass123!")
        return r.json(), s

    def _deactivate(self, owner, u):
        owner.put(f"{API}/admin/users/{u['id']}", json={"email": u["email"], "name": u["name"], "role": u["role"], "active": False})

    def test_customer_service(self, owner, published_variant):
        u, cs = self._mk(owner, "customer_service")
        try:
            p, v = published_variant
            assert cs.get(f"{API}/admin/orders").status_code == 200
            o = cs.post(f"{API}/admin/orders", json={"product_id": p["id"], "variant_id": v["id"], "source": "DIRECT_MESSENGER", "customer_name": "TEST_CS"})
            assert o.status_code == 200
            oid = o.json()["id"]
            assert cs.post(f"{API}/admin/orders/{oid}/evidence", data={"reference": "TEST_CS_TX"}).status_code == 200
            r = cs.post(f"{API}/admin/orders/{oid}/transition", json={"to": "PAID_AWAITING_FULFILLMENT"})
            assert r.status_code == 403
            assert cs.post(f"{API}/admin/orders/{oid}/deliver", json={"content": "x"}).status_code == 403
            assert cs.get(f"{API}/admin/products").status_code == 403
            assert cs.get(f"{API}/admin/suppliers").status_code == 403
            assert cs.post(f"{API}/admin/users", json={"email": "test_x@example.com", "name": "x", "role": "owner", "password": "12345678"}).status_code == 403
            owner.post(f"{API}/admin/orders/{oid}/transition", json={"to": "CANCELLED", "note": "TEST cleanup"})
        finally:
            self._deactivate(owner, u)
        s2, r2 = login(u["email"], "TestPass123!")
        assert s2 is None and r2.status_code == 401

    def test_product_manager(self, owner):
        u, pm = self._mk(owner, "product_manager")
        try:
            assert pm.get(f"{API}/admin/orders").status_code == 403
            assert pm.get(f"{API}/admin/products").status_code == 200
            assert pm.get(f"{API}/admin/suppliers").status_code == 200
        finally:
            self._deactivate(owner, u)

    def test_deactivated_user_token_revoked(self, owner):
        u, cs = self._mk(owner, "customer_service")
        self._deactivate(owner, u)
        assert cs.get(f"{API}/admin/orders").status_code == 401
