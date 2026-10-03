import os
import asyncio
import smtplib
import json
import logging
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
BOT_SESSION_PATH = os.path.join(DATA_DIR, "bot_session")

os.makedirs(ADMIN_SESSIONS_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(DATA_DIR, "bot.log"),
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger(__name__)

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
    "user_lang": {}
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
                info["expires"] = datetime.fromisoformat(info["expires"])
            if isinstance(info.get("activated"), str):
                info["activated"] = datetime.fromisoformat(info["activated"])
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
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
    except:
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
        return expires > now
    except:
        return False

def can_telegram_reporter(user_id):
    return is_owner(user_id) or is_admin(user_id)

def get_user_lang(user_id):
    data = load_data()
    return data.get("user_lang", {}).get(str(user_id), None)

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
        Button.inline("🚫 ریپورت کانال/گروه" if lang== "fa" else "🚫 REPORT CHANNEL/GROUP", "tg_report", style="danger"),
        Button.inline("📝 ریپورت پست" if lang== "fa" else "📝 REPORT POST", "tg_report_post", style="danger")
    ])
    kb.append([
        Button.inline("👤 ریپورت پروفایل" if lang== "fa" else "👤 REPORT PROFILE", "tg_report_profile", style="danger"),
        Button.inline("🤖 ریپورت ربات" if lang== "fa" else "🤖 REPORT BOT", "tg_report_bot", style="danger")
    ])
    kb.append([
        Button.inline("👤 ریپورت اکانت" if lang== "fa" else "👤 REPORT ACCOUNT", "tg_report_account", style="danger"),
        Button.inline("📋 ریپورت دستی" if lang== "fa" else "📋 MANUAL REPORT", "tg_manual_report", style="primary")
    ])
    if is_own:
        kb.append([
            Button.inline("⚙️ مدیریت اکانت‌ها" if lang== "fa" else "⚙️ MANAGE ACCOUNTS", "tg_manage_acc", style="primary"),
            Button.inline("📊 وضعیت سشن‌ها" if lang== "fa" else "📊 SESSION STATUS", "tg_session_status", style="primary")
        ])
    kb.append([Button.inline("🔙 بازگشت به منوی اصلی" if lang== "fa" else "🔙 BACK TO MAIN", "back_main", style="primary")])
    return kb

def reason_keyboard():
    return [
        [Button.inline("🚫 Spam", "reason_1"), Button.inline("❌ Fake", "reason_2")],
        [Button.inline("🔪 Violence", "reason_3"), Button.inline("🔞 Porn", "reason_4")],
        [Button.inline("👶 Child Abuse", "reason_5"), Button.inline("©️ Copyright", "reason_6")],
        [Button.inline("📋 Personal Details", "reason_7"), Button.inline("📝 Other", "reason_8")],
        [Button.inline("💸 Scam", "reason_9")]
    ]

def is_subscribed_to_force_channels(client, user_id, force_channels):
    return True

async def get_all_users():
    data = load_data()
    return data.get("users", [])

async def is_admin_panel_access(user_id):
    return is_owner(user_id) or is_admin(user_id)

def add_user(user_id):
    data = load_data()
    if user_id not in data["users"]:
        data["users"].append(user_id)
        save_data(data)

def add_admin(user_id, days):
    data = load_data()
    expires = datetime.now(pytz.timezone('Asia/Tehran')) + timedelta(days=days)
    activated = datetime.now(pytz.timezone('Asia/Tehran'))
    data["admins"][str(user_id)] = {
        "activated": activated,
        "expires": expires
    }
    data.setdefault("admin_data", {}).setdefault(str(user_id), {
        "smtp": [],
        "active_senders": [],
        "recipients": []
    })
    save_data(data)

async def remove_admin(user_id):
    data = load_data()
    data.get("admins", {}).pop(str(user_id), None)
    data.get("admin_data", {}).pop(str(user_id), None)
    save_data(data)

async def broadcast_message(client, message):
    data = load_data()
    users = data.get("users", [])
    total = len(users)
    sent = 0
    blocked = 0
    failed = 0
    for i, uid in enumerate(users):
        try:
            await client.send_message(uid, message)
            sent += 1
        except errors.UserIsBlockedError:
            blocked += 1
        except:
            failed += 1
        await asyncio.sleep(0.2)
    return total, sent, blocked, failed

