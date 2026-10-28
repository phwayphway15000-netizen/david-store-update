import { createContext, useContext, useEffect, useState, createElement } from "react";

const D = {
  home: ["Home", "ပင်မ"], all_products: ["All Products", "ပစ္စည်းအားလုံး"], promotions: ["Promotions", "ပရိုမိုးရှင်း"],
  support: ["Support", "အကူအညီ"], search: ["Search products…", "ပစ္စည်း ရှာရန်…"], explore: ["Explore Products", "ပစ္စည်းများ ကြည့်ရန်"],
  contact_support: ["Contact Support", "ဆက်သွယ်ရန်"], featured_promos: ["Featured promotions", "အထူးပရိုမိုးရှင်းများ"],
  popular: ["Popular products", "လူကြိုက်များသော ပစ္စည်းများ"], view_all: ["View all", "အားလုံးကြည့်ရန်"],
  browse_brand: ["Browse by brand", "Brand အလိုက် ရှာရန်"], services: ["Digital services", "Digital ဝန်ဆောင်မှုများ"],
  services_sub: ["We also build custom software for Myanmar businesses.", "မြန်မာလုပ်ငန်းများအတွက် Software များလည်း ဖန်တီးပေးပါသည်။"],
  ask_quote: ["Ask for a quote", "စျေးနှုန်း မေးမြန်းရန်"], why: ["Why order with us", "ဘာကြောင့် ကျွန်ုပ်တို့ထံ မှာသင့်သလဲ"],
  faq: ["Frequently asked questions", "မေးလေ့ရှိသော မေးခွန်းများ"], buy_now: ["Buy Now", "ယခုဝယ်မည်"],
  in_stock: ["In stock", "ပစ္စည်းရှိ"], low_stock: ["Low stock", "နည်းနေပြီ"], out_of_stock: ["Out of stock", "ပစ္စည်းပြတ်"],
  from: ["From", "စျေးနှုန်း"], brand: ["Brand", "Brand"], category: ["Category", "အမျိုးအစား"], price: ["Price", "စျေးနှုန်း"],
  sort: ["Sort", "စီရန်"], newest: ["Newest", "အသစ်ဆုံး"], price_asc: ["Price: low to high", "စျေး နည်း→များ"],
  price_desc: ["Price: high to low", "စျေး များ→နည်း"], popular_sort: ["Most popular", "လူကြိုက်အများဆုံး"],
  only_in_stock: ["In stock only", "ပစ္စည်းရှိသာ"], only_promo: ["On promotion", "ပရိုမိုးရှင်းသာ"], all: ["All", "အားလုံး"],
  min: ["Min Ks", "အနည်းဆုံး"], max: ["Max Ks", "အများဆုံး"], clear: ["Clear filters", "Filter ဖျက်ရန်"],
  no_results: ["No products match your filters.", "ရှာဖွေမှုနှင့် ကိုက်ညီသော ပစ္စည်း မရှိပါ။"], load_more: ["Load more", "ထပ်ကြည့်ရန်"],
  results: ["products", "ခု"], choose_plan: ["Choose a plan", "Plan ရွေးပါ"], buy_tg: ["Buy Now via Telegram", "Telegram ဖြင့် ဝယ်မည်"],
  order_msgr: ["Order via Messenger", "Messenger ဖြင့် မှာမည်"], details: ["Details", "အသေးစိတ်"], duration: ["Duration", "ကာလ"],
  product_type: ["Product type", "အမျိုးအစား"], activation: ["Activation method", "Activate လုပ်ပုံ"],
  eligibility: ["Eligibility", "လိုအပ်ချက်"], warranty: ["Warranty", "အာမခံ"], delivery: ["Delivery", "ပို့ဆောင်ချိန်"],
  stock_checked: ["Supplier stock last checked", "Supplier stock နောက်ဆုံးစစ်ချိန်"], save: ["Save", "သက်သာ"],
  ends: ["Ends", "ကုန်ဆုံးမည်"], copy: ["Copy order summary", "အော်ဒါ အကျဉ်း ကူးယူရန်"], copied: ["Copied!", "ကူးယူပြီး!"],
  open_msgr: ["Open Messenger", "Messenger ဖွင့်ရန်"], msgr_hint: ["Send this summary to our Page on Messenger so our team can match your order.", "ဤအကျဉ်းကို Messenger မှ Page သို့ ပို့ပေးပါ။"],
  tg_off: ["Telegram checkout is being set up. Please order via Messenger or contact support.", "Telegram checkout ပြင်ဆင်နေဆဲဖြစ်ပါသည်။"],
  no_pw: ["We never ask for your passwords or OTP codes.", "Password နှင့် OTP များကို ဘယ်တော့မှ မတောင်းပါ။"],
  disclaimer: ["Independent reseller. Brand names belong to their owners; we are not affiliated with or endorsed by them.", "လွတ်လပ်သော ရောင်းချသူ ဖြစ်ပြီး Brand ပိုင်ရှင်များနှင့် တရားဝင် ဆက်နွယ်မှု မရှိပါ။"],
  track: ["Track order", "အော်ဒါ စစ်ရန်"], sample: ["Sample", "နမူနာ"], hot: ["Hot", "Hot"], featured: ["Featured", "အထူး"],
  policies: ["Policies", "မူဝါဒများ"], contact: ["Contact", "ဆက်သွယ်ရန်"], follow: ["Follow us", "Follow လုပ်ရန်"],
  about: ["About Us", "ကျွန်ုပ်တို့အကြောင်း"], privacy: ["Privacy Policy", "ကိုယ်ရေးလုံခြုံမှု"], terms: ["Terms of Service", "စည်းကမ်းချက်များ"],
  refund: ["Refund Policy", "ငွေပြန်အမ်းမှု"], delivery_policy: ["Delivery Policy", "ပို့ဆောင်မှု မူဝါဒ"], warranty_terms: ["Warranty Terms", "အာမခံ စည်းကမ်း"],
  share: ["Share on Facebook", "Facebook တွင် Share ရန်"], name_optional: ["Your name (optional)", "အမည် (မဖြည့်လည်းရ)"],
  create_ref: ["Create order reference", "Order Reference ထုတ်ရန်"], help_center: ["Help Center", "အကူအညီ စင်တာ"],
  why1: ["Transparent ordering", "ပွင့်လင်းသော မှာယူမှု"], why1d: ["Every order gets a unique ID and a locked price before you pay.", "ငွေမပေးမီ အော်ဒါ ID နှင့် စျေးနှုန်းကို သတ်မှတ်ပေးပါသည်။"],
  why2: ["Human-verified payments", "လူကိုယ်တိုင် စစ်ဆေးသော ငွေပေးချေမှု"], why2d: ["Our team checks every KBZPay, WavePay or AYA Pay transfer manually.", "ငွေလွှဲတိုင်းကို ဝန်ထမ်းမှ ကိုယ်တိုင် စစ်ဆေးပါသည်။"],
  why3: ["Real customer support", "တကယ့် Customer Support"], why3d: ["Talk to us on Telegram, Messenger or phone in Burmese or English.", "မြန်မာ/အင်္ဂလိပ် ဘာသာဖြင့် ဆက်သွယ်နိုင်ပါသည်။"],
  why4: ["Clear delivery process", "ရှင်းလင်းသော ပို့ဆောင်မှု"], why4d: ["Delivery happens in the channel you ordered from, with status updates.", "မှာယူသည့် Channel မှတဆင့် အခြေအနေနှင့်တကွ ပို့ဆောင်ပါသည်။"],
};

const Ctx = createContext(null);

export function I18nProvider({ children }) {
  const [lang, setLang] = useState(() => localStorage.getItem("lang") || "my");
  useEffect(() => {
    localStorage.setItem("lang", lang);
    document.documentElement.lang = lang;
  }, [lang]);
  const t = (k) => (D[k] ? D[k][lang === "my" ? 1 : 0] : k);
  const pick = (en, my) => (lang === "my" ? my || en : en || my);
  return createElement(Ctx.Provider, { value: { lang, setLang, t, pick } }, children);
}

export const useI18n = () => useContext(Ctx);
