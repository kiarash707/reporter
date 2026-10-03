import os
import asyncio
import smtplib
import json
import logging
import hmac
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import pytz
from telethon import TelegramClient, events, Button, errors
from telethon.sessions import StringSession
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import (
    InputReportReasonSpam,
    InputReportReasonViolence,
    InputReportReasonPornography,
    InputReportReasonFake,
    InputReportReasonChildAbuse,
    InputReportReasonCopyright,
    InputReportReasonPersonalDetails,
    InputReportReasonOther
)

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_IDS = [int(x.strip()) for x in os.getenv("OWNER_IDS", "8437686179").split(",") if x.strip().isdigit()]

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise RuntimeError("Missing required environment variables: API_ID, API_HASH, BOT_TOKEN")

# Persistent files are stored under DATA_DIR.
# On Railway, mount a Volume to this directory (for example /app/data).
DATA_DIR = os.path.abspath(os.getenv("DATA_DIR", "."))
os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, "data.json")
ADMIN_SESSIONS_DIR = os.path.join(DATA_DIR, "admin_sessions")
# The bot account is authenticated from BOT_TOKEN on every process start.
# Do not reuse an old persistent MTProto bot session: it can belong to a different bot token.
BOT_SESSION_PATH = os.path.join(DATA_DIR, "bot_session")

os.makedirs(ADMIN_SESSIONS_DIR, exist_ok=True)

_log_file = os.path.join(DATA_DIR, "bot.log")
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(_log_file, encoding='utf-8'),
        logging.StreamHandler()
    ],
    force=True
)
logger = logging.getLogger("reporter")

MONITOR_TOKEN = os.getenv("MONITOR_TOKEN", "")
MONITOR_PORT = int(os.getenv("MONITOR_PORT", "8080"))
BOT_STARTED_AT = None
MONITOR_SERVER = None
BOT_LOOP = None
BOT_PROCESSING_ENABLED = True

REPORT_REASONS = {
    '1': ('🚫 Spam', InputReportReasonSpam(), 'This content is spam'),
    '2': ('❌ Fake', InputReportReasonFake(), 'This content is fake'),
    '3': ('🔪 Violence', InputReportReasonViolence(), 'This content contains violence'),
    '4': ('🔞 Pornography', InputReportReasonPornography(), 'This content contains pornography'),
    '5': ('👶 Child Abuse', InputReportReasonChildAbuse(), 'This content involves child abuse'),
    '6': ('©️ Copyright', InputReportReasonCopyright(), 'This content violates copyright'),
    '7': ('📋 Personal Details', InputReportReasonPersonalDetails(), 'This content exposes personal details'),
    '8': ('📝 Other', InputReportReasonOther(), 'Reported by bot - other reason'),
    '9': ('💸 Scam', InputReportReasonOther(), 'This channel/post/user is a scam')
}

DEFAULT_DATA = {
    "admins": {},
    "users": [],
    "blocked": [],
    "force_channels": [],
    "admin_data": {},
    "global_smtp_status": "on",
    "send_today": 0,
    "send_week": 0,
    "today_date": "",
    "week_number": "",
    "bot_status": "on",
    "user_lang": {},
    "user_meta": {}
}

def load_data():
    if not os.path.exists(DATA_FILE):
        data = DEFAULT_DATA.copy()
        save_data(data)
        return data
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        data = {}
    if not isinstance(data, dict):
        data = {}
    for key, value in DEFAULT_DATA.items():
        if key not in data:
            if isinstance(value, list):
                data[key] = []
            elif isinstance(value, dict):
                data[key] = {}
            else:
                data[key] = value
    def safe_list(k):
        if not isinstance(data.get(k), list):
            data[k] = []
    def safe_dict(k):
        if not isinstance(data.get(k), dict):
            data[k] = {}
    safe_list("users")
    safe_list("blocked")
    safe_list("force_channels")
    safe_dict("admin_data")
    safe_dict("admins")
    safe_dict("user_lang")
    safe_dict("user_meta")
    if not isinstance(data.get("send_today"), int):
        data["send_today"] = 0
    if not isinstance(data.get("send_week"), int):
        data["send_week"] = 0
    if not isinstance(data.get("today_date"), str):
        data["today_date"] = ""
    if not isinstance(data.get("week_number"), str):
        data["week_number"] = ""
    if data.get("global_smtp_status") not in ("on", "off"):
        data["global_smtp_status"] = "on"
    if data.get("bot_status") not in ("on", "off"):
        data["bot_status"] = "on"
    if "admins" in data:
        for uid_str in list(data["admins"].keys()):
            info = data["admins"][uid_str]
            if isinstance(info.get("expires"), str):
                info["expires"] = _normalize_tehran_datetime(datetime.fromisoformat(info["expires"]))
            else:
                info["expires"] = _normalize_tehran_datetime(info.get("expires"))
            if isinstance(info.get("activated"), str):
                info["activated"] = _normalize_tehran_datetime(datetime.fromisoformat(info["activated"]))
            else:
                info["activated"] = _normalize_tehran_datetime(info.get("activated"))
    for uid_str in data.get("admins", {}):
        data.setdefault("admin_data", {}).setdefault(uid_str, {
            "smtp": [],
            "active_senders": [],
            "recipients": []
        })
    for oid in OWNER_IDS:
        data.setdefault("admin_data", {}).setdefault(str(oid), {
            "smtp": [],
            "active_senders": [],
            "recipients": []
        })
    return data

def _normalize_tehran_datetime(value):
    if not isinstance(value, datetime):
        return value
    tehran = pytz.timezone("Asia/Tehran")
    if value.tzinfo is None:
        return tehran.localize(value)
    return value.astimezone(tehran)


def _is_active_expiry(expires, now_tehran=None):
    try:
        normalized = _normalize_tehran_datetime(expires)
        if not isinstance(normalized, datetime):
            return False
        now = now_tehran or datetime.now(pytz.timezone("Asia/Tehran"))
        return normalized > now
    except Exception:
        return False


def save_data(data):
    data_to_save = data.copy()
    if "admins" in data_to_save:
        admins_copy = {}
        for uid_str, info in data_to_save["admins"].items():
            info_copy = info.copy()
            if isinstance(info_copy.get("expires"), datetime):
                info_copy["expires"] = info_copy["expires"].isoformat()
            if isinstance(info_copy.get("activated"), datetime):
                info_copy["activated"] = info_copy["activated"].isoformat()
            admins_copy[uid_str] = info_copy
        data_to_save["admins"] = admins_copy
    temp_file = DATA_FILE + ".tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        os.replace(temp_file, DATA_FILE)
    except Exception:
        logger.exception("Failed to persist bot data")
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception:
            pass

def is_owner(user_id):
    return user_id in OWNER_IDS

def is_admin(user_id):
    data = load_data()
    admins = data.get("admins", {})
    if str(user_id) not in admins:
        return False
    try:
        tehran = pytz.timezone('Asia/Tehran')
        now = datetime.now(tehran)
        expires = admins[str(user_id)]["expires"]
        return _is_active_expiry(expires, now)
    except:
        return False

def can_telegram_reporter(user_id):
    return is_owner(user_id) or is_admin(user_id)

def get_user_lang(user_id):
    data = load_data()
    return data.get("user_lang", {}).get(str(user_id), None)

def touch_user(user_id):
    data = load_data()
    meta = data.setdefault("user_meta", {})
    key = str(user_id)
    now = datetime.now(pytz.timezone("Asia/Tehran")).isoformat()
    item = meta.get(key)
    if not isinstance(item, dict):
        meta[key] = {"first_seen": now, "last_seen": now}
        save_data(data)
        return
    last_seen = item.get("last_seen")
    try:
        old = datetime.fromisoformat(last_seen) if last_seen else None
    except Exception:
        old = None
    if old is None or (datetime.now(pytz.timezone("Asia/Tehran")) - old).total_seconds() >= 60:
        item["last_seen"] = now
        save_data(data)


def set_user_lang(user_id, lang):
    data = load_data()
    data.setdefault("user_lang", {})[str(user_id)] = lang
    save_data(data)

def is_blocked(user_id):
    data = load_data()
    return str(user_id) in [str(x) for x in data.get("blocked", [])]

def get_admin_data(user_id):
    data = load_data()
    admin_data = data.get("admin_data", {})
    uid = str(user_id)
    if uid not in admin_data:
        admin_data[uid] = {"smtp": [], "active_senders": [], "recipients": []}
        save_data(data)
    return admin_data[uid]

def get_admin_sessions_dir(admin_id):
    d = os.path.join(ADMIN_SESSIONS_DIR, str(admin_id))
    os.makedirs(d, exist_ok=True)
    return d

def get_user_sessions(user_id, force_refresh=False):
    cache_attr = f"session_cache_{user_id}"
    if not hasattr(get_user_sessions, cache_attr) or force_refresh:
        sessions = []
        if is_owner(user_id):
            for root, dirs, files in os.walk(ADMIN_SESSIONS_DIR):
                for f in files:
                    if f.endswith('.session'):
                        rel_path = os.path.relpath(os.path.join(root, f), ADMIN_SESSIONS_DIR)
                        admin_id_str = rel_path.split(os.sep)[0]
                        sessions.append((admin_id_str, f))
        else:
            admin_dir = get_admin_sessions_dir(user_id)
            for f in os.listdir(admin_dir):
                if f.endswith('.session'):
                    sessions.append((str(user_id), f))
        setattr(get_user_sessions, cache_attr, sessions)
    return getattr(get_user_sessions, cache_attr)

def clear_user_cache(user_id=None):
    if user_id:
        cache_attr = f"session_cache_{user_id}"
        if hasattr(get_user_sessions, cache_attr):
            delattr(get_user_sessions, cache_attr)
    else:
        for attr in list(get_user_sessions.__dict__.keys()):
            if attr.startswith("session_cache_"):
                delattr(get_user_sessions, attr)

USER_STATE = {}

def set_bot_processing(enabled):
    global BOT_PROCESSING_ENABLED
    BOT_PROCESSING_ENABLED = bool(enabled)
    data = load_data()
    data["bot_status"] = "on" if BOT_PROCESSING_ENABLED else "off"
    save_data(data)
    logger.info("Bot processing %s by dashboard control", "enabled" if BOT_PROCESSING_ENABLED else "paused")


def dashboard_user_snapshot():
    data = load_data()
    blocked = {str(x) for x in data.get("blocked", [])}
    admins = data.get("admins", {})
    now_tehran = datetime.now(pytz.timezone("Asia/Tehran"))
    rows = []
    for raw_uid in data.get("users", []):
        uid = int(raw_uid) if str(raw_uid).isdigit() else raw_uid
        info = admins.get(str(uid), {})
        expires = info.get("expires")
        active_admin = _is_active_expiry(expires, now_tehran)
        rows.append({
            "id": uid,
            "blocked": str(uid) in blocked,
            "admin": is_owner(uid) or active_admin,
            "owner": is_owner(uid),
            "language": data.get("user_lang", {}).get(str(uid), "fa"),
            "admin_expires": expires.isoformat() if isinstance(expires, datetime) else None,
            "first_seen": data.get("user_meta", {}).get(str(uid), {}).get("first_seen"),
            "last_seen": data.get("user_meta", {}).get(str(uid), {}).get("last_seen")
        })
    rows.sort(key=lambda x: int(x["id"]) if str(x["id"]).isdigit() else 0, reverse=True)
    return rows


