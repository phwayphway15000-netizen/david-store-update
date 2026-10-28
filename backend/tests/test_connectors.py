import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import connectors as C  # noqa: E402
from core import encrypt  # noqa: E402

PRESETS = {p["name"]: p for p in C.PRESETS["suppliers"]}


def sup(name, key="TESTKEY123"):
    p = PRESETS[name]
    c, a = p["connector"], p["authentication"]
    return {"id": "t", "name": name, "preset_key": C.preset_key(name), "base_url": p["base_url"], "products_endpoint": c["products_endpoint"],
            "items_path": c.get("response_list_key") or "", "auth_location": a["location"], "auth_header_name": a["name"],
            "auth_prefix": a.get("prefix") or "", "field_mappings": c["field_mappings"], "query_params": c.get("query_params") or {},
            "pagination": c.get("pagination") or {}, "rate_limit_rpm": 6000, "allowed_host": httpx.URL(p["base_url"]).host,
            "credential_enc": encrypt(key) if key else None}


REAL_CLIENT = httpx.AsyncClient


def mock(monkeypatch, handler):
    monkeypatch.setattr(C.httpx, "AsyncClient", lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(C.S, "check_url", lambda u: u)


def run(coro):
    return asyncio.run(coro)


def test_all_presets_present_and_secret_free():
    assert len(PRESETS) == 18
    raw = (Path(__file__).resolve().parents[1] / "supplier_presets.json").read_text()
    for p in PRESETS.values():
        assert "api_key" not in p["authentication"]
    assert "TESTKEY" not in raw


def test_auth_locations():
    h, q = C.build_auth(sup("AIVaultHub"), "K1")
    assert h["X-API-Key"] == "K1" and "K1" not in json.dumps(q)
    h, q = C.build_auth(sup("Akunding"), "K2")
    assert h["Authorization"] == "Bearer K2"
    h, q = C.build_auth(sup("Acczone"), "K3")
    assert q["apikey"] == "K3" and "K3" not in json.dumps(h)
    h, q = C.build_auth(sup("Chirago"), "K4")
    assert q["action"] == "products" and h["Authorization"] == "Bearer K4"


def test_nested_mapping_and_tiers():
    s = sup("Canboso")
    n = C.normalize_preset(s, {"productId": 7, "name": "X", "price": {"amount": "2.5", "currency": "usd"}, "availability": {"available": 0}})
    assert n["external_id"] == "7" and n["cost"] == 2.5 and n["currency"] == "USD" and n["stock_status"] == "out_of_stock"
    s = sup("AIVaultHub")
    n = C.normalize_preset(s, {"service_id": "a", "name": "GPT", "stock": 3, "pricing_tiers": [{"duration": "1 month", "price": 2}, {"duration": "3 months", "price": 5}], "__root_currency": "USD"})
    assert [v["cost"] for v in n["variants"]] == [2, 5] and n["variants"][1]["name"] == "3 months" and n["currency"] == "USD"
    n = C.normalize_preset(s, {"name": "no id"})
    assert n["needs_review"]


def test_currency_conversion():
    p = C.PricingIn(strategy="fixed_markup", value=3000, rounding=100)
    assert C.compute_price(2, "USD", {"USD": 6500}, p) == 16000
    with pytest.raises(ValueError):
        C.compute_price(2, "EUR", {"USD": 6500}, p)


def test_fetch_success_and_errors(monkeypatch):
    s = sup("MMOStore")
    seen = {}

    def ok(req):
        seen["h"] = req.headers.get("X-API-Key")
        return httpx.Response(200, json={"data": [{"id": 1, "name": "A", "price_usd": 1, "stock": 4}]})
    mock(monkeypatch, ok)
    status, items = run(C.fetch_preset(s))
    assert status == 200 and len(items) == 1 and seen["h"] == "TESTKEY123"
    for code, expect in ((401, "AUTH_FAILED"), (404, "NOT_FOUND"), (429, "RATE_LIMITED"), (302, "UNEXPECTED_REDIRECT")):
        mock(monkeypatch, lambda req, c=code: httpx.Response(c, headers={"location": "https://evil.example"}, json={}))
        with pytest.raises(C.SupplierError) as e:
            run(C.fetch_preset(s))
        assert e.value.code == expect and "TESTKEY123" not in str(e.value)
    mock(monkeypatch, lambda req: httpx.Response(200, text="<html>"))
    with pytest.raises(C.SupplierError) as e:
        run(C.fetch_preset(s))
    assert e.value.code == "MALFORMED_RESPONSE"


def test_http_and_foreign_host_rejected(monkeypatch):
    mock(monkeypatch, lambda req: httpx.Response(200, json={"products": []}))
    with pytest.raises(C.SupplierError) as e:
        run(C.fetch_preset(sup("BlackHatWorld")))
    assert e.value.code == "CONFIGURATION_ERROR"
    s = sup("Akunding")
    s["allowed_host"] = "other.example"
    with pytest.raises(C.SupplierError):
        run(C.fetch_preset(s))


def test_offset_pagination(monkeypatch):
    s = sup("ShopeeLabs")
    s["pagination"] = {"method": "offset", "page_size": 2}

    def h(req):
        off = int(req.url.params["offset"])
        rows = [{"id": i, "name": f"p{i}", "list_price": 1} for i in range(off, min(off + 2, 5))]
        return httpx.Response(200, json={"products": rows})
    mock(monkeypatch, h)
    _, items = run(C.fetch_preset(s))
    assert len(items) == 5
