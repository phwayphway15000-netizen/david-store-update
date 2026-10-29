# PRD — AI Tools By David Digital Store

## Original problem statement
MASTER BUILD PROMPT — AI Tools By David Digital Store: premium digital marketplace & operations system for Myanmar (Burmese + English, MMK). Storefront inspired by microwavecreation.com IA (no copying), admin dashboard at /admin with RBAC (Owner/Admin/Product Manager/Customer Service), product management (manual, CSV/XLSX, variants, promos, stock overrides, bulk, audit), Supplier API Integration Manager (encrypted creds, SSRF protection, test/fetch/review/import, scheduled sync with retry, price-change alerts, never overwrite locked prices), Telegram bot checkout (deep-link opaque single-use tokens, /start /products /orders /help /support, owner commands /admin /pending /orders /paymentreview /deliverypending /order /stats, inline admin actions with confirmation), manual payments (KBZPay/WavePay/AYA Pay disabled until owner configures; evidence ≠ proof), manual delivery (encrypted artifacts, idempotent), Messenger ordering (Mode A click-to-Messenger + copyable order reference; Mode B official API optional/disabled with checklist), unified order inbox, strict order state machine (13 states), Meta-compliant crawlable OG pages, sitemap/robots, rate limiting, audit logs. (Full text in conversation.)

User choices: email+password login; real Telegram bot token supplied; Burmese default; Messenger button only; contacts: Facebook https://www.facebook.com/share/1HyMbyD1ZX/, Telegram channel https://t.me/aladdindigitalstorechannel, phone 09764900097 (no email given).

## Architecture (substitutions documented)
- Frontend: React (CRA) + Tailwind + shadcn/ui (instead of Next.js). Crawlable server-rendered product pages at /api/og/product/{slug} (OG tags, same data as SPA); /api/sitemap.xml; /robots.txt.
- Backend: FastAPI + MongoDB (instead of PostgreSQL). Collections mirror requested schema: users, brands, categories, products (embedded variants), suppliers (encrypted creds), supplier_products, supplier_sync_runs, inventory_snapshots, stock_overrides, price_history, promotions, customers, customer_channel_identities, checkout_intents, orders (embedded items + price snapshot), order_events, payment_methods, payment_evidence, payment_reviews, deliveries, delivery_artifacts, delivery_events, telegram_events, telegram_sessions, settings, audit_logs, files, counters.
- Atomic compare-and-set status transitions; idempotent approval; delivery lock; telegram update_id unique index.
- Background: in-process asyncio scheduler for supplier sync (no Redis).
- Storage: Emergent object storage (public product images, private payment evidence).
- Files: backend/core.py, catalog.py, orders.py, tg_api.py, telegram_bot.py, suppliers.py, routes_public.py, routes_admin.py, seed.py, server.py.

## Env vars (backend/.env)
MONGO_URL, DB_NAME, JWT_SECRET, ENCRYPTION_KEY (Fernet), ADMIN_EMAIL, ADMIN_PASSWORD, TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_USER_ID, TELEGRAM_BOT_USERNAME, TELEGRAM_WEBHOOK_SECRET, PUBLIC_BASE_URL (must equal the deployed URL; webhook auto-registers on startup), FRONTEND_URL, DEMO_SUPPLIER_KEY (sandbox supplier), EMERGENT_LLM_KEY (object storage).

## User personas
Owner (David), Admin, Product Manager, Customer Service staff; Myanmar customers ordering via Telegram/Messenger.

