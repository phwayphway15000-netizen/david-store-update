# Retest of iteration_3 action items: atomic import, stock mapping, no-retry on AUTH/CONFIG errors,
# re-sync preserving admin price/publication (in-process sync with a stubbed supplier fetch; no real supplier calls)
import asyncio
import sys
import threading
from datetime import datetime, timezone

import pytest
from conftest import BASE_URL

sys.path.insert(0, "/app/backend")
API = f"{BASE_URL}/api/admin/supplier-integrations"
SP_IDS = ["TEST_r4_a", "TEST_r4_oos", "TEST_r4_qty", "TEST_r4_unk", "TEST_r4_conc"]


def iso():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture(scope="module")
def sid(owner, mongo):
    s = {x["preset_key"]: x for x in owner.get(API).json()["suppliers"]}["aivaulthub"]
    before = mongo.suppliers.find_one({"id": s["id"]}, {"_id": 0})
    rates_before = (mongo.settings.find_one({"id": "global"}) or {}).get("exchange_rates")
    owner.put(f"{API}/exchange-rates", json={"USD": 6500})
    mongo.supplier_products.delete_many({"id": {"$in": SP_IDS}})
    base = {"supplier_id": s["id"], "currency": "USD", "cost": 2, "needs_review": False, "linked_product_id": None,
            "variants": [{"key": "0", "name": "1 month", "cost": 2}, {"key": "1", "name": "3 months", "cost": 5}], "last_seen_at": iso()}
    docs = [("TEST_r4_a", "TEST_ext_r4_a", None, "in_stock"), ("TEST_r4_oos", "TEST_ext_r4_oos", 0, "out_of_stock"),
            ("TEST_r4_qty", "TEST_ext_r4_qty", 7, "in_stock"), ("TEST_r4_unk", "TEST_ext_r4_unk", None, "unknown"),
            ("TEST_r4_conc", "TEST_ext_r4_conc", 5, "in_stock")]
    for i, ext, stock, st in docs:
        mongo.supplier_products.insert_one({**base, "id": i, "external_id": ext, "name": f"TEST_R4 {i}", "stock": stock, "stock_status": st})
    yield s["id"]
    pids = [p["linked_product_id"] for p in mongo.supplier_products.find({"id": {"$in": SP_IDS}}) if p.get("linked_product_id")]
    mongo.products.delete_many({"$or": [{"id": {"$in": pids}}, {"name": {"$regex": "^TEST_R4"}}]})
    mongo.supplier_products.delete_many({"id": {"$in": SP_IDS}})
    mongo.inventory_snapshots.delete_many({"external_id": {"$regex": "^TEST_ext_r4"}})
    mongo.price_history.delete_many({"external_id": {"$regex": "^TEST_ext_r4"}})
    mongo.price_history.delete_many({"product_id": {"$in": pids}})
    mongo.supplier_sync_runs.delete_many({"supplier_id": s["id"], "trigger": "TEST_r4"})
    keep = {k: before.get(k) for k in ("health", "last_error", "last_sync_at", "connection_status", "credential_enc", "last_test", "sync_lock_until")}
    mongo.suppliers.update_one({"id": s["id"]}, {"$set": keep})
    if rates_before is None:
        mongo.settings.update_one({"id": "global"}, {"$unset": {"exchange_rates": ""}})
    else:
        mongo.settings.update_one({"id": "global"}, {"$set": {"exchange_rates": rates_before}})


def do_import(owner, spid):
    return owner.post(f"{API}/catalogue/import", json={"items": [{"supplier_product_id": spid}],
                                                      "pricing": {"strategy": "fixed_markup", "value": 3000, "rounding": 100}})


def run_inproc(coro_factory):
    """Run backend coroutines in a fresh loop with a fresh motor client."""
    import importlib
    import core
    importlib.reload(core)
    import tg_api, suppliers, connectors
    for m in (tg_api, suppliers, connectors):
        importlib.reload(m)

    async def noop(*a, **k):
        return False, "stub"
    tg_api.notify_owner = noop
    suppliers.tg_api.notify_owner = noop
    return asyncio.new_event_loop().run_until_complete(coro_factory(core, suppliers, connectors))


