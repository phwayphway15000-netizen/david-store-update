# UI seed/cleanup for reseller flow (iteration 5). Usage: python ui_seed_iter5.py seed|cleanup
import sys
from conftest import BASE_URL, login, OWNER_EMAIL, OWNER_PASSWORD, BE
from pymongo import MongoClient

db = MongoClient(BE["MONGO_URL"])[BE["DB_NAME"]]
if sys.argv[1] == "seed":
    s, _ = login(OWNER_EMAIL, OWNER_PASSWORD)
    p = s.post(f"{BASE_URL}/api/admin/products", json={"name": "TEST_UI Reseller Pack", "status": "published", "variants": [
        {"name": "TEST_1M", "price_mmk": 5000, "reseller_price_mmk": 1000},
        {"name": "TEST_3M", "price_mmk": 12000},
        {"name": "TEST_OOS", "price_mmk": 6000, "reseller_price_mmk": 800, "stock_status": "out_of_stock"}]}).json()
    print(p["id"], [v["id"] for v in p["variants"]])
else:
    ids = [p["id"] for p in db.products.find({"name": {"$regex": "^TEST_UI"}}, {"id": 1})]
    db.products.delete_many({"id": {"$in": ids}})
    rids = [r["id"] for r in db.resellers.find({"email": {"$regex": "^test_ui"}}, {"id": 1})]
    tr = db.resellers.find_one({"email": "test_reseller1@example.com"}, {"id": 1})
    if tr:
        rids.append(tr["id"])
    print("orders", db.reseller_orders.delete_many({"reseller_id": {"$in": rids}}).deleted_count)
    print("resellers", db.resellers.delete_many({"email": {"$regex": "^test_ui"}}).deleted_count, "products", len(ids))