## Implemented (2026-10-28)
- Storefront: home (hero/promo banner, featured promos, popular, brands, services, why us, FAQ, footer), catalog filters/sort/infinite load/skeletons/empty, product detail with plan variants, Buy via Telegram, Order via Messenger (reference DAV-YYYY-NNNNNN + copy + track), support, policies, order tracking, EN/MM, dark mode, mobile.
- Admin: dashboard KPIs + verified revenue chart + integration health + activity; products CRUD/variants/promo windows/stock override/images/bulk/CSV-XLSX import (rows grouped by name into plans); brands & categories; suppliers wizard (validate, test, OpenAPI read, sync, review/import, history); unified order inbox + detail (approve w/ confirmation, reject w/ reason, request evidence, delivery, manual handoff, complete w/ artifact purge, refunds, assignee, evidence upload/view, audit trail); promotions; payment methods (owner-only, can't enable without recipient); team/roles; settings (brand/logo/contacts/hero/policies/FAQ, Telegram webhook + test, Messenger checklist); audit log.
- Telegram bot (real): full customer + owner flows as specified.
- Security: bcrypt, httpOnly JWT cookies + refresh, brute-force lockout, RBAC server-side, origin check (CSRF), rate limits, SSRF guard, Fernet encryption, webhook secret header, token never logged.
- Testing: iteration_1 — 32/36 backend + UI flows pass; all reported findings fixed afterwards (XFF, host URL, reject reason required, CSV grouping/regex escape, lockout reset, refresh active check, revenue by completed_at, order actions button, catalog filter race, route permission guard, placeholder text).

## Supplier Integrations (2026-10-28)
- 18 built-in presets from user JSON (secrets stripped) in backend/supplier_presets.json; installed into supplier_definitions + suppliers (preset_key) on startup.
- connectors.py: one-key connect (header/bearer/query auth per preset), Connect & Test with sanitized error codes, host allowlist, HTTPS-only, no redirects, offset pagination, rate-limit delay, nested/fixed/root/pricing-tier mappings -> multi-variant supplier products, needs_review flags.
- Per-supplier sync lock, scheduler (interval per preset), sync-all, revoke/replace key, settings (interval/disable).
- Supplier Catalogue: filters, exchange rates -> MMK, pricing strategies + preview, bulk import as DRAFT (atomic claim), reset-to-supplier field action. Field ownership: sync only touches supplier cost/stock/sync time.
- Status: BlackHatWorld CONFIGURATION_ERROR (HTTP), Prmast/Samayra NEEDS_REVIEW; others CONFIGURATION READY (no live keys supplied).
- Tests: backend/tests/test_connectors.py (mocked) 7/7; iteration_3 60/61 then fixes applied; iteration_4 verified variant-key preservation, atomic import, no-retry on auth/config errors.
- 2026-10-28: user chose to enter real keys themselves in Admin (AIVaultHub, Acczone, Canboso, StoreGPTPlus + all); imported products stay hidden until reviewed. Shared stock rule (suppliers.stock_of) for import+sync, claim released on any import error, metric renamed 'Catalogue items', editor shows supplier cost in its currency. No real keys connected yet.
- 2026-10-28: product photos now shown in full (object-contain on product cards, product detail main image, admin editor thumbnails).

## Reseller ordering (2026-10-29)
- User request: "add reseller ordering system that directly report to admin to confirm the order and manual payment check. Reseller accounts are also created by admin." Choices: separate reseller price per plan; payment screenshot upload; admin panel only notifications; cart with quantities; delivery inside reseller portal.
- backend/resellers.py: separate `resellers` collection + `reseller_token` cookie (isolated from admin auth), admin-only account creation, brute-force lockout. `reseller_orders` flow PENDING_CONFIRMATION → AWAITING_PAYMENT → PAYMENT_SUBMITTED → PAID / PAYMENT_REJECTED → DELIVERED (+ REJECTED, CANCELLED); atomic status moves, server-side pricing from `variants[].reseller_price_mmk`, private screenshot storage, encrypted per-item delivery content.
- Frontend: /reseller/login, /reseller (catalog + cart), /reseller/orders, /reseller/orders/:id; admin /admin/resellers, /admin/reseller-orders(/:id); product editor 'Reseller price (MMK)'.
- Tested iteration_5: 39/40 backend + full UI flow; remaining notes leak fixed after.

## Backlog
- P2 reseller: delete button in UI, refresh cart prices from catalog, 404 page for missing orders.
- P1: Official Meta Messenger Platform connector (needs Page token + App Review); Turnstile on suspicious checkout; DNS-pinning for supplier requests; Burmese status labels on Track page.
- P2: Per-order customer notifications for Messenger orders; reports export; multi-admin Telegram operators.

## Next tasks
- Owner: enter KBZPay/WavePay/AYA Pay recipients and enable; replace sample products/prices; add support email; set m.me link for Messenger ref attribution.
