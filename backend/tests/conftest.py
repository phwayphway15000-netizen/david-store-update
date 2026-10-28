import os
import pytest
import requests
from pathlib import Path
from dotenv import dotenv_values

FE = dotenv_values(Path("/app/frontend/.env"))
BE = dotenv_values(Path("/app/backend/.env"))
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FE["REACT_APP_BACKEND_URL"]).rstrip("/")
OWNER_EMAIL = os.environ.get("TEST_OWNER_EMAIL") or BE["ADMIN_EMAIL"]
OWNER_PASSWORD = os.environ.get("TEST_OWNER_PASSWORD") or BE["ADMIN_PASSWORD"]
SUPPLIER_KEY = BE["DEMO_SUPPLIER_KEY"]
SUPPLIER_BASE = BE["PUBLIC_BASE_URL"].rstrip("/")


def login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        return None, r
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return s, r


@pytest.fixture(scope="session")
def owner():
    s, r = login(OWNER_EMAIL, OWNER_PASSWORD)
    if not s:
        pytest.skip(f"Owner login failed {r.status_code} {r.text}")
    return s


@pytest.fixture(scope="session")
def anon():
    return requests.Session()


@pytest.fixture(scope="session")
def mongo():
    from pymongo import MongoClient
    return MongoClient(BE["MONGO_URL"])[BE["DB_NAME"]]


@pytest.fixture(scope="session")
def published_variant(anon):
    d = anon.get(f"{BASE_URL}/api/products", params={"in_stock": "true", "limit": 48}).json()
    for p in d["items"]:
        for v in p["variants"]:
            if v.get("available"):
                return p, v
    pytest.skip("No available published product")