def dashboard_admin_snapshot():
    data = load_data()
    now_tehran = datetime.now(pytz.timezone("Asia/Tehran"))
    rows = []
    seen = set()
    for uid in OWNER_IDS:
        rows.append({"id": uid, "owner": True, "active": True, "expires": None})
        seen.add(str(uid))
    for uid_str, info in data.get("admins", {}).items():
        if uid_str in seen:
            continue
        expires = info.get("expires")
        active = _is_active_expiry(expires, now_tehran)
        rows.append({
            "id": int(uid_str) if uid_str.isdigit() else uid_str,
            "owner": False,
            "active": active,
            "expires": expires.isoformat() if isinstance(expires, datetime) else None
        })
    return rows


def dashboard_channel_snapshot():
    data = load_data()
    return [{"channel": str(x)} for x in data.get("force_channels", [])]


def run_dashboard_coroutine(coro, timeout=30):
    if BOT_LOOP is None:
        raise RuntimeError("Bot event loop is not ready")
    future = asyncio.run_coroutine_threadsafe(coro, BOT_LOOP)
    try:
        return future.result(timeout=timeout)
    except Exception:
        future.cancel()
        raise


async def test_smtp_connection(email, app_password):
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
        server.ehlo()
        server.starttls()
        server.login(email, app_password)
        server.quit()
        return True
    except:
        return False

def send_email_sync(sender_email, password, to_email, subject, body):
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["From"] = sender_email
        msg["To"] = to_email
        msg["Subject"] = subject
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        return True, None
    except Exception as e:
        return False, str(e)

async def check_session_status(session_tuple):
    admin_id_str, filename = session_tuple
    path = os.path.join(ADMIN_SESSIONS_DIR, admin_id_str, filename)
    try:
        with open(path, 'r') as f:
            session_str = f.read().strip()
        if not session_str:
            return "❌ Empty"
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return "❌ Not authorized"
        me = await client.get_me()
        await client.disconnect()
        return f"✅ Active (ID: {me.id})"
    except FileNotFoundError:
        return "❌ File not found"
    except Exception as e:
        return f"⚠️ {str(e)[:30]}"

async def join_channel_with_approval(client, entity, session_file):
    try:
        await client(JoinChannelRequest(entity))
        return {'success': True, 'message': "✅ Joined"}
    except errors.UserAlreadyParticipantError:
        return {'success': True, 'message': "✅ Already joined"}
    except errors.InviteRequestSentError:
        return {'success': True, 'message': "✅ Join request sent"}
    except errors.FloodWaitError as e:
        return {'success': False, 'message': f"❌ Flood wait: {e.seconds}s"}
    except errors.ChannelPrivateError:
        return {'success': False, 'message': "❌ Channel is private"}
    except errors.ChannelInvalidError:
        return {'success': False, 'message': "❌ Invalid channel"}
    except Exception as e:
        return {'success': False, 'message': f"❌ Error: {str(e)[:30]}"}

async def perform_report(client, entity, reason, message, count=1):
    successes = 0
    failures = 0
    for i in range(count):
        try:
            await client(ReportPeerRequest(peer=entity, reason=reason, message=message))
            successes += 1
        except errors.FloodWaitError as e:
            failures += 1
            break
        except:
            failures += 1
        if i < count - 1:
            await asyncio.sleep(4)
    return successes, failures

async def validate_phone_number(phone):
    if not phone.startswith('+'):
        return False
    clean = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if len(clean) < 8 or len(clean) > 15:
        return False
    if not clean[1:].isdigit():
        return False
    return True

async def validate_post_link(link):
    if not (link.startswith('https://t.me/') or link.startswith('t.me/')):
        return False
    clean = link.replace('https://t.me/', '').replace('t.me/', '')
    parts = clean.split('/')
    if len(parts) < 2:
        return False
    try:
        post_id = int(parts[-1])
        if post_id <= 0:
            return False
    except:
        return False
    return True

# =============== KEYBOARD FUNCTIONS ===============

def main_menu_keyboard(user_id):
    lang = get_user_lang(user_id) or "fa"
    if not (is_owner(user_id) or is_admin(user_id)):
        return None
    kb = [
        [
            Button.inline("📧 ایمیل ریپورتر" if lang == "fa" else "📧 Email Reporter", "menu_email", style="primary"),
            Button.inline("🚫 تلگرام ریپورتر" if lang == "fa" else "🚫 Telegram Reporter", "menu_telegram", style="primary")
        ],
        [
            Button.inline("🌐 تغییر زبان" if lang == "fa" else "🌐 Change Language", "change_lang", style="success"),
            Button.url("📞 پشتیبانی / Support", "https://t.me/shikh4")
        ]
    ]
    if is_owner(user_id):
        kb.append([Button.inline("👑 پنل مالک" if lang == "fa" else "👑 Owner Panel", "owner_panel", style="danger")])
        kb.append([Button.inline("➕ افزودن ادمین" if lang == "fa" else "➕ Add Admin", "add_admin", style="success")])
    return kb

def owner_panel_keyboard(user_id):
    lang = get_user_lang(user_id) or "fa"
    return [
        [
            Button.inline("📢 پیام همگانی" if lang == "fa" else "📢 Broadcast", "em_broadcast", style="primary"),
            Button.inline("👤 پیام به کاربر" if lang == "fa" else "👤 Message User", "em_msg_user", style="primary")
        ],
        [
            Button.inline("🚫 بلاک کاربر" if lang == "fa" else "🚫 Block User", "em_block", style="danger"),
            Button.inline("✅ آنبلاک کاربر" if lang == "fa" else "✅ Unblock User", "em_unblock", style="success")
        ],
        [
            Button.inline("📢 مدیریت کانال اجباری" if lang == "fa" else "📢 Manage Force Channel", "em_force_channel", style="primary")
        ],
        [Button.inline("🔙 بازگشت به منوی اصلی" if lang == "fa" else "🔙 Back to Main Menu", "back_main", style="primary")]
    ]

def email_menu_keyboard(user_id):
    lang = get_user_lang(user_id) or "fa"
    is_own = is_owner(user_id)
    kb = []
    if lang == "fa":
        if is_own:
            kb.append([
                Button.inline("➕ افزودن SMTP", "em_smtp_add", style="primary"),
                Button.inline("📋 لیست SMTP", "em_smtp_list", style="primary")
            ])
            kb.append([
                Button.inline("🟢 فعال‌سازی ارسال‌کننده", "em_activate", style="success"),
                Button.inline("📧 ارسال تکی", "em_single_send", style="primary")
            ])
        else:
            kb.append([
                Button.inline("➕ افزودن SMTP", "em_smtp_add", style="primary"),
                Button.inline("📋 لیست SMTP", "em_smtp_list", style="primary")
            ])
            kb.append([
                Button.inline("🟢 فعال‌سازی ارسال‌کننده", "em_activate", style="success"),
                Button.inline("📧 ارسال تکی", "em_single_send", style="primary")
            ])
        kb.append([
            Button.inline("📨 ارسال گروهی", "em_bulk_send", style="success"),
            Button.inline("👥 لیست گیرنده‌ها", "em_recips", style="primary")
        ])
        kb.append([
            Button.inline("➕ افزودن گیرنده", "em_add_recip", style="primary"),
            Button.inline("🗑 پاک‌کردن گیرنده‌ها", "em_clear_recip", style="danger")
        ])
        kb.append([
            Button.inline("📊 آمار زنده", "em_stats", style="primary"),
            Button.inline("دریافت نمایندگی", "em_agency", style="success")
        ])
        kb.append([Button.inline("🔙 بازگشت به منوی اصلی", "back_main", style="primary")])
    else:
        if is_own:
            kb.append([
                Button.inline("➕ ADD SMTP", "em_smtp_add", style="primary"),
                Button.inline("📋 SMTP LIST", "em_smtp_list", style="primary")
            ])
            kb.append([
                Button.inline("🟢 ACTIVATE SENDER", "em_activate", style="success"),
                Button.inline("📧 SEND SINGLE", "em_single_send", style="primary")
            ])
        else:
            kb.append([
                Button.inline("➕ ADD SMTP", "em_smtp_add", style="primary"),
                Button.inline("📋 SMTP LIST", "em_smtp_list", style="primary")
            ])
            kb.append([
                Button.inline("🟢 ACTIVATE SENDER", "em_activate", style="success"),
                Button.inline("📧 SEND SINGLE", "em_single_send", style="primary")
            ])
        kb.append([
            Button.inline("📨 BULK SEND", "em_bulk_send", style="success"),
            Button.inline("👥 RECIPIENTS LIST", "em_recips", style="primary")
        ])
        kb.append([
            Button.inline("➕ ADD RECIPIENT", "em_add_recip", style="primary"),
            Button.inline("🗑 CLEAR RECIPIENTS", "em_clear_recip", style="danger")
        ])
        kb.append([
            Button.inline("📊 LIVE STATS", "em_stats", style="primary"),
            Button.inline("AGENCY", "em_agency", style="success")
        ])
        kb.append([Button.inline("🔙 BACK TO MAIN MENU", "back_main", style="primary")])
    return kb

def force_channel_keyboard(user_id):
    lang = get_user_lang(user_id) or "fa"
    return [
        [
            Button.inline("➕ افزودن کانال" if lang=="fa" else "➕ ADD CHANNEL", "em_fc_add", style="primary"),
            Button.inline("➖ حذف کانال" if lang=="fa" else "➖ REMOVE CHANNEL", "em_fc_remove", style="danger")
        ],
        [
            Button.inline("📋 لیست کانال‌ها" if lang=="fa" else "📋 CHANNEL LIST", "em_fc_list", style="primary"),
            Button.inline("🔙 بازگشت" if lang=="fa" else "🔙 BACK", "em_back", style="primary")
        ]
    ]

