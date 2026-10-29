# Reseller ordering system tests (iteration 5): accounts, catalog, auth, cart orders, admin flow, isolation, roles.
import io
import uuid
import pytest
import requests
from conftest import BASE_URL, login, BE

API = f"{BASE_URL}/api"
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7V\xbd\xfa\x00\x00\x00\x00IEND\xaeB`\x82")
PW = "TEST_Pass#2026"
U = uuid.uuid4().hex[:6]


def rlogin(email, pw=PW):
    s = requests.Session()
    r = s.post(f"{API}/reseller/auth/login", json={"email": email, "password": pw})
    return s, r


@pytest.fixture(scope="module")
def env(owner, mongo):
    created = {"products": [], "resellers": [], "users": []}
    # TEST product: v0 reseller price 1000, v1 reseller price 2500, v2 no reseller price, v3 out-of-stock w/ reseller price
    body = {"name": f"TEST_Reseller Product {U}", "status": "published", "variants": [
        {"name": "TEST_A", "price_mmk": 5000, "reseller_price_mmk": 1000},
        {"name": "TEST_B", "price_mmk": 9000, "reseller_price_mmk": 2500},
        {"name": "TEST_C", "price_mmk": 7000},
        {"name": "TEST_OOS", "price_mmk": 7000, "reseller_price_mmk": 900, "stock_status": "out_of_stock"}]}
    r = owner.post(f"{API}/admin/products", json=body)
    assert r.status_code == 200, r.text
    p = r.json()
    created["products"].append(p["id"])
    draft = owner.post(f"{API}/admin/products", json={**body, "name": f"TEST_Draft Reseller {U}", "status": "draft"}).json()
    created["products"].append(draft["id"])
    rs = {}
    for k in ("a", "b"):
        rr = owner.post(f"{API}/admin/resellers", json={"email": f"test_rs_{k}_{U}@example.com", "name": f"TEST_RS {k}",
                                                        "business_name": f"TEST_Biz {k}", "notes": "PRIVATE_ADMIN_NOTE", "password": PW})
        assert rr.status_code == 200, rr.text
        rs[k] = rr.json()
        created["resellers"].append(rs[k]["id"])
    yield {"p": p, "draft": draft, "rs": rs, "created": created}
    for pid in created["products"]:
        mongo.products.delete_one({"id": pid})
    for rid in created["resellers"]:
        mongo.reseller_orders.delete_many({"reseller_id": rid})
        mongo.resellers.delete_one({"id": rid})
    for uid in created["users"]:
        mongo.users.delete_one({"id": uid})
    mongo.login_attempts.delete_many({"identifier": {"$regex": U}})


@pytest.fixture(scope="module")
def ra(env):
    s, r = rlogin(env["rs"]["a"]["email"])
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def rb(env):
    s, r = rlogin(env["rs"]["b"]["email"])
    assert r.status_code == 200, r.text
    return s


def items(env, *spec):
    vs = env["p"]["variants"]
    return [{"product_id": env["p"]["id"], "variant_id": vs[i]["id"], "quantity": q} for i, q in spec]


# --- accounts ---
class TestAccounts:
    def test_duplicate_email_rejected(self, owner, env):
        r = owner.post(f"{API}/admin/resellers", json={"email": env["rs"]["a"]["email"].upper(), "name": "dup", "password": PW})
        assert r.status_code == 400

    def test_admin_email_rejected(self, owner):
        r = owner.post(f"{API}/admin/resellers", json={"email": BE["ADMIN_EMAIL"], "name": "dup", "password": PW})
        assert r.status_code == 400

    def test_no_password_hash_in_list(self, owner, env):
        lst = owner.get(f"{API}/admin/resellers").json()
        row = next(x for x in lst if x["id"] == env["rs"]["a"]["id"])
        assert "password_hash" not in row and row["orders"] == 0

    def test_no_public_signup(self):
        r = requests.post(f"{API}/reseller/auth/register", json={"email": "x@example.com", "password": PW})
        assert r.status_code in (404, 405)

    def test_private_notes_not_exposed_to_reseller(self, ra):
        me = ra.get(f"{API}/reseller/auth/me").json()
        assert "PRIVATE_ADMIN_NOTE" not in str(me), f"admin private notes leaked to reseller: {me}"


# --- auth ---
class TestAuth:
    def test_wrong_password_401(self, env):
        _, r = rlogin(env["rs"]["b"]["email"], "wrong-password")
        assert r.status_code == 401

    def test_lockout_429(self):
        email = f"test_lock_{U}@example.com"
        codes = [rlogin(email, "bad")[1].status_code for _ in range(6)]
        assert codes[:5] == [401] * 5 and codes[5] == 429, codes

    def test_cookie_httponly(self, env):
        _, r = rlogin(env["rs"]["b"]["email"])
        sc = r.headers.get("set-cookie", "")
        assert "reseller_token" in sc and "HttpOnly" in sc and "Secure" in sc

    def test_reseller_cannot_access_admin(self, ra):
        assert ra.get(f"{API}/admin/reseller-orders").status_code == 401
        assert ra.get(f"{API}/admin/resellers").status_code == 401
        tok = ra.cookies.get("reseller_token")
        assert requests.get(f"{API}/admin/resellers", headers={"Authorization": f"Bearer {tok}"}).status_code == 401

    def test_admin_cannot_access_reseller(self, owner):
        assert owner.get(f"{API}/reseller/catalog").status_code == 401
        assert owner.get(f"{API}/reseller/orders").status_code == 401

    def test_disable_blocks_login_and_session(self, owner, env):
        c = owner.post(f"{API}/admin/resellers", json={"email": f"test_rs_dis_{U}@example.com", "name": "TEST_dis", "password": PW}).json()
        env["created"]["resellers"].append(c["id"])
        s, r = rlogin(c["email"])
        assert r.status_code == 200 and s.get(f"{API}/reseller/auth/me").status_code == 200
        u = owner.put(f"{API}/admin/resellers/{c['id']}", json={"email": c["email"], "name": "TEST_dis", "active": False})
        assert u.status_code == 200 and u.json()["active"] is False
        assert s.get(f"{API}/reseller/auth/me").status_code == 401
        assert rlogin(c["email"])[1].status_code == 401
        # re-enable + password reset
        owner.put(f"{API}/admin/resellers/{c['id']}", json={"email": c["email"], "name": "TEST_dis2", "active": True, "password": "NewPass#999"})
        assert rlogin(c["email"], "NewPass#999")[1].status_code == 200
        assert owner.delete(f"{API}/admin/resellers/{c['id']}").status_code == 200
        assert rlogin(c["email"], "NewPass#999")[1].status_code == 401


# --- catalog visibility ---
class TestCatalog:
    def test_catalog_only_reseller_priced(self, ra, env):
        cat = ra.get(f"{API}/reseller/catalog").json()
        ids = [p["id"] for p in cat]
        assert env["p"]["id"] in ids and env["draft"]["id"] not in ids
        p = next(x for x in cat if x["id"] == env["p"]["id"])
        names = {v["name"]: v for v in p["variants"]}
        assert set(names) == {"TEST_A", "TEST_B", "TEST_OOS"}
        assert names["TEST_A"]["reseller_price_mmk"] == 1000 and names["TEST_OOS"]["available"] is False

    def test_public_never_exposes_reseller_price(self, env):
        r = requests.get(f"{API}/products", params={"limit": 48})
        assert r.status_code == 200 and "reseller_price" not in r.text
        d = requests.get(f"{API}/products/{env['p']['slug']}")
        assert d.status_code == 200 and "reseller_price" not in d.text

    def test_catalog_requires_auth(self):
        assert requests.get(f"{API}/reseller/catalog").status_code == 401


# --- order creation ---
class TestOrderCreate:
    def test_create_server_prices(self, ra, env):
        body = {"items": [dict(i, unit_price_mmk=1, line_total_mmk=1) for i in items(env, (0, 3), (1, 2))], "note": "TEST_note", "total_mmk": 5}
        r = ra.post(f"{API}/reseller/orders", json=body)
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["status"] == "PENDING_CONFIRMATION" and o["total_mmk"] == 3 * 1000 + 2 * 2500
        assert o["ref"].startswith("RS-")
        env["o1"] = o
        got = ra.get(f"{API}/reseller/orders/{o['id']}").json()
        assert got["total_mmk"] == 8000 and len(got["items"]) == 2

    def test_duplicate_lines(self, ra, env):
        assert ra.post(f"{API}/reseller/orders", json={"items": items(env, (0, 1), (0, 2))}).status_code == 400

    def test_out_of_stock(self, ra, env):
        assert ra.post(f"{API}/reseller/orders", json={"items": items(env, (3, 1))}).status_code == 400

    def test_no_reseller_price_variant(self, ra, env):
        assert ra.post(f"{API}/reseller/orders", json={"items": items(env, (2, 1))}).status_code == 400

    @pytest.mark.parametrize("q", [0, 101, -1])
    def test_qty_bounds(self, ra, env, q):
        assert ra.post(f"{API}/reseller/orders", json={"items": items(env, (0, q))}).status_code == 422

    def test_empty(self, ra):
        assert ra.post(f"{API}/reseller/orders", json={"items": []}).status_code == 422

    def test_draft_product(self, ra, env):
        d = env["draft"]
        assert ra.post(f"{API}/reseller/orders", json={"items": [{"product_id": d["id"], "variant_id": d["variants"][0]["id"], "quantity": 1}]}).status_code == 400


# --- full lifecycle ---
class TestLifecycle:
    def test_isolation(self, rb, env):
        oid = env["o1"]["id"]
        assert rb.get(f"{API}/reseller/orders/{oid}").status_code == 404
        assert rb.post(f"{API}/reseller/orders/{oid}/cancel").status_code == 404
        assert all(o["id"] != oid for o in rb.get(f"{API}/reseller/orders").json())

    def test_pay_before_confirm_rejected(self, ra, env):
        r = ra.post(f"{API}/reseller/orders/{env['o1']['id']}/payment", files={"file": ("a.png", PNG, "image/png")})
        assert r.status_code == 400

    def test_admin_lists_with_counts(self, owner, env):
        d = owner.get(f"{API}/admin/reseller-orders", params={"status": "PENDING_CONFIRMATION"}).json()
        assert any(o["id"] == env["o1"]["id"] for o in d["items"]) and d["counts"].get("PENDING_CONFIRMATION", 0) >= 1

    def test_confirm_then_double(self, owner, env):
        oid = env["o1"]["id"]
        r = owner.post(f"{API}/admin/reseller-orders/{oid}/action", json={"action": "confirm"})
        assert r.status_code == 200 and r.json()["status"] == "AWAITING_PAYMENT"
        assert owner.post(f"{API}/admin/reseller-orders/{oid}/action", json={"action": "confirm"}).status_code == 409

    def test_non_image_rejected(self, ra, env):
        r = ra.post(f"{API}/reseller/orders/{env['o1']['id']}/payment", files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")})
        assert r.status_code == 400

    def test_too_large_rejected(self, ra, env):
        big = PNG + b"\0" * (8 * 1024 * 1024 + 10)
        r = ra.post(f"{API}/reseller/orders/{env['o1']['id']}/payment", files={"file": ("a.png", big, "image/png")})
        assert r.status_code in (400, 413)

    def test_upload_and_view(self, ra, rb, owner, env):
        oid = env["o1"]["id"]
        r = ra.post(f"{API}/reseller/orders/{oid}/payment", data={"reference": "TEST_ref1"}, files={"file": ("a.png", PNG, "image/png")})
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["status"] == "PAYMENT_SUBMITTED" and len(o["evidence"]) == 1
        eid = o["evidence"][0]["id"]
        env["eid"] = eid
        assert ra.post(f"{API}/reseller/orders/{oid}/payment", files={"file": ("a.png", PNG, "image/png")}).status_code == 400
        img = owner.get(f"{API}/admin/reseller-orders/{oid}/evidence/{eid}")
        assert img.status_code == 200 and img.content[:4] == b"\x89PNG"
        assert ra.get(f"{API}/reseller/orders/{oid}/evidence/{eid}").status_code == 200
        assert rb.get(f"{API}/reseller/orders/{oid}/evidence/{eid}").status_code == 404
        assert "storage_path" not in str(rb.get(f"{API}/reseller/orders").json())

    def test_reseller_cannot_cancel_after_submit(self, ra, env):
        assert ra.post(f"{API}/reseller/orders/{env['o1']['id']}/cancel").status_code == 409

    def test_reject_payment_needs_reason_and_reupload(self, owner, ra, env):
        oid = env["o1"]["id"]
        assert owner.post(f"{API}/admin/reseller-orders/{oid}/action", json={"action": "reject_payment", "note": " "}).status_code == 400
        r = owner.post(f"{API}/admin/reseller-orders/{oid}/action", json={"action": "reject_payment", "note": "TEST_blurry"})
        assert r.status_code == 200 and r.json()["status"] == "PAYMENT_REJECTED"
        mine = ra.get(f"{API}/reseller/orders/{oid}").json()
        assert mine["status"] == "PAYMENT_REJECTED" and "TEST_blurry" in str(mine["events"])
        assert mine["evidence"][0]["review_status"] == "rejected"
        r2 = ra.post(f"{API}/reseller/orders/{oid}/payment", files={"file": ("b.png", PNG, "image/png")})
        assert r2.status_code == 200 and r2.json()["status"] == "PAYMENT_SUBMITTED" and len(r2.json()["evidence"]) == 2

    def test_deliver_before_paid(self, owner, env):
        o = env["o1"]
        r = owner.post(f"{API}/admin/reseller-orders/{o['id']}/deliver", json={"items": [{"item_id": i["id"], "content": "x"} for i in o["items"]]})
        assert r.status_code == 400

    def test_approve_payment(self, owner, env):
        oid = env["o1"]["id"]
        r = owner.post(f"{API}/admin/reseller-orders/{oid}/action", json={"action": "approve_payment"})
        assert r.status_code == 200 and r.json()["status"] == "PAID"
        assert owner.post(f"{API}/admin/reseller-orders/{oid}/action", json={"action": "approve_payment"}).status_code == 409

    def test_deliver_partial_rejected(self, owner, env):
        o = env["o1"]
        r = owner.post(f"{API}/admin/reseller-orders/{o['id']}/deliver", json={"items": [{"item_id": o["items"][0]["id"], "content": "x"}]})
        assert r.status_code == 400

    def test_deliver_and_reseller_sees(self, owner, ra, rb, env):
        o = env["o1"]
        body = {"items": [{"item_id": i["id"], "content": f"TEST_cred_{n}"} for n, i in enumerate(o["items"])]}
        r = owner.post(f"{API}/admin/reseller-orders/{o['id']}/deliver", json=body)
        assert r.status_code == 200 and r.json()["status"] == "DELIVERED"
        assert owner.post(f"{API}/admin/reseller-orders/{o['id']}/deliver", json=body).status_code == 400
        mine = ra.get(f"{API}/reseller/orders/{o['id']}").json()
        assert [i["delivery"] for i in mine["items"]] == ["TEST_cred_0", "TEST_cred_1"]
        lst = ra.get(f"{API}/reseller/orders").json()
        assert "TEST_cred_0" not in str(lst)
        assert "delivery_enc" not in str(mine)

    def test_spent_stats(self, owner, env):
        row = next(x for x in owner.get(f"{API}/admin/resellers").json() if x["id"] == env["rs"]["a"]["id"])
        assert row["spent_mmk"] == 8000 and row["orders"] >= 1


class TestRejectCancel:
    def test_reject_order_reason(self, owner, ra, env):
        o = ra.post(f"{API}/reseller/orders", json={"items": items(env, (0, 1))}).json()
        assert owner.post(f"{API}/admin/reseller-orders/{o['id']}/action", json={"action": "reject"}).status_code == 400
        r = owner.post(f"{API}/admin/reseller-orders/{o['id']}/action", json={"action": "reject", "note": "TEST_no stock"})
        assert r.status_code == 200 and r.json()["status"] == "REJECTED"
        assert "TEST_no stock" in str(ra.get(f"{API}/reseller/orders/{o['id']}").json()["events"])

    def test_reseller_cancel_pending_and_awaiting(self, owner, ra, env):
        o = ra.post(f"{API}/reseller/orders", json={"items": items(env, (0, 1))}).json()
        assert ra.post(f"{API}/reseller/orders/{o['id']}/cancel").json()["status"] == "CANCELLED"
        assert ra.post(f"{API}/reseller/orders/{o['id']}/cancel").status_code == 409
        o2 = ra.post(f"{API}/reseller/orders", json={"items": items(env, (1, 1))}).json()
        owner.post(f"{API}/admin/reseller-orders/{o2['id']}/action", json={"action": "confirm"})
        assert ra.post(f"{API}/reseller/orders/{o2['id']}/cancel").json()["status"] == "CANCELLED"


# --- staff roles ---
class TestRoles:
    def test_customer_service(self, owner, ra, env):
        out = {}
        for flag in (False, True):
            email = f"test_cs_{int(flag)}_{U}@example.com"
            u = owner.post(f"{API}/admin/users", json={"email": email, "name": "TEST_cs", "role": "customer_service",
                                                       "password": PW, "can_approve_payments": flag})
            assert u.status_code == 200, u.text
            env["created"]["users"].append(u.json()["id"])
            s, _ = login(email, PW)
            assert s
            out[flag] = s
        o = ra.post(f"{API}/reseller/orders", json={"items": items(env, (0, 1))}).json()
        cs = out[False]
        assert cs.get(f"{API}/admin/reseller-orders").status_code == 200
        assert cs.get(f"{API}/admin/reseller-orders/{o['id']}").status_code == 200
        assert cs.post(f"{API}/admin/reseller-orders/{o['id']}/action", json={"action": "confirm"}).status_code == 403
        assert cs.get(f"{API}/admin/resellers").status_code == 403
        assert cs.post(f"{API}/admin/resellers", json={"email": f"x{U}@example.com", "name": "x", "password": PW}).status_code == 403
        r = out[True].post(f"{API}/admin/reseller-orders/{o['id']}/action", json={"action": "confirm"})
        assert r.status_code == 200 and r.json()["status"] == "AWAITING_PAYMENT"
        assert out[True].get(f"{API}/admin/resellers").status_code == 403
