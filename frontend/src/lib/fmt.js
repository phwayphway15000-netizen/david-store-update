export const mmk = (n) => `${Number(n || 0).toLocaleString("en-US")} Ks`;

export const fmtDate = (s) => (s ? new Date(s).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" }) : "—");

export const STATUS_STYLE = {
  CHECKOUT_STARTED: "bg-slate-100 text-slate-700 border-slate-300",
  AWAITING_CUSTOMER_CONFIRMATION: "bg-slate-100 text-slate-700 border-slate-300",
  AWAITING_PAYMENT: "bg-amber-50 text-amber-700 border-amber-300",
  PAYMENT_SUBMITTED: "bg-blue-50 text-blue-700 border-blue-300",
  PAYMENT_UNDER_REVIEW: "bg-blue-50 text-blue-700 border-blue-300 animate-pulse",
  PAYMENT_REJECTED: "bg-rose-50 text-rose-700 border-rose-300",
  PAID_AWAITING_FULFILLMENT: "bg-emerald-50 text-emerald-700 border-emerald-300",
  FULFILLMENT_IN_PROGRESS: "bg-sky-50 text-sky-700 border-sky-300",
  DELIVERED: "bg-indigo-50 text-indigo-700 border-indigo-300",
  COMPLETED: "bg-teal-50 text-teal-800 border-teal-300 font-semibold",
  CANCELLED: "bg-slate-100 text-slate-500 border-slate-200",
  REFUND_PENDING: "bg-orange-50 text-orange-700 border-orange-300",
  REFUNDED: "bg-stone-100 text-stone-600 border-stone-300",
};

export const statusLabel = (s) => (s || "").replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());

export const SOURCES = ["WEBSITE_TELEGRAM", "WEBSITE_MESSENGER", "DIRECT_MESSENGER", "ADMIN_MANUAL"];
