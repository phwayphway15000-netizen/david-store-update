# Seed/cleanup TEST_ui supplier product for UI catalogue test. usage: python ui_seed_iter4.py seed|clean
import sys, json
sys.path.insert(0, "/app/backend/tests")
from datetime import datetime, timezone
from conftest import BE
from pymongo import MongoClient
db = MongoClient(BE["MONGO_URL"])[BE["DB_NAME"]]
sid = db.suppliers.find_one({"preset_key": "aivaulthub"})["id"]
if sys.argv[1] == "seed":
    st = db.settings.find_one({"id": "global"}) or {}
    open("/tmp/rates_before.json", "w").write(json.dumps(st.get("exchange_rates")))
    db.supplier_products.delete_many({"id": "TEST_ui_sp1"})
    db.supplier_products.insert_one({"id": "TEST_ui_sp1", "supplier_id": sid, "external_id": "TEST_ui_ext1", "name": "TEST_UI ChatGPT Plus",
                                     "description": "TEST desc", "currency": "USD", "cost": 2, "stock": 9, "stock_status": "in_stock",
                                     "variants": [{"key": "0", "name": "1 month", "cost": 2}, {"key": "1", "name": "3 months", "cost": 5}],
                                     "needs_review": False, "linked_product_id": None, "last_seen_at": datetime.now(timezone.utc).isoformat()})
    print("seeded")
else:
    sp = db.supplier_products.find_one({"id": "TEST_ui_sp1"}) or {}
    pid = sp.get("linked_product_id")
    print("products deleted", db.products.delete_many({"$or": [{"id": pid}, {"name": {"$regex": "^TEST_UI"}}]}).deleted_count)
    db.price_history.delete_many({"product_id": pid})
    db.supplier_products.delete_many({"id": "TEST_ui_sp1"})
    before = json.loads(open("/tmp/rates_before.json").read())
    if before is None:
        db.settings.update_one({"id": "global"}, {"$unset": {"exchange_rates": ""}})
    else:
        db.settings.update_one({"id": "global"}, {"$set": {"exchange_rates": before}})
    print("rates restored", before)
