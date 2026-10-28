# Supplier preset integrations (18 presets), connect/revoke/sync, exchange rates, catalogue preview/import, RBAC
import json
import pytest
import requests
from datetime import datetime, timezone
from conftest import BASE_URL, login

API = f"{BASE_URL}/api/admin/supplier-integrations"
FAKE_KEY = "TEST_fakekey123"


@pytest.fixture(scope="module")
def presets(owner):
    r = owner.get(API)
    assert r.status_code == 200
    return {s["preset_key"]: s for s in r.json()["suppliers"]}


@pytest.fixture(scope="module")
def test_sp(mongo, presets):
    sid = presets["aivaulthub"]["id"]
    mongo.supplier_products.delete_many({"id": "TEST_sp1"})
    mongo.supplier_products.insert_one({"id": "TEST_sp1", "supplier_id": sid, "external_id": "TEST_ext1", "name": "TEST_GPT",
                                        "currency": "USD", "cost": 2, "stock": 5, "stock_status": "in_stock",
                                        "variants": [{"key": "0", "name": "1 month", "cost": 2}, {"key": "1", "name": "3 months", "cost": 5}],
                                        "needs_review": False, "linked_product_id": None,
                                        "last_seen_at": datetime.now(timezone.utc).isoformat()})
    yield sid
    pids = [p["linked_product_id"] for p in mongo.supplier_products.find({"id": "TEST_sp1"}) if p.get("linked_product_id")]
    mongo.products.delete_many({"id": {"$in": pids}})
    mongo.supplier_products.delete_many({"id": "TEST_sp1"})


# --- overview ---
class TestOverview:
    def test_18_presets_and_statuses(self, owner, presets):
        assert len(presets) == 18
        assert presets["blackhatworld"]["connection_status"] == "CONFIGURATION_ERROR"
        assert "SECURITY_REVIEW" in presets["blackhatworld"]["review_note"]
        assert presets["prmast"]["connection_status"] == "NEEDS_REVIEW"
        assert presets["samayra"]["connection_status"] == "NEEDS_REVIEW"
        others = [k for k in presets if k not in ("blackhatworld", "prmast", "samayra")]
        assert all(presets[k]["connection_status"] == "NOT_CONNECTED" for k in others), {k: presets[k]["connection_status"] for k in others}

    def test_no_secret_fields(self, owner):
        txt = owner.get(API).text
        assert "credential_enc" not in txt and "custom_headers_enc" not in txt
        d = owner.get(API).json()
        assert d["metrics"]["total"] == 18
        for s in d["suppliers"]:
            assert "key_masked" in s and "has_key" in s


# --- RBAC ---
class TestRBAC:
    def test_unauth_401(self, anon):
        assert anon.get(API).status_code == 401
        assert anon.post(f"{API}/catalogue/preview", json={}).status_code in (401, 422)

    def test_customer_service_403(self, owner, mongo):
        email = "test_cs_integrations@example.com"
        mongo.users.delete_many({"email": email})
        r = owner.post(f"{BASE_URL}/api/admin/users", json={"email": email, "name": "TEST CS", "role": "customer_service", "password": "TestPass!2345"})
        assert r.status_code == 200, r.text
        try:
            cs, lr = login(email, "TestPass!2345")
            assert cs, lr.text
            assert cs.get(API).status_code == 403
            assert cs.get(f"{API}/exchange-rates").status_code == 403
            assert cs.get(f"{API}/catalogue").status_code == 403
        finally:
            mongo.users.delete_many({"email": email})