async def check_limits():
    data = load_data()
    tehran = pytz.timezone('Asia/Tehran')
    now = datetime.now(tehran)
    today = now.strftime("%Y-%m-%d")
    week = now.strftime("%Y-W%W")
    if data.get("today_date") != today:
        data["today_date"] = today
        data["send_today"] = 0
    if data.get("week_number") != week:
        data["week_number"] = week
        data["send_week"] = 0
    save_data(data)

async def scheduled_backup():
    while True:
        try:
            await asyncio.sleep(29 * 24 * 60 * 60)
            data = load_data()
            msg = "💾 Backup Data

" + json.dumps(data, ensure_ascii=False, indent=2)
            for oid in OWNER_IDS:
                try:
                    await bot_instance.send_message(oid, msg[:4096])
                except:
                    pass
        except asyncio.CancelledError:
            raise
        except:
            await asyncio.sleep(60)

async def notify_startup():
    for oid in OWNER_IDS:
        try:
            await bot_instance.send_message(
                oid,
                "✅ SHIKH REPORTER online.
"
                f"⏱️ Started: {datetime.now(pytz.timezone('Asia/Tehran')).strftime('%Y-%m-%d %H:%M:%S')}"
            )
        except:
            pass

async def execute_email_send(event, state, user_id, lang):
    data = load_data()
    admin_data = data.get("admin_data", {}).get(str(user_id), {})
    smtp_accounts = admin_data.get("smtp", [])
    active_senders = admin_data.get("active_senders", [])
    recipients = admin_data.get("recipients", [])
    if not smtp_accounts or not active_senders or not recipients:
        await event.reply("❌ SMTP/فرستنده/گیرنده کافی نیست" if lang == "fa" else "❌ SMTP/sender/recipient data missing")
        return
    subject = state.get("email_subject", "Report")
    body = state.get("email_body", "")
    successful = 0
    failed = 0
    for sender_index in active_senders:
        try:
            sender = smtp_accounts[sender_index]
            for recipient in recipients:
                ok, err = await asyncio.to_thread(
                    send_email_sync,
                    sender["email"],
                    sender["password"],
                    recipient,
                    subject,
                    body
                )
                if ok:
                    successful += 1
                else:
                    failed += 1
        except Exception:
            failed += 1
    data["send_today"] = data.get("send_today", 0) + successful
    data["send_week"] = data.get("send_week", 0) + successful
    save_data(data)
    await event.reply(
        (f"✅ ارسال تمام شد\n📤 موفق: {successful}\n❌ ناموفق: {failed}")
        if lang == "fa" else
        (f"✅ Sending finished\n📤 Success: {successful}\n❌ Failed: {failed}")
    )

async def start_handler(event):
    user_id = event.sender_id
    data = load_data()
    add_user(user_id)

    if is_blocked(user_id):
        await event.reply("🚫 شما مسدود شده‌اید")
        return

    lang = get_user_lang(user_id)
    if not lang:
        lang = "fa"
        set_user_lang(user_id, lang)

    if not (is_owner(user_id) or is_admin(user_id)):
        await event.reply(
            "سلام 👋
این ربات فقط برای ادمین‌ها فعال است.
"
            "از مالک درخواست دسترسی کنید."
        )
        return

    await event.reply("🏠 منوی اصلی", buttons=main_menu_keyboard(user_id))

