import os
import asyncio
import smtplib
import json
import logging
import random
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import pytz
from telethon import TelegramClient, events, Button, errors
from telethon.sessions import StringSession
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.messages import ReportRequest, CheckChatInviteRequest
from telethon.tl.types import (
    InputReportReasonSpam,
    InputReportReasonViolence,
    InputReportReasonPornography,
    InputReportReasonFake,
    InputReportReasonChildAbuse,
    InputReportReasonCopyright,
    InputReportReasonPersonalDetails,
    InputReportReasonOther,
    InputReportReasonIllegalDrugs,
    InputPeerChannel,
    InputPeerChat,
    InputPeerUser,
    InputPeerEmpty,
    PeerChannel,
    PeerChat,
    PeerUser
)

API_ID = 27786760
API_HASH = "572e48bb7059438ed4e04c572e251f98"
BOT_TOKEN = "8648562521:AAHtF7Lf7naGFUODcck8YYx8TaFaG-cN-no"
SUPPORT_USERNAME = "@Zyrex_OR"
OWNER_IDS = [8806549778,7172066915,7248348866]

# ====== گروه گزارشات ======
REPORT_GROUP_ID = -1004497758593

DATA_FILE = "datadfasr.json"
ADMIN_SESSIONS_DIR = "admin_sessiorns1"
ACTIVE_OPERATIONS = {}

os.makedirs(ADMIN_SESSIONS_DIR, exist_ok=True)

# تنظیم لاگینگ
handler = logging.FileHandler('botreport.log', encoding='utf-8')
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[handler]
)

REPORT_REASONS = {
    '1': ('🚫 Spam', InputReportReasonSpam(), 'This content is spam and violates Telegram policies'),
    '2': ('❌ Fake', InputReportReasonFake(), 'This content is fake and misleading'),
    '3': ('🔪 Violence', InputReportReasonViolence(), 'This content promotes violence'),
    '4': ('🔞 Pornography', InputReportReasonPornography(), 'This content contains illegal pornography'),
    '5': ('👶 Child Abuse', InputReportReasonChildAbuse(), 'This content involves child abuse'),
    '6': ('©️ Copyright', InputReportReasonCopyright(), 'This content violates copyright laws'),
    '7': ('📋 Personal Details', InputReportReasonPersonalDetails(), 'This content exposes personal details without consent'),
    '8': ('📝 Other', InputReportReasonOther(), 'This content violates Telegram Terms of Service'),
    '9': ('💸 Scam', InputReportReasonOther(), 'This channel/post/user is involved in scam and fraud'),
    '10': ('💊 Drugs', InputReportReasonIllegalDrugs(), 'This content promotes illegal drugs')
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
    "shared_sessions": [],
    "last_report_time": {},
    "total_reports": 0,
    "support_tickets": {},
    "active_report_group_msg": {}
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
    safe_list("shared_sessions")
    safe_dict("admin_data")
    safe_dict("admins")
    safe_dict("user_lang")
    safe_dict("last_report_time")
    safe_dict("support_tickets")
    safe_dict("active_report_group_msg")
    
    if not isinstance(data.get("send_today"), int):
        data["send_today"] = 0
    if not isinstance(data.get("send_week"), int):
        data["send_week"] = 0
    if not isinstance(data.get("total_reports"), int):
        data["total_reports"] = 0
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
                try:
                    info["expires"] = datetime.fromisoformat(info["expires"])
                except:
                    info["expires"] = datetime.now(pytz.timezone('Asia/Tehran'))
            if isinstance(info.get("activated"), str):
                try:
                    info["activated"] = datetime.fromisoformat(info["activated"])
                except:
                    info["activated"] = datetime.now(pytz.timezone('Asia/Tehran'))
    
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
        if expires.tzinfo is None:
            expires = tehran.localize(expires)
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

def get_all_sessions():
    sessions = []
    if os.path.exists(ADMIN_SESSIONS_DIR):
        for admin_id_str in os.listdir(ADMIN_SESSIONS_DIR):
            admin_dir = os.path.join(ADMIN_SESSIONS_DIR, admin_id_str)
            if os.path.isdir(admin_dir):
                for f in os.listdir(admin_dir):
                    if f.endswith('.session'):
                        sessions.append((admin_id_str, f))
    return sessions

def get_user_sessions(user_id, force_refresh=False):
    cache_attr = "session_cache_" + str(user_id)
    if not hasattr(get_user_sessions, cache_attr) or force_refresh:
        sessions = get_all_sessions()
        unique_sessions = []
        seen = set()
        for admin_id, filename in sessions:
            key = admin_id + ":" + filename
            if key not in seen:
                seen.add(key)
                unique_sessions.append((admin_id, filename))
        setattr(get_user_sessions, cache_attr, unique_sessions)
    return getattr(get_user_sessions, cache_attr)

def clear_user_cache(user_id=None):
    if user_id:
        cache_attr = "session_cache_" + str(user_id)
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
    server = None
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["From"] = sender_email
        msg["To"] = to_email
        msg["Subject"] = subject
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, to_email, msg.as_string())
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        if server:
            try:
                server.quit()
            except:
                pass

def calculate_estimated_time(num_accounts, reports_per_account, targets_count=1, delay_seconds=5):
    total_reports = num_accounts * reports_per_account * targets_count
    total_time = total_reports * delay_seconds
    total_time += (num_accounts - 1) * targets_count * 3
    total_time += (targets_count - 1) * 2
    total_time += num_accounts * targets_count * 5
    return total_time

def format_time(seconds):
    if seconds < 60:
        return str(int(seconds)) + " ثانیه"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = int(seconds % 60)
        if secs > 0:
            return str(int(minutes)) + " دقیقه و " + str(secs) + " ثانیه"
        return str(int(minutes)) + " دقیقه"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return str(int(hours)) + " ساعت و " + str(int(minutes)) + " دقیقه"
        return str(int(hours)) + " ساعت"

async def resolve_entity(client, target, op_type="report"):
    try:
        target = target.strip()
        
        if target.startswith("@"):
            try:
                entity = await client.get_entity(target)
                return entity
            except:
                try:
                    entity = await client.get_input_entity(target)
                    return entity
                except:
                    return None
        
        if "t.me" in target or "telegram.me" in target:
            clean = target.replace("https://", "").replace("http://", "")
            clean = clean.replace("t.me/", "").replace("telegram.me/", "")
            
            if "/" in clean:
                parts = clean.split("/")
                channel_username = parts[0]
                try:
                    entity = await client.get_entity("@" + channel_username)
                    return entity
                except:
                    return None
            else:
                try:
                    entity = await client.get_entity("@" + clean)
                    return entity
                except:
                    return None
        
        if "joinchat" in target or "+" in target:
            try:
                result = await client(CheckChatInviteRequest(target))
                if result.chat:
                    return result.chat
            except:
                return None
        
        try:
            entity = await client.get_entity(target)
            return entity
        except:
            return None
            
    except Exception as e:
        logger.error("resolve_entity error: " + str(e))
        return None

async def perform_real_report(client, entity, reason, message, count=1, delay_seconds=5):
    successes = 0
    failures = 0
    
    if not entity:
        return 0, 1
    
    try:
        try:
            input_peer = await client.get_input_entity(entity)
        except:
            entity = await client.get_entity(entity)
            input_peer = await client.get_input_entity(entity)
        
        for i in range(count):
            try:
                result = await client(ReportPeerRequest(
                    peer=input_peer,
                    reason=reason,
                    message=message
                ))
                successes += 1
                logger.info("Report success: " + str(entity) + " - " + str(i+1))
                
            except errors.FloodWaitError as e:
                wait_time = min(e.seconds, 30)
                logger.warning("Flood wait: " + str(e.seconds) + "s, waiting " + str(wait_time) + "s")
                await asyncio.sleep(wait_time)
                try:
                    result = await client(ReportPeerRequest(
                        peer=input_peer,
                        reason=reason,
                        message=message
                    ))
                    successes += 1
                except:
                    failures += 1
                    
            except errors.ChatAdminRequiredError:
                failures += 1
                break
                
            except errors.PeerIdInvalidError:
                failures += 1
                break
                
            except Exception as e:
                logger.error("Report attempt " + str(i+1) + " failed: " + str(e))
                try:
                    await asyncio.sleep(2)
                    result = await client(ReportRequest(
                        peer=input_peer,
                        id=[],
                        reason=reason,
                        message=message
                    ))
                    successes += 1
                except:
                    failures += 1
            
            if i < count - 1:
                actual_delay = random.uniform(delay_seconds, delay_seconds + 1.5)
                await asyncio.sleep(actual_delay)
    
    except Exception as e:
        logger.error("perform_real_report error: " + str(e))
        failures += 1
    
    return successes, failures

async def join_channel_smart(client, entity):
    try:
        await client(JoinChannelRequest(entity))
        await asyncio.sleep(random.uniform(1, 3))
        return True
    except errors.UserAlreadyParticipantError:
        return True
    except errors.InviteRequestSentError:
        return True
    except errors.FloodWaitError as e:
        if e.seconds < 60:
            await asyncio.sleep(e.seconds)
            try:
                await client(JoinChannelRequest(entity))
                return True
            except:
                return False
        return False
    except:
        return False

