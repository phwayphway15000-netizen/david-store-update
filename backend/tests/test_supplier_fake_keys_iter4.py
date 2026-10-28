# Fake-key connect for Canboso / StoreGPTPlus (real hosts, 1 call each) -> AUTH_FAILED, key never echoed, revoke restores
import json
import pytest
from conftest import BASE_URL

API = f"{BASE_URL}/api/admin/supplier-integrations"
FAKE = "TEST_fakekey_iter4_zz"


@pytest.mark.parametrize("pk", ["canboso", "storegptplus"])
def test_fake_key(owner, pk):
    s = {x["preset_key"]: x for x in owner.get(API).json()["suppliers"]}[pk]
    try:
        r = owner.post(f"{API}/{s['id']}/connect", json={"api_key": FAKE}, timeout=60)
        print(pk, r.json().get("error_code"), r.json().get("message"))
        assert r.status_code == 200 and FAKE not in r.text
        assert r.json()["ok"] is False and r.json()["error_code"] == "AUTH_FAILED"
        card = {x["preset_key"]: x for x in owner.get(API).json()["suppliers"]}[pk]
        assert card["connection_status"] == "AUTH_FAILED" and FAKE not in json.dumps(card)
        sy = owner.post(f"{API}/{s['id']}/sync", timeout=90)
        print("sync", sy.status_code, sy.json().get("attempts"), sy.json().get("error"))
        assert sy.json().get("attempts") == 1
    finally:
        owner.post(f"{API}/{s['id']}/revoke")
    card = {x["preset_key"]: x for x in owner.get(API).json()["suppliers"]}[pk]
    assert card["connection_status"] == "NOT_CONNECTED" and not card["has_key"]
