import sys
sys.path.insert(0, "/app/backend/tests")
from conftest import login, BASE_URL, BE, OWNER_EMAIL, OWNER_PASSWORD
from pymongo import MongoClient
import requests

API = f"{BASE_URL}/api"
db = MongoClient(BE["MONGO_URL"])[BE["DB_NAME"]]
s, _ = login(OWNER_EMAIL, OWNER_PASSWORD)

# DEMO-3 (stock 0) import -> should be out of stock on storefront
sup = db.suppliers.find_one({"name": {"$regex": "^TEST_"}, "deleted_at": None})
if sup:
    sp = db.supplier_products.find_one({"supplier_id": sup["id"], "external_id": "DEMO-3"})
    r = s.post(f"{API}/admin/suppliers/{sup['id']}/import", json={"items": [{"supplier_product_id": sp["id"], "name": "TEST_Demo Voice OOS", "price_mmk": 30000, "publish": True}]})
    pid = r.json()["created"][0]
    p = db.products.find_one({"id": pid})
    pub = requests.get(f"{API}/products/{p['slug']}").json()
    print("DEMO-3 public available:", pub.get("available"), [v.get("available") for v in pub["variants"]])
    co = requests.post(f"{API}/checkout/messenger", json={"product_id": pid, "variant_id": p["variants"][0]["id"]})
    print("checkout OOS status:", co.status_code, co.text[:120])

# cleanup
for p in db.products.find({"name": {"$regex": "^TEST_"}, "deleted_at": None}):
    s.delete(f"{API}/admin/products/{p['id']}")
    print("deleted product", p["name"])
for x in db.suppliers.find({"name": {"$regex": "^TEST_"}, "deleted_at": None}):
    s.delete(f"{API}/admin/suppliers/{x['id']}")
    print("deleted supplier", x["name"])
for o in db.orders.find({"status": {"$in": ["AWAITING_PAYMENT", "PAYMENT_SUBMITTED", "AWAITING_CUSTOMER_CONFIRMATION", "PAYMENT_REJECTED"]},
                         "$or": [{"customer_name": {"$regex": "^TEST"}}, {"source": "WEBSITE_TELEGRAM"}]}):
    r = s.post(f"{API}/admin/orders/{o['id']}/transition", json={"to": "CANCELLED", "note": "TEST cleanup"})
    print("cancel", o["ref"], r.status_code)
n = db.users.update_many({"email": {"$regex": "^test_"}, "active": True}, {"$set": {"active": False}}).modified_count
print("deactivated users", n)
print("owner ok:", login(OWNER_EMAIL, OWNER_PASSWORD)[0] is not None)