def telegram_menu_keyboard(user_id):
    lang = get_user_lang(user_id) or "fa"
    is_own = is_owner(user_id)
    kb = []
    kb.append([
        Button.inline("🚫 ریپورت کانال/گروه" if lang=="fa" else "🚫 REPORT CHANNEL/GROUP", "tg_report", style="danger"),
        Button.inline("📝 ریپورت پست" if lang=="fa" else "📝 REPORT POST", "tg_report_post", style="danger")
    ])
    kb.append([
        Button.inline("👤 ریپورت پروفایل" if lang=="fa" else "👤 REPORT PROFILE", "tg_report_profile", style="danger"),
        Button.inline("🤖 ریپورت ربات" if lang=="fa" else "🤖 REPORT BOT", "tg_report_bot", style="danger")
    ])
    kb.append([
        Button.inline("👤 ریپورت اکانت" if lang=="fa" else "👤 REPORT ACCOUNT", "tg_report_account", style="danger"),
        Button.inline("📋 ریپورت دستی" if lang=="fa" else "📋 MANUAL REPORT", "tg_manual_report", style="primary")
    ])
    if is_own:
        kb.append([
            Button.inline("⚙️ مدیریت اکانت‌ها" if lang=="fa" else "⚙️ MANAGE ACCOUNTS", "tg_manage_acc", style="primary"),
            Button.inline("🔙 بازگشت به منوی اصلی" if lang=="fa" else "🔙 BACK TO MAIN MENU", "back_main", style="primary")
        ])
    else:
        kb.append([
            Button.inline("➕ افزودن اکانت" if lang=="fa" else "➕ ADD ACCOUNT", "tg_add_acc", style="success"),
            Button.inline("📋 لیست اکانت‌ها" if lang=="fa" else "📋 LIST ACCOUNTS", "tg_list_shared", style="primary")
        ])
        kb.append([
            Button.inline("🗑 حذف اکانت" if lang=="fa" else "🗑 DELETE ACCOUNT", "tg_del_acc", style="danger"),
            Button.inline("🔙 بازگشت به منوی اصلی" if lang=="fa" else "🔙 BACK TO MAIN MENU", "back_main", style="primary")
        ])
    return kb

def manage_accounts_keyboard(user_id):
    lang = get_user_lang(user_id) or "fa"
    return [
        [
            Button.inline("➕ افزودن اکانت" if lang=="fa" else "➕ ADD ACCOUNT", "tg_add_acc", style="success"),
            Button.inline("🗑 حذف اکانت" if lang=="fa" else "🗑 DELETE ACCOUNT", "tg_del_acc", style="danger")
        ],
        [
            Button.inline("📋 لیست اکانت‌ها" if lang=="fa" else "📋 LIST ACCOUNTS", "tg_list_all", style="primary"),
            Button.inline("📋 لیست اشتراکی" if lang=="fa" else "📋 LIST SHARED", "tg_list_shared", style="primary")
        ],
        [Button.inline("🔙 بازگشت" if lang=="fa" else "🔙 BACK", "tg_back", style="primary")]
    ]