# --- connect / revoke / sync ---
class TestConnect:
    def test_blackhatworld_config_error(self, owner, presets):
        s = presets["blackhatworld"]
        r = owner.post(f"{API}/{s['id']}/connect", json={"api_key": FAKE_KEY})
        try:
            assert r.status_code == 200
            d = r.json()
            assert d["ok"] is False and d["error_code"] == "CONFIGURATION_ERROR"
            assert d["connection_status"] == "CONFIGURATION_ERROR"
            assert FAKE_KEY not in r.text
        finally:
            owner.post(f"{API}/{s['id']}/revoke")
        assert {x["preset_key"]: x for x in owner.get(API).json()["suppliers"]}["blackhatworld"]["connection_status"] == "CONFIGURATION_ERROR"

    @pytest.mark.parametrize("pk", ["aivaulthub", "acczone"])
    def test_fake_key_sanitized_then_revoke(self, owner, presets, pk):
        s = presets[pk]
        r = owner.post(f"{API}/{s['id']}/connect", json={"api_key": FAKE_KEY}, timeout=60)
        try:
            assert r.status_code == 200, r.text
            assert FAKE_KEY not in r.text
            d = r.json()
            print(pk, d.get("ok"), d.get("error_code"), d.get("message"), d.get("connection_status"))
            if d["ok"] is False:
                assert d["error_code"] in ("AUTH_FAILED", "NOT_FOUND", "MALFORMED_RESPONSE", "DNS_OR_CONNECT", "TIMEOUT", "TLS_ERROR",
                                           "RATE_LIMITED", "HTTP_ERROR", "UNEXPECTED_REDIRECT", "NETWORK_ERROR", "CONFIGURATION_ERROR")
            card = {x["preset_key"]: x for x in owner.get(API).json()["suppliers"]}[pk]
            assert card["has_key"] is True and card["connection_status"] == d["connection_status"]
            assert FAKE_KEY not in json.dumps(card)
        finally:
            rv = owner.post(f"{API}/{s['id']}/revoke")
            assert rv.status_code == 200
        card = {x["preset_key"]: x for x in owner.get(API).json()["suppliers"]}[pk]
        assert card["has_key"] is False and card["connection_status"] == "NOT_CONNECTED" and card["key_masked"] == ""

    def test_sync_without_key_400(self, owner, presets):
        r = owner.post(f"{API}/{presets['canboso']['id']}/sync")
        assert r.status_code == 400

    def test_sync_lock_409(self, owner, presets, mongo):
        s = presets["canboso"]
        mongo.suppliers.update_one({"id": s["id"]}, {"$set": {"sync_lock_until": "2999-01-01T00:00:00+00:00", "credential_enc": "x"}})
        try:
            r = owner.post(f"{API}/{s['id']}/sync")
            assert r.status_code == 409
        finally:
            mongo.suppliers.update_one({"id": s["id"]}, {"$set": {"sync_lock_until": None, "credential_enc": None, "connection_status": "NOT_CONNECTED"}})

    def test_unknown_id_404(self, owner):
        assert owner.post(f"{API}/nope/connect", json={"api_key": FAKE_KEY}).status_code == 404

    def test_short_key_422(self, owner, presets):
        assert owner.post(f"{API}/{presets['canboso']['id']}/connect", json={"api_key": "ab"}).status_code == 422