class TestStockMapping:
    @pytest.mark.parametrize("spid,exp_status,exp_stock,exp_avail", [
        ("TEST_r4_oos", "out_of_stock", 0, False), ("TEST_r4_qty", "in_stock", 7, True), ("TEST_r4_a", "in_stock", 999, True)])
    def test_import_stock(self, owner, sid, spid, exp_status, exp_stock, exp_avail):
        r = do_import(owner, spid)
        assert r.status_code == 200 and len(r.json()["created"]) == 1, r.text
        p = owner.get(f"{BASE_URL}/api/admin/products/{r.json()['created'][0]}").json()
        assert p["status"] == "draft"
        assert [v["stock_status"] for v in p["variants"]] == [exp_status] * 2
        assert [v["supplier_stock"] for v in p["variants"]] == [exp_stock] * 2
        assert p["available"] is exp_avail

    def test_import_unknown_stock_consistent_with_sync(self, owner, sid, mongo):
        """unknown stock: import vs sync should agree on availability."""
        r = do_import(owner, "TEST_r4_unk")
        pid = r.json()["created"][0]
        p = mongo.products.find_one({"id": pid})
        imp = (p["variants"][0]["supplier_stock"], p["available"])
        n = {"external_id": "TEST_ext_r4_unk", "cost": 2, "stock": None, "stock_status": "unknown",
             "variants": [{"key": "0", "cost": 2}, {"key": "1", "cost": 5}]}

        async def go(core, S, C):
            s = await core.db.suppliers.find_one({"id": sid}, {"_id": 0})
            await S.update_linked_variants(s, n)
        run_inproc(go)
        p2 = mongo.products.find_one({"id": pid})
        syn = (p2["variants"][0]["supplier_stock"], p2["available"])
        print("import:", imp, "sync:", syn)
        assert imp == syn, f"import {imp} vs sync {syn}"


class TestAtomicImport:
    def test_concurrent_import_creates_one(self, owner, sid, mongo):
        results = []

        def worker():
            results.append(do_import(owner, "TEST_r4_conc").json())
        ts = [threading.Thread(target=worker) for _ in range(6)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        created = sum(len(r.get("created", [])) for r in results)
        assert created == 1, results
        assert mongo.products.count_documents({"variants.supplier_product_id": "TEST_ext_r4_conc", "deleted_at": None}) == 1
        sp = mongo.supplier_products.find_one({"id": "TEST_r4_conc"})
        assert sp["linked_product_id"] not in (None, "__claimed__")


class TestNoRetry:
    @pytest.mark.parametrize("code,exp", [("AUTH_FAILED", 1), ("CONFIGURATION_ERROR", 1), ("TIMEOUT", 3)])
    def test_retry_policy(self, sid, code, exp):
        async def go(core, S, C):
            async def boom(s):
                raise C.SupplierError(code, "stub")
            C.fetch_preset = boom
            s = await core.db.suppliers.find_one({"id": sid}, {"_id": 0})
            run = {"attempts": 0}
            items, err = await S.fetch_with_retry(s, run)
            return run["attempts"], err
        attempts, err = run_inproc(go)
        assert attempts == exp, (attempts, err)
        assert err.startswith(code)


class TestResyncPreservesAdmin:
    def test_edit_then_resync(self, owner, sid, mongo):
        sp = mongo.supplier_products.find_one({"id": "TEST_r4_a"})
        pid = sp["linked_product_id"]
        assert pid, "TEST_r4_a must be imported by TestStockMapping first"
        p = owner.get(f"{BASE_URL}/api/admin/products/{pid}").json()
        payload = {k: p.get(k) for k in ("description", "images")}
        payload.update(name="TEST_R4 Edited name", status="published")
        payload["variants"] = [{**{k: v.get(k) for k in ("id", "name", "duration", "stock_status", "supplier_id", "supplier_product_id", "price_locked", "active")},
                                "price_mmk": 77700 + i} for i, v in enumerate(p["variants"])]
        r = owner.put(f"{BASE_URL}/api/admin/products/{pid}", json=payload)
        assert r.status_code == 200, r.text
        edited = mongo.products.find_one({"id": pid})
        assert [v["supplier_variant_key"] for v in edited["variants"]] == ["0", "1"]
        assert [v["supplier_currency"] for v in edited["variants"]] == ["USD", "USD"]
        old_sync = edited["variants"][0]["last_synced_at"]

        raw = {"service_id": "TEST_ext_r4_a", "name": "TEST_R4 supplier renamed", "stock": 4, "__root_currency": "USD",
               "pricing_tiers": [{"name": "1 month", "price": 3}, {"name": "3 months", "price": 8}]}

        async def go(core, S, C):
            async def fake(s):
                return 200, [raw]
            C.fetch_preset = fake
            s = await core.db.suppliers.find_one({"id": sid}, {"_id": 0})
            return await S.run_sync(s, {"type": "system", "id": "TEST"}, "TEST_r4")
        run = run_inproc(go)
        assert run["status"] == "success", run
        after = mongo.products.find_one({"id": pid})
        assert after["status"] == "published"
        assert after["name"] == "TEST_R4 Edited name"
        assert [v["price_mmk"] for v in after["variants"]] == [77700, 77701]
        assert [v["supplier_cost"] for v in after["variants"]] == [3, 8]
        assert [v["supplier_stock"] for v in after["variants"]] == [4, 4]
        assert after["variants"][0]["last_synced_at"] != old_sync
        assert after["available"] is True
        # out of stock on next sync
        raw["stock"] = 0
        run_inproc(go)
        after2 = mongo.products.find_one({"id": pid})
        assert after2["available"] is False and after2["status"] == "published"
        assert [v["price_mmk"] for v in after2["variants"]] == [77700, 77701]
