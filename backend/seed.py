import os
from core import db, now_iso, new_id, hash_password, slugify, logger
from catalog import recompute

CATEGORIES = [("AI Tools", "AI ကိရိယာများ", "sparkles"), ("Creative Tools", "ဖန်တီးမှု ကိရိယာများ", "palette"),
              ("Office & Productivity", "ရုံးသုံးနှင့် ထုတ်လုပ်မှု", "briefcase"), ("Education", "ပညာရေး", "graduation-cap"),
              ("Developer Tools", "Developer ကိရိယာများ", "code")]
BRANDS = [("ChatGPT", "#10A37F"), ("Gemini", "#4285F4"), ("Canva", "#00C4CC"), ("CapCut", "#111827"), ("ElevenLabs", "#0F172A"),
          ("Descript", "#5B5BD6"), ("Synthesia", "#1E40AF"), ("Coursera", "#0056D2"), ("Udemy", "#A435F0"), ("Notion", "#000000")]

POLICY = lambda en, my: {"en": en, "my": my}  # noqa

DEFAULT_SETTINGS = {
    "id": "global", "brand_name": "AI Tools By David Digital Store", "logo_url": "", "og_image": "",
    "tagline_en": "Digital subscriptions, AI tools & creative software — ordered transparently, verified by humans.",
    "tagline_my": "AI Tools၊ Creative Software နှင့် Digital Subscription များကို ပွင့်လင်းမြင်သာစွာ မှာယူနိုင်ပါသည်။",
    "contacts": {"phone": "09764900097", "email": "[Add support email in Admin → Settings]",
                 "facebook": "https://www.facebook.com/share/1HyMbyD1ZX/",
                 "telegram_channel": "https://t.me/aladdindigitalstorechannel", "address": "Myanmar"},
    "messenger_url": "https://www.facebook.com/share/1HyMbyD1ZX/",
    "hero": {"badge_en": "Myanmar's digital tools marketplace", "badge_my": "မြန်မာ့ Digital Tools စျေးကွက်",
             "title_en": "Premium AI & creative tools, paid in Kyat.", "title_my": "Premium AI နှင့် Creative Tools များ — ကျပ်ငွေဖြင့်",
             "subtitle_en": "Choose a plan, confirm on Telegram or Messenger, pay with KBZPay, WavePay or AYA Pay, and get human-verified delivery.",
             "subtitle_my": "Plan ရွေးပါ၊ Telegram (သို့) Messenger မှ အတည်ပြုပါ၊ KBZPay / WavePay / AYA Pay ဖြင့် ငွေပေးချေပြီး လူကိုယ်တိုင် စစ်ဆေးပို့ဆောင်ပေးပါမည်။",
             "image_url": ""},
    "faq": [
        {"q_en": "How do I place an order?", "q_my": "ဘယ်လို မှာယူရမလဲ?",
         "a_en": "Open a product, pick a plan and press Buy Now. Our Telegram bot shows your order and payment steps. You can also order via Messenger with a copyable order reference.",
         "a_my": "Product ကိုဖွင့်ပြီး Plan ရွေးကာ Buy Now ကိုနှိပ်ပါ။ Telegram Bot မှ အော်ဒါနှင့် ငွေပေးချေရန် အဆင့်များကို ပြပေးပါမည်။ Messenger မှလည်း Order Reference ဖြင့် မှာယူနိုင်ပါသည်။"},
        {"q_en": "When is my payment confirmed?", "q_my": "ငွေပေးချေမှုကို ဘယ်အချိန် အတည်ပြုမလဲ?",
         "a_en": "A team member checks that the money actually arrived in our account. Screenshots are treated as evidence only, so confirmation is manual.",
         "a_my": "ကျွန်ုပ်တို့အကောင့်သို့ ငွေရောက်ကြောင်း ဝန်ထမ်းမှ ကိုယ်တိုင်စစ်ဆေးပြီးမှ အတည်ပြုပါသည်။ Screenshot များကို အထောက်အထားအဖြစ်သာ သတ်မှတ်ပါသည်။"},
        {"q_en": "Will you ask for my password or OTP?", "q_my": "Password သို့မဟုတ် OTP တောင်းမလား?",
         "a_en": "Never. We do not collect passwords, OTP codes or recovery secrets through checkout.",
         "a_my": "ဘယ်တော့မှ မတောင်းပါ။ Password၊ OTP နှင့် Recovery Code များကို မကောက်ခံပါ။"},
        {"q_en": "Are you an official partner of these brands?", "q_my": "ဤ Brand များ၏ တရားဝင် Partner လား?",
         "a_en": "No. We are an independent reseller and service provider. Brand names are used only to describe products.",
         "a_my": "မဟုတ်ပါ။ ကျွန်ုပ်တို့သည် လွတ်လပ်သော ရောင်းချသူ ဖြစ်ပါသည်။ Brand အမည်များကို ထုတ်ကုန်ဖော်ပြရန်သာ အသုံးပြုပါသည်။"},
    ],
    "policies": {
        "about": POLICY("AI Tools By David Digital Store is an independent Myanmar-based seller of digital subscriptions, software plans, learning plans and digital services. We are not affiliated with or endorsed by the brands listed in our catalogue.",
                        "AI Tools By David Digital Store သည် မြန်မာနိုင်ငံအခြေစိုက် Digital Subscription နှင့် Digital Service ရောင်းချသူ ဖြစ်ပါသည်။ ဖော်ပြထားသော Brand များနှင့် တရားဝင်ဆက်နွယ်မှု မရှိပါ။"),
        "privacy": POLICY("We collect only what we need to process your order: your Telegram or Messenger identifier, the name you share, your order details and the payment evidence you send. Payment evidence is stored privately and only viewed by authorised staff. We never ask for passwords or OTP codes. Contact us to request deletion of your data.",
                          "အော်ဒါဆောင်ရွက်ရန် လိုအပ်သော အချက်အလက်များ (Telegram/Messenger ID၊ အမည်၊ အော်ဒါ၊ ငွေပေးချေမှု အထောက်အထား) ကိုသာ ကောက်ခံပါသည်။ Password နှင့် OTP များကို မတောင်းပါ။"),
        "terms": POLICY("Prices are in Myanmar Kyat (MMK). An order is confirmed only after our team manually verifies your payment. Product availability depends on supplier stock and may change. Service terms of each software provider continue to apply to your use of the product.",
                        "စျေးနှုန်းများကို ကျပ်ငွေဖြင့် ဖော်ပြပါသည်။ ငွေပေးချေမှုကို ဝန်ထမ်းမှ စစ်ဆေးအတည်ပြုပြီးမှ အော်ဒါ အတည်ဖြစ်ပါသည်။"),
        "refund": POLICY("If we cannot deliver your order after payment is verified, you will receive a full refund. Refund requests for delivered products are reviewed case by case according to the warranty terms shown on each product page.",
                         "ငွေပေးချေပြီး ပို့ဆောင်မပေးနိုင်ပါက ငွေအပြည့်ပြန်အမ်းပါမည်။ ပို့ဆောင်ပြီးသော ပစ္စည်းများအတွက် Warranty စည်းကမ်းအတိုင်း စစ်ဆေးပါမည်။"),
        "delivery": POLICY("Digital products are delivered manually through the same channel you ordered from (Telegram or Messenger) after payment verification. Typical delivery time is shown on each product page and is an estimate, not a guarantee.",
                           "ငွေပေးချေမှု အတည်ပြုပြီးနောက် မှာယူသည့် Channel (Telegram/Messenger) မှတဆင့် ပို့ဆောင်ပေးပါသည်။"),
        "warranty": POLICY("Warranty coverage and duration are stated on each product page. Warranty does not cover issues caused by violating the software provider's terms.",
                           "Warranty သက်တမ်းနှင့် အကျုံးဝင်မှုကို Product စာမျက်နှာတွင် ဖော်ပြထားပါသည်။"),
    },
    "services": [
        {"key": "web", "icon": "globe", "en": "Website development", "my": "Website ဖန်တီးခြင်း"},
        {"key": "app", "icon": "smartphone", "en": "App development", "my": "App ဖန်တီးခြင်း"},
        {"key": "tgbot", "icon": "send", "en": "Telegram bot development", "my": "Telegram Bot ဖန်တီးခြင်း"},
        {"key": "agent", "icon": "bot", "en": "AI agent development", "my": "AI Agent ဖန်တီးခြင်း"},
        {"key": "integrations", "icon": "plug", "en": "Custom integrations", "my": "စိတ်ကြိုက် Integration များ"},
    ],
}

