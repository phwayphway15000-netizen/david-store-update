import os
import html
import httpx

from core import logger


def bot_token():
    return (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()


def bot_username():
    return (os.environ.get("TELEGRAM_BOT_USERNAME") or "").strip().lstrip("@")


def owner_id():
    return (os.environ.get("TELEGRAM_OWNER_USER_ID") or "").strip()


def configured():
    return bool(bot_token() and bot_username())


def esc(s):
    return html.escape(str(s if s is not None else ""))


async def tg_call(method, **params):
    """Returns (ok, result_or_error). Never logs the token."""
    if not bot_token():
        return False, "Telegram bot token not configured"
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"https://api.telegram.org/bot{bot_token()}/{method}", json=params)
        data = r.json()
        if data.get("ok"):
            return True, data.get("result")
        logger.warning(f"Telegram {method} failed: {data.get('description')}")
        return False, data.get("description", "Telegram error")
    except Exception as e:
        logger.warning(f"Telegram {method} exception: {type(e).__name__}")
        return False, "Telegram request failed"


def kb(rows):
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in rows]}


async def send(chat_id, text, buttons=None):
    params = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if buttons:
        params["reply_markup"] = kb(buttons)
    return await tg_call("sendMessage", **params)


async def notify_owner(text, buttons=None):
    if owner_id():
        return await send(owner_id(), text, buttons)
    return False, "Owner not configured"


async def download_file(file_id):
    ok, res = await tg_call("getFile", file_id=file_id)
    if not ok:
        return None
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(f"https://api.telegram.org/file/bot{bot_token()}/{res['file_path']}")
        r.raise_for_status()
        return r.content
    except Exception:
        return None
