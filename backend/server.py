import asyncio
import os
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from core import db, client, logger, init_storage
from seed import seed
import routes_public
import routes_admin
import suppliers
import connectors
import telegram_bot as TB

app = FastAPI(title="AI Tools By David Digital Store API")
app.include_router(routes_public.router)
app.include_router(routes_admin.router)
app.include_router(suppliers.router)
app.include_router(connectors.router)

ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip() and o.strip() != "*"]
if os.environ.get("FRONTEND_URL"):
    ORIGINS.append(os.environ["FRONTEND_URL"].rstrip("/"))


@app.middleware("http")
async def origin_guard(request: Request, call_next):
    """CSRF defence: reject cross-site state-changing requests from unknown origins."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and not request.url.path.startswith("/api/telegram/webhook"):
        origin = request.headers.get("origin")
        if origin:
            host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
            if urlparse(origin).netloc != host and origin.rstrip("/") not in ORIGINS:
                return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return resp


app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    await seed()
    await connectors.install_presets()
    await db.supplier_products.create_index([("supplier_id", 1), ("name", 1)])
    init_storage()
    asyncio.create_task(suppliers.scheduler_loop())
    asyncio.create_task(connectors.scheduler_loop())
    if os.environ.get("PUBLIC_BASE_URL"):
        try:
            await TB.register_webhook(os.environ["PUBLIC_BASE_URL"])
        except Exception as e:
            logger.error(f"Webhook registration error: {type(e).__name__}")


@app.on_event("shutdown")
async def shutdown():
    client.close()
