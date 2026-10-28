import os
import re
import time
import uuid
import asyncio
import logging
import secrets
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import bcrypt
import jwt
import requests
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("store")
logging.getLogger("httpx").setLevel(logging.WARNING)

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
APP_NAME = "davidstore"


def now():
    return datetime.now(timezone.utc)


def now_iso():
    return now().isoformat()


def new_id():
    return str(uuid.uuid4())


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s[:60] or "item") + "-" + secrets.token_hex(3)


# ---------- encryption ----------
_fernet = Fernet(os.environ["ENCRYPTION_KEY"].encode())


def encrypt(value):
    return _fernet.encrypt(value.encode()).decode() if value else None


def decrypt(value):
    return _fernet.decrypt(value.encode()).decode() if value else None


def mask(value):
    return ("•" * 6 + value[-4:]) if value and len(value) > 6 else ("•" * 6 if value else "")


# ---------- passwords / jwt ----------
JWT_ALG = "HS256"


def hash_password(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw, hashed):
    return bcrypt.checkpw(pw.encode(), hashed.encode())


def create_token(user_id, kind, minutes):
    payload = {"sub": user_id, "type": kind, "exp": now() + timedelta(minutes=minutes)}
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALG)


# ---------- RBAC ----------
ROLES = ["owner", "admin", "product_manager", "customer_service"]
PERMS = {
    "owner": {"*"},
    "admin": {"dashboard", "products", "catalog", "suppliers", "promotions", "orders", "orders.approve",
              "orders.deliver", "settings", "audit", "users.view"},
    "product_manager": {"dashboard", "products", "catalog", "suppliers", "promotions"},
    "customer_service": {"dashboard", "orders"},
}


def has_perm(user, perm):
    p = PERMS.get(user.get("role"), set())
    if "*" in p or perm in p:
        return True
    if perm == "orders.approve" and user.get("can_approve_payments"):
        return True
    return False


async def current_user(request: Request):
    token = request.cookies.get("access_token")
    auth = request.headers.get("Authorization", "")
    if not token and auth.startswith("Bearer "):
        token = auth[7:]
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    if payload.get("type") != "access":
        raise HTTPException(401, "Invalid token type")
    user = await db.users.find_one({"id": payload["sub"], "active": True, "deleted_at": None},
                                   {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(401, "User not found")
    return user


def require(perm):
    async def dep(user=Depends(current_user)):
        if not has_perm(user, perm):
            raise HTTPException(403, "You do not have permission for this action")
        return user
    return dep


def actor_of(user):
    return {"type": "admin_user", "id": user["id"], "name": user.get("name") or user["email"], "role": user["role"]}


async def audit(actor, action, entity_type, entity_id=None, details=None):
    await db.audit_logs.insert_one({
        "id": new_id(), "actor": actor, "action": action, "entity_type": entity_type,
        "entity_id": entity_id, "details": details or {}, "created_at": now_iso(),
    })


# ---------- rate limiting (in-memory, per instance) ----------
_hits = defaultdict(deque)


def rate_limit(key, limit, window_sec):
    q = _hits[key]
    t = time.time()
    while q and q[0] < t - window_sec:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "Too many requests. Please slow down and try again shortly.")
    q.append(t)


def client_ip(request: Request):
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[-1].strip() if fwd else (request.client.host if request.client else "unknown")


# ---------- object storage ----------
STORAGE_URL = ((os.environ.get("INTEGRATION_PROXY_URL") or "").strip()
               or "https://integrations.emergentagent.com").rstrip("/") + "/objstore/api/v1/storage"
_storage_key = None


def _init_storage(force=False):
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": os.environ.get("EMERGENT_LLM_KEY")}, timeout=30)
    r.raise_for_status()
    _storage_key = r.json()["storage_key"]
    return _storage_key


def _put(path, data, content_type):
    for attempt in range(2):
        r = requests.put(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": _init_storage(attempt == 1),
                         "Content-Type": content_type}, data=data, timeout=120)
        if r.status_code == 404 and attempt == 0:
            continue
        r.raise_for_status()
        return r.json()


def _get(path):
    r = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": _init_storage()}, timeout=60)
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "application/octet-stream")


async def put_object(path, data, content_type):
    return await asyncio.to_thread(_put, path, data, content_type)


async def get_object(path):
    return await asyncio.to_thread(_get, path)


def init_storage():
    try:
        _init_storage()
        logger.info("Storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")


IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}