# --- exchange rates + catalogue ---
class TestCatalogue:
    def test_rates(self, owner):
        r = owner.put(f"{API}/exchange-rates", json={"USD": 6500, "BAD": "x", "NEG": -1})
        assert r.status_code == 200
        assert r.json() == {"USD": 6500.0, "MMK": 1}
        assert owner.get(f"{API}/exchange-rates").json()["USD"] == 6500

    def test_catalogue_lists_doc(self, owner, test_sp):
        d = owner.get(f"{API}/catalogue", params={"q": "TEST_GPT"}).json()
        assert any(i["id"] == "TEST_sp1" for i in d["items"])
        d2 = owner.get(f"{API}/catalogue", params={"supplier": test_sp}).json()
        assert any(i["id"] == "TEST_sp1" for i in d2["items"])

    def test_preview(self, owner, test_sp):
        owner.put(f"{API}/exchange-rates", json={"USD": 6500})
        r = owner.post(f"{API}/catalogue/preview", json={"items": [{"supplier_product_id": "TEST_sp1"}],
                                                         "pricing": {"strategy": "fixed_markup", "value": 3000, "rounding": 100}})
        assert r.status_code == 200
        assert [x["price_mmk"] for x in r.json()] == [16000, 35500]
        r2 = owner.post(f"{API}/catalogue/preview", json={"items": [{"supplier_product_id": "TEST_sp1"}],
                                                          "pricing": {"strategy": "percent_markup", "value": 10, "rounding": 500}})
        assert [x["price_mmk"] for x in r2.json()] == [14500, 36000]

    def test_import_then_duplicate_and_public(self, owner, anon, test_sp, mongo):
        body = {"items": [{"supplier_product_id": "TEST_sp1"}], "pricing": {"strategy": "fixed_markup", "value": 3000, "rounding": 100}}
        r = owner.post(f"{API}/catalogue/import", json=body)
        assert r.status_code == 200, r.text
        d = r.json()
        assert len(d["created"]) == 1 and d["errors"] == []
        pid = d["created"][0]
        p = owner.get(f"{BASE_URL}/api/admin/products/{pid}").json()
        assert p["status"] == "draft" and p["source_type"] == "SUPPLIER_API"
        assert [v["price_mmk"] for v in p["variants"]] == [16000, 35500]
        assert all(v["price_locked"] for v in p["variants"])
        assert [v["supplier_variant_key"] for v in p["variants"]] == ["0", "1"]
        r2 = owner.post(f"{API}/catalogue/import", json=body)
        assert "already imported" in r2.json()["errors"][0]["error"]
        # publish via bulk, check public endpoints never leak cost
        assert owner.post(f"{BASE_URL}/api/admin/products/bulk", json={"ids": [pid], "action": "publish"}).status_code == 200
        lst = anon.get(f"{BASE_URL}/api/products", params={"q": "TEST_GPT", "limit": 48})
        assert lst.status_code == 200
        assert "supplier_cost" not in lst.text and "supplier_currency" not in lst.text
        det = anon.get(f"{BASE_URL}/api/products/{p['slug']}")
        assert det.status_code == 200, det.text
        assert "supplier_cost" not in det.text and "supplier_" not in det.text.replace("supplier_stock_", ""), det.text[:500]

    def test_edit_imported_product_keeps_variant_key(self, owner, mongo, test_sp):
        """Publishing/editing via Products editor (PUT) must not drop supplier_variant_key."""
        sp = mongo.supplier_products.find_one({"id": "TEST_sp1"})
        pid = sp["linked_product_id"]
        p = owner.get(f"{BASE_URL}/api/admin/products/{pid}").json()
        payload = {k: p.get(k) for k in ("name", "description", "images", "status")}
        payload["status"] = "published"
        payload["variants"] = [{k: v.get(k) for k in ("id", "name", "duration", "price_mmk", "stock_status", "supplier_id", "supplier_product_id", "price_locked", "active")} for v in p["variants"]]
        r = owner.put(f"{BASE_URL}/api/admin/products/{pid}", json=payload)
        assert r.status_code == 200, r.text
        after = mongo.products.find_one({"id": pid})
        assert [v.get("supplier_variant_key") for v in after["variants"]] == ["0", "1"], after["variants"]


# --- manual products / custom suppliers unaffected ---
class TestRegression:
    def test_manual_product_create(self, owner, mongo):
        r = owner.post(f"{BASE_URL}/api/admin/products", json={"name": "TEST_Manual product", "status": "draft",
                                                              "variants": [{"name": "1M", "price_mmk": 10000}]})
        try:
            assert r.status_code == 200
            assert r.json()["source_type"] == "MANUAL"
        finally:
            mongo.products.delete_many({"name": "TEST_Manual product"})

    def test_custom_suppliers_list_excludes_presets(self, owner):
        r = owner.get(f"{BASE_URL}/api/admin/suppliers")
        assert r.status_code == 200
        assert all(not s.get("preset_key") for s in r.json())


@pytest.fixture(scope="module", autouse=True)
def restore_rates(mongo):
    before = (mongo.settings.find_one({"id": "global"}) or {}).get("exchange_rates")
    yield
    if before is None:
        mongo.settings.update_one({"id": "global"}, {"$unset": {"exchange_rates": ""}})
    else:
        mongo.settings.update_one({"id": "global"}, {"$set": {"exchange_rates": before}})