def reason_keyboard():
    buttons = []
    row = []
    for i in range(1, 10):
        reason_name = REPORT_REASONS[str(i)][0]
        row.append(Button.inline(reason_name, f"tg_reason_{i}", style="primary"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([Button.inline("🔙 Back", "tg_back", style="primary")])
    return buttons

def admin_duration_keyboard(lang):
    return [
        [
            Button.inline("1 ساعت" if lang=="fa" else "1 hour", "adm_1h", style="primary"),
            Button.inline("1 روز" if lang=="fa" else "1 day", "adm_1d", style="primary")
        ],
        [
            Button.inline("1 هفته" if lang=="fa" else "1 week", "adm_1w", style="primary"),
            Button.inline("1 ماه" if lang=="fa" else "1 month", "adm_1m", style="primary")
        ],
        [
            Button.inline("3 ماه" if lang=="fa" else "3 months", "adm_3m", style="primary"),
            Button.inline("6 ماه" if lang=="fa" else "6 months", "adm_6m", style="primary")
        ],
        [
            Button.inline("1 سال" if lang=="fa" else "1 year", "adm_1y", style="success"),
            Button.inline("🔙 برگشت" if lang=="fa" else "🔙 Back", "back_main", style="primary")
        ]
    ]

# =============== HANDLERS ===============

async def start_handler(event):
    user_id = event.sender_id
    logger.info("Incoming /start update from user_id=%s", user_id)
    touch_user(user_id)
    if not BOT_PROCESSING_ENABLED:
        await event.reply("⏸️ ربات موقتاً متوقف است. از داشبورد آن را فعال کنید.")
        return
    if is_blocked(user_id):
        await event.reply("🚫 شما بلاک هستید" if get_user_lang(user_id) == "fa" else "🚫 You are blocked")
        return

    data = load_data()
    if str(user_id) not in data["users"]:
        data["users"].append(user_id)
        save_data(data)

    lang = get_user_lang(user_id)
    if lang is None:
        buttons = [
            [Button.inline("فارسی", "lang_fa", style="primary"), Button.inline("English", "lang_en", style="primary")]
        ]
        await event.reply("🌍 Please choose your language:\nلطفاً زبان خود را انتخاب کنید:", buttons=buttons)
        return

    if not (is_owner(user_id) or is_admin(user_id)):
        await event.reply(
            "⛔ شما مجاز به استفاده از این ربات نیستید. لطفاً با پشتیبانی تماس بگیرید." if lang == "fa" else "⛔ You are not authorized to use this bot. Please contact support."
        )
        return

    await event.reply(
        "✅ به ربات ریپورتر شیخ خوش آمدید" if lang == "fa" else "✅ Welcome to SHIKH REPORTER Bot",
        buttons=main_menu_keyboard(user_id)
    )

async def callback_handler(event):
    data_str = event.data.decode('utf-8')
    logger.info("Incoming callback update from user_id=%s", event.sender_id)
    if not BOT_PROCESSING_ENABLED:
        await event.answer("⏸️ ربات موقتاً متوقف است.", alert=True)
        return
    user_id = event.sender_id
    lang = get_user_lang(user_id) or "fa"

    # ignore dummy callbacks
    if data_str in ["noop", "none"]:
        await event.answer()
        return

    if data_str in ["lang_fa", "lang_en"]:
        lang_code = "fa" if data_str == "lang_fa" else "en"
        set_user_lang(user_id, lang_code)
        lang = lang_code
        if not (is_owner(user_id) or is_admin(user_id)):
            await event.edit(
                "⛔ شما مجاز به استفاده از این ربات نیستید. لطفاً با پشتیبانی تماس بگیرید." if lang == "fa" else "⛔ You are not authorized to use this bot. Please contact support."
            )
            return
        await event.edit(
            "✅ زبان ذخیره شد" if lang == "fa" else "✅ Language saved",
            buttons=main_menu_keyboard(user_id)
        )
        return

    if not (is_owner(user_id) or is_admin(user_id)):
        await event.answer("⛔ دسترسی غیرمجاز" if lang == "fa" else "⛔ Unauthorized", alert=True)
        return

    if data_str == "change_lang":
        buttons = [
            [Button.inline("فارسی", "lang_fa", style="primary"), Button.inline("English", "lang_en", style="primary")]
        ]
        await event.edit("🌍 انتخاب زبان / Choose language:", buttons=buttons)
        return

    if data_str == "menu_email":
        await event.edit(
            "📧 **ایمیل ریپورتر**" if lang == "fa" else "📧 **Email Reporter**",
            buttons=email_menu_keyboard(user_id)
        )
        return

    if data_str == "menu_telegram":
        if not can_telegram_reporter(user_id):
            await event.answer("⛔ دسترسی غیرمجاز" if lang == "fa" else "⛔ Unauthorized access", alert=True)
            return
        await event.edit(
            "🚫 **تلگرام ریپورتر**" if lang == "fa" else "🚫 **Telegram Reporter**",
            buttons=telegram_menu_keyboard(user_id)
        )
        return

    if data_str == "back_main":
        await event.edit("✅ منوی اصلی" if lang == "fa" else "✅ Main Menu", buttons=main_menu_keyboard(user_id))
        return

    if data_str == "owner_panel":
        if not is_owner(user_id):
            await event.answer("⛔ دسترسی غیرمجاز" if lang == "fa" else "⛔ Unauthorized", alert=True)
            return
        await event.edit("👑 پنل مالک" if lang == "fa" else "👑 Owner Panel",
                        buttons=owner_panel_keyboard(user_id))
        return

    if data_str == "add_admin":
        if not is_owner(user_id):
            await event.answer("⛔ دسترسی غیرمجاز" if lang == "fa" else "⛔ Unauthorized", alert=True)
            return
        USER_STATE[user_id] = {"action": "add_admin", "step": "waiting_user_id"}
        await event.edit("🆔 آیدی عددی کاربر را برای افزودن به ادمین‌ها وارد کنید" if lang == "fa" else "🆔 Enter user ID to add as admin")
        return

    if data_str.startswith("adm_"):
        state = USER_STATE.get(user_id, {})
        if state.get("action") != "add_admin" or state.get("step") != "waiting_duration":
            await event.answer("⏳ لطفاً ابتدا آیدی کاربر را وارد کنید" if lang == "fa" else "⏳ Please enter user ID first", alert=True)
            return
        target_user = state.get("target_user")
        if not target_user:
            await event.answer("❌ خطا" if lang == "fa" else "❌ Error")
            return

        current_time = datetime.now(pytz.timezone('Asia/Tehran'))
        duration_map = {
            "adm_1h": timedelta(hours=1),
            "adm_1d": timedelta(days=1),
            "adm_1w": timedelta(weeks=1),
            "adm_1m": timedelta(days=30),
            "adm_3m": timedelta(days=90),
            "adm_6m": timedelta(days=180),
            "adm_1y": timedelta(days=365)
        }
        duration = duration_map.get(data_str)
        if not duration:
            await event.answer("مدت نامعتبر" if lang == "fa" else "Invalid duration")
            return

        expires = current_time + duration
        data_db = load_data()
        data_db.setdefault("admins", {})[str(target_user)] = {
            "expires": expires,
            "activated": current_time
        }
        data_db.setdefault("admin_data", {}).setdefault(str(target_user), {
            "smtp": [],
            "active_senders": [],
            "recipients": []
        })
        save_data(data_db)

        await event.edit(
            f"✅ ادمین برای کاربر {target_user} با موفقیت افزوده شد\n"
            f"تاریخ انقضا: {expires.strftime('%Y-%m-%d %H:%M:%S')}" if lang == "fa" else
            f"✅ Admin added for user {target_user}\n"
            f"Expires: {expires.strftime('%Y-%m-%d %H:%M:%S')}",
            buttons=[[Button.inline("🔙 بازگشت به منوی اصلی" if lang == "fa" else "🔙 BACK TO MAIN MENU", "back_main", style="primary")]]
        )
        USER_STATE.pop(user_id, None)
        return

    if data_str.startswith("em_"):
        await email_callback(event, data_str, user_id, lang)
        return

    if data_str.startswith("tg_"):
        await telegram_callback(event, data_str, user_id, lang)
        return

    await event.answer("Unknown")

# =============== EMAIL CALLBACKS ===============

async def email_callback(event, data, user_id, lang):
    data_db = load_data()
    admin_data = get_admin_data(user_id)

    if data == "em_smtp_add":
        USER_STATE[user_id] = {"section": "email", "flow": "smtp", "step": "waiting_email"}
        await event.edit("📧 آدرس Gmail را وارد کنید" if lang == "fa" else "📧 Enter Gmail address")
        return

    if data == "em_smtp_list":
        smtp_list = admin_data.get("smtp", [])
        if not smtp_list:
            await event.edit("❌ SMTP ثبت نشده" if lang == "fa" else "❌ No SMTP found",
                           buttons=[[Button.inline("🔙 بازگشت" if lang == "fa" else "BACK", "em_back", style="primary")]])
            return
        kb = []
        row = []
        for smtp in smtp_list:
            email = smtp.get("email", "")
            if email:
                row.append(Button.inline(email, f"em_smtp_view_{email}", style="primary"))
                if len(row) == 2:
                    kb.append(row)
                    row = []
        if row:
            kb.append(row)
        kb.append([Button.inline("🔙 بازگشت" if lang == "fa" else "BACK", "em_back", style="primary")])
        await event.edit("📋 لیست SMTP", buttons=kb)
        return

    if data.startswith("em_smtp_view_"):
        email = data.replace("em_smtp_view_", "", 1)
        kb = [
            [Button.inline("🗑 حذف" if lang == "fa" else "DELETE", f"em_smtp_del_{email}", style="danger")],
            [Button.inline("🔙 بازگشت" if lang == "fa" else "BACK", "em_smtp_list", style="primary")]
        ]
        await event.edit(f"📧 {email}\n\nحذف شود؟" if lang == "fa" else f"📧 {email}\n\nDelete?",
                        buttons=kb)
        return

    if data.startswith("em_smtp_del_"):
        email = data.replace("em_smtp_del_", "", 1)
        admin_data["smtp"] = [s for s in admin_data.get("smtp", []) if s.get("email") != email]
        save_data(data_db)
        smtp_list = admin_data["smtp"]
        if not smtp_list:
            await event.edit("✅ حذف شد\n📭 لیست خالی" if lang == "fa" else "✅ Deleted\nEmpty list",
                           buttons=[[Button.inline("🔙 بازگشت" if lang == "fa" else "BACK", "em_back", style="primary")]])
            return
        kb = []
        row = []
        for s in smtp_list:
            em = s.get("email", "")
            row.append(Button.inline(em, f"em_smtp_view_{em}", style="primary"))
            if len(row) == 2:
                kb.append(row)
                row = []
        if row:
            kb.append(row)
        kb.append([Button.inline("🔙 بازگشت" if lang == "fa" else "BACK", "em_back", style="primary")])
        await event.edit("📋 لیست SMTP", buttons=kb)
        return

    if data == "em_activate":
        smtp_list = admin_data.get("smtp", [])
        active = admin_data.get("active_senders", [])
        kb = []
        for s in smtp_list:
            email = s.get("email", "")
            status = "🟢" if email in active else "🔴"
            kb.append([Button.inline(f"{status} {email}", f"em_toggle_{email}", style="success" if email in active else "primary")])
        kb.append([Button.inline("🔙 بازگشت" if lang == "fa" else "BACK", "em_back", style="primary")])
        await event.edit("🟢 انتخاب SMTP فعال" if lang == "fa" else "🟢 Select active SMTP", buttons=kb)
        return

    if data.startswith("em_toggle_"):
        email = data.replace("em_toggle_", "", 1)
        active = admin_data.get("active_senders", [])
        if email in active:
            active.remove(email)
        else:
            active.append(email)
        save_data(data_db)
        kb = []
        for s in admin_data.get("smtp", []):
            em = s.get("email", "")
            status = "🟢" if em in active else "🔴"
            kb.append([Button.inline(f"{status} {em}", f"em_toggle_{em}", style="success" if em in active else "primary")])
        kb.append([Button.inline("🔙 بازگشت" if lang == "fa" else "BACK", "em_back", style="primary")])
        await event.edit("🟢 انتخاب SMTP فعال" if lang == "fa" else "🟢 Select active SMTP", buttons=kb)
        await event.answer("✅ وضعیت تغییر کرد" if lang == "fa" else "✅ Status changed")
        return

    if data == "em_single_send":
        USER_STATE[user_id] = {"section": "email", "flow": "single", "step": "to"}
        await event.edit("📧 گیرنده را وارد کنید" if lang == "fa" else "📧 Enter recipient")
        return

    if data == "em_bulk_send":
        USER_STATE[user_id] = {"section": "email", "flow": "bulk", "step": "subject"}
        await event.edit("✏️ موضوع را وارد کنید" if lang == "fa" else "✏️ Enter subject")
        return

    if data == "em_add_recip":
        USER_STATE[user_id] = {"section": "email", "step": "add_recipient"}
        await event.edit("📧 ایمیل گیرنده را ارسال کنید" if lang == "fa" else "📧 Send recipient email")
        return

    if data == "em_clear_recip":
        admin_data["recipients"] = []
        save_data(data_db)
        await event.edit("🗑 پاک شد" if lang == "fa" else "🗑 Cleared")
        return

    if data == "em_recips":
        recips = admin_data.get("recipients", [])
        text = "\n".join(recips) if recips else ("خالی" if lang == "fa" else "Empty")
        await event.edit(text, buttons=[[Button.inline("🔙 بازگشت" if lang == "fa" else "BACK", "em_back", style="primary")]])
        return

    if data == "em_stats":
        today = data_db.get("send_today", 0)
        week = data_db.get("send_week", 0)
        await event.edit(f"📊 ارسال امروز: {today}\n📊 ارسال این هفته: {week}" if lang == "fa" else
                        f"📊 Today: {today}\n📊 This Week: {week}")
        return

    if data == "em_agency":
        await event.answer("بخش نمایندگی غیرفعال است" if lang == "fa" else "Agency disabled", alert=True)
        return

    if data in ["em_broadcast", "em_msg_user", "em_block", "em_unblock", "em_force_channel", "em_fc_add", "em_fc_remove", "em_fc_list"]:
        if not is_owner(user_id):
            await event.answer("⛔ دسترسی غیرمجاز" if lang == "fa" else "⛔ Unauthorized", alert=True)
            return

    if data == "em_broadcast":
        USER_STATE[user_id] = {"section": "email", "step": "waiting_broadcast"}
        await event.edit("📨 متن همگانی را ارسال کنید" if lang == "fa" else "📨 Send broadcast message")
        return

    if data == "em_msg_user":
        USER_STATE[user_id] = {"section": "email", "step": "waiting_msg_user_id"}
        await event.edit("🆔 آیدی کاربر را ارسال کنید" if lang == "fa" else "🆔 Send user ID")
        return

    if data == "em_block":
        USER_STATE[user_id] = {"section": "email", "step": "waiting_block_id"}
        await event.edit("🚫 آیدی برای بلاک" if lang == "fa" else "🚫 Send ID to block")
        return

    if data == "em_unblock":
        USER_STATE[user_id] = {"section": "email", "step": "waiting_unblock_id"}
        await event.edit("✅ آیدی برای آنبلاک" if lang == "fa" else "✅ Send ID to unblock")
        return

    if data == "em_force_channel":
        await event.edit("📢 مدیریت کانال اجباری" if lang == "fa" else "📢 Manage Force Channel",
                        buttons=force_channel_keyboard(user_id))
        return

    if data == "em_fc_add":
        USER_STATE[user_id] = {"section": "email", "step": "waiting_fc_add"}
        await event.edit("📢 لینک یا یوزرنیم کانال را ارسال کنید" if lang == "fa" else "📢 Send channel username/link")
        return

    if data == "em_fc_remove":
        USER_STATE[user_id] = {"section": "email", "step": "waiting_fc_remove"}
        await event.edit("🗑 یوزرنیم کانال برای حذف" if lang == "fa" else "🗑 Send username to remove")
        return

    if data == "em_fc_list":
        channels = data_db.get("force_channels", [])
        text = "\n".join(channels) if channels else ("خالی" if lang == "fa" else "Empty")
        await event.edit(text)
        return

    if data == "em_back":
        await event.edit("📧 ایمیل ریپورتر" if lang == "fa" else "📧 Email Reporter",
                        buttons=email_menu_keyboard(user_id))
        return

    await event.answer("Unknown email callback")

# =============== TELEGRAM CALLBACKS ===============

async def telegram_callback(event, data, user_id, lang):
    if not can_telegram_reporter(user_id):
        await event.answer("⛔ دسترسی غیرمجاز" if lang == "fa" else "⛔ Unauthorized access", alert=True)
        return

    if data == "tg_report":
        sessions = get_user_sessions(user_id)
        if not sessions:
            await event.answer("❌ هیچ اکانتی در دسترس نیست" if lang == "fa" else "❌ No accounts available", alert=True)
            return
        USER_STATE[user_id] = {"section": "telegram", "type": "report", "step": "count", "sessions": sessions}
        await event.edit(f"🔢 تعداد اکانت؟ (1-{len(sessions)})" if lang == "fa" else f"🔢 Number of accounts? (1-{len(sessions)})")
        return

    if data == "tg_report_post":
        sessions = get_user_sessions(user_id)
        if not sessions:
            await event.answer("❌ هیچ اکانتی در دسترس نیست" if lang == "fa" else "❌ No accounts available", alert=True)
            return
        USER_STATE[user_id] = {"section": "telegram", "type": "report_post", "step": "count", "sessions": sessions}
        await event.edit(f"🔢 تعداد اکانت؟ (1-{len(sessions)})" if lang == "fa" else f"🔢 Number of accounts? (1-{len(sessions)})")
        return

    if data == "tg_report_profile":
        sessions = get_user_sessions(user_id)
        if not sessions:
            await event.answer("❌ هیچ اکانتی در دسترس نیست" if lang == "fa" else "❌ No accounts available", alert=True)
            return
        USER_STATE[user_id] = {"section": "telegram", "type": "report_profile", "step": "count", "sessions": sessions}
        await event.edit(f"🔢 تعداد اکانت؟ (1-{len(sessions)})" if lang == "fa" else f"🔢 Number of accounts? (1-{len(sessions)})")
        return

    if data == "tg_report_bot":
        sessions = get_user_sessions(user_id)
        if not sessions:
            await event.answer("❌ هیچ اکانتی در دسترس نیست" if lang == "fa" else "❌ No accounts available", alert=True)
            return
        USER_STATE[user_id] = {"section": "telegram", "type": "report_bot", "step": "count", "sessions": sessions}
        await event.edit(f"🔢 تعداد اکانت؟ (1-{len(sessions)})" if lang == "fa" else f"🔢 Number of accounts? (1-{len(sessions)})")
        return

    if data == "tg_report_account":
        sessions = get_user_sessions(user_id)
        if not sessions:
            await event.answer("❌ هیچ اکانتی در دسترس نیست" if lang == "fa" else "❌ No accounts available", alert=True)
            return
        USER_STATE[user_id] = {"section": "telegram", "type": "report_account", "step": "count", "sessions": sessions}
        await event.edit(f"🔢 تعداد اکانت؟ (1-{len(sessions)})" if lang == "fa" else f"🔢 Number of accounts? (1-{len(sessions)})")
        return

    if data == "tg_manual_report":
        sessions = get_user_sessions(user_id)
        if not sessions:
            await event.answer("❌ هیچ اکانتی در دسترس نیست" if lang == "fa" else "❌ No accounts available", alert=True)
            return
        USER_STATE[user_id] = {"section": "telegram", "type": "manual_report", "step": "count", "sessions": sessions}
        await event.edit(f"🔢 تعداد اکانت؟ (1-{len(sessions)})" if lang == "fa" else f"🔢 Number of accounts? (1-{len(sessions)})")
        return

    if data == "tg_manage_acc":
        if not is_owner(user_id):
            await event.answer("⛔ دسترسی غیرمجاز" if lang == "fa" else "⛔ Unauthorized", alert=True)
            return
        await event.edit("⚙️ مدیریت اکانت‌ها" if lang == "fa" else "⚙️ Manage Accounts",
                        buttons=manage_accounts_keyboard(user_id))
        return

    if data == "tg_list_shared":
        sessions = get_user_sessions(user_id)
        if not sessions:
            await event.answer("❌ اکانتی وجود ندارد" if lang == "fa" else "❌ No accounts", alert=True)
            return
        kb = []
        for admin_id, filename in sessions[:15]:
            phone = filename.replace('.session', '')
            status = await check_session_status((admin_id, filename))
            btn_text = f"📱 +{phone} - {status}"
            kb.append([
                Button.inline(btn_text, "noop"),
                Button.inline("🗑", f"tg_delacc_{admin_id}_{phone}", style="danger")
            ])
        kb.append([Button.inline("🔙 بازگشت" if lang=="fa" else "BACK", "tg_back", style="primary")])
        await event.edit("📋 لیست اکانت‌ها" if lang=="fa" else "📋 Accounts", buttons=kb)
        return

    if data == "tg_list_all":
        if not is_owner(user_id):
            await event.answer("⛔ دسترسی غیرمجاز" if lang == "fa" else "⛔ Unauthorized", alert=True)
            return
        sessions = get_user_sessions(user_id)
        if not sessions:
            await event.answer("❌ اکانتی وجود ندارد" if lang == "fa" else "❌ No accounts", alert=True)
            return
        kb = []
        for admin_id, filename in sessions[:15]:
            phone = filename.replace('.session', '')
            status = await check_session_status((admin_id, filename))
            btn_text = f"📱 +{phone} (Admin {admin_id}) - {status}"
            kb.append([
                Button.inline(btn_text, "noop"),
                Button.inline("🗑", f"tg_delacc_{admin_id}_{phone}", style="danger")
            ])
        kb.append([Button.inline("🔙 بازگشت" if lang=="fa" else "BACK", "tg_back", style="primary")])
        await event.edit("📋 لیست اکانت‌ها" if lang=="fa" else "📋 Accounts", buttons=kb)
        return

    if data == "tg_add_acc":
        if is_owner(user_id):
            USER_STATE[user_id] = {"section": "telegram", "step": "select_admin"}
            await event.edit("🆔 آیدی عددی ادمین مقصد را وارد کنید (یا 0 برای خودتان)" if lang == "fa" else "🆔 Enter target admin ID (or 0 for yourself)")
        else:
            USER_STATE[user_id] = {"section": "telegram", "step": "phone", "target_admin": user_id}
            await event.edit("📱 شماره تلفن با + را وارد کنید" if lang == "fa" else "📱 Enter phone number with +")
        return

    if data == "tg_del_acc":
        if is_owner(user_id):
            USER_STATE[user_id] = {"section": "telegram", "step": "delete_select_admin"}
            await event.edit("🆔 آیدی عددی ادمین برای حذف اکانت را وارد کنید" if lang == "fa" else "🆔 Enter admin ID to delete account from")
        else:
            USER_STATE[user_id] = {"section": "telegram", "step": "delete_phone", "target_admin": user_id}
            await event.edit("📱 شماره تلفن برای حذف را وارد کنید" if lang == "fa" else "📱 Enter phone number to delete")
        return

    if data.startswith("tg_delacc_"):
        parts = data[len("tg_delacc_"):].split("_", 1)
        if len(parts) != 2:
            await event.answer("Error")
            return
        admin_id_str, phone_clean = parts
        if not is_owner(user_id) and admin_id_str != str(user_id):
            await event.answer("⛔ Unauthorized", alert=True)
            return
        admin_dir = get_admin_sessions_dir(int(admin_id_str))
        path = os.path.join(admin_dir, f"{phone_clean}.session")
        if os.path.exists(path):
            os.remove(path)
            clear_user_cache()
            await event.answer("✅ حذف شد" if lang=="fa" else "✅ Deleted", alert=True)
        else:
            await event.answer("❌ یافت نشد" if lang=="fa" else "❌ Not found", alert=True)
        sessions = get_user_sessions(user_id, force_refresh=True)
        kb = []
        for a_id, fn in sessions[:15]:
            ph = fn.replace('.session', '')
            st = await check_session_status((a_id, fn))
            btn_text = f"📱 +{ph} - {st}"
            kb.append([
                Button.inline(btn_text, "noop"),
                Button.inline("🗑", f"tg_delacc_{a_id}_{ph}", style="danger")
            ])
        kb.append([Button.inline("🔙 بازگشت" if lang=="fa" else "BACK", "tg_back", style="primary")])
        await event.edit("📋 لیست اکانت‌ها" if lang=="fa" else "📋 Accounts", buttons=kb)
        return

    if data == "tg_back":
        await event.edit("🚫 تلگرام ریپورتر" if lang == "fa" else "🚫 Telegram Reporter",
                        buttons=telegram_menu_keyboard(user_id))
        return

    if data.startswith("tg_reason_"):
        reason_key = data.replace("tg_reason_", "", 1)
        state = USER_STATE.get(user_id, {})
        if not state:
            await event.answer("Session expired")
            return
        state["reason_key"] = reason_key
        if state.get("type") == "manual_report":
            state["step"] = "custom_reason"
            await event.edit("📝 متن گزارش سفارشی (حداقل 4 خط)" if lang == "fa" else "📝 Enter custom report message (min 4 lines)")
        else:
            state["step"] = "count_per_account"
            await event.edit("🔢 تعداد ریپورت هر اکانت؟ (1-50)" if lang == "fa" else "🔢 Reports per account? (1-50)")
        return

    await event.answer("Unknown telegram callback")

# =============== MESSAGE HANDLERS ===============

async def message_handler(event):
    logger.info("Incoming private message update from user_id=%s state=%s", event.sender_id, USER_STATE.get(event.sender_id, {}).get("step"))
    if not BOT_PROCESSING_ENABLED:
        return
    touch_user(event.sender_id)
    if event.text.startswith('/'):
        return

    text = event.text.strip()
    user_id = event.sender_id
    state = USER_STATE.get(user_id, {})
    lang = get_user_lang(user_id) or "fa"

    if not state:
        return

    if not (is_owner(user_id) or is_admin(user_id)):
        USER_STATE.pop(user_id, None)
        return

    if state.get("action") == "add_admin" and state.get("step") == "waiting_user_id":
        if not text.isdigit():
            await event.reply("❌ لطفاً یک آیدی عددی وارد کنید" if lang == "fa" else "❌ Please enter a numeric ID")
            return
        target_user = int(text)
        state["target_user"] = target_user
        state["step"] = "waiting_duration"
        await event.reply("⏰ مدت ادمین را انتخاب کنید:" if lang == "fa" else "⏰ Select admin duration:",
                         buttons=admin_duration_keyboard(lang))
        return

    section = state.get("section")
    if section == "email":
        await email_message_handler(event, state, text, user_id, lang)
    elif section == "telegram":
        await telegram_message_handler(event, state, text, user_id, lang)

async def email_message_handler(event, state, text, user_id, lang):
    data_db = load_data()
    admin_data = get_admin_data(user_id)
    flow = state.get("flow")
    step = state.get("step")

    if flow == "smtp":
        if step == "waiting_email":
            if "@" not in text or "." not in text:
                await event.reply("❌ ایمیل معتبر نیست" if lang == "fa" else "❌ Invalid email")
                return
            state["email"] = text
            state["step"] = "waiting_password"
            await event.reply("🔑 App Password را وارد کنید" if lang == "fa" else "🔑 Enter App Password")
            return
        if step == "waiting_password":
            email = state["email"]
            password = text.replace(" ", "")
            ok = await test_smtp_connection(email, password)
            if not ok:
                USER_STATE.pop(user_id, None)
                await event.reply("❌ ایمیل یا App Password اشتباه است" if lang == "fa" else "❌ Wrong email or app password")
                return
            admin_data.setdefault("smtp", []).append({"email": email, "password": password})
            save_data(data_db)
            USER_STATE.pop(user_id, None)
            await event.reply("✅ SMTP با موفقیت ذخیره شد" if lang == "fa" else "✅ SMTP saved successfully")
            return

    if flow == "single":
        if step == "to":
            if "@" not in text or "." not in text:
                await event.reply("❌ ایمیل معتبر نیست" if lang == "fa" else "❌ Invalid email")
                return
            state["to"] = text
            state["step"] = "subject"
            await event.reply("📝 موضوع را وارد کنید" if lang == "fa" else "📝 Enter subject")
            return
        if step == "subject":
            state["subject"] = text
            state["step"] = "body"
            await event.reply("📝 متن ایمیل را وارد کنید" if lang == "fa" else "📝 Enter email body")
            return
        if step == "body":
            to = state["to"]
            subject = state["subject"]
            body = text
            smtp_list = admin_data.get("smtp", [])
            if not smtp_list:
                USER_STATE.pop(user_id, None)
                await event.reply("❌ SMTP موجود نیست" if lang == "fa" else "❌ No SMTP available")
                return
            active = admin_data.get("active_senders", [])
            sender = next((s for s in smtp_list if s["email"] in active), smtp_list[0])
            ok, _ = send_email_sync(sender["email"], sender["password"], to, subject, body)
            if ok:
                await event.reply("✅ ارسال شد" if lang == "fa" else "✅ Sent")
            else:
                await event.reply("❌ خطا در ارسال" if lang == "fa" else "❌ Send failed")
            USER_STATE.pop(user_id, None)
            return

    if flow == "bulk":
        if step == "subject":
            state["subject"] = text
            state["step"] = "body"
            await event.reply("📝 متن ایمیل را وارد کنید" if lang == "fa" else "📝 Enter email body")
            return
        if step == "body":
            subject = state["subject"]
            body = text
            recips = admin_data.get("recipients", [])
            smtp_list = admin_data.get("smtp", [])
            if not smtp_list:
                USER_STATE.pop(user_id, None)
                await event.reply("❌ SMTP ندارید" if lang == "fa" else "❌ No SMTP")
                return
            if not recips:
                USER_STATE.pop(user_id, None)
                await event.reply("❌ گیرنده‌ای نیست" if lang == "fa" else "❌ No recipients")
                return
            active = admin_data.get("active_senders", [])
            sender = next((s for s in smtp_list if s["email"] in active), smtp_list[0])
            success = 0
            failed = 0
            for r in recips:
                ok, _ = send_email_sync(sender["email"], sender["password"], r, subject, body)
                if ok:
                    success += 1
                else:
                    failed += 1
                await asyncio.sleep(1)
            await event.reply(
                f"✅ تمام شد\n📨 کل: {len(recips)}\n✅ موفق: {success}\n❌ ناموفق: {failed}"
                if lang == "fa" else
                f"✅ Done\n📨 Total: {len(recips)}\n✅ Success: {success}\n❌ Failed: {failed}"
            )
            USER_STATE.pop(user_id, None)
            return

    if step == "add_recipient":
        emails = [x.strip() for x in text.splitlines() if x.strip()]
        added = 0
        dup = 0
        for email in emails:
            if email in admin_data["recipients"]:
                dup += 1
                continue
            admin_data["recipients"].append(email)
            added += 1
        save_data(data_db)
        await event.reply(f"✅ {added} گیرنده اضافه شد\n⚠️ تکراری: {dup}" if lang == "fa" else
                         f"✅ {added} added\n⚠️ duplicate: {dup}")
        USER_STATE.pop(user_id, None)
        return

    if step == "waiting_broadcast":
        if not is_owner(user_id):
            USER_STATE.pop(user_id, None)
            return
        if not text.strip():
            await event.reply("❌ متن خالی است" if lang == "fa" else "❌ Empty text")
            return
        data_db = load_data()
        users = data_db.get("users", [])
        sent = 0
        blocked = 0
        failed = 0
        total = len(users)
        if total == 0:
            await event.reply("❌ کاربری وجود ندارد" if lang == "fa" else "❌ No users")
            USER_STATE.pop(user_id, None)
            return
        msg = await event.reply("🚀 ارسال همگانی آغاز شد..." if lang == "fa" else "🚀 Broadcast started...")
        for i, uid in enumerate(users, 1):
            try:
                await event.client.send_message(int(uid), text)
                sent += 1
            except errors.UserIsBlockedError:
                blocked += 1
            except:
                failed += 1
            if i % 10 == 0 or i == total:
                percent = int(i * 100 / total)
                bar = "🟩" * (percent // 10) + "⬜" * (10 - percent // 10)
                try:
                    await msg.edit(
                        f"🚀 ارسال همگانی\n{bar} {percent}%\n👥 کل: {total}\n📤 موفق: {sent}\n🚫 بلاک: {blocked}\n❌ خطا: {failed}"
                        if lang == "fa" else
                        f"🚀 Broadcast\n{bar} {percent}%\n👥 Total: {total}\n📤 Sent: {sent}\n🚫 Blocked: {blocked}\n❌ Failed: {failed}"
                    )
                except:
                    pass
            await asyncio.sleep(0.05)
        await msg.edit(
            f"✅ ارسال همگانی پایان یافت\n🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩 100%\n👥 کل: {total}\n📤 موفق: {sent}\n🚫 بلاک: {blocked}\n❌ خطا: {failed}"
            if lang == "fa" else
            f"✅ Broadcast completed\n🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩 100%\n👥 Total: {total}\n📤 Sent: {sent}\n🚫 Blocked: {blocked}\n❌ Failed: {failed}"
        )
        USER_STATE.pop(user_id, None)
        return

    if step == "waiting_msg_user_id":
        if not is_owner(user_id):
            USER_STATE.pop(user_id, None)
            return
        if not text.isdigit():
            await event.reply("❌ فقط آیدی عددی" if lang == "fa" else "❌ Numeric ID only")
            return
        state["target_user"] = int(text)
        state["step"] = "waiting_msg_user_text"
        await event.reply("✉️ متن پیام را ارسال کنید" if lang == "fa" else "✉️ Send message text")
        return

    if step == "waiting_msg_user_text":
        if not is_owner(user_id):
            USER_STATE.pop(user_id, None)
            return
        target = state.get("target_user")
        if not target:
            USER_STATE.pop(user_id, None)
            return
        try:
            await event.client.send_message(target, text)
            await event.reply("✅ پیام ارسال شد" if lang == "fa" else "✅ Message sent")
        except:
            await event.reply("❌ ارسال ناموفق" if lang == "fa" else "❌ Failed")
        USER_STATE.pop(user_id, None)
        return

    if step == "waiting_block_id":
        if not is_owner(user_id):
            USER_STATE.pop(user_id, None)
            return
        if not text.isdigit():
            await event.reply("❌ فقط آیدی عددی" if lang == "fa" else "❌ Numeric ID only")
            return
        data_db = load_data()
        data_db.setdefault("blocked", [])
        target = int(text)
        if target not in data_db["blocked"]:
            data_db["blocked"].append(target)
            save_data(data_db)
        await event.reply("🚫 کاربر بلاک شد" if lang == "fa" else "🚫 User blocked")
        USER_STATE.pop(user_id, None)
        return

    if step == "waiting_unblock_id":
        if not is_owner(user_id):
            USER_STATE.pop(user_id, None)
            return
        if not text.isdigit():
            await event.reply("❌ فقط آیدی عددی" if lang == "fa" else "❌ Numeric ID only")
            return
        data_db = load_data()
        data_db.setdefault("blocked", [])
        target = int(text)
        if target in data_db["blocked"]:
            data_db["blocked"].remove(target)
            save_data(data_db)
        await event.reply("✅ کاربر آنبلاک شد" if lang == "fa" else "✅ User unblocked")
        USER_STATE.pop(user_id, None)
        return

    if step == "waiting_fc_add":
        if not is_owner(user_id):
            USER_STATE.pop(user_id, None)
            return
        if not text.strip():
            await event.reply("❌ ورودی نامعتبر" if lang == "fa" else "❌ Invalid input")
            return
        channel = text.strip()
        if not channel.startswith("@"):
            channel = "@" + channel
        data_db = load_data()
        data_db.setdefault("force_channels", [])
        if channel not in data_db["force_channels"]:
            data_db["force_channels"].append(channel)
            save_data(data_db)
        await event.reply("✅ کانال اضافه شد" if lang == "fa" else "✅ Channel added")
        USER_STATE.pop(user_id, None)
        return

    if step == "waiting_fc_remove":
        if not is_owner(user_id):
            USER_STATE.pop(user_id, None)
            return
        if not text.strip():
            await event.reply("❌ ورودی نامعتبر" if lang == "fa" else "❌ Invalid input")
            return
        channel = text.strip()
        if not channel.startswith("@"):
            channel = "@" + channel
        data_db = load_data()
        data_db.setdefault("force_channels", [])
        if channel in data_db["force_channels"]:
            data_db["force_channels"].remove(channel)
            save_data(data_db)
        await event.reply("✅ کانال حذف شد" if lang == "fa" else "✅ Channel removed")
        USER_STATE.pop(user_id, None)
        return

async def telegram_message_handler(event, state, text, user_id, lang):
    step = state.get("step")
    data_db = load_data()

    if step == "select_admin":
        if not text.strip().isdigit() and text != "0":
            await event.reply("❌ آیدی نامعتبر" if lang == "fa" else "❌ Invalid ID")
            return
        if text == "0":
            target_admin = user_id
        else:
            target_admin = int(text)
        if target_admin != user_id and not is_admin(target_admin) and not is_owner(target_admin):
            await event.reply("❌ ادمین یافت نشد" if lang == "fa" else "❌ Admin not found")
            return
        state["target_admin"] = target_admin
        state["step"] = "phone"
        await event.reply("📱 شماره تلفن با + را وارد کنید" if lang == "fa" else "📱 Enter phone number with +")
        return

    if step == "delete_select_admin":
        if not text.strip().isdigit():
            await event.reply("❌ آیدی نامعتبر" if lang == "fa" else "❌ Invalid ID")
            return
        target_admin = int(text)
        if target_admin != user_id and not is_admin(target_admin) and not is_owner(target_admin):
            await event.reply("❌ ادمین یافت نشد" if lang == "fa" else "❌ Admin not found")
            return
        state["target_admin"] = target_admin
        state["step"] = "delete_phone"
        await event.reply("📱 شماره تلفن برای حذف را وارد کنید" if lang == "fa" else "📱 Enter phone number to delete")
        return

    if step == "phone":
        if not await validate_phone_number(text):
            await event.reply("❌ شماره نامعتبر است" if lang == "fa" else "❌ Invalid phone number")
            return
        state["phone"] = text
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        try:
            await client.send_code_request(text)
            state["client"] = client
            state["step"] = "code"
            await event.reply("✅ کد ارسال شد. کد را وارد کنید" if lang == "fa" else "✅ Code sent. Enter code")
        except Exception as e:
            await event.reply(f"❌ خطا: {str(e)[:100]}")
            await client.disconnect()
            USER_STATE.pop(user_id, None)
        return

    if step == "code":
        if len(text) < 4:
            await event.reply("❌ کد نامعتبر" if lang == "fa" else "❌ Invalid code")
            return
        client = state.get("client")
        phone = state.get("phone")
        target_admin = state.get("target_admin", user_id)
        if not client or not phone:
            USER_STATE.pop(user_id, None)
            return
        try:
            await client.sign_in(phone, text)
            session_str = client.session.save()
            phone_clean = phone.replace('+', '').replace(' ', '')
            filename = f"{phone_clean}.session"
            admin_dir = get_admin_sessions_dir(target_admin)
            path = os.path.join(admin_dir, filename)
            with open(path, "w", encoding='utf-8') as f:
                f.write(session_str)
            clear_user_cache()
            me = await client.get_me()
            profile = f"✅ اکانت اضافه شد\n👤 {me.first_name or ''} {me.last_name or ''}\n📱 {phone}\n🆔 {me.id}\n@{me.username or 'None'}"
            await event.reply(profile)
            await client.disconnect()
            USER_STATE.pop(user_id, None)
        except errors.SessionPasswordNeededError:
            state["step"] = "password"
            await event.reply("🔐 رمز دو مرحله‌ای را وارد کنید" if lang == "fa" else "🔐 Enter 2FA password")
        except errors.PhoneCodeInvalidError:
            await event.reply("❌ کد اشتباه است" if lang == "fa" else "❌ Invalid code")
        except errors.PhoneCodeExpiredError:
            await event.reply("❌ کد منقضی شده" if lang == "fa" else "❌ Code expired")
            await client.disconnect()
            USER_STATE.pop(user_id, None)
        except Exception as e:
            await event.reply(f"❌ خطا: {str(e)[:100]}")
            await client.disconnect()
            USER_STATE.pop(user_id, None)
        return

    if step == "password":
        if not text:
            await event.reply("❌ رمز نامعتبر" if lang == "fa" else "❌ Invalid password")
            return
        client = state.get("client")
        phone = state.get("phone")
        target_admin = state.get("target_admin", user_id)
        if not client:
            USER_STATE.pop(user_id, None)
            return
        try:
            await client.sign_in(password=text)
            session_str = client.session.save()
            phone_clean = phone.replace('+', '').replace(' ', '')
            filename = f"{phone_clean}.session"
            admin_dir = get_admin_sessions_dir(target_admin)
            path = os.path.join(admin_dir, filename)
            with open(path, "w", encoding='utf-8') as f:
                f.write(session_str)
            clear_user_cache()
            me = await client.get_me()
            profile = f"✅ اکانت اضافه شد\n👤 {me.first_name or ''} {me.last_name or ''}\n📱 {phone}\n🆔 {me.id}\n@{me.username or 'None'}"
            await event.reply(profile)
            await client.disconnect()
            USER_STATE.pop(user_id, None)
        except errors.PasswordHashInvalidError:
            await event.reply("❌ رمز اشتباه است" if lang == "fa" else "❌ Invalid password")
        except Exception as e:
            await event.reply(f"❌ خطا: {str(e)[:100]}")
            await client.disconnect()
            USER_STATE.pop(user_id, None)
        return

    if step == "delete_phone":
        if not text.startswith('+'):
            await event.reply("❌ شماره باید با + شروع شود" if lang == "fa" else "❌ Number must start with +")
            return
        phone_clean = text.replace('+', '').replace(' ', '')
        target_admin = state.get("target_admin", user_id)
        admin_dir = get_admin_sessions_dir(target_admin)
        deleted = False
        for f in os.listdir(admin_dir):
            if f == f"{phone_clean}.session":
                os.remove(os.path.join(admin_dir, f))
                deleted = True
        if deleted:
            clear_user_cache()
            await event.reply(f"✅ اکانت {text} حذف شد" if lang == "fa" else f"✅ Account {text} deleted")
        else:
            await event.reply(f"❌ اکانتی یافت نشد" if lang == "fa" else f"❌ No account found")
        USER_STATE.pop(user_id, None)
        return

    if step == "count":
        try:
            count = int(text)
            sessions = state["sessions"]
            if count < 1 or count > len(sessions):
                await event.reply(f"❌ عدد بین 1 تا {len(sessions)}" if lang == "fa" else f"❌ Between 1 and {len(sessions)}")
                return
            state["count"] = count
            state["selected_sessions"] = sessions[:count]
            op_type = state.get("type")
            if op_type in ["report_post"]:
                state["step"] = "post_links"
                await event.reply("🔗 لینک پست‌ها را ارسال کنید (1 تا 6 لینک)" if lang == "fa" else "🔗 Enter post links (1-6)")
            else:
                state["step"] = "target"
                await event.reply("🔗 لینک/یوزرنیم هدف را وارد کنید" if lang == "fa" else "🔗 Enter target link/username")
        except ValueError:
            await event.reply("❌ عدد وارد کنید" if lang == "fa" else "❌ Enter a number")
        return

    if step == "post_links":
        post_links = [link.strip() for link in text.split('\n') if link.strip()]
        if not post_links or len(post_links) > 6:
            await event.reply("❌ بین 1 تا 6 لینک" if lang == "fa" else "❌ 1 to 6 links")
            return
        for link in post_links:
            if not await validate_post_link(link):
                await event.reply(f"❌ لینک نامعتبر: {link}" if lang == "fa" else f"❌ Invalid link: {link}")
                return
        state["post_links"] = post_links
        state["step"] = "select_reason"
        await event.reply("📝 دلیل ریپورت را انتخاب کنید:", buttons=reason_keyboard())
        return

    if step == "target":
        target = text.strip()
        if not target:
            await event.reply("❌ خالی نباشد" if lang == "fa" else "❌ Not empty")
            return
        state["target"] = target
        if state.get("type") == "manual_report":
            state["step"] = "custom_reason"
            await event.reply("📝 متن گزارش سفارشی (حداقل 4 خط)" if lang == "fa" else "📝 Custom report message (min 4 lines)")
        else:
            state["step"] = "select_reason"
            await event.reply("📝 دلیل ریپورت را انتخاب کنید:", buttons=reason_keyboard())
        return

    if step == "count_per_account":
        try:
            cnt = int(text)
            if cnt < 1 or cnt > 50:
                await event.reply("❌ عدد بین 1 تا 50" if lang == "fa" else "❌ Between 1 and 50")
                return
            state["count_per_account"] = cnt
            state["step"] = "custom_reason"
            await event.reply("📝 متن دلخواه (یا /skip)" if lang == "fa" else "📝 Custom message (or /skip)")
        except ValueError:
            await event.reply("❌ عدد وارد کنید" if lang == "fa" else "❌ Enter a number")
        return

    if step == "custom_reason":
        if text == "/skip":
            reason_key = state.get("reason_key", "1")
            text = REPORT_REASONS[reason_key][2]
        state["custom_reason"] = text
        await execute_report_operation(event, state, user_id, lang)
        USER_STATE.pop(user_id, None)
        return

async def execute_report_operation(event, state, user_id, lang):
    sessions = state["selected_sessions"]
    op_type = state.get("type")
    reason_key = state.get("reason_key", "1")
    reason_name, reason_obj, default_msg = REPORT_REASONS[reason_key]
    custom_msg = state.get("custom_reason", default_msg)
    count_per_account = state.get("count_per_account", 1)

    total_success = 0
    total_fail = 0
    errors_list = []

    await event.reply("🚀 شروع عملیات ریپورت..." if lang == "fa" else "🚀 Starting report operation...")

    if op_type == "report_post":
        post_links = state.get("post_links", [])
        target_links = post_links
    else:
        target_links = [state.get("target", "")]

    for target in target_links:
        for admin_id_str, filename in sessions:
            path = os.path.join(ADMIN_SESSIONS_DIR, admin_id_str, filename)
            try:
                with open(path, 'r') as f:
                    session_str = f.read().strip()
                if not session_str:
                    total_fail += 1
                    continue

                client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
                await client.connect()
                if not await client.is_user_authorized():
                    total_fail += 1
                    await client.disconnect()
                    continue

                try:
                    if target.startswith("@"):
                        entity = await client.get_entity(target)
                    else:
                        clean = target.replace("https://t.me/", "").replace("t.me/", "")
                        if op_type == "report_post":
                            parts = clean.split("/")
                            if len(parts) >= 2:
                                channel = parts[0]
                                entity = await client.get_entity("@" + channel if not channel.startswith("@") else channel)
                            else:
                                total_fail += 1
                                await client.disconnect()
                                continue
                        else:
                            entity = await client.get_entity(clean)

                    if op_type in ["report", "report_post"]:
                        await join_channel_with_approval(client, entity, filename)

                    s, f = await perform_report(client, entity, reason_obj, custom_msg, count_per_account)
                    total_success += s
                    total_fail += f

                except Exception as e:
                    total_fail += 1
                    errors_list.append(f"{filename}: {str(e)[:50]}")

                await client.disconnect()
                await asyncio.sleep(3)

            except Exception as e:
                total_fail += 1
                errors_list.append(f"{filename}: {str(e)[:50]}")

    result = (
        f"📊 **عملیات ریپورت پایان یافت**\n\n"
        f"🎯 هدف: {state.get('target', 'Multiple posts')}\n"
        f"📝 دلیل: {reason_name}\n"
        f"👥 اکانت‌ها: {len(sessions)}\n"
        f"🔢 ریپورت/اکانت: {count_per_account}\n"
        f"✅ موفق: {total_success}\n"
        f"❌ ناموفق: {total_fail}"
        if lang == "fa" else
        f"📊 **Report Operation Complete**\n\n"
        f"🎯 Target: {state.get('target', 'Multiple posts')}\n"
        f"📝 Reason: {reason_name}\n"
        f"👥 Accounts: {len(sessions)}\n"
        f"🔢 Reports/Account: {count_per_account}\n"
        f"✅ Success: {total_success}\n"
        f"❌ Failed: {total_fail}"
    )

    if errors_list and len(errors_list) <= 5:
        result += "\n\n⚠️ خطاها:\n" + "\n".join(errors_list[:5]) if lang == "fa" else "\n\n⚠️ Errors:\n" + "\n".join(errors_list[:5])

    await event.reply(result)


def _tail_log_file(lines=100):
    try:
        lines = max(1, min(int(lines), 300))
    except (TypeError, ValueError):
        lines = 100

    log_path = os.path.join(DATA_DIR, "bot.log")
    if not os.path.exists(log_path):
        return []

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            return f.readlines()[-lines:]
    except Exception:
        return []


def _session_count():
    count = 0
    try:
        for root, _, files in os.walk(ADMIN_SESSIONS_DIR):
            count += sum(1 for name in files if name.endswith(".session"))
    except Exception:
        pass
    return count


class MonitorHandler(BaseHTTPRequestHandler):
    server_version = "ReporterMonitor/1.0"

    def _send_json(self, status_code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        if not MONITOR_TOKEN:
            return False
        supplied = self.headers.get("X-Monitor-Token", "")
        try:
            return hmac.compare_digest(supplied, MONITOR_TOKEN)
        except Exception:
            return False

    def do_GET(self):
        try:
            parsed = urlparse(self.path)

            if parsed.path == "/health":
                self._send_json(200, {
                    "status": "ok",
                    "service": os.getenv("RAILWAY_SERVICE_NAME", "reporter")
                })
                return

            if not self._authorized():
                self._send_json(401, {"error": "unauthorized"})
                return

            if parsed.path == "/api/status":
                data = load_data()
                now_tehran = datetime.now(pytz.timezone("Asia/Tehran"))
                admins = data.get("admins", {})
                active_admins = 0

                for info in admins.values():
                    try:
                        if _is_active_expiry(info.get("expires"), now_tehran):
                            active_admins += 1
                    except Exception:
                        pass

                uptime_seconds = 0
                if BOT_STARTED_AT is not None:
                    uptime_seconds = max(
                        0,
                        int((datetime.now(pytz.UTC) - BOT_STARTED_AT).total_seconds())
                    )

                telegram_connected = False
                try:
                    telegram_connected = bool(bot_instance.is_connected())
                except Exception:
                    pass

                self._send_json(200, {
                    "status": "online",
                    "telegram_connected": telegram_connected,
                    "started_at": BOT_STARTED_AT.isoformat() if BOT_STARTED_AT else None,
                    "uptime_seconds": uptime_seconds,
                    "users": len(data.get("users", [])),
                    "admins": len(admins),
                    "active_admins": active_admins,
                    "sessions": _session_count(),
                    "send_today": data.get("send_today", 0),
                    "send_week": data.get("send_week", 0),
                    "bot_status": data.get("bot_status", "on"),
                    "processing_enabled": BOT_PROCESSING_ENABLED,
                    "blocked_users": len(data.get("blocked", [])),
                    "force_channels": len(data.get("force_channels", [])),
                    "smtp_status": data.get("global_smtp_status", "on"),
                    "service": os.getenv("RAILWAY_SERVICE_NAME", "reporter"),
                    "environment": os.getenv("RAILWAY_ENVIRONMENT_NAME", "production"),
                    "region": os.getenv("RAILWAY_REGION", ""),
                    "deployment_id": os.getenv("RAILWAY_DEPLOYMENT_ID", ""),
                    "monitor_port": MONITOR_PORT
                })
                return

            if parsed.path == "/api/users":
                params = parse_qs(parsed.query)
                query = params.get("q", [""])[0].strip().lower()
                users = dashboard_user_snapshot()
                if query:
                    users = [u for u in users if query in str(u["id"]).lower()]
                try:
                    limit = min(500, max(1, int(params.get("limit", ["300"])[0])))
                except ValueError:
                    limit = 300
                self._send_json(200, {"users": users[:limit], "total": len(users)})
                return

            if parsed.path == "/api/admins":
                self._send_json(200, {"admins": dashboard_admin_snapshot()})
                return

            if parsed.path == "/api/channels":
                self._send_json(200, {"channels": dashboard_channel_snapshot()})
                return

            if parsed.path == "/api/logs":
                params = parse_qs(parsed.query)
                lines = params.get("lines", ["100"])[0]
                self._send_json(200, {"lines": _tail_log_file(lines)})
                return

            self._send_json(404, {"error": "not_found"})
        except Exception:
            logger.exception("Monitor HTTP error")
            try:
                self._send_json(500, {"error": "monitor_error"})
            except Exception:
                pass

    def log_message(self, format, *args):
        return


    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            if not self._authorized():
                self._send_json(401, {"error": "unauthorized"})
                return

            raw = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
            payload = json.loads(raw.decode("utf-8") or "{}") if raw else {}

            if parsed.path == "/api/control":
                action = payload.get("action")
                if action == "pause":
                    set_bot_processing(False)
                    self._send_json(200, {"ok": True, "message": "ربات متوقف شد"})
                    return
                if action == "resume":
                    set_bot_processing(True)
                    self._send_json(200, {"ok": True, "message": "ربات فعال شد"})
                    return
                if action == "restart":
                    data = load_data()
                    data["bot_status"] = "on"
                    save_data(data)
                    logger.warning("Restart requested from dashboard")
                    self._send_json(200, {"ok": True, "message": "درخواست راه‌اندازی مجدد ثبت شد"})
                    def delayed_exit():
                        import time as _time
                        _time.sleep(0.4)
                        os._exit(1)
                    threading.Thread(target=delayed_exit, daemon=True).start()
                    return
                self._send_json(400, {"ok": False, "error": "action_invalid"})
                return

            if parsed.path == "/api/users":
                action = payload.get("action")
                user_id = payload.get("user_id")
                if not str(user_id).isdigit():
                    self._send_json(400, {"ok": False, "error": "user_id_invalid"})
                    return
                user_id = int(user_id)
                data = load_data()
                blocked = data.setdefault("blocked", [])

                if action == "block":
                    if user_id not in [int(x) for x in blocked if str(x).isdigit()]:
                        blocked.append(user_id)
                    save_data(data)
                    logger.info("User %s blocked from dashboard", user_id)
                    self._send_json(200, {"ok": True, "message": "کاربر بلاک شد"})
                    return

                if action == "unblock":
                    data["blocked"] = [x for x in blocked if str(x) != str(user_id)]
                    save_data(data)
                    logger.info("User %s unblocked from dashboard", user_id)
                    self._send_json(200, {"ok": True, "message": "کاربر آنبلاک شد"})
                    return

                if action == "message":
                    message = str(payload.get("message", "")).strip()
                    if not message:
                        self._send_json(400, {"ok": False, "error": "message_empty"})
                        return
                    run_dashboard_coroutine(bot_instance.send_message(user_id, message))
                    logger.info("Dashboard sent a private message to user %s", user_id)
                    self._send_json(200, {"ok": True, "message": "پیام ارسال شد"})
                    return

                self._send_json(400, {"ok": False, "error": "action_invalid"})
                return

            if parsed.path == "/api/admins":
                action = payload.get("action")
                user_id = payload.get("user_id")
                if not str(user_id).isdigit():
                    self._send_json(400, {"ok": False, "error": "user_id_invalid"})
                    return
                user_id = int(user_id)

                if action == "add":
                    try:
                        days = int(payload.get("days", 30))
                    except (TypeError, ValueError):
                        days = 30
                    days = min(3650, max(1, days))
                    current_time = datetime.now(pytz.timezone("Asia/Tehran"))
                    data = load_data()
                    data.setdefault("admins", {})[str(user_id)] = {
                        "expires": current_time + timedelta(days=days),
                        "activated": current_time
                    }
                    data.setdefault("admin_data", {}).setdefault(str(user_id), {
                        "smtp": [], "active_senders": [], "recipients": []
                    })
                    save_data(data)
                    logger.info("Admin %s added from dashboard for %s days", user_id, days)
                    self._send_json(200, {"ok": True, "message": "ادمین اضافه شد", "days": days})
                    return

                if action == "remove":
                    if user_id in OWNER_IDS:
                        self._send_json(400, {"ok": False, "error": "owner_cannot_be_removed"})
                        return
                    data = load_data()
                    data.setdefault("admins", {}).pop(str(user_id), None)
                    save_data(data)
                    logger.info("Admin %s removed from dashboard", user_id)
                    self._send_json(200, {"ok": True, "message": "ادمین حذف شد"})
                    return

                self._send_json(400, {"ok": False, "error": "action_invalid"})
                return

            if parsed.path == "/api/channels":
                action = payload.get("action")
                channel = str(payload.get("channel", "")).strip()
                if not channel:
                    self._send_json(400, {"ok": False, "error": "channel_empty"})
                    return
                if not channel.startswith("@"):
                    channel = "@" + channel
                data = load_data()
                channels = data.setdefault("force_channels", [])

                if action == "add":
                    if channel not in channels:
                        channels.append(channel)
                    save_data(data)
                    logger.info("Force channel %s added from dashboard", channel)
                    self._send_json(200, {"ok": True, "message": "کانال اضافه شد"})
                    return

                if action == "remove":
                    data["force_channels"] = [x for x in channels if str(x) != channel]
                    save_data(data)
                    logger.info("Force channel %s removed from dashboard", channel)
                    self._send_json(200, {"ok": True, "message": "کانال حذف شد"})
                    return

                self._send_json(400, {"ok": False, "error": "action_invalid"})
                return

            self._send_json(404, {"error": "not_found"})
        except Exception as exc:
            logger.exception("Monitor POST error")
            try:
                self._send_json(500, {"error": str(exc)[:180]})
            except Exception:
                pass

    def log_message(self, format, *args):
        return

def start_monitor_server():
    if not MONITOR_TOKEN:
        logger.warning("MONITOR_TOKEN is not configured; monitoring API is disabled.")
        return None

    try:
        server = ThreadingHTTPServer(("0.0.0.0", MONITOR_PORT), MonitorHandler)
        thread = threading.Thread(
            target=server.serve_forever,
            name="monitor-http",
            daemon=True
        )
        thread.start()
        logger.info("Monitoring API started on port %s", MONITOR_PORT)
        return server
    except Exception:
        logger.exception("Monitoring API could not start; Telegram bot will continue.")
        return None


async def main():
    global bot, bot_instance, BOT_STARTED_AT, MONITOR_SERVER, BOT_LOOP, BOT_PROCESSING_ENABLED
    BOT_LOOP = asyncio.get_running_loop()
    persisted = load_data()
    BOT_PROCESSING_ENABLED = persisted.get("bot_status", "on") != "off"

    # Register handlers before connecting so no update is missed during startup.
    bot = TelegramClient(StringSession(), API_ID, API_HASH, receive_updates=True)
    bot_instance = bot
    bot.add_event_handler(
        start_handler,
        events.NewMessage(incoming=True, pattern=r'^/start(?:@\w+)?(?:\s+(.+))?$')
    )
    bot.add_event_handler(callback_handler, events.CallbackQuery())
    bot.add_event_handler(
        message_handler,
        events.NewMessage(
            incoming=True,
            func=lambda e: e.is_private and bool(e.text) and not e.text.startswith('/')
        )
    )
    logger.info("Telegram event handlers registered")

    await bot.start(bot_token=BOT_TOKEN)
    me = await bot.get_me()
    if not getattr(me, "bot", False):
        raise RuntimeError("BOT_TOKEN authenticated as a non-bot Telegram account")
    logger.info("Telegram bot identity verified: @%s (id=%s)", me.username or "unknown", me.id)

    BOT_STARTED_AT = datetime.now(pytz.UTC)
    MONITOR_SERVER = start_monitor_server()
    logger.info("Bot started; processing_enabled=%s", BOT_PROCESSING_ENABLED)

    # Process any updates that arrived before the event loop became fully ready.
    try:
        await bot.catch_up()
        logger.info("Telegram update catch-up completed")
    except Exception:
        logger.exception("Telegram update catch-up failed; continuing with live updates")

    logger.info("SHIKH REPORTER is running...")
    try:
        await bot.run_until_disconnected()
    finally:
        if MONITOR_SERVER is not None:
            try:
                MONITOR_SERVER.shutdown()
            except Exception:
                pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by process signal")
    except Exception:
        logger.exception("FATAL: bot process stopped because of an unhandled exception")
        raise
)
    )
    bot.add_event_handler(callback_handler, events.CallbackQuery())
    bot.add_event_handler(
        message_handler,
        events.NewMessage(incoming=True, func=lambda e: e.is_private and bool(e.text) and not e.text.startswith('/'))
    )
    logger.info("Telegram event handlers registered")

    await bot.start(bot_token=BOT_TOKEN)
    me = await bot.get_me()
    if not getattr(me, "bot", False):
        raise RuntimeError("BOT_TOKEN authenticated as a non-bot Telegram account")
    logger.info("Telegram bot identity verified: @%s (id=%s)", me.username or "unknown", me.id)

    BOT_STARTED_AT = datetime.now(pytz.UTC)
    MONITOR_SERVER = start_monitor_server()
    logger.info("Bot started; processing_enabled=%s", BOT_PROCESSING_ENABLED)

    # Process any updates that arrived before the event loop became fully ready.
    try:
        await bot.catch_up()
        logger.info("Telegram update catch-up completed")
    except Exception:
        logger.exception("Telegram update catch-up failed; continuing with live updates")

    logger.info("SHIKH REPORTER is running...")
    try:
        await bot.run_until_disconnected()
    finally:
        if MONITOR_SERVER is not None:
            try:
                MONITOR_SERVER.shutdown()
            except Exception:
                pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by process signal")
    except Exception:
        logger.exception("FATAL: bot process stopped because of an unhandled exception")
        raise