async def validate_phone_number(phone):
    if not phone.startswith('+'):
        return False
    clean = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if len(clean) < 8 or len(clean) > 15:
        return False
    if not clean[1:].isdigit():
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
            Button.inline("🌐 تغییر زبان" if lang == "fa" else "🌐 Change Language", "change_lang", style="primary"),
            Button.inline("🎧 پشتیبانی" if lang == "fa" else "🎧 Support", "support_menu", style="primary")
        ]
    ]
    if is_owner(user_id):
        kb.append([Button.inline("👑 پنل مالک" if lang == "fa" else "👑 Owner Panel", "owner_panel", style="primary")])
        kb.append([Button.inline("➕ افزودن ادمین" if lang == "fa" else "➕ Add Admin", "add_admin", style="primary")])
    return kb

def owner_panel_keyboard(user_id):
    lang = get_user_lang(user_id) or "fa"
    return [
        [
            Button.inline("📢 پیام همگانی" if lang == "fa" else "📢 Broadcast", "em_broadcast", style="primary"),
            Button.inline("👤 پیام به کاربر" if lang == "fa" else "👤 Message User", "em_msg_user", style="primary")
        ],
        [
            Button.inline("🚫 بلاک کاربر" if lang == "fa" else "🚫 Block User", "em_block", style="primary"),
            Button.inline("✅ آنبلاک کاربر" if lang == "fa" else "✅ Unblock User", "em_unblock", style="primary")
        ],
        [
            Button.inline("➕ افزودن ادمین جدید" if lang == "fa" else "➕ Add New Admin", "add_admin", style="primary"),
            Button.inline("👑 افزودن مالک جدید" if lang == "fa" else "👑 Add New Owner", "add_owner", style="primary")
        ],
        [
            Button.inline("📋 لیست ادمین‌ها" if lang == "fa" else "📋 Admin List", "list_admins", style="primary"),
            Button.inline("👑 لیست مالکین" if lang == "fa" else "👑 Owner List", "list_owners", style="primary")
        ],
        [
            Button.inline("📢 مدیریت کانال اجباری" if lang == "fa" else "📢 Manage Force Channel", "em_force_channel", style="primary")
        ],
        [
            Button.inline("🔄 مدیریت اشتراک سشن‌ها" if lang == "fa" else "🔄 Manage Session Sharing", "em_manage_sharing", style="primary")
        ],
        [
            Button.inline("🎫 تیکت‌های پشتیبانی" if lang == "fa" else "🎫 Support Tickets", "owner_tickets", style="primary")
        ],
        [
            Button.inline("📊 آمار کلی ربات" if lang == "fa" else "📊 Bot Stats", "owner_stats", style="primary"),
            Button.inline("⚠️ کاربران بلاک‌شده" if lang == "fa" else "⚠️ Blocked Users", "owner_blocked_list", style="primary")
        ],
        [
            Button.inline("🗑 حذف ادمین" if lang == "fa" else "🗑 Remove Admin", "owner_remove_admin", style="primary"),
            Button.inline("📅 تمدید اشتراک ادمین" if lang == "fa" else "📅 Extend Admin", "owner_extend_admin", style="primary")
        ],
        [
            Button.inline("💾 بکاپ دیتا" if lang == "fa" else "💾 Backup Data", "owner_backup", style="primary"),
            Button.inline("🔄 ریست ریپورت‌ها" if lang == "fa" else "🔄 Reset Reports", "owner_reset_reports", style="primary")
        ],
        [Button.inline("🔙 بازگشت به منوی اصلی" if lang == "fa" else "🔙 Back to Main Menu", "back_main", style="primary")]
    ]

def email_menu_keyboard(user_id):
    lang = get_user_lang(user_id) or "fa"
    kb = []
    if lang == "fa":
        kb.append([
            Button.inline("➕ افزودن SMTP", "em_smtp_add", style="primary"),
            Button.inline("📋 لیست SMTP", "em_smtp_list", style="primary")
        ])
        kb.append([
            Button.inline("🟢 فعال‌سازی ارسال‌کننده", "em_activate", style="primary"),
            Button.inline("📧 ارسال تکی", "em_single_send", style="primary")
        ])
        kb.append([
            Button.inline("📨 ارسال گروهی", "em_bulk_send", style="primary"),
            Button.inline("👥 لیست گیرنده‌ها", "em_recips", style="primary")
        ])
        kb.append([
            Button.inline("➕ افزودن گیرنده", "em_add_recip", style="primary"),
            Button.inline("🗑 پاک‌کردن گیرنده‌ها", "em_clear_recip", style="primary")
        ])
        kb.append([
            Button.inline("📊 آمار زنده", "em_stats", style="primary"),
            Button.inline("دریافت نمایندگی", "em_agency", style="primary")
        ])
        kb.append([Button.inline("🔙 بازگشت به منوی اصلی", "back_main", style="primary")])
    else:
        kb.append([
            Button.inline("➕ ADD SMTP", "em_smtp_add", style="primary"),
            Button.inline("📋 SMTP LIST", "em_smtp_list", style="primary")
        ])
        kb.append([
            Button.inline("🟢 ACTIVATE SENDER", "em_activate", style="primary"),
            Button.inline("📧 SEND SINGLE", "em_single_send", style="primary")
        ])
        kb.append([
            Button.inline("📨 BULK SEND", "em_bulk_send", style="primary"),
            Button.inline("👥 RECIPIENTS LIST", "em_recips", style="primary")
        ])
        kb.append([
            Button.inline("➕ ADD RECIPIENT", "em_add_recip", style="primary"),
            Button.inline("🗑 CLEAR RECIPIENTS", "em_clear_recip", style="primary")
        ])
        kb.append([
            Button.inline("📊 LIVE STATS", "em_stats", style="primary"),
            Button.inline("AGENCY", "em_agency", style="primary")
        ])
        kb.append([Button.inline("🔙 BACK TO MAIN MENU", "back_main", style="primary")])
    return kb

def force_channel_keyboard(user_id):
    lang = get_user_lang(user_id) or "fa"
    return [
        [
            Button.inline("➕ افزودن کانال" if lang=="fa" else "➕ ADD CHANNEL", "em_fc_add", style="primary"),
            Button.inline("➖ حذف کانال" if lang=="fa" else "➖ REMOVE CHANNEL", "em_fc_remove", style="primary")
        ],
        [
            Button.inline("📋 لیست کانال‌ها" if lang=="fa" else "📋 CHANNEL LIST", "em_fc_list", style="primary"),
            Button.inline("🔙 بازگشت" if lang=="fa" else "🔙 BACK", "em_back", style="primary")
        ]
    ]

def telegram_menu_keyboard(user_id):
    lang = get_user_lang(user_id) or "fa"
    kb = []
    kb.append([
        Button.inline("🚫 ریپورت کانال/گروه" if lang=="fa" else "🚫 REPORT CHANNEL/GROUP", "tg_report", style="primary"),
        Button.inline("📝 ریپورت پست" if lang=="fa" else "📝 REPORT POST", "tg_report_post", style="primary")
    ])
    kb.append([
        Button.inline("👤 ریپورت پروفایل" if lang=="fa" else "👤 REPORT PROFILE", "tg_report_profile", style="primary"),
        Button.inline("🤖 ریپورت ربات" if lang=="fa" else "🤖 REPORT BOT", "tg_report_bot", style="primary")
    ])
    kb.append([
        Button.inline("👤 ریپورت اکانت" if lang=="fa" else "👤 REPORT ACCOUNT", "tg_report_account", style="primary"),
        Button.inline("📋 ریپورت دستی" if lang=="fa" else "📋 MANUAL REPORT", "tg_manual_report", style="primary")
    ])
    kb.append([
        Button.inline("➕ افزودن اکانت" if lang=="fa" else "➕ ADD ACCOUNT", "tg_add_acc", style="primary"),
        Button.inline("📋 لیست اکانت‌ها" if lang=="fa" else "📋 LIST ACCOUNTS", "tg_list_all", style="primary")
    ])
    kb.append([
        Button.inline("🗑 حذف اکانت" if lang=="fa" else "🗑 DELETE ACCOUNT", "tg_del_acc", style="primary"),
        Button.inline("🔙 بازگشت به منوی اصلی" if lang=="fa" else "🔙 BACK TO MAIN MENU", "back_main", style="primary")
    ])
    return kb

def reason_keyboard():
    buttons = []
    row = []
    for i in range(1, 11):
        reason_name = REPORT_REASONS[str(i)][0]
        row.append(Button.inline(reason_name, "tg_reason_" + str(i), style="primary"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([Button.inline("🔙 Back", "tg_back", style="primary")])
    return buttons

def join_question_keyboard(lang):
    return [
        [
            Button.inline("✅ جوین شوند" if lang=="fa" else "✅ JOIN", "join_yes", style="primary"),
            Button.inline("❌ جوین نشوند" if lang=="fa" else "❌ NO JOIN", "join_no", style="primary")
        ]
    ]

def cancel_keyboard(lang):
    return [[Button.inline("🛑 لغو عملیات" if lang=="fa" else "🛑 CANCEL OPERATION", "cancel_operation", style="danger")]]

def group_cancel_keyboard():
    return [[Button.inline("🛑 لغو عملیات", "group_cancel_operation", style="danger")]]

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
            Button.inline("1 سال" if lang=="fa" else "1 year", "adm_1y", style="primary"),
            Button.inline("🔙 برگشت" if lang=="fa" else "🔙 Back", "owner_panel", style="primary")
        ]
    ]