SAMPLES = [("ChatGPT", "AI Tools", "Sample — ChatGPT Plus plan", [("1 Month", "1 month", 30000)], True),
           ("Gemini", "AI Tools", "Sample — Gemini AI Pro plan", [("1 Month", "1 month", 28000), ("3 Months", "3 months", 80000)], False),
           ("Canva", "Creative Tools", "Sample — Canva Pro plan", [("1 Month", "1 month", 8000), ("1 Year", "12 months", 60000)], True),
           ("CapCut", "Creative Tools", "Sample — CapCut Pro plan", [("1 Month", "1 month", 12000)], False),
           ("ElevenLabs", "AI Tools", "Sample — ElevenLabs Creator plan", [("1 Month", "1 month", 35000)], False),
           ("Notion", "Office & Productivity", "Sample — Notion Plus plan", [("1 Month", "1 month", 15000)], False),
           ("Coursera", "Education", "Sample — Coursera Plus plan", [("1 Month", "1 month", 70000)], False),
           ("Descript", "Developer Tools", "Sample — Descript Creator plan", [("1 Month", "1 month", 25000)], False)]


async def seed():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.login_attempts.create_index("identifier")
    for coll in ("products", "brands", "categories", "orders", "suppliers", "promotions", "payment_methods", "supplier_products"):
        await db[coll].create_index("id", unique=True)
    await db.products.create_index("slug", unique=True)
    await db.products.create_index([("status", 1), ("deleted_at", 1), ("created_at", -1)])
    await db.orders.create_index("ref", unique=True)
    await db.orders.create_index([("status", 1), ("created_at", -1)])
    await db.order_events.create_index("order_id")
    await db.payment_evidence.create_index("order_id")
    await db.checkout_intents.create_index("token_hash", unique=True)
    await db.checkout_intents.create_index("id", unique=True)
    await db.telegram_events.create_index("update_id", unique=True)
    await db.supplier_products.create_index([("supplier_id", 1), ("external_id", 1)], unique=True)
    await db.customer_channel_identities.create_index([("channel", 1), ("external_id", 1)], unique=True)
    await db.audit_logs.create_index([("created_at", -1)])
    await db.files.create_index("storage_path")

    email = os.environ["ADMIN_EMAIL"].lower()
    if not await db.users.find_one({"email": email}):
        await db.users.insert_one({"id": new_id(), "email": email, "name": "Owner", "role": "owner", "active": True,
                                   "can_approve_payments": True, "password_hash": hash_password(os.environ["ADMIN_PASSWORD"]),
                                   "created_at": now_iso(), "deleted_at": None})
        logger.info("Owner account seeded")
    if not await db.settings.find_one({"id": "global"}):
        await db.settings.insert_one(dict(DEFAULT_SETTINGS))
    if not await db.categories.count_documents({}):
        for i, (n, m, icon) in enumerate(CATEGORIES):
            await db.categories.insert_one({"id": new_id(), "name": n, "name_my": m, "icon": icon, "sort": i,
                                            "slug": slugify(n).rsplit("-", 1)[0], "created_at": now_iso(), "deleted_at": None})
    if not await db.brands.count_documents({}):
        for i, (n, c) in enumerate(BRANDS):
            await db.brands.insert_one({"id": new_id(), "name": n, "color": c, "logo_url": "", "sort": i,
                                        "slug": slugify(n).rsplit("-", 1)[0], "created_at": now_iso(), "deleted_at": None})
    if not await db.payment_methods.count_documents({}):
        for i, (n, code) in enumerate([("KBZPay", "kbzpay"), ("WavePay", "wavepay"), ("AYA Pay", "ayapay")]):
            await db.payment_methods.insert_one({"id": new_id(), "code": code, "name": n, "account_name": "", "account_number": "",
                                                 "instructions": "", "enabled": False, "sort": i, "created_at": now_iso()})
    if not await db.meta.find_one({"_id": "samples_seeded"}):
        brands = {b["name"]: b["id"] async for b in db.brands.find({}, {"_id": 0})}
        cats = {c["name"]: c["id"] async for c in db.categories.find({}, {"_id": 0})}
        for bname, cname, pname, plans, featured in SAMPLES:
            p = {"id": new_id(), "slug": slugify(pname), "name": pname, "name_my": "", "brand_id": brands.get(bname),
                 "category_id": cats.get(cname), "short_description": f"Editable sample listing for {bname}. Replace price and details in Admin → Products.",
                 "short_description_my": f"{bname} အတွက် နမူနာ စာရင်း — Admin မှ ပြင်ဆင်ပါ။",
                 "description": f"This is a SAMPLE product created to preview the store. Update the plan, price, eligibility and warranty in the admin dashboard before selling. Independent reseller — not affiliated with {bname}.",
                 "description_my": "", "product_type": "subscription", "activation_method": "[Set activation method]",
                 "eligibility": "[Set eligibility requirements]", "warranty": "[Set warranty terms]", "delivery_time": "[Set delivery time]",
                 "images": [], "featured": featured, "hot": featured, "status": "published", "source_type": "MANUAL", "is_sample": True,
                 "variants": [{"id": new_id(), "name": n, "duration": d, "price_mmk": pr, "promo_price_mmk": int(pr * 0.9) if featured and i == 0 else None,
                               "promo_start": None, "promo_end": None, "stock_status": "in_stock", "stock_qty": None, "stock_override": None,
                               "supplier_id": None, "supplier_product_id": None, "supplier_cost": None, "supplier_stock": None,
                               "last_synced_at": None, "price_locked": True, "active": True} for i, (n, d, pr) in enumerate(plans)],
                 "order_count": 0, "created_at": now_iso(), "updated_at": now_iso(), "deleted_at": None}
            recompute(p)
            await db.products.insert_one(p)
        await db.meta.insert_one({"_id": "samples_seeded", "at": now_iso()})