async def callback_handler(event):
    user_id = event.sender_id
    if is_blocked(user_id):
        return

    data = load_data()
    lang = get_user_lang(user_id) or "fa"
    payload = event.data.decode("utf-8")

    try:
        await event.answer()
    except:
        pass

    if payload == "back_main":
        await event.edit("🏠 منوی اصلی", buttons=main_menu_keyboard(user_id))
        return

    if payload == "change_lang":
        await event.edit("🌐 انتخاب زبان / Choose language", buttons=[
            [Button.inline("🇮🇷 فارسی", "lang_fa"), Button.inline("🇬🇧 English", "lang_en")]
        ])
        return

    if payload in ("lang_fa", "lang_en"):
        set_user_lang(user_id, "fa" if payload == "lang_fa" else "en")
        await event.edit("✅ زبان تغییر کرد", buttons=main_menu_keyboard(user_id))
        return

    if payload == "menu_email":
        if not can_telegram_reporter(user_id):
            return
        await event.edit("📧 منوی ایمیل", buttons=email_menu_keyboard(user_id))
        return

    if payload == "menu_telegram":
        if not can_telegram_reporter(user_id):
            return
        await event.edit("🚫 منوی تلگرام ریپورتر", buttons=telegram_menu_keyboard(user_id))
        return

    if payload == "owner_panel":
        if not is_owner(user_id):
            return
        await event.edit("👑 پنل مالک", buttons=owner_panel_keyboard(user_id))
        return

    if payload == "add_admin":
        if not is_owner(user_id):
            return
        USER_STATE[user_id] = {"step": "add_admin"}
        await event.edit("🆔 آیدی عددی ادمین را بفرستید")
        return

    if payload == "em_broadcast":
        if not is_owner(user_id):
            return
        USER_STATE[user_id] = {"step": "waiting_broadcast"}
        await event.edit("📢 متن پیام همگانی را ارسال کنید")
        return

    if payload == "em_msg_user":
        if not is_owner(user_id):
            return
        USER_STATE[user_id] = {"step": "waiting_msg_user_id"}
        await event.edit("🆔 آیدی کاربر را بفرستید")
        return

    if payload == "em_block":
        if not is_owner(user_id):
            return
        USER_STATE[user_id] = {"step": "waiting_block_id"}
        await event.edit("🆔 آیدی کاربر برای بلاک")
        return

    if payload == "em_unblock":
        if not is_owner(user_id):
            return
        USER_STATE[user_id] = {"step": "waiting_unblock_id"}
        await event.edit("🆔 آیدی کاربر برای آنبلاک")
        return

    if payload == "em_force_channel":
        if not is_owner(user_id):
            return
        await event.edit("📢 مدیریت کانال اجباری", buttons=force_channel_keyboard(user_id))
        return

    if payload == "em_back":
        await event.edit("👑 پنل مالک", buttons=owner_panel_keyboard(user_id))
        return

    if payload == "em_fc_add":
        if not is_owner(user_id):
            return
        USER_STATE[user_id] = {"step": "waiting_fc_add"}
        await event.edit("📢 یوزرنیم کانال را بفرستید")
        return

    if payload == "em_fc_remove":
        if not is_owner(user_id):
            return
        USER_STATE[user_id] = {"step": "waiting_fc_remove"}
        await event.edit("📢 یوزرنیم کانال برای حذف")
        return

    if payload == "em_fc_list":
        if not is_owner(user_id):
            return
        channels = load_data().get("force_channels", [])
        await event.edit(
            "📋 کانال‌ها:\n" + ("\n".join(channels) if channels else "لیست خالی"),
            buttons=force_channel_keyboard(user_id)
        )
        return

    if payload == "em_smtp_add":
        if not can_telegram_reporter(user_id):
            return
        USER_STATE[user_id] = {"step": "smtp_email"}
        await event.edit("📧 ایمیل Gmail را بفرستید")
        return

    if payload == "em_smtp_list":
        if not can_telegram_reporter(user_id):
            return
        admin_data = get_admin_data(user_id)
        smtp = admin_data.get("smtp", [])
        if not smtp:
            await event.edit("📋 لیست SMTP خالی است", buttons=email_menu_keyboard(user_id))
            return
        lines = []
        for i, s in enumerate(smtp, 1):
            lines.append(f"{i}. {s.get('email', 'unknown')}")
        await event.edit("📋 SMTP:\n" + "\n".join(lines), buttons=email_menu_keyboard(user_id))
        return

    if payload == "em_activate":
        if not can_telegram_reporter(user_id):
            return
        USER_STATE[user_id] = {"step": "activate_sender"}
        await event.edit("🔢 شماره SMTP برای فعال‌سازی را بفرستید")
        return

    if payload == "em_single_send":
        if not can_telegram_reporter(user_id):
            return
        USER_STATE[user_id] = {"step": "email_subject"}
        await event.edit("📝 موضوع ایمیل را بفرستید")
        return

    if payload == "em_bulk_send":
        if not can_telegram_reporter(user_id):
            return
        USER_STATE[user_id] = {"step": "email_subject_bulk"}
        await event.edit("📝 موضوع ایمیل گروهی را بفرستید")
        return

    if payload == "em_recips":
        if not can_telegram_reporter(user_id):
            return
        recipients = get_admin_data(user_id).get("recipients", [])
        await event.edit(
            "👥 گیرنده‌ها:\n" + ("\n".join(recipients) if recipients else "لیست خالی"),
            buttons=email_menu_keyboard(user_id)
        )
        return

    if payload == "em_add_recip":
        if not can_telegram_reporter(user_id):
            return
        USER_STATE[user_id] = {"step": "add_recipient"}
        await event.edit("📧 ایمیل گیرنده را بفرستید")
        return

    if payload == "em_clear_recip":
        if not can_telegram_reporter(user_id):
            return
        data["admin_data"].setdefault(str(user_id), {"smtp": [], "active_senders": [], "recipients": []})
        data["admin_data"][str(user_id)]["recipients"] = []
        save_data(data)
        await event.edit("✅ گیرنده‌ها پاک شدند", buttons=email_menu_keyboard(user_id))
        return

    if payload == "em_stats":
        if not can_telegram_reporter(user_id):
            return
        await check_limits()
        stats = load_data()
        await event.edit(
            f"📊 امروز: {stats.get('send_today', 0)}\n"
            f"📅 این هفته: {stats.get('send_week', 0)}",
            buttons=email_menu_keyboard(user_id)
        )
        return

    if payload == "em_agency":
        if not can_telegram_reporter(user_id):
            return
        await event.edit("ℹ️ بخش نمایندگی در این نسخه نمایشی است.", buttons=email_menu_keyboard(user_id))
        return

    if payload == "tg_manage_acc":
        if not is_owner(user_id):
            return
        USER_STATE[user_id] = {"step": "select_admin"}
        await event.edit("🆔 آیدی ادمین هدف را بفرستید (برای خودتان 0)")
        return

    if payload == "tg_session_status":
        if not is_owner(user_id):
            return
        sessions = get_user_sessions(user_id, force_refresh=True)
        if not sessions:
            await event.edit("📋 هیچ سشنی ثبت نشده است", buttons=telegram_menu_keyboard(user_id))
            return
        lines = []
        for s in sessions:
            status = await check_session_status(s)
            lines.append(f"{s[0]}/{s[1]}: {status}")
        await event.edit("📊 وضعیت سشن‌ها:\n\n" + "\n".join(lines), buttons=telegram_menu_keyboard(user_id))
        return

    if payload.startswith("tg_report"):
        if not can_telegram_reporter(user_id):
            return
        op_type = {
            "tg_report": "report",
            "tg_report_post": "report_post",
            "tg_report_profile": "report_profile",
            "tg_report_bot": "report_bot",
            "tg_report_account": "report_account",
            "tg_manual_report": "manual_report"
        }.get(payload)
        if not op_type:
            return
        sessions = get_user_sessions(user_id, force_refresh=True)
        if not sessions:
            await event.edit("❌ ابتدا حداقل یک اکانت اضافه کنید")
            return
        USER_STATE[user_id] = {
            "step": "count",
            "type": op_type,
            "sessions": sessions
        }
        await event.edit(f"👥 تعداد اکانت‌ها: {len(sessions)}\nچند اکانت استفاده شود؟")
        return

    if payload.startswith("reason_"):
        if not can_telegram_reporter(user_id):
            return
        state = USER_STATE.get(user_id)
        if not state:
            return
        reason_key = payload.split("_", 1)[1]
        state["reason_key"] = reason_key
        op_type = state.get("type")
        if op_type == "report_post":
            state["step"] = "count_per_account"
            await event.edit("🔢 چند ریپورت به ازای هر اکانت؟ (1-50)")
        else:
            state["step"] = "count_per_account"
            await event.edit("🔢 چند ریپورت به ازای هر اکانت؟ (1-50)")
        return