def extend_duration_keyboard(lang):
    return [
        [
            Button.inline("+1 ساعت" if lang=="fa" else "+1 hour", "ext_1h", style="primary"),
            Button.inline("+1 روز" if lang=="fa" else "+1 day", "ext_1d", style="primary")
        ],
        [
            Button.inline("+1 هفته" if lang=="fa" else "+1 week", "ext_1w", style="primary"),
            Button.inline("+1 ماه" if lang=="fa" else "+1 month", "ext_1m", style="primary")
        ],
        [
            Button.inline("+3 ماه" if lang=="fa" else "+3 months", "ext_3m", style="primary"),
            Button.inline("+6 ماه" if lang=="fa" else "+6 months", "ext_6m", style="primary")
        ],
        [
            Button.inline("+1 سال" if lang=="fa" else "+1 year", "ext_1y", style="primary"),
            Button.inline("🔙 برگشت" if lang=="fa" else "🔙 Back", "owner_panel", style="primary")
        ]
    ]

def session_sharing_keyboard(user_id):
    lang = get_user_lang(user_id) or "fa"
    return [
        [
            Button.inline("➕ اشتراک‌گذاری سشن" if lang=="fa" else "➕ SHARE SESSION", "em_share_session", style="primary"),
            Button.inline("➖ حذف اشتراک" if lang=="fa" else "➖ UNSHARE SESSION", "em_unshare_session", style="primary")
        ],
        [
            Button.inline("📋 سشن‌های مشترک" if lang=="fa" else "📋 SHARED SESSIONS", "em_list_shared", style="primary"),
            Button.inline("🔙 بازگشت" if lang=="fa" else "🔙 BACK", "back_main", style="primary")
        ]
    ]

def result_details_keyboard(lang, op_id):
    return [
        [
            Button.inline("✅ اکانت‌های موفق" if lang=="fa" else "✅ Successful", "res_ok_" + op_id, style="success"),
            Button.inline("❌ اکانت‌های ناموفق" if lang=="fa" else "❌ Failed", "res_fail_" + op_id, style="danger")
        ]
    ]

def support_menu_keyboard(lang):
    return [
        [Button.inline("✍️ ارسال پیام به پشتیبانی" if lang=="fa" else "✍️ Send Message to Support", "support_new", style="primary")],
        [Button.inline("📋 تیکت‌های من" if lang=="fa" else "📋 My Tickets", "support_my", style="primary")],
        [Button.inline("🔙 بازگشت" if lang=="fa" else "🔙 BACK", "back_main", style="primary")]
    ]

REPORT_OPERATIONS = {}

def gen_op_id():
    return str(random.randint(100000, 999999))

async def send_report_to_group(bot, user_id, target, reason_name, total_success, total_fail, lang, op_id):
    try:
        text = (
            "📊 **گزارش عملیات ریپورت**\n\n"
            "👤 کاربر: `" + str(user_id) + "`\n"
            "🎯 مقصد: `" + str(target) + "`\n"
            "📝 دلیل: " + reason_name + "\n"
            "✅ موفق: " + str(total_success) + "\n"
            "❌ ناموفق: " + str(total_fail)
        )
        sent = await bot.send_message(REPORT_GROUP_ID, text, buttons=group_cancel_keyboard())
        data_db = load_data()
        data_db.setdefault("active_report_group_msg", {})[str(sent.id)] = {
            "user_id": user_id,
            "op_id": op_id
        }
        save_data(data_db)
        return sent.id
    except Exception as e:
        logger.error("send_report_to_group error: " + str(e))
        return None

async def update_report_group_msg(bot, msg_id, user_id, target, reason_name, total_success, total_fail):
    try:
        text = (
            "📊 **گزارش عملیات ریپورت**\n\n"
            "👤 کاربر: `" + str(user_id) + "`\n"
            "🎯 مقصد: `" + str(target) + "`\n"
            "📝 دلیل: " + reason_name + "\n"
            "✅ موفق: " + str(total_success) + "\n"
            "❌ ناموفق: " + str(total_fail)
        )
        await bot.edit_message(REPORT_GROUP_ID, msg_id, text, buttons=group_cancel_keyboard())
    except Exception as e:
        logger.error("update_report_group_msg error: " + str(e))

# =============== HANDLERS ===============

async def start_handler(event):
    user_id = event.sender_id
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
        "✅ به ربات Report gram خوش امدید" if lang == "fa" else "✅ Welcome to SHIKH REPORTER Bot",
        buttons=main_menu_keyboard(user_id)
    )