async def message_handler(event):
    user_id = event.sender_id
    text = event.raw_text.strip()
    lang = get_user_lang(user_id) or "fa"

    if is_blocked(user_id):
        return

    add_user(user_id)

    state = USER_STATE.get(user_id)
    if not state:
        return

    step = state.get("step")

    if step == "add_admin":
        if not is_owner(user_id):
            USER_STATE.pop(user_id, None)
            return
        if not text.isdigit():
            await event.reply("❌ آیدی نامعتبر")
            return
        target = int(text)
        USER_STATE[user_id] = {"step": "add_admin_days", "target": target}
        await event.reply("⏳ چند روز دسترسی؟")
        return

    if step == "add_admin_days":
        if not is_owner(user_id):
            USER_STATE.pop(user_id, None)
            return
        try:
            days = int(text)
            if days <= 0 or days > 3650:
                raise ValueError
        except ValueError:
            await event.reply("❌ تعداد روز باید بین 1 تا 3650 باشد")
            return
        target = state["target"]
        add_admin(target, days)
        await event.reply("✅ ادمین اضافه شد")
        USER_STATE.pop(user_id, None)
        return

    if step == "smtp_email":
        if not can_telegram_reporter(user_id):
            USER_STATE.pop(user_id, None)
            return
        state["email"] = text
        state["step"] = "smtp_password"
        await event.reply("🔐 App Password جیمیل را بفرستید")
        return

    if step == "smtp_password":
        if not can_telegram_reporter(user_id):
            USER_STATE.pop(user_id, None)
            return
        ok = await test_smtp_connection(state["email"], text)
        if not ok:
            await event.reply("❌ اتصال SMTP ناموفق بود")
            USER_STATE.pop(user_id, None)
            return
        data_db = load_data()
        admin_data = data_db["admin_data"].setdefault(str(user_id), {"smtp": [], "active_senders": [], "recipients": []})
        admin_data["smtp"].append({"email": state["email"], "password": text})
        save_data(data_db)
        await event.reply("✅ SMTP اضافه شد")
        USER_STATE.pop(user_id, None)
        return

    if step == "activate_sender":
        if not can_telegram_reporter(user_id):
            USER_STATE.pop(user_id, None)
            return
        try:
            index = int(text) - 1
            admin_data = get_admin_data(user_id)
            if index < 0 or index >= len(admin_data.get("smtp", [])):
                raise ValueError
            data_db = load_data()
            data_db["admin_data"][str(user_id)]["active_senders"] = [index]
            save_data(data_db)
            await event.reply("✅ فرستنده فعال شد")
        except ValueError:
            await event.reply("❌ شماره SMTP نامعتبر است")
        USER_STATE.pop(user_id, None)
        return

    if step == "add_recipient":
        if not can_telegram_reporter(user_id):
            USER_STATE.pop(user_id, None)
            return
        data_db = load_data()
        admin_data = data_db["admin_data"].setdefault(str(user_id), {"smtp": [], "active_senders": [], "recipients": []})
        if text not in admin_data["recipients"]:
            admin_data["recipients"].append(text)
        save_data(data_db)
        await event.reply("✅ گیرنده اضافه شد")
        USER_STATE.pop(user_id, None)
        return

    if step in ("email_subject", "email_subject_bulk"):
        if not can_telegram_reporter(user_id):
            USER_STATE.pop(user_id, None)
            return
        state["email_subject"] = text
        state["step"] = "email_body"
        await event.reply("📝 متن ایمیل را بفرستید")
        return

    if step == "email_body":
        if not can_telegram_reporter(user_id):
            USER_STATE.pop(user_id, None)
            return
        state["email_body"] = text
        await execute_email_send(event, state, user_id, lang)
        USER_STATE.pop(user_id, None)
        return

    if step == "waiting_broadcast":
        if not is_owner(user_id):
            USER_STATE.pop(user_id, None)
            return
        total, sent, blocked, failed = await broadcast_message(event.client, text)
        await event.reply(
            f"✅ Broadcast completed\n👥 Total: {total}\n📤 Sent: {sent}\n🚫 Blocked: {blocked}\n❌ Failed: {failed}"
        )
        USER_STATE.pop(user_id, None)
        return

    if step == "waiting_msg_user_id":
        if not is_owner(user_id):
            USER_STATE.pop(user_id, None)
            return
        if not text.isdigit():
            await event.reply("❌ فقط آیدی عددی")
            return
        state["target_user"] = int(text)
        state["step"] = "waiting_msg_user_text"
        await event.reply("✉️ متن پیام را ارسال کنید")
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
            await event.reply("✅ پیام ارسال شد")
        except:
            await event.reply("❌ ارسال ناموفق")
        USER_STATE.pop(user_id, None)
        return

    if step == "waiting_block_id":
        if not is_owner(user_id):
            USER_STATE.pop(user_id, None)
            return
        if not text.isdigit():
            await event.reply("❌ فقط آیدی عددی")
            return
        data_db = load_data()
        data_db.setdefault("blocked", [])
        target = int(text)
        if target not in data_db["blocked"]:
            data_db["blocked"].append(target)
            save_data(data_db)
        await event.reply("🚫 کاربر بلاک شد")
        USER_STATE.pop(user_id, None)
        return

    if step == "waiting_unblock_id":
        if not is_owner(user_id):
            USER_STATE.pop(user_id, None)
            return
        if not text.isdigit():
            await event.reply("❌ فقط آیدی عددی")
            return
        data_db = load_data()
        data_db.setdefault("blocked", [])
        target = int(text)
        if target in data_db["blocked"]:
            data_db["blocked"].remove(target)
            save_data(data_db)
        await event.reply("✅ کاربر آنبلاک شد")
        USER_STATE.pop(user_id, None)
        return

    if step == "waiting_fc_add":
        if not is_owner(user_id):
            USER_STATE.pop(user_id, None)
            return
        if not text.strip():
            await event.reply("❌ ورودی نامعتبر")
            return
        channel = text.strip()
        if not channel.startswith("@"):
            channel = "@" + channel
        data_db = load_data()
        data_db.setdefault("force_channels", [])
        if channel not in data_db["force_channels"]:
            data_db["force_channels"].append(channel)
            save_data(data_db)
        await event.reply("✅ کانال اضافه شد")
        USER_STATE.pop(user_id, None)
        return

    if step == "waiting_fc_remove":
        if not is_owner(user_id):
            USER_STATE.pop(user_id, None)
            return
        if not text.strip():
            await event.reply("❌ ورودی نامعتبر")
            return
        channel = text.strip()
        if not channel.startswith("@"):
            channel = "@" + channel
        data_db = load_data()
        data_db.setdefault("force_channels", [])
        if channel in data_db["force_channels"]:
            data_db["force_channels"].remove(channel)
            save_data(data_db)
        await event.reply("✅ کانال حذف شد")
        USER_STATE.pop(user_id, None)
        return