async def callback_handler(event):
    data_str = event.data.decode('utf-8')
    user_id = event.sender_id
    lang = get_user_lang(user_id) or "fa"

    if data_str in ["noop", "none"]:
        await event.answer()
        return

    # ===== دکمه لغو در گروه =====
    if data_str == "group_cancel_operation":
        msg_id = event.message_id
        data_db = load_data()
        info = data_db.get("active_report_group_msg", {}).get(str(msg_id))
        if not info:
            await event.answer("❌ عملیاتی برای این گزارش یافت نشد", alert=True)
            return
        if not is_owner(user_id):
            await event.answer("⛔ فقط مالک می‌تواند لغو کند", alert=True)
            return
        target_uid = info.get("user_id")
        if target_uid:
            ACTIVE_OPERATIONS[target_uid] = False
            try:
                await event.client.send_message(
                    target_uid,
                    "🛑 **عملیات شما توسط مالک لغو شد**\n\n"
                    "ادمین گرامی، عملیات ریپورت شما به دستور مالک متوقف شد."
                )
            except:
                pass
        await event.answer("🛑 عملیات لغو شد", alert=True)
        try:
            await event.edit(
                event.message.text + "\n\n🛑 **لغو شده توسط مالک**",
                buttons=None
            )
        except:
            pass
        return

    # ===== نمایش اکانت های موفق/ناموفق =====
    if data_str.startswith("res_ok_") or data_str.startswith("res_fail_"):
        op_id = data_str.split("_")[-1]
        op = REPORT_OPERATIONS.get(op_id)
        if not op:
            await event.answer("❌ اطلاعات یافت نشد", alert=True)
            return
        if not is_owner(user_id) and op.get("user_id") != user_id:
            await event.answer("⛔ دسترسی غیرمجاز", alert=True)
            return
        
        if data_str.startswith("res_ok_"):
            accs = op.get("success_accounts", [])
            title = "✅ اکانت‌های موفق"
        else:
            accs = op.get("fail_accounts", [])
            title = "❌ اکانت‌های ناموفق"
        
        if not accs:
            txt = title + "\n\n(خالی)"
        else:
            txt = title + " (" + str(len(accs)) + ")\n\n" + "\n".join("• " + a for a in accs[:100])
        await event.answer(txt[:200], alert=True)
        return

    # ===== پشتیبانی =====
    if data_str == "support_menu":
        await event.edit(
            "🎧 **پشتیبانی**\n\n"
            "هر سوال یا مشکلی دارید، همین‌جا بپرسید. پیام شما مستقیم برای مالک ارسال می‌شود.",
            buttons=support_menu_keyboard(lang)
        )
        return

    if data_str == "support_new":
        USER_STATE[user_id] = {"section": "support", "step": "waiting_message"}
        await event.edit(
            "🎧 پیام خود را بنویسید و ارسال کنید:",
            buttons=[[Button.inline("🔙 بازگشت" if lang=="fa" else "BACK", "support_menu", style="primary")]]
        )
        return

    if data_str == "support_my":
        data_db = load_data()
        tickets = data_db.get("support_tickets", {})
        my = tickets.get(str(user_id), [])
        if not my:
            await event.edit(
                "📭 تیکتی ندارید" if lang=="fa" else "📭 No tickets",
                buttons=[[Button.inline("🔙 بازگشت" if lang=="fa" else "BACK", "support_menu", style="primary")]]
            )
            return
        text = "📋 تیکت‌های شما:\n\n"
        for i, t in enumerate(my[-10:], 1):
            text += str(i) + ") " + t.get("msg", "")[:80] + "\nوضعیت: " + t.get("status", "pending") + "\n\n"
        await event.edit(text, buttons=[[Button.inline("🔙 بازگشت" if lang=="fa" else "BACK", "support_menu", style="primary")]])
        return

    if data_str == "owner_tickets":
        if not is_owner(user_id):
            await event.answer("⛔ Unauthorized", alert=True)
            return
        data_db = load_data()
        tickets = data_db.get("support_tickets", {})
        all_t = []
        for uid, tlist in tickets.items():
            for t in tlist:
                all_t.append((uid, t))
        if not all_t:
            await event.edit("📭 تیکتی وجود ندارد", buttons=[[Button.inline("🔙 بازگشت", "owner_panel", style="primary")]])
            return
        text = "🎫 تیکت‌های پشتیبانی:\n\n"
        for i, (uid, t) in enumerate(all_t[-15:], 1):
            text += str(i) + ") از `" + uid + "`:\n" + t.get("msg", "")[:100] + "\n---\n"
        await event.edit(text, buttons=[[Button.inline("🔙 بازگشت", "owner_panel", style="primary")]])
        return

    # ===== آمار کلی ربات =====
    if data_str == "owner_stats":
        if not is_owner(user_id):
            await event.answer("⛔ Unauthorized", alert=True)
            return
        data_db = load_data()
        total_users = len(data_db.get("users", []))
        total_admins = len(data_db.get("admins", {}))
        total_blocked = len(data_db.get("blocked", []))
        total_reports = data_db.get("total_reports", 0)
        total_sessions = len(get_all_sessions())
        total_owners = len(OWNER_IDS)
        txt = (
            "📊 **آمار کلی ربات**\n\n"
            "👥 کل کاربران: " + str(total_users) + "\n"
            "📋 کل ادمین‌ها: " + str(total_admins) + "\n"
            "👑 کل مالکین: " + str(total_owners) + "\n"
            "🚫 کاربران بلاک‌شده: " + str(total_blocked) + "\n"
            "📱 کل سشن‌ها: " + str(total_sessions) + "\n"
            "✅ کل ریپورت‌های موفق: " + str(total_reports)
        )
        await event.edit(txt, buttons=[[Button.inline("🔙 بازگشت", "owner_panel", style="primary")]])
        return

    # ===== لیست کاربران بلاک‌شده =====
    if data_str == "owner_blocked_list":
        if not is_owner(user_id):
            await event.answer("⛔ Unauthorized", alert=True)
            return
        data_db = load_data()
        blocked = data_db.get("blocked", [])
        if not blocked:
            await event.edit("📭 کاربر بلاک‌شده‌ای وجود ندارد",
                            buttons=[[Button.inline("🔙 بازگشت", "owner_panel", style="primary")]])
            return
        text = "⚠️ کاربران بلاک‌شده:\n\n"
        for i, uid in enumerate(blocked[:30], 1):
            text += str(i) + ". `" + str(uid) + "`\n"
        await event.edit(text, buttons=[[Button.inline("🔙 بازگشت", "owner_panel", style="primary")]])
        return

    # ===== حذف ادمین =====
    if data_str == "owner_remove_admin":
        if not is_owner(user_id):
            await event.answer("⛔ Unauthorized", alert=True)
            return
        data_db = load_data()
        admins = data_db.get("admins", {})
        if not admins:
            await event.answer("❌ ادمینی وجود ندارد", alert=True)
            return
        kb = []
        for uid in list(admins.keys())[:30]:
            kb.append([Button.inline("🗑 حذف ادمین `" + uid + "`", "owner_deladm_" + uid, style="danger")])
        kb.append([Button.inline("🔙 بازگشت", "owner_panel", style="primary")])
        await event.edit("🗑 انتخاب ادمین برای حذف:", buttons=kb)
        return

    if data_str.startswith("owner_deladm_"):
        if not is_owner(user_id):
            await event.answer("⛔ Unauthorized", alert=True)
            return
        target_uid = data_str.replace("owner_deladm_", "")
        data_db = load_data()
        if target_uid in data_db.get("admins", {}):
            del data_db["admins"][target_uid]
            save_data(data_db)
            await event.answer("✅ ادمین حذف شد", alert=True)
            try:
                await event.client.send_message(
                    int(target_uid),
                    "⛔ دسترسی ادمین شما توسط مالک لغو شد."
                )
            except:
                pass
        else:
            await event.answer("❌ یافت نشد", alert=True)
        await event.edit("🗑 ادمین حذف شد.",
                        buttons=[[Button.inline("🔙 بازگشت به پنل مالک", "owner_panel", style="primary")]])
        return

    # ===== تمدید اشتراک ادمین =====
    if data_str == "owner_extend_admin":
        if not is_owner(user_id):
            await event.answer("⛔ Unauthorized", alert=True)
            return
        USER_STATE[user_id] = {"action": "extend_admin", "step": "waiting_user_id"}
        await event.edit("🆔 آیدی عددی ادمین را برای تمدید وارد کنید:")
        return

    if data_str.startswith("ext_"):
        state = USER_STATE.get(user_id, {})
        if state.get("action") != "extend_admin" or state.get("step") != "waiting_duration":
            await event.answer("⏳ لطفاً ابتدا آیدی را وارد کنید", alert=True)
            return
        target_user = state.get("target_user")
        if not target_user:
            await event.answer("❌ خطا", alert=True)
            return
        duration_map = {
            "ext_1h": timedelta(hours=1),
            "ext_1d": timedelta(days=1),
            "ext_1w": timedelta(weeks=1),
            "ext_1m": timedelta(days=30),
            "ext_3m": timedelta(days=90),
            "ext_6m": timedelta(days=180),
            "ext_1y": timedelta(days=365)
        }
        duration = duration_map.get(data_str)
        if not duration:
            await event.answer("❌ مدت نامعتبر", alert=True)
            return
        data_db = load_data()
        admins = data_db.get("admins", {})
        if str(target_user) not in admins:
            await event.answer("❌ ادمین یافت نشد", alert=True)
            USER_STATE.pop(user_id, None)
            return
        tehran = pytz.timezone('Asia/Tehran')
        now = datetime.now(tehran)
        cur_expires = admins[str(target_user)].get("expires")
        if isinstance(cur_expires, str):
            try:
                cur_expires = datetime.fromisoformat(cur_expires)
            except:
                cur_expires = now
        if cur_expires.tzinfo is None:
            cur_expires = tehran.localize(cur_expires)
        base = max(cur_expires, now)
        new_expires = base + duration
        admins[str(target_user)]["expires"] = new_expires
        save_data(data_db)
        await event.edit(
            "✅ اشتراک ادمین `" + str(target_user) + "` تمدید شد\n"
            "📅 انقضای جدید: " + new_expires.strftime('%Y-%m-%d %H:%M'),
            buttons=[[Button.inline("🔙 بازگشت به پنل مالک", "owner_panel", style="primary")]]
        )
        try:
            await event.client.send_message(
                target_user,
                "🎉 اشتراک ادمین شما تمدید شد!\n📅 انقضای جدید: " + new_expires.strftime('%Y-%m-%d %H:%M')
            )
        except:
            pass
        USER_STATE.pop(user_id, None)
        return

    # ===== بکاپ دیتا =====
    if data_str == "owner_backup":
        if not is_owner(user_id):
            await event.answer("⛔ Unauthorized", alert=True)
            return
        try:
            if os.path.exists(DATA_FILE):
                await event.client.send_file(user_id, DATA_FILE, caption="💾 بکاپ دیتا")
                await event.answer("✅ بکاپ ارسال شد", alert=True)
        except Exception as e:
            await event.answer("❌ خطا: " + str(e)[:100], alert=True)
        return

    # ===== ریست ریپورت‌ها =====
    if data_str == "owner_reset_reports":
        if not is_owner(user_id):
            await event.answer("⛔ Unauthorized", alert=True)
            return
        data_db = load_data()
        data_db["total_reports"] = 0
        data_db["send_today"] = 0
        data_db["send_week"] = 0
        save_data(data_db)
        await event.answer("✅ ریپورت‌ها ریست شد", alert=True)
        await event.edit("✅ آمار ریپورت‌ها صفر شد.",
                        buttons=[[Button.inline("🔙 بازگشت به پنل مالک", "owner_panel", style="primary")]])
        return

    # ===== افزودن مالک جدید =====
    if data_str == "add_owner":
        if not is_owner(user_id):
            await event.answer("⛔ Unauthorized", alert=True)
            return
        USER_STATE[user_id] = {"action": "add_owner", "step": "waiting_user_id"}
        await event.edit("👑 آیدی عددی مالک جدید را وارد کنید:")
        return

    # ===== لیست مالکین =====
    if data_str == "list_owners":
        if not is_owner(user_id):
            await event.answer("⛔ Unauthorized", alert=True)
            return
        txt = "👑 **لیست مالکین:**\n\n"
        for oid in OWNER_IDS:
            txt += "• `" + str(oid) + "`\n"
        await event.edit(txt, buttons=[[Button.inline("🔙 بازگشت", "owner_panel", style="primary")]])
        return

    # ===== لیست ادمین‌ها با تاریخ =====
    if data_str == "list_admins":
        if not is_owner(user_id):
            await event.answer("⛔ Unauthorized", alert=True)
            return
        data_db = load_data()
        admins = data_db.get("admins", {})
        if not admins:
            await event.edit("📭 ادمینی وجود ندارد", buttons=[[Button.inline("🔙 بازگشت", "owner_panel", style="primary")]])
            return
        tehran = pytz.timezone('Asia/Tehran')
        now = datetime.now(tehran)
        txt = "📋 **لیست ادمین‌ها:**\n\n"
        for uid, info in admins.items():
            exp = info.get("expires")
            act = info.get("activated")
            if isinstance(exp, str):
                try:
                    exp = datetime.fromisoformat(exp)
                except:
                    exp = None
            if exp is not None and exp.tzinfo is None:
                exp = tehran.localize(exp)
            if exp and exp > now:
                status = "🟢 فعال"
            else:
                status = "🔴 منقضی"
            exp_str = exp.strftime('%Y-%m-%d %H:%M') if exp else "نامشخص"
            act_str = act.strftime('%Y-%m-%d %H:%M') if isinstance(act, datetime) else "نامشخص"
            txt += "• `" + uid + "`\n  وضعیت: " + status + "\n  فعال‌سازی: " + act_str + "\n  انقضا: " + exp_str + "\n\n"
        await event.edit(txt, buttons=[[Button.inline("🔙 بازگشت", "owner_panel", style="primary")]])
        return

    if data_str in ["lang_fa", "lang_en"]:
        lang_code = "fa" if data_str == "lang_fa" else "en"
        set_user_lang(user_id, lang_code)
        lang = lang_code
        if not (is_owner(user_id) or is_admin(user_id)):
            await event.edit(
                "⛔ شما مجاز به استفاده از این ربات نیستید." if lang == "fa" else "⛔ Unauthorized"
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

    if data_str == "cancel_operation":
        if user_id in ACTIVE_OPERATIONS and ACTIVE_OPERATIONS[user_id]:
            ACTIVE_OPERATIONS[user_id] = False
            await event.answer("🛑 عملیات لغو شد" if lang == "fa" else "🛑 Operation cancelled", alert=True)
            await event.edit("🛑 عملیات لغو شد" if lang == "fa" else "🛑 Operation cancelled",
                           buttons=[[Button.inline("🔙 بازگشت" if lang=="fa" else "BACK", "back_main", style="primary")]])
        else:
            await event.answer("❌ عملیاتی در حال اجرا نیست" if lang == "fa" else "❌ No operation running", alert=True)
        return

    if data_str == "join_yes":
        state = USER_STATE.get(user_id, {})
        if state and state.get("step") == "join_question":
            state["should_join"] = True
            state["step"] = "select_reason"
            await event.edit("📝 دلیل ریپورت را انتخاب کنید:", buttons=reason_keyboard())
        return

    if data_str == "join_no":
        state = USER_STATE.get(user_id, {})
        if state and state.get("step") == "join_question":
            state["should_join"] = False
            state["step"] = "select_reason"
            await event.edit("📝 دلیل ریپورت را انتخاب کنید:", buttons=reason_keyboard())
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
            "✅ ادمین برای کاربر " + str(target_user) + " با موفقیت افزوده شد\n" +
            "تاریخ انقضا: " + expires.strftime('%Y-%m-%d %H:%M:%S') if lang == "fa" else
            "✅ Admin added for user " + str(target_user) + "\n" +
            "Expires: " + expires.strftime('%Y-%m-%d %H:%M:%S'),
            buttons=[[Button.inline("🔙 بازگشت به پنل مالک" if lang == "fa" else "🔙 BACK TO OWNER PANEL", "owner_panel", style="primary")]]
        )
        USER_STATE.pop(user_id, None)
        try:
            await event.client.send_message(
                target_user,
                "🎉 شما به عنوان ادمین ربات انتخاب شدید!\n\n"
                "⏰ انقضا: " + expires.strftime('%Y-%m-%d %H:%M:%S') + "\n\n"
                "برای شروع /start را ارسال کنید."
            )
        except:
            pass
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

    if data == "em_manage_sharing":
        if not is_owner(user_id):
            await event.answer("⛔ دسترسی غیرمجاز" if lang == "fa" else "⛔ Unauthorized", alert=True)
            return
        await event.edit("🔄 مدیریت اشتراک سشن‌ها" if lang == "fa" else "🔄 Manage Session Sharing",
                        buttons=session_sharing_keyboard(user_id))
        return

    if data == "em_share_session":
        if not is_owner(user_id):
            await event.answer("⛔ دسترسی غیرمجاز" if lang == "fa" else "⛔ Unauthorized", alert=True)
            return
        USER_STATE[user_id] = {"section": "email", "step": "share_session_select"}
        all_sessions = get_all_sessions()
        if not all_sessions:
            await event.edit("❌ سشنی وجود ندارد" if lang == "fa" else "❌ No sessions available")
            return
        kb = []
        for admin_id, filename in all_sessions[:20]:
            phone = filename.replace('.session', '')
            data_db = load_data()
            shared = data_db.get("shared_sessions", [])
            is_shared = any(s.get("admin_id") == admin_id and s.get("filename") == filename for s in shared if isinstance(s, dict))
            status = "🟢" if is_shared else "⚪"
            kb.append([Button.inline(status + " +" + phone + " (Admin " + admin_id + ")", "em_share_" + admin_id + "_" + phone, style="primary")])
        kb.append([Button.inline("🔙 بازگشت" if lang=="fa" else "BACK", "em_manage_sharing", style="primary")])
        await event.edit("🔄 انتخاب سشن برای اشتراک‌گذاری" if lang=="fa" else "🔄 Select session to share", buttons=kb)
        return

    if data.startswith("em_share_"):
        if not is_owner(user_id):
            await event.answer("⛔ دسترسی غیرمجاز" if lang == "fa" else "⛔ Unauthorized", alert=True)
            return
        parts = data[len("em_share_"):].split("_", 1)
        if len(parts) != 2:
            await event.answer("Error")
            return
        admin_id, phone = parts
        filename = phone + ".session"
        data_db = load_data()
        shared = data_db.get("shared_sessions", [])
        entry = {"admin_id": admin_id, "filename": filename}
        if entry in shared:
            shared.remove(entry)
            await event.answer("✅ از اشتراک خارج شد" if lang=="fa" else "✅ Unshared", alert=True)
        else:
            shared.append(entry)
            await event.answer("✅ به اشتراک گذاشته شد" if lang=="fa" else "✅ Shared", alert=True)
        data_db["shared_sessions"] = shared
        save_data(data_db)
        clear_user_cache()
        
        all_sessions = get_all_sessions()
        kb = []
        for a_id, fn in all_sessions[:20]:
            ph = fn.replace('.session', '')
            is_shared = any(s.get("admin_id") == a_id and s.get("filename") == fn for s in shared if isinstance(s, dict))
            status = "🟢" if is_shared else "⚪"
            kb.append([Button.inline(status + " +" + ph + " (Admin " + a_id + ")", "em_share_" + a_id + "_" + ph, style="primary")])
        kb.append([Button.inline("🔙 بازگشت" if lang=="fa" else "BACK", "em_manage_sharing", style="primary")])
        await event.edit("🔄 انتخاب سشن برای اشتراک‌گذاری" if lang=="fa" else "🔄 Select session to share", buttons=kb)
        return

    if data == "em_list_shared":
        if not is_owner(user_id):
            await event.answer("⛔ دسترسی غیرمجاز" if lang == "fa" else "⛔ Unauthorized", alert=True)
            return
        data_db = load_data()
        shared = data_db.get("shared_sessions", [])
        if not shared:
            await event.edit("❌ سشن مشترکی وجود ندارد" if lang == "fa" else "❌ No shared sessions",
                           buttons=[[Button.inline("🔙 بازگشت" if lang=="fa" else "BACK", "em_manage_sharing", style="primary")]])
            return
        text = "📋 سشن‌های مشترک:\n\n"
        for s in shared:
            if isinstance(s, dict):
                text += "📱 +" + s.get('filename', '').replace('.session', '') + " (Admin " + s.get('admin_id', '') + ")\n"
        await event.edit(text, buttons=[[Button.inline("🔙 بازگشت" if lang=="fa" else "BACK", "em_manage_sharing", style="primary")]])
        return

    if data == "em_unshare_session":
        if not is_owner(user_id):
            await event.answer("⛔ دسترسی غیرمجاز" if lang == "fa" else "⛔ Unauthorized", alert=True)
            return
        data_db = load_data()
        shared = data_db.get("shared_sessions", [])
        if not shared:
            await event.edit("❌ سشن مشترکی وجود ندارد" if lang == "fa" else "❌ No shared sessions",
                           buttons=[[Button.inline("🔙 بازگشت" if lang=="fa" else "BACK", "em_manage_sharing", style="primary")]])
            return
        kb = []
        for s in shared:
            if isinstance(s, dict):
                admin_id = s.get("admin_id", "")
                filename = s.get("filename", "")
                phone = filename.replace('.session', '')
                kb.append([Button.inline("🗑 +" + phone + " (Admin " + admin_id + ")", "em_unshare_" + admin_id + "_" + phone, style="primary")])
        kb.append([Button.inline("🔙 بازگشت" if lang=="fa" else "BACK", "em_manage_sharing", style="primary")])
        await event.edit("🗑 انتخاب سشن برای حذف از اشتراک" if lang=="fa" else "🗑 Select session to unshare", buttons=kb)
        return

    if data.startswith("em_unshare_"):
        if not is_owner(user_id):
            await event.answer("⛔ دسترسی غیرمجاز" if lang == "fa" else "⛔ Unauthorized", alert=True)
            return
        parts = data[len("em_unshare_"):].split("_", 1)
        if len(parts) != 2:
            await event.answer("Error")
            return
        admin_id, phone = parts
        filename = phone + ".session"
        data_db = load_data()
        shared = data_db.get("shared_sessions", [])
        entry = {"admin_id": admin_id, "filename": filename}
        if entry in shared:
            shared.remove(entry)
            data_db["shared_sessions"] = shared
            save_data(data_db)
            clear_user_cache()
            await event.answer("✅ حذف شد" if lang=="fa" else "✅ Removed", alert=True)
        else:
            await event.answer("❌ یافت نشد" if lang=="fa" else "❌ Not found", alert=True)
        
        shared = data_db.get("shared_sessions", [])
        if not shared:
            await event.edit("❌ سشن مشترکی وجود ندارد" if lang == "fa" else "❌ No shared sessions",
                           buttons=[[Button.inline("🔙 بازگشت" if lang=="fa" else "BACK", "em_manage_sharing", style="primary")]])
            return
        kb = []
        for s in shared:
            if isinstance(s, dict):
                a_id = s.get("admin_id", "")
                fn = s.get("filename", "")
                ph = fn.replace('.session', '')
                kb.append([Button.inline("🗑 +" + ph + " (Admin " + a_id + ")", "em_unshare_" + a_id + "_" + ph, style="primary")])
        kb.append([Button.inline("🔙 بازگشت" if lang=="fa" else "BACK", "em_manage_sharing", style="primary")])
        await event.edit("🗑 انتخاب سشن برای حذف از اشتراک" if lang=="fa" else "🗑 Select session to unshare", buttons=kb)
        return

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
                row.append(Button.inline(email, "em_smtp_view_" + email, style="primary"))
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
            [Button.inline("🗑 حذف" if lang == "fa" else "DELETE", "em_smtp_del_" + email, style="primary")],
            [Button.inline("🔙 بازگشت" if lang == "fa" else "BACK", "em_smtp_list", style="primary")]
        ]
        await event.edit("📧 " + email + "\n\nحذف شود؟" if lang == "fa" else "📧 " + email + "\n\nDelete?",
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
            row.append(Button.inline(em, "em_smtp_view_" + em, style="primary"))
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
            kb.append([Button.inline(status + " " + email, "em_toggle_" + email, style="primary")])
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
            kb.append([Button.inline(status + " " + em, "em_toggle_" + em, style="primary")])
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
        total = data_db.get("total_reports", 0)
        await event.edit("📊 ارسال امروز: " + str(today) + "\n📊 ارسال این هفته: " + str(week) + "\n📊 کل ریپورت‌ها: " + str(total) if lang == "fa" else
                        "📊 Today: " + str(today) + "\n📊 This Week: " + str(week) + "\n📊 Total Reports: " + str(total))
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

    if data in ["tg_report", "tg_report_post", "tg_report_profile", "tg_report_bot", "tg_report_account", "tg_manual_report"]:
        sessions = get_user_sessions(user_id)
        if not sessions:
            await event.answer("❌ هیچ اکانتی در دسترس نیست" if lang == "fa" else "❌ No accounts available", alert=True)
            return
        report_type_map = {
            "tg_report": "report",
            "tg_report_post": "report_post",
            "tg_report_profile": "report_profile",
            "tg_report_bot": "report_bot",
            "tg_report_account": "report_account",
            "tg_manual_report": "manual_report"
        }
        USER_STATE[user_id] = {"section": "telegram", "type": report_type_map[data], "step": "count", "sessions": sessions}
        await event.edit("🔢 تعداد اکانت؟ (1-" + str(len(sessions)) + ")" if lang == "fa" else "🔢 Number of accounts? (1-" + str(len(sessions)) + ")")
        return

    if data == "tg_list_all":
        sessions = get_all_sessions()
        if not sessions:
            await event.answer("❌ اکانتی وجود ندارد" if lang == "fa" else "❌ No accounts", alert=True)
            return
        kb = []
        for admin_id, filename in sessions[:15]:
            phone = filename.replace('.session', '')
            btn_text = "📱 +" + phone + " (Admin " + admin_id + ")"
            kb.append([
                Button.inline(btn_text, "noop", style="primary"),
                Button.inline("🗑", "tg_delacc_" + admin_id + "_" + phone, style="primary")
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
        path = os.path.join(admin_dir, phone_clean + ".session")
        if os.path.exists(path):
            os.remove(path)
            data_db = load_data()
            shared = data_db.get("shared_sessions", [])
            shared = [s for s in shared if not (isinstance(s, dict) and s.get("admin_id") == admin_id_str and s.get("filename") == phone_clean + ".session")]
            data_db["shared_sessions"] = shared
            save_data(data_db)
            clear_user_cache()
            await event.answer("✅ حذف شد" if lang=="fa" else "✅ Deleted", alert=True)
        else:
            await event.answer("❌ یافت نشد" if lang=="fa" else "❌ Not found", alert=True)
        
        sessions = get_all_sessions()
        kb = []
        for a_id, fn in sessions[:15]:
            ph = fn.replace('.session', '')
            btn_text = "📱 +" + ph + " (Admin " + a_id + ")"
            kb.append([
                Button.inline(btn_text, "noop", style="primary"),
                Button.inline("🗑", "tg_delacc_" + a_id + "_" + ph, style="primary")
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
    if event.text.startswith('/'):
        return

    text = event.text.strip()
    user_id = event.sender_id
    state = USER_STATE.get(user_id, {})
    lang = get_user_lang(user_id) or "fa"

    if not state:
        return

    # پشتیبانی بدون نیاز به ادمین بودن
    if state.get("section") == "support":
        if state.get("step") == "waiting_message":
            if not text:
                await event.reply("❌ متن خالی است")
                return
            data_db = load_data()
            tickets = data_db.setdefault("support_tickets", {})
            lst = tickets.setdefault(str(user_id), [])
            t = {
                "msg": text,
                "time": datetime.now(pytz.timezone('Asia/Tehran')).isoformat(),
                "status": "pending",
                "from_name": event.sender.first_name or ""
            }
            lst.append(t)
            save_data(data_db)
            for oid in OWNER_IDS:
                try:
                    kb = [
                        [Button.inline("🚫 بلاک کاربر", "sup_block_" + str(user_id), style="danger")],
                        [Button.inline("✍️ پاسخ دادن", "sup_reply_" + str(user_id), style="primary")]
                    ]
                    await event.client.send_message(
                        oid,
                        "🎧 **پیام جدید از پشتیبانی**\n\n"
                        "👤 از: `" + str(user_id) + "`\n"
                        "📛 نام: " + (event.sender.first_name or "نامشخص") + "\n\n"
                        "💬 محتوای پیام:\n" + text,
                        buttons=kb
                    )
                except Exception as e:
                    logger.error("Support notify owner error: " + str(e))
            USER_STATE.pop(user_id, None)
            await event.reply(
                "✅ پیام شما برای پشتیبانی ارسال شد. به‌زودی پاسخ داده می‌شود.",
                buttons=[[Button.inline("🔙 بازگشت", "back_main", style="primary")]]
            )
            return

    if state.get("action") == "reply_user" and state.get("step") == "waiting_reply":
        target = state.get("target_user")
        if target:
            try:
                await event.client.send_message(
                    target,
                    "🎧 **پاسخ پشتیبانی:**\n\n" + text
                )
                await event.reply("✅ پاسخ ارسال شد به کاربر `" + str(target) + "`")
            except Exception as e:
                await event.reply("❌ ارسال نشد: " + str(e)[:100])
        USER_STATE.pop(user_id, None)
        return

    if not (is_owner(user_id) or is_admin(user_id)):
        USER_STATE.pop(user_id, None)
        return

    if state.get("action") == "add_owner" and state.get("step") == "waiting_user_id":
        if not text.isdigit():
            await event.reply("❌ لطفاً یک آیدی عددی وارد کنید")
            return
        new_owner = int(text)
        if new_owner in OWNER_IDS:
            await event.reply("⚠️ این کاربر قبلاً مالک است")
            USER_STATE.pop(user_id, None)
            return
        OWNER_IDS.append(new_owner)
        data_db = load_data()
        data_db.setdefault("admin_data", {}).setdefault(str(new_owner), {
            "smtp": [], "active_senders": [], "recipients": []
        })
        save_data(data_db)
        await event.reply("👑 کاربر `" + str(new_owner) + "` به مالکین اضافه شد.")
        try:
            await event.client.send_message(
                new_owner,
                "👑 شما به عنوان مالک ربات انتخاب شدید!\n\nبرای شروع /start را ارسال کنید."
            )
        except:
            pass
        USER_STATE.pop(user_id, None)
        return

    if state.get("action") == "extend_admin" and state.get("step") == "waiting_user_id":
        if not text.isdigit():
            await event.reply("❌ آیدی عددی وارد کنید")
            return
        target_user = int(text)
        data_db = load_data()
        if str(target_user) not in data_db.get("admins", {}):
            await event.reply("❌ این کاربر ادمین نیست")
            USER_STATE.pop(user_id, None)
            return
        state["target_user"] = target_user
        state["step"] = "waiting_duration"
        await event.reply("📅 مدت تمدید را انتخاب کنید:", buttons=extend_duration_keyboard(lang))
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

    if step == "share_session_select":
        await event.answer("از دکمه‌ها استفاده کنید" if lang == "fa" else "Use buttons", alert=True)
        return

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
                "✅ تمام شد\n📨 کل: " + str(len(recips)) + "\n✅ موفق: " + str(success) + "\n❌ ناموفق: " + str(failed)
                if lang == "fa" else
                "✅ Done\n📨 Total: " + str(len(recips)) + "\n✅ Success: " + str(success) + "\n❌ Failed: " + str(failed)
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
        await event.reply("✅ " + str(added) + " گیرنده اضافه شد\n⚠️ تکراری: " + str(dup) if lang == "fa" else
                         "✅ " + str(added) + " added\n⚠️ duplicate: " + str(dup))
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
                        "🚀 ارسال همگانی\n" + bar + " " + str(percent) + "%\n👥 کل: " + str(total) + "\n📤 موفق: " + str(sent) + "\n🚫 بلاک: " + str(blocked) + "\n❌ خطا: " + str(failed)
                        if lang == "fa" else
                        "🚀 Broadcast\n" + bar + " " + str(percent) + "%\n👥 Total: " + str(total) + "\n📤 Sent: " + str(sent) + "\n🚫 Blocked: " + str(blocked) + "\n❌ Failed: " + str(failed)
                    )
                except:
                    pass
            await asyncio.sleep(0.05)
        await msg.edit(
            "✅ ارسال همگانی پایان یافت\n🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩 100%\n👥 کل: " + str(total) + "\n📤 موفق: " + str(sent) + "\n🚫 بلاک: " + str(blocked) + "\n❌ خطا: " + str(failed)
            if lang == "fa" else
            "✅ Broadcast completed\n🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩 100%\n👥 Total: " + str(total) + "\n📤 Sent: " + str(sent) + "\n🚫 Blocked: " + str(blocked) + "\n❌ Failed: " + str(failed)
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
            await event.reply("❌ خطا: " + str(e)[:100])
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
            filename = phone_clean + ".session"
            admin_dir = get_admin_sessions_dir(target_admin)
            path = os.path.join(admin_dir, filename)
            with open(path, "w", encoding='utf-8') as f:
                f.write(session_str)
            clear_user_cache()
            me = await client.get_me()
            profile = "✅ اکانت اضافه شد\n👤 " + (me.first_name or '') + " " + (me.last_name or '') + "\n📱 " + phone + "\n🆔 " + str(me.id) + "\n@" + (me.username or 'None')
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
            await event.reply("❌ خطا: " + str(e)[:100])
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
            filename = phone_clean + ".session"
            admin_dir = get_admin_sessions_dir(target_admin)
            path = os.path.join(admin_dir, filename)
            with open(path, "w", encoding='utf-8') as f:
                f.write(session_str)
            clear_user_cache()
            me = await client.get_me()
            profile = "✅ اکانت اضافه شد\n👤 " + (me.first_name or '') + " " + (me.last_name or '') + "\n📱 " + phone + "\n🆔 " + str(me.id) + "\n@" + (me.username or 'None')
            await event.reply(profile)
            await client.disconnect()
            USER_STATE.pop(user_id, None)
        except errors.PasswordHashInvalidError:
            await event.reply("❌ رمز اشتباه است" if lang == "fa" else "❌ Invalid password")
        except Exception as e:
            await event.reply("❌ خطا: " + str(e)[:100])
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
            if f == phone_clean + ".session":
                os.remove(os.path.join(admin_dir, f))
                deleted = True
                data_db = load_data()
                shared = data_db.get("shared_sessions", [])
                shared = [s for s in shared if not (isinstance(s, dict) and s.get("admin_id") == str(target_admin) and s.get("filename") == phone_clean + ".session")]
                data_db["shared_sessions"] = shared
                save_data(data_db)
        if deleted:
            clear_user_cache()
            await event.reply("✅ اکانت " + text + " حذف شد" if lang == "fa" else "✅ Account " + text + " deleted")
        else:
            await event.reply("❌ اکانتی یافت نشد" if lang == "fa" else "❌ No account found")
        USER_STATE.pop(user_id, None)
        return

    if step == "count":
        try:
            count = int(text)
            sessions = state["sessions"]
            if count < 1 or count > len(sessions):
                await event.reply("❌ عدد بین 1 تا " + str(len(sessions)) if lang == "fa" else "❌ Between 1 and " + str(len(sessions)))
                return
            state["count"] = count
            state["selected_sessions"] = sessions[:count]
            op_type = state.get("type")
            if op_type == "report_post":
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
        state["post_links"] = post_links
        state["step"] = "delay_time"
        await event.reply(
            "⏱ تاخیر بین ریپورت‌ها چند ثانیه باشد؟\n"
            "در چند ثانیه ۱ ریپورت ارسال شود\n\n"
            "حداکثر: 10 | پیشنهادی: 4"
            if lang == "fa" else
            "⏱ Delay between reports in seconds?\n"
            "How many seconds per 1 report\n\n"
            "Max: 10 | Suggested: 4"
        )
        return

    if step == "target":
        target = text.strip()
        if not target:
            await event.reply("❌ خالی نباشد" if lang == "fa" else "❌ Not empty")
            return
        state["target"] = target
        state["step"] = "delay_time"
        await event.reply(
            "⏱ تاخیر بین ریپورت‌ها چند ثانیه باشد؟\n"
            "در چند ثانیه ۱ ریپورت ارسال شود\n\n"
            "حداکثر: 10 | پیشنهادی: 4"
            if lang == "fa" else
            "⏱ Delay between reports in seconds?\n"
            "How many seconds per 1 report\n\n"
            "Max: 10 | Suggested: 4"
        )
        return

    if step == "delay_time":
        try:
            delay_seconds = int(text)
            if delay_seconds < 1 or delay_seconds > 10:
                await event.reply(
                    "❌ عدد باید بین 1 تا 10 ثانیه باشد"
                    if lang == "fa" else
                    "❌ Number must be between 1 and 10 seconds"
                )
                return
            state["delay_seconds"] = delay_seconds
            state["step"] = "join_question"
            await event.reply(
                "❓ اکانت‌ها ابتدا جوین شوند؟" if lang == "fa" else "❓ Should accounts join first?",
                buttons=join_question_keyboard(lang)
            )
        except ValueError:
            await event.reply("❌ عدد وارد کنید" if lang == "fa" else "❌ Enter a number")
        return

    if step == "count_per_account":
        try:
            cnt = int(text)
            if cnt < 1 or cnt > 50:
                await event.reply("❌ عدد بین 1 تا 50" if lang == "fa" else "❌ Between 1 and 50")
                return
            state["count_per_account"] = cnt
            state["step"] = "custom_reason"
            await event.reply(
                "📝 متن دلخواه (یا /skip)" if lang == "fa" else
                "📝 Custom message (or /skip)"
            )
        except ValueError:
            await event.reply("❌ عدد وارد کنید" if lang == "fa" else "❌ Enter a number")
        return

    if step == "custom_reason":
        if text == "/skip":
            reason_key = state.get("reason_key", "1")
            text = REPORT_REASONS[reason_key][2]
        state["custom_reason"] = text
        
        num_accounts = len(state.get("selected_sessions", []))
        cnt = state.get("count_per_account", 1)
        targets = state.get("post_links", [state.get("target", "")])
        delay_seconds = state.get("delay_seconds", 4)
        est_time = calculate_estimated_time(num_accounts, cnt, len(targets), delay_seconds)
        time_str = format_time(est_time)
        
        await event.reply(
            "🚀 شروع عملیات ریپورت...\n" +
            "⏱ زمان تقریبی: " + time_str + "\n" +
            "👥 اکانت‌ها: " + str(num_accounts) + "\n" +
            "🔢 ریپورت/اکانت: " + str(cnt) + "\n" +
            "⏱ تاخیر بین ریپورت‌ها: " + str(delay_seconds) + " ثانیه\n\n" +
            "📊 هر 5 دقیقه گزارش پیشرفت دریافت می‌کنید" if lang == "fa" else
            "🚀 Starting report operation...\n" +
            "⏱ Estimated time: " + time_str + "\n" +
            "👥 Accounts: " + str(num_accounts) + "\n" +
            "🔢 Reports/Account: " + str(cnt) + "\n" +
            "⏱ Delay between reports: " + str(delay_seconds) + " seconds\n\n" +
            "📊 You will receive progress updates every 5 minutes",
            buttons=cancel_keyboard(lang)
        )
        
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
    delay_seconds = state.get("delay_seconds", 4)
    should_join = state.get("should_join", False)

    total_success = 0
    total_fail = 0
    errors_list = []
    success_accounts = []
    fail_accounts = []
    operation_start = datetime.now()
    last_progress_update = operation_start
    last_group_update = operation_start

    ACTIVE_OPERATIONS[user_id] = True
    op_id = gen_op_id()

    target_display = state.get('target', 'Multiple posts')
    group_msg_id = await send_report_to_group(
        event.client, user_id, target_display, reason_name,
        total_success, total_fail, lang, op_id
    )

    REPORT_OPERATIONS[op_id] = {
        "user_id": user_id,
        "success_accounts": success_accounts,
        "fail_accounts": fail_accounts,
        "lang": lang
    }

    if op_type == "report_post":
        target_links = state.get("post_links", [])
    else:
        target_links = [state.get("target", "")]

    for target_idx, target in enumerate(target_links):
        for session_idx, (admin_id_str, filename) in enumerate(sessions):
            if not ACTIVE_OPERATIONS.get(user_id, False):
                await event.reply("🛑 عملیات لغو شد" if lang == "fa" else "🛑 Operation cancelled")
                if group_msg_id:
                    try:
                        await event.client.edit_message(
                            REPORT_GROUP_ID, group_msg_id,
                            "🛑 **عملیات لغو شد**\n\n"
                            "👤 کاربر: `" + str(user_id) + "`\n"
                            "🎯 مقصد: `" + str(target_display) + "`\n"
                            "✅ موفق: " + str(total_success) + "\n"
                            "❌ ناموفق: " + str(total_fail) + "\n\n"
                            "🛑 لغو شده توسط کاربر یا مالک"
                        )
                    except:
                        pass
                ACTIVE_OPERATIONS[user_id] = False
                return

            path = os.path.join(ADMIN_SESSIONS_DIR, admin_id_str, filename)
            phone_disp = filename.replace('.session', '')
            try:
                with open(path, 'r') as f:
                    session_str = f.read().strip()
                if not session_str:
                    total_fail += 1
                    fail_accounts.append(phone_disp + " (خالی)")
                    continue

                client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
                await client.connect()
                if not await client.is_user_authorized():
                    total_fail += 1
                    fail_accounts.append(phone_disp + " (غیرمجاز)")
                    await client.disconnect()
                    continue

                try:
                    entity = await resolve_entity(client, target, op_type)
                    
                    if entity:
                        if should_join and op_type in ["report", "report_post"]:
                            await join_channel_smart(client, entity)
                            await asyncio.sleep(random.uniform(1, 3))
                        
                        s, f = await perform_real_report(client, entity, reason_obj, custom_msg, count_per_account, delay_seconds)
                        total_success += s
                        total_fail += f
                        if s > 0:
                            success_accounts.append(phone_disp)
                        else:
                            fail_accounts.append(phone_disp)
                        
                        data_db = load_data()
                        data_db["total_reports"] = data_db.get("total_reports", 0) + s
                        save_data(data_db)
                    else:
                        total_fail += 1
                        fail_accounts.append(phone_disp + " (هدف یافت نشد)")
                        errors_list.append(filename + ": Entity not found")

                except Exception as e:
                    total_fail += 1
                    fail_accounts.append(phone_disp + " (خطا)")
                    errors_list.append(filename + ": " + str(e)[:50])
                    logger.error("Session " + filename + " error: " + str(e))

                await client.disconnect()
                await asyncio.sleep(random.uniform(2, 5))

            except Exception as e:
                total_fail += 1
                fail_accounts.append(phone_disp + " (خطا فایل)")
                errors_list.append(filename + ": " + str(e)[:50])

            now = datetime.now()
            # آپدیت گروه هر 30 ثانیه
            if (now - last_group_update).total_seconds() >= 30:
                if group_msg_id:
                    await update_report_group_msg(
                        event.client, group_msg_id, user_id,
                        target_display, reason_name, total_success, total_fail
                    )
                    last_group_update = now
            # آپدیت چت کاربر هر 5 دقیقه
            if (now - last_progress_update).total_seconds() >= 300:
                elapsed = now - operation_start
                total_accounts = len(sessions) * len(target_links)
                processed_accounts = (target_idx * len(sessions)) + session_idx + 1
                progress_percent = int(processed_accounts * 100 / total_accounts) if total_accounts > 0 else 0
                
                progress_msg = (
                    "📊 **گزارش پیشرفت**\n" +
                    "⏱ زمان سپری شده: " + format_time(int(elapsed.total_seconds())) + "\n" +
                    "📈 پیشرفت: " + str(progress_percent) + "%\n" +
                    "✅ ریپورت موفق: " + str(total_success) + "\n" +
                    "❌ ریپورت ناموفق: " + str(total_fail) + "\n" +
                    "👥 اکانت‌های پردازش شده: " + str(processed_accounts) + "/" + str(total_accounts)
                    if lang == "fa" else
                    "📊 **Progress Report**\n" +
                    "⏱ Elapsed: " + format_time(int(elapsed.total_seconds())) + "\n" +
                    "📈 Progress: " + str(progress_percent) + "%\n" +
                    "✅ Success: " + str(total_success) + "\n" +
                    "❌ Failed: " + str(total_fail) + "\n" +
                    "👥 Processed: " + str(processed_accounts) + "/" + str(total_accounts)
                )
                await event.reply(progress_msg, buttons=cancel_keyboard(lang))
                last_progress_update = now

    total_time = datetime.now() - operation_start
    result = (
        "📊 **عملیات ریپورت پایان یافت**\n\n" +
        "🎯 هدف: " + state.get('target', 'Multiple posts') + "\n" +
        "📝 دلیل: " + reason_name + "\n" +
        "👥 اکانت‌ها: " + str(len(sessions)) + "\n" +
        "🔢 ریپورت/اکانت: " + str(count_per_account) + "\n" +
        "✅ موفق: " + str(total_success) + "\n" +
        "❌ ناموفق: " + str(total_fail) + "\n" +
        "⏱ زمان کل: " + format_time(int(total_time.total_seconds()))
        if lang == "fa" else
        "📊 **Report Operation Complete**\n\n" +
        "🎯 Target: " + state.get('target', 'Multiple posts') + "\n" +
        "📝 Reason: " + reason_name + "\n" +
        "👥 Accounts: " + str(len(sessions)) + "\n" +
        "🔢 Reports/Account: " + str(count_per_account) + "\n" +
        "✅ Success: " + str(total_success) + "\n" +
        "❌ Failed: " + str(total_fail) + "\n" +
        "⏱ Total Time: " + format_time(int(total_time.total_seconds()))
    )

    if errors_list and len(errors_list) <= 5:
        result += "\n\n⚠️ خطاها:\n" + "\n".join(errors_list[:5]) if lang == "fa" else "\n\n⚠️ Errors:\n" + "\n".join(errors_list[:5])

    REPORT_OPERATIONS[op_id] = {
        "user_id": user_id,
        "success_accounts": success_accounts,
        "fail_accounts": fail_accounts,
        "lang": lang
    }

    await event.reply(result, buttons=result_details_keyboard(lang, op_id))
    
    if group_msg_id:
        try:
            final_text = (
                "📊 **گزارش عملیات ریپورت** ✅ (پایان یافت)\n\n"
                "👤 کاربر: `" + str(user_id) + "`\n"
                "🎯 مقصد: `" + str(target_display) + "`\n"
                "📝 دلیل: " + reason_name + "\n"
                "✅ موفق: " + str(total_success) + "\n"
                "❌ ناموفق: " + str(total_fail) + "\n"
                "⏱ زمان: " + format_time(int(total_time.total_seconds()))
            )
            await event.client.edit_message(
                REPORT_GROUP_ID, group_msg_id, final_text, buttons=None
            )
        except Exception as e:
            logger.error("Final group update error: " + str(e))
    
    if not is_owner(user_id):
        for owner_id in OWNER_IDS:
            try:
                await event.client.send_message(
                    owner_id,
                    "📢 **گزارش ریپورت**\n\n" +
                    "👤 ادمین: " + str(user_id) + "\n" +
                    "🎯 هدف: " + state.get('target', 'Multiple posts') + "\n" +
                    "📝 دلیل: " + reason_name + "\n" +
                    "👥 تعداد اکانت: " + str(len(sessions)) + "\n" +
                    "✅ موفق: " + str(total_success) + "\n" +
                    "❌ ناموفق: " + str(total_fail) + "\n" +
                    "⏱ زمان: " + format_time(int(total_time.total_seconds()))
                )
            except:
                pass
    
    ACTIVE_OPERATIONS[user_id] = False

# =============== HANDLER FOR OWNER SUPPORT ACTIONS ===============

async def support_action_handler(event):
    data_str = event.data.decode('utf-8')
    user_id = event.sender_id

    if data_str.startswith("sup_block_"):
        if not is_owner(user_id):
            await event.answer("⛔ Unauthorized", alert=True)
            return
        target = int(data_str.replace("sup_block_", ""))
        data_db = load_data()
        data_db.setdefault("blocked", [])
        if target not in data_db["blocked"]:
            data_db["blocked"].append(target)
            save_data(data_db)
        await event.answer("🚫 کاربر بلاک شد", alert=True)
        try:
            await event.edit(event.message.text + "\n\n🚫 بلاک شده")
        except:
            pass
        return

    if data_str.startswith("sup_reply_"):
        if not is_owner(user_id):
            await event.answer("⛔ Unauthorized", alert=True)
            return
        target = int(data_str.replace("sup_reply_", ""))
        USER_STATE[user_id] = {"action": "reply_user", "step": "waiting_reply", "target_user": target}
        await event.answer("✍️ پاسخ خود را بنویسید و ارسال کنید", alert=True)
        return

async def main():
    bot = TelegramClient("bot_session", API_ID, API_HASH)
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("Bot started")

    bot.add_event_handler(start_handler, events.NewMessage(pattern=r'/start(?: (.+))?'))
    bot.add_event_handler(callback_handler, events.CallbackQuery())
    bot.add_event_handler(support_action_handler, events.CallbackQuery(pattern=r'^(sup_block_|sup_reply_)'))
    bot.add_event_handler(message_handler, events.NewMessage(func=lambda e: e.is_private and not e.text.startswith('/')))

    logger.info("SHIKH REPORTER is running...")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