async def telegram_message_handler(event, state, text, user_id, lang):
    step = state.get("step")
    data_db = load_data()

    if step == "select_admin":
        if not text.strip().isdigit() and text != "0":
            await event.reply("❌ آیدی نامعتبر")
            return
        if text == "0":
            target_admin = user_id
        else:
            target_admin = int(text)
        if target_admin != user_id and not is_admin(target_admin) and not is_owner(target_admin):
            await event.reply("❌ ادمین یافت نشد")
            return
        state["target_admin"] = target_admin
        state["step"] = "phone"
        await event.reply("📱 شماره تلفن با + را وارد کنید")
        return

    if step == "delete_select_admin":
        if not text.strip().isdigit():
            await event.reply("❌ آیدی نامعتبر")
            return
        target_admin = int(text)
        if target_admin != user_id and not is_admin(target_admin) and not is_owner(target_admin):
            await event.reply("❌ ادمین یافت نشد")
            return
        state["target_admin"] = target_admin
        state["step"] = "delete_phone"
        await event.reply("📱 شماره تلفن برای حذف را وارد کنید")
        return

    if step == "phone":
        if not await validate_phone_number(text):
            await event.reply("❌ شماره نامعتبر است")
            return
        state["phone"] = text
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        try:
            await client.send_code_request(text)
            state["client"] = client
            state["step"] = "code"
            await event.reply("✅ کد ارسال شد. کد را وارد کنید")
        except Exception as e:
            await event.reply(f"❌ خطا: {str(e)[:100]}")
            await client.disconnect()
            USER_STATE.pop(user_id, None)
        return

    if step == "code":
        if len(text) < 4:
            await event.reply("❌ کد نامعتبر")
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
            await event.reply("🔐 رمز دو مرحله‌ای را وارد کنید")
        except errors.PhoneCodeInvalidError:
            await event.reply("❌ کد اشتباه است")
        except errors.PhoneCodeExpiredError:
            await event.reply("❌ کد منقضی شده")
            await client.disconnect()
            USER_STATE.pop(user_id, None)
        except Exception as e:
            await event.reply(f"❌ خطا: {str(e)[:100]}")
            await client.disconnect()
            USER_STATE.pop(user_id, None)
        return

    if step == "password":
        if not text:
            await event.reply("❌ رمز نامعتبر")
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
            await event.reply("❌ رمز اشتباه است")
        except Exception as e:
            await event.reply(f"❌ خطا: {str(e)[:100]}")
            await client.disconnect()
            USER_STATE.pop(user_id, None)
        return

    if step == "delete_phone":
        if not text.startswith('+'):
            await event.reply("❌ شماره باید با + شروع شود")
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
            await event.reply(f"✅ اکانت {text} حذف شد")
        else:
            await event.reply("❌ اکانتی یافت نشد")
        USER_STATE.pop(user_id, None)
        return

    if step == "count":
        try:
            count = int(text)
            sessions = state["sessions"]
            if count < 1 or count > len(sessions):
                await event.reply(f"❌ عدد بین 1 تا {len(sessions)}")
                return
            state["count"] = count
            state["selected_sessions"] = sessions[:count]
            op_type = state.get("type")
            if op_type in ["report_post"]:
                state["step"] = "post_links"
                await event.reply("🔗 لینک پست‌ها را ارسال کنید (1 تا 6 لینک)")
            else:
                state["step"] = "target"
                await event.reply("🔗 لینک/یوزرنیم هدف را وارد کنید")
        except ValueError:
            await event.reply("❌ عدد وارد کنید")
        return

    if step == "post_links":
        post_links = [link.strip() for link in text.split('\n') if link.strip()]
        if not post_links or len(post_links) > 6:
            await event.reply("❌ بین 1 تا 6 لینک")
            return
        for link in post_links:
            if not await validate_post_link(link):
                await event.reply(f"❌ لینک نامعتبر: {link}")
                return
        state["post_links"] = post_links
        state["step"] = "select_reason"
        await event.reply("📝 دلیل ریپورت را انتخاب کنید:", buttons=reason_keyboard())
        return

    if step == "target":
        target = text.strip()
        if not target:
            await event.reply("❌ خالی نباشد")
            return
        state["target"] = target
        if state.get("type") == "manual_report":
            state["step"] = "custom_reason"
            await event.reply("📝 متن گزارش سفارشی (حداقل 4 خط)")
        else:
            state["step"] = "select_reason"
            await event.reply("📝 دلیل ریپورت را انتخاب کنید:", buttons=reason_keyboard())
        return

    if step == "count_per_account":
        try:
            cnt = int(text)
            if cnt < 1 or cnt > 50:
                await event.reply("❌ عدد بین 1 تا 50")
                return
            state["count_per_account"] = cnt
            state["step"] = "custom_reason"
            await event.reply("📝 متن دلخواه (یا /skip)")
        except ValueError:
            await event.reply("❌ عدد وارد کنید")
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

async def main():
    global bot_instance
    bot_instance = TelegramClient(BOT_SESSION_PATH, API_ID, API_HASH)
    await bot_instance.start(bot_token=BOT_TOKEN)
    logger.info("Bot started")

    bot_instance.add_event_handler(start_handler, events.NewMessage(pattern=r'/start(?: (.+))?'))
    bot_instance.add_event_handler(callback_handler, events.CallbackQuery())
    bot_instance.add_event_handler(message_handler, events.NewMessage(func=lambda e: e.is_private and not e.text.startswith('/')))

    logger.info("SHIKH REPORTER is running...")
    asyncio.create_task(scheduled_backup())
    await notify_startup()
    await bot_instance.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
