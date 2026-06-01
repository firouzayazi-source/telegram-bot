import os
import json
import time
import asyncio
import logging
import aiosqlite
import jdatetime
import pytz
from datetime import datetime
from collections import defaultdict, deque
import aiofiles

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("ALL_PROXY", None)
os.environ["NO_PROXY"] = "*"

TOKEN          = os.getenv("BOT_TOKEN", "8792062012:AAGXforSa1IY45AuC-yOHs2PsdzudvtdD44")
ADMIN_ID       = int(os.getenv("ADMIN_ID", "638469407"))
DATA_FILE      = "data.json"
DB_FILE        = "users.db"
BANNER_FILE    = "banner.json"
WORKHOURS_FILE = "workhours.json"
BUTTONS_FILE   = "buttons.json"
SETTINGS_FILE  = "settings.json"
STATS_FILE     = "stats.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

IRAN_TZ = pytz.timezone("Asia/Tehran")

def shamsi_now():
    now = datetime.now(IRAN_TZ)
    return jdatetime.datetime.fromgregorian(datetime=now).strftime("%Y/%m/%d - %H:%M")

def gregorian_now():
    return datetime.now(IRAN_TZ).strftime("%Y-%m-%d %H:%M:%S")

# ======================================
# MENU
# ======================================
MENU_ITEMS = {
    "1": "🌐 شبکه‌های اجتماعی",
    "2": "🌐 سایت استوک لند",
    "3": "💰 شرایط اقساط",
    "4": "📞 پشتیبانی",
    "5": "📍 آدرس فروشگاه",
}
SECTION_NAMES = {
    "welcome": "🏠 خوش‌آمدگویی",
    "1": "🌐 شبکه‌های اجتماعی",
    "2": "🌐 سایت استوک لند",
    "3": "💰 شرایط اقساط",
    "4": "📞 پشتیبانی",
    "5": "📍 آدرس فروشگاه",
    "workhours_page": "🕐 ساعت کاری",
}

DAY_NAMES = {
    "0":"شنبه","1":"یکشنبه","2":"دوشنبه",
    "3":"سه‌شنبه","4":"چهارشنبه","5":"پنجشنبه","6":"جمعه"
}

# ======================================
# GLOBALS
# ======================================
responses = None
banners   = {}
workhours = {}
buttons   = {}
settings  = {}
stats     = {}

DEFAULT_WORKHOURS = {
    "enabled": True,
    "schedule": {
        "0": {"open": True,  "shifts": [{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
        "1": {"open": True,  "shifts": [{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
        "2": {"open": True,  "shifts": [{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
        "3": {"open": True,  "shifts": [{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
        "4": {"open": True,  "shifts": [{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
        "5": {"open": True,  "shifts": [{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
        "6": {"open": True,  "shifts": [{"from":"17:00","to":"23:00"}]},
    },
    "msg_open":   "✅ الان باز است",
    "msg_closed": "🔴 الان بسته است",
}

DEFAULT_SETTINGS = {
    "show_workhours_in_sections": True,   # نمایش ساعت کاری زیر همه بخش‌ها
    "show_datetime_footer":       True,   # نمایش تاریخ و ساعت پایین پیام‌ها
    "show_workhours_menu":        True,   # نمایش گزینه ساعت کاری در منوی کاربر
    "notify_new_user":            False,  # اعلان عضو جدید به ادمین
    "store_open":                 True,   # باز/بسته دستی فروشگاه
}

# تنظیم نمایش ساعت کاری برای هر بخش جداگانه
DEFAULT_SECTION_WORKHOURS = {
    "welcome":        True,
    "1":              True,
    "2":              True,
    "3":              True,
    "4":              True,
    "5":              True,
    "workhours_page": False,
}

# ======================================
# HELPERS
# ======================================
def get_banner(key):
    if key not in banners:
        banners[key] = {"file_id": None, "active": False}
    return banners[key]

def get_section_buttons(key):
    if key not in buttons:
        buttons[key] = {"enabled": True, "items": []}
    return buttons[key]

def get_setting(key):
    return settings.get(key, DEFAULT_SETTINGS.get(key, False))

def get_section_wh(key):
    """آیا نمایش ساعت کاری برای این بخش فعاله؟"""
    if not get_setting("show_workhours_in_sections"):
        return False
    sec_wh = settings.get("section_workhours", DEFAULT_SECTION_WORKHOURS.copy())
    return sec_wh.get(key, True)

def set_section_wh(key, value):
    if "section_workhours" not in settings:
        settings["section_workhours"] = DEFAULT_SECTION_WORKHOURS.copy()
    settings["section_workhours"][key] = value

def is_open_now():
    if not get_setting("store_open"):       return False
    if not workhours.get("enabled", True):  return True
    now     = datetime.now(IRAN_TZ)
    j_now   = jdatetime.datetime.fromgregorian(datetime=now)
    day     = workhours.get("schedule", {}).get(str(j_now.weekday()), {})
    if not day.get("open", False): return False
    now_str = now.strftime("%H:%M")
    for shift in day.get("shifts", []):
        if shift["from"] <= now_str <= shift["to"]: return True
    return False

def today_workhours_text():
    """متن ساعت کاری امروز به فارسی"""
    if not workhours.get("enabled", True):
        return None
    now    = datetime.now(IRAN_TZ)
    j_now  = jdatetime.datetime.fromgregorian(datetime=now)
    wd     = str(j_now.weekday())
    day    = workhours.get("schedule", {}).get(wd, {})
    name   = DAY_NAMES.get(wd, "")
    status = workhours.get("msg_open","✅ الان باز است") if is_open_now() else workhours.get("msg_closed","🔴 الان بسته است")

    if not day.get("open"):
        return f"🕐 امروز {name}: تعطیل\n{status}"

    shifts = day.get("shifts", [])
    shifts_text = "  و  ".join([f"{s['from']} تا {s['to']}" for s in shifts])
    return f"🕐 امروز {name}: {shifts_text}\n{status}"

def build_message(title, content, section_key):
    """ساختن پیام کامل با footer و ساعت کاری"""
    footer = f"\n🕒 {shamsi_now()}" if get_setting("show_datetime_footer") else ""
    wh_text = today_workhours_text() if get_section_wh(section_key) else None

    lines = [f"📌 {title}", "──────────────", content, "──────────────"]
    if wh_text:
        lines.append(wh_text)
        lines.append("──────────────")
    lines.append(footer.strip() if footer.strip() else "")
    return "\n".join([l for l in lines if l != ""])

def workhours_full_summary():
    """جدول کامل ساعت کاری"""
    lines = []
    for k, name in DAY_NAMES.items():
        day = workhours.get("schedule", {}).get(k, {})
        if not day.get("open"):
            lines.append(f"• {name}: تعطیل")
        else:
            shifts = "  و  ".join([f"{s['from']} تا {s['to']}" for s in day.get("shifts", [])])
            lines.append(f"• {name}: {shifts}")
    return "\n".join(lines)

def progress_bar(value, total, length=8):
    if total == 0: return "░" * length
    filled = int(length * value / total)
    return "▓" * filled + "░" * (length - filled)

def section_page_text(key):
    name    = SECTION_NAMES.get(key, key)
    content = responses.get(key, "") if responses else ""
    b       = get_banner(key)
    sec     = get_section_buttons(key)
    wh_on   = get_section_wh(key)
    has_text   = "✅ تنظیم شده"  if content and content not in ("تنظیم نشده","") else "❌ ندارد"
    has_banner = "✅ فعال"        if b.get("active") and b.get("file_id") else ("⏸ غیرفعال" if b.get("file_id") else "➕ ندارد")
    btn_count  = len(sec.get("items", []))
    btn_en     = "✅" if sec.get("enabled") else "❌"
    wh_st      = "✅ نمایش دارد" if wh_on else "❌ نمایش ندارد"
    return (
        f"📋 بخش: {name}\n──────────────\n"
        f"✏️ متن: {has_text}\n"
        f"🖼 بنر: {has_banner}\n"
        f"🔘 دکمه‌ها: {btn_count} عدد {btn_en}\n"
        f"🕐 ساعت کاری: {wh_st}\n"
        f"──────────────"
    )

# ======================================
# STATS
# ======================================
async def record_stat(section_key):
    if section_key not in stats:
        stats[section_key] = 0
    stats[section_key] += 1
    await save_stats()

async def load_stats():
    global stats
    try:
        async with aiofiles.open(STATS_FILE,"r",encoding="utf-8") as f:
            stats = json.loads(await f.read())
    except Exception:
        stats = {}

async def save_stats():
    try:
        async with aiofiles.open(STATS_FILE,"w",encoding="utf-8") as f:
            await f.write(json.dumps(stats, ensure_ascii=False, indent=4))
    except Exception as e:
        logger.error(f"save_stats: {e}")

# ======================================
# LOAD / SAVE
# ======================================
async def load_data():
    global responses
    try:
        async with aiofiles.open(DATA_FILE,"r",encoding="utf-8") as f:
            responses = json.loads(await f.read())
    except Exception:
        responses = MENU_ITEMS.copy()
        responses["welcome"] = "✨ خوش آمدید به ربات استوک لند"

async def save_data():
    try:
        async with aiofiles.open(DATA_FILE,"w",encoding="utf-8") as f:
            await f.write(json.dumps(responses, ensure_ascii=False, indent=4))
    except Exception as e:
        logger.error(f"save_data: {e}")

async def load_banners():
    global banners
    try:
        async with aiofiles.open(BANNER_FILE,"r",encoding="utf-8") as f:
            data = json.loads(await f.read())
            if isinstance(data, dict): banners = data
    except Exception:
        banners = {}
    for key in SECTION_NAMES:
        if key not in banners:
            banners[key] = {"file_id": None, "active": False}

async def save_banners():
    try:
        async with aiofiles.open(BANNER_FILE,"w",encoding="utf-8") as f:
            await f.write(json.dumps(banners, ensure_ascii=False, indent=4))
    except Exception as e:
        logger.error(f"save_banners: {e}")

async def load_workhours():
    global workhours
    try:
        async with aiofiles.open(WORKHOURS_FILE,"r",encoding="utf-8") as f:
            workhours = json.loads(await f.read())
    except Exception:
        workhours = DEFAULT_WORKHOURS.copy()
        await save_workhours()

async def save_workhours():
    try:
        async with aiofiles.open(WORKHOURS_FILE,"w",encoding="utf-8") as f:
            await f.write(json.dumps(workhours, ensure_ascii=False, indent=4))
    except Exception as e:
        logger.error(f"save_workhours: {e}")

async def load_buttons():
    global buttons
    try:
        async with aiofiles.open(BUTTONS_FILE,"r",encoding="utf-8") as f:
            buttons = json.loads(await f.read())
    except Exception:
        buttons = {}
    for key in SECTION_NAMES:
        if key not in buttons:
            buttons[key] = {"enabled": True, "items": []}

async def save_buttons():
    try:
        async with aiofiles.open(BUTTONS_FILE,"w",encoding="utf-8") as f:
            await f.write(json.dumps(buttons, ensure_ascii=False, indent=4))
    except Exception as e:
        logger.error(f"save_buttons: {e}")

async def load_settings():
    global settings
    try:
        async with aiofiles.open(SETTINGS_FILE,"r",encoding="utf-8") as f:
            settings = json.loads(await f.read())
    except Exception:
        settings = DEFAULT_SETTINGS.copy()
        settings["section_workhours"] = DEFAULT_SECTION_WORKHOURS.copy()
        await save_settings()

async def save_settings():
    try:
        async with aiofiles.open(SETTINGS_FILE,"w",encoding="utf-8") as f:
            await f.write(json.dumps(settings, ensure_ascii=False, indent=4))
    except Exception as e:
        logger.error(f"save_settings: {e}")

# ======================================
# DATABASE
# ======================================
db = None

async def init_db():
    global db
    db = await aiosqlite.connect(DB_FILE)
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        joined_at TEXT, last_seen TEXT, is_blocked INTEGER DEFAULT 0)""")
    try:
        await db.execute("ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0")
    except Exception:
        pass
    await db.commit()

async def save_user(user):
    now = gregorian_now()
    await db.execute("INSERT OR IGNORE INTO users VALUES (?,?,?,?,?,0)",
        (user.id, user.username or "", user.first_name or "", now, now))
    await db.execute("UPDATE users SET username=?,first_name=?,last_seen=? WHERE user_id=?",
        (user.username or "", user.first_name or "", now, user.id))
    await db.commit()

async def get_all_users():
    async with db.execute("SELECT user_id FROM users WHERE is_blocked=0") as c:
        return [r[0] for r in await c.fetchall()]

async def is_blocked(user_id):
    async with db.execute("SELECT is_blocked FROM users WHERE user_id=?", (user_id,)) as c:
        row = await c.fetchone()
        return bool(row and row[0])

async def block_user(user_id):
    await db.execute("UPDATE users SET is_blocked=1 WHERE user_id=?", (user_id,))
    await db.commit()

async def unblock_user(user_id):
    await db.execute("UPDATE users SET is_blocked=0 WHERE user_id=?", (user_id,))
    await db.commit()

async def search_users(query):
    q = f"%{query}%"
    async with db.execute(
        "SELECT user_id,first_name,username,last_seen,is_blocked FROM users "
        "WHERE first_name LIKE ? OR username LIKE ? OR CAST(user_id AS TEXT) LIKE ? "
        "ORDER BY last_seen DESC LIMIT 15", (q,q,q)
    ) as c:
        return await c.fetchall()

async def get_users_page(offset=0, limit=15, filter_type="all"):
    filters = {
        "today":   "WHERE DATE(last_seen)=DATE('now','localtime')",
        "week":    "WHERE last_seen>=datetime('now','-7 days','localtime')",
        "blocked": "WHERE is_blocked=1",
    }
    q = filters.get(filter_type, "")
    async with db.execute(
        f"SELECT user_id,first_name,username,last_seen,is_blocked FROM users {q} "
        f"ORDER BY last_seen DESC LIMIT {limit} OFFSET {offset}"
    ) as c:
        return await c.fetchall()

async def total_users():
    async with db.execute("SELECT COUNT(*) FROM users") as c:
        return (await c.fetchone())[0]

async def today_users():
    async with db.execute("SELECT COUNT(*) FROM users WHERE DATE(last_seen)=DATE('now','localtime')") as c:
        return (await c.fetchone())[0]

async def week_users():
    async with db.execute("SELECT COUNT(*) FROM users WHERE last_seen>=datetime('now','-7 days','localtime')") as c:
        return (await c.fetchone())[0]

async def month_users():
    async with db.execute("SELECT COUNT(*) FROM users WHERE last_seen>=datetime('now','-30 days','localtime')") as c:
        return (await c.fetchone())[0]

async def new_today():
    async with db.execute("SELECT COUNT(*) FROM users WHERE DATE(joined_at)=DATE('now','localtime')") as c:
        return (await c.fetchone())[0]

async def blocked_count():
    async with db.execute("SELECT COUNT(*) FROM users WHERE is_blocked=1") as c:
        return (await c.fetchone())[0]

# ======================================
# ANTI-SPAM
# ======================================
WINDOW, LIMIT, BLOCK = 10, 7, 60
spam         = defaultdict(lambda: deque(maxlen=LIMIT))
blocked_temp = {}

async def anti_spam(user_id):
    if user_id == ADMIN_ID: return True
    if await is_blocked(user_id): return False
    now = time.time()
    if user_id in blocked_temp and blocked_temp[user_id] > now: return False
    q = spam[user_id]
    q.append(now)
    if len(q) >= LIMIT and (now - q[0]) <= WINDOW:
        blocked_temp[user_id] = now + BLOCK
        return False
    return True

# ======================================
# KEYBOARDS
# ======================================
def main_menu():
    keys = list(MENU_ITEMS.keys())
    rows = []
    for i in range(0, len(keys), 2):
        row = [MENU_ITEMS[keys[i]]]
        if i+1 < len(keys): row.append(MENU_ITEMS[keys[i+1]])
        rows.append(row)
    if get_setting("show_workhours_menu"):
        rows.append(["🕐 ساعت کاری"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def admin_menu():
    is_open = is_open_now()
    toggle  = "🔴 بستن فروشگاه" if is_open else "🟢 باز کردن فروشگاه"
    st_icon = "🟢" if is_open else "🔴"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 داشبورد",       callback_data="dash"),
         InlineKeyboardButton("👥 کاربران",        callback_data="users_menu")],
        [InlineKeyboardButton("📋 مدیریت بخش‌ها", callback_data="sections")],
        [InlineKeyboardButton("🕐 ساعت کاری",     callback_data="workhours_menu"),
         InlineKeyboardButton("⚙️ تنظیمات",       callback_data="settings_menu")],
        [InlineKeyboardButton("📢 پخش همگانی",    callback_data="broadcast")],
        [InlineKeyboardButton("💾 بک‌آپ",         callback_data="backup"),
         InlineKeyboardButton("📊 آمار بخش‌ها",   callback_data="sections_stats")],
        [InlineKeyboardButton(f"{st_icon} {toggle}", callback_data="quick_toggle")],
    ])

def back_admin():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت به پنل", callback_data="back_to_admin")]])

def admin_cancel_menu():
    return ReplyKeyboardMarkup([["❌ لغو عملیات"]], resize_keyboard=True)

# ── کاربران ──
def users_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 همه",    callback_data="ulist_all_0"),
         InlineKeyboardButton("📅 امروز", callback_data="ulist_today_0")],
        [InlineKeyboardButton("📆 هفته",  callback_data="ulist_week_0"),
         InlineKeyboardButton("🚫 بلاک",  callback_data="ulist_blocked_0")],
        [InlineKeyboardButton("🔍 جستجو", callback_data="users_search")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="back_to_admin")],
    ])

def users_list_kb(rows, offset, filter_type, total):
    btns = []
    for r in rows:
        bl   = "🚫 " if r[4] else ""
        name = r[1] or "—"
        btns.append([InlineKeyboardButton(f"{bl}{name} | {r[0]}", callback_data=f"uview_{r[0]}")])
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"ulist_{filter_type}_{offset-15}"))
    if offset+15 < total:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"ulist_{filter_type}_{offset+15}"))
    if nav: btns.append(nav)
    btns.append([InlineKeyboardButton("🔙 برگشت", callback_data="users_menu")])
    return InlineKeyboardMarkup(btns)

def user_detail_kb(user_id, is_bl):
    action = "✅ رفع بلاک" if is_bl else "🚫 بلاک کردن"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(action, callback_data=f"utoggle_{user_id}")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="users_menu")],
    ])

# ── بخش‌ها ──
def sections_list_kb():
    btns = []
    for key, name in SECTION_NAMES.items():
        if key == "workhours_page": continue
        content  = responses.get(key, "") if responses else ""
        b        = get_banner(key)
        sec      = get_section_buttons(key)
        t_icon   = "✅" if content and content not in ("تنظیم نشده","") else "➕"
        b_icon   = "🖼" if b.get("active") and b.get("file_id") else "○"
        btn_icon = f"🔘{len(sec.get('items',[]))}" if sec.get("enabled") else "○"
        btns.append([InlineKeyboardButton(
            f"{name}  {t_icon}{b_icon}{btn_icon}", callback_data=f"sec_{key}")])
    btns.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_to_admin")])
    return InlineKeyboardMarkup(btns)

def section_kb(key):
    b      = get_banner(key)
    sec    = get_section_buttons(key)
    wh_on  = get_section_wh(key)
    ban_st = "🖼✅" if b.get("active") and b.get("file_id") else ("🖼⏸" if b.get("file_id") else "🖼➕")
    btn_st = f"🔘✅({len(sec.get('items',[]))})" if sec.get("enabled") else f"🔘❌({len(sec.get('items',[]))})"
    wh_st  = "🕐✅ ساعت کاری" if wh_on else "🕐❌ ساعت کاری"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ ویرایش متن",   callback_data=f"sec_text_{key}")],
        [InlineKeyboardButton(f"{ban_st} بنر",    callback_data=f"sec_banner_{key}")],
        [InlineKeyboardButton(f"{btn_st} دکمه‌ها",callback_data=f"sec_btns_{key}")],
        [InlineKeyboardButton(wh_st,              callback_data=f"sec_wh_{key}")],
        [InlineKeyboardButton("🔙 برگشت",        callback_data="sections")],
    ])

def banner_kb(key):
    b      = get_banner(key)
    toggle = "🔴 غیرفعال" if b.get("active") else "🟢 فعال کردن"
    btns   = [
        [InlineKeyboardButton("📤 آپلود / تغییر", callback_data=f"ban_up_{key}")],
        [InlineKeyboardButton(toggle,             callback_data=f"ban_tg_{key}")],
    ]
    if b.get("file_id"):
        btns.append([InlineKeyboardButton("🗑 حذف بنر", callback_data=f"ban_dl_{key}")])
    btns.append([InlineKeyboardButton("🔙 برگشت", callback_data=f"sec_{key}")])
    return InlineKeyboardMarkup(btns)

def section_btns_kb(key):
    sec    = get_section_buttons(key)
    toggle = "🔴 غیرفعال همه" if sec.get("enabled") else "🟢 فعال همه"
    btns   = [[InlineKeyboardButton(toggle, callback_data=f"btn_tg_{key}")]]
    for item in sec.get("items", []):
        btns.append([
            InlineKeyboardButton(f"🔗 {item['title']}", callback_data=f"btn_edt_{key}_{item['id']}"),
            InlineKeyboardButton("🗑",                  callback_data=f"btn_del_{key}_{item['id']}"),
        ])
    btns.append([InlineKeyboardButton("➕ دکمه جدید", callback_data=f"btn_add_{key}")])
    btns.append([InlineKeyboardButton("🔙 برگشت",    callback_data=f"sec_{key}")])
    return InlineKeyboardMarkup(btns)

# ── ساعت کاری ──
def workhours_kb():
    en     = workhours.get("enabled", True)
    toggle = "🔴 غیرفعال کردن" if en else "🟢 فعال کردن"
    btns   = [[InlineKeyboardButton(toggle, callback_data="wh_toggle")]]
    for k, name in DAY_NAMES.items():
        day = workhours.get("schedule", {}).get(k, {})
        st  = "✅" if day.get("open") else "❌"
        btns.append([InlineKeyboardButton(f"{st} {name}", callback_data=f"wh_day_{k}")])
    btns.append([InlineKeyboardButton("✏️ پیام باز بودن",  callback_data="wh_msg_open")])
    btns.append([InlineKeyboardButton("✏️ پیام بسته بودن", callback_data="wh_msg_closed")])
    btns.append([InlineKeyboardButton("🔙 برگشت",          callback_data="back_to_admin")])
    return InlineKeyboardMarkup(btns)

def workhours_day_kb(day_key):
    day    = workhours.get("schedule", {}).get(day_key, {})
    toggle = "🔴 تعطیل کردن" if day.get("open") else "🟢 باز کردن"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle,               callback_data=f"wh_dtg_{day_key}")],
        [InlineKeyboardButton("✏️ تنظیم ساعت‌ها", callback_data=f"wh_shifts_{day_key}")],
        [InlineKeyboardButton("🔙 برگشت",          callback_data="workhours_menu")],
    ])

# ── تنظیمات ──
def settings_kb():
    def t(key): return "✅" if get_setting(key) else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{t('show_workhours_in_sections')} ساعت کاری در بخش‌ها",
                              callback_data="stg_show_workhours_in_sections")],
        [InlineKeyboardButton(f"{t('show_datetime_footer')} تاریخ و ساعت پایین پیام‌ها",
                              callback_data="stg_show_datetime_footer")],
        [InlineKeyboardButton(f"{t('show_workhours_menu')} گزینه ساعت کاری در منو",
                              callback_data="stg_show_workhours_menu")],
        [InlineKeyboardButton(f"{t('notify_new_user')} اعلان عضو جدید",
                              callback_data="stg_notify_new_user")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="back_to_admin")],
    ])

# ── کاربر: دکمه‌های بخش ──
def user_section_kb(key):
    sec = get_section_buttons(key)
    if not sec.get("enabled", True): return None
    items = [x for x in sec.get("items", []) if x.get("url")]
    if not items: return None
    btns = []
    row  = []
    for i, item in enumerate(items):
        row.append(InlineKeyboardButton(item["title"], url=item["url"]))
        if len(row) == 2 or i == len(items)-1:
            btns.append(row); row = []
    return InlineKeyboardMarkup(btns) if btns else None

# ======================================
# SEND WITH BANNER
# ======================================
async def send_with_banner(msg, text, key, reply_markup=None):
    b = get_banner(key)
    if b.get("active") and b.get("file_id"):
        try:
            await msg.reply_photo(photo=b["file_id"], caption=text, reply_markup=reply_markup)
            return
        except Exception as e:
            logger.error(f"banner [{key}]: {e}")
    await msg.reply_text(text, reply_markup=reply_markup)

# ======================================
# BROADCAST
# ======================================
async def send_broadcast(context, text, photo_id=None):
    users   = await get_all_users()
    total   = len(users)
    success = failed = 0
    status  = await context.bot.send_message(ADMIN_ID, f"📢 شروع پخش به {total} کاربر...")
    for i, uid in enumerate(users, 1):
        try:
            if photo_id: await context.bot.send_photo(uid, photo=photo_id, caption=text)
            else:        await context.bot.send_message(uid, text)
            success += 1
        except Exception:
            failed += 1
        if i % 10 == 0 or i == total:
            try: await status.edit_text(f"📢 پخش...\n✅ {success} | ❌ {failed} | {i}/{total}")
            except Exception: pass
        await asyncio.sleep(0.2)
    await status.edit_text(f"✅ پخش تمام شد!\nموفق: {success} | شکست: {failed}")

# ======================================
# BACKUP
# ======================================
async def send_backup(bot):
    now   = shamsi_now().replace("/","-").replace(" ","_").replace(":","-")
    files = [
        (DATA_FILE,      f"backup_data_{now}.json"),
        (BANNER_FILE,    f"backup_banner_{now}.json"),
        (WORKHOURS_FILE, f"backup_workhours_{now}.json"),
        (BUTTONS_FILE,   f"backup_buttons_{now}.json"),
        (SETTINGS_FILE,  f"backup_settings_{now}.json"),
        (STATS_FILE,     f"backup_stats_{now}.json"),
        (DB_FILE,        f"backup_users_{now}.db"),
    ]
    await bot.send_message(ADMIN_ID, f"💾 بک‌آپ کامل — {shamsi_now()}")
    for filepath, filename in files:
        try:
            async with aiofiles.open(filepath,"rb") as f:
                content = await f.read()
            await bot.send_document(ADMIN_ID, document=content, filename=filename)
        except Exception as e:
            logger.error(f"backup {filepath}: {e}")

# ======================================
# HANDLERS
# ======================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user   = update.effective_user
    is_new = False
    async with db.execute("SELECT user_id FROM users WHERE user_id=?", (user.id,)) as c:
        is_new = (await c.fetchone()) is None
    await save_user(user)

    if get_setting("notify_new_user") and is_new:
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"🆕 کاربر جدید!\n👤 {user.first_name or '—'}\n"
                f"{'@'+user.username if user.username else '—'}\n🆔 {user.id}"
            )
        except Exception: pass

    welcome_text = responses.get("welcome", "✨ خوش آمدید به ربات استوک لند")
    full_text    = build_message("خوش‌آمدگویی", welcome_text, "welcome")
    kb           = user_section_kb("welcome")
    await send_with_banner(update.message, full_text, "welcome", reply_markup=kb or main_menu())

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ دسترسی ندارید")
    await update.message.reply_text("👑 پنل مدیریت", reply_markup=admin_menu())

# ======================================
# CALLBACKS
# ======================================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID: return
    data = query.data

    if data == "back_to_admin":
        await query.message.edit_text("👑 پنل مدیریت", reply_markup=admin_menu())

    elif data == "quick_toggle":
        settings["store_open"] = not get_setting("store_open")
        await save_settings()
        st = "🟢 فروشگاه باز شد" if settings["store_open"] else "🔴 فروشگاه بسته شد"
        await query.answer(st, show_alert=True)
        await query.message.edit_text("👑 پنل مدیریت", reply_markup=admin_menu())

    elif data == "dash":
        t  = await total_users()
        d  = await today_users()
        w  = await week_users()
        m  = await month_users()
        nt = await new_today()
        bl = await blocked_count()
        op = "🟢 باز" if is_open_now() else "🔴 بسته"
        wh_text = today_workhours_text() or ""
        await query.message.edit_text(
            f"📊 داشبورد — {shamsi_now()}\n"
            f"══════════════\n"
            f"👥 کل: {t}  |  🚫 بلاک: {bl}\n"
            f"══════════════\n"
            f"🆕 عضو امروز: {nt}\n"
            f"📅 فعال امروز: {d}  {progress_bar(d,t)}\n"
            f"📆 فعال هفته: {w}  {progress_bar(w,t)}\n"
            f"🗓 فعال ماه: {m}  {progress_bar(m,t)}\n"
            f"══════════════\n"
            f"🏪 وضعیت: {op}\n"
            f"{wh_text}",
            reply_markup=admin_menu())

    elif data == "sections_stats":
        if not stats:
            await query.message.edit_text("📊 هنوز آماری ثبت نشده.", reply_markup=back_admin()); return
        sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)
        total_views  = sum(stats.values())
        lines = ["📊 آمار بازدید بخش‌ها:\n──────────────"]
        for key, count in sorted_stats:
            name = SECTION_NAMES.get(key, key)
            pct  = int(100 * count / total_views) if total_views else 0
            bar  = progress_bar(count, total_views, 8)
            lines.append(f"{name}\n  {bar} {count} بازدید ({pct}%)")
        lines.append(f"──────────────\nمجموع: {total_views}")
        await query.message.edit_text("\n".join(lines), reply_markup=back_admin())

    elif data == "broadcast":
        context.user_data["mode"] = "broadcast"
        await query.message.reply_text(
            "📢 پیام پخش را ارسال کنید:\n• فقط متن → متنی\n• عکس+کپشن → با تصویر",
            reply_markup=admin_cancel_menu())

    elif data == "backup":
        await query.message.edit_text("💾 در حال ارسال بک‌آپ کامل...", reply_markup=back_admin())
        await send_backup(query.message._bot)
        await query.message.edit_text("✅ بک‌آپ کامل ارسال شد.", reply_markup=back_admin())

    # ── کاربران ──
    elif data == "users_menu":
        t  = await total_users()
        bl = await blocked_count()
        await query.message.edit_text(
            f"👥 مدیریت کاربران\n──────────────\nکل: {t} | بلاک: {bl}",
            reply_markup=users_menu_kb())

    elif data == "users_search":
        context.user_data["mode"] = "users_search"
        await query.message.reply_text("🔍 نام، آیدی یا یوزرنیم:", reply_markup=admin_cancel_menu())

    elif data.startswith("ulist_"):
        parts       = data.split("_")
        filter_type = parts[1]
        offset      = int(parts[2])
        filters = {
            "today":   "WHERE DATE(last_seen)=DATE('now','localtime')",
            "week":    "WHERE last_seen>=datetime('now','-7 days','localtime')",
            "blocked": "WHERE is_blocked=1",
        }
        q = filters.get(filter_type, "")
        async with db.execute(f"SELECT COUNT(*) FROM users {q}") as c:
            total = (await c.fetchone())[0]
        rows  = await get_users_page(offset, 15, filter_type)
        label = {"all":"همه","today":"امروز","week":"هفته","blocked":"بلاک"}.get(filter_type,"")
        await query.message.edit_text(
            f"👥 کاربران — {label}\n{offset+1} تا {min(offset+15,total)} از {total}:",
            reply_markup=users_list_kb(rows, offset, filter_type, total))

    elif data.startswith("uview_"):
        uid = int(data[6:])
        async with db.execute(
            "SELECT user_id,first_name,username,joined_at,last_seen,is_blocked FROM users WHERE user_id=?",
            (uid,)
        ) as c:
            row = await c.fetchone()
        if not row: await query.answer("یافت نشد!", show_alert=True); return
        bl_st = "🚫 بلاک" if row[5] else "✅ فعال"
        await query.message.edit_text(
            f"👤 کاربر\n──────────────\n"
            f"نام: {row[1] or '—'}\n"
            f"یوزرنیم: {'@'+row[2] if row[2] else '—'}\n"
            f"آیدی: {row[0]}\n"
            f"عضویت: {row[3]}\n"
            f"آخرین فعالیت: {row[4]}\n"
            f"وضعیت: {bl_st}",
            reply_markup=user_detail_kb(uid, bool(row[5])))

    elif data.startswith("utoggle_"):
        uid = int(data[8:])
        async with db.execute("SELECT is_blocked FROM users WHERE user_id=?", (uid,)) as c:
            row = await c.fetchone()
        if not row: return
        if row[0]: await unblock_user(uid); await query.answer("✅ رفع بلاک شد", show_alert=True)
        else:      await block_user(uid);   await query.answer("🚫 بلاک شد", show_alert=True)
        async with db.execute(
            "SELECT user_id,first_name,username,joined_at,last_seen,is_blocked FROM users WHERE user_id=?",
            (uid,)
        ) as c:
            row = await c.fetchone()
        bl_st = "🚫 بلاک" if row[5] else "✅ فعال"
        await query.message.edit_text(
            f"👤 کاربر\n──────────────\nنام: {row[1] or '—'}\nآیدی: {row[0]}\nوضعیت: {bl_st}",
            reply_markup=user_detail_kb(uid, bool(row[5])))

    # ── بخش‌ها ──
    elif data == "sections":
        await query.message.edit_text("📋 مدیریت بخش‌ها:", reply_markup=sections_list_kb())

    elif data.startswith("sec_") and not any(data.startswith(p) for p in
            ["sec_text_","sec_banner_","sec_btns_","sec_wh_"]):
        key = data[4:]
        await query.message.edit_text(section_page_text(key), reply_markup=section_kb(key))

    elif data.startswith("sec_text_"):
        key = data[9:]
        context.user_data.update({"mode":"edit_text","edit_key":key})
        await query.message.reply_text(
            f"✏️ متن فعلی:\n\n{responses.get(key,'تنظیم نشده')}\n\nمتن جدید:",
            reply_markup=admin_cancel_menu())

    elif data.startswith("sec_wh_"):
        key    = data[7:]
        cur    = get_section_wh(key)
        set_section_wh(key, not cur)
        await save_settings()
        await query.answer("✅ فعال شد" if not cur else "❌ غیرفعال شد", show_alert=True)
        await query.message.edit_text(section_page_text(key), reply_markup=section_kb(key))

    elif data.startswith("sec_banner_"):
        key = data[11:]
        b   = get_banner(key)
        await query.message.edit_text(
            f"🖼 بنر: {SECTION_NAMES.get(key,key)}\n"
            f"عکس: {'✅' if b.get('file_id') else '❌'}\n"
            f"وضعیت: {'✅ فعال' if b.get('active') else '❌ غیرفعال'}",
            reply_markup=banner_kb(key))

    elif data.startswith("ban_up_"):
        key = data[7:]
        context.user_data.update({"mode":"banner_upload","banner_key":key})
        await query.message.reply_text(
            f"📤 عکس بنر «{SECTION_NAMES.get(key,key)}» را ارسال کنید:",
            reply_markup=admin_cancel_menu())

    elif data.startswith("ban_tg_"):
        key = data[7:]
        b   = get_banner(key)
        if not b.get("file_id"): await query.answer("ابتدا عکس آپلود کنید!", show_alert=True); return
        b["active"] = not b.get("active", False)
        await save_banners()
        await query.answer("✅ فعال" if b["active"] else "❌ غیرفعال", show_alert=True)
        await query.message.edit_text(
            f"🖼 بنر: {SECTION_NAMES.get(key,key)}\nعکس: ✅\nوضعیت: {'✅ فعال' if b['active'] else '❌ غیرفعال'}",
            reply_markup=banner_kb(key))

    elif data.startswith("ban_dl_"):
        key = data[7:]
        banners[key] = {"file_id": None, "active": False}
        await save_banners()
        await query.answer("🗑 حذف شد.", show_alert=True)
        await query.message.edit_text(
            f"🖼 بنر: {SECTION_NAMES.get(key,key)}\nعکس: ❌\nوضعیت: ❌",
            reply_markup=banner_kb(key))

    elif data.startswith("sec_btns_"):
        key = data[9:]
        sec = get_section_buttons(key)
        await query.message.edit_text(
            f"🔘 دکمه‌های: {SECTION_NAMES.get(key,key)}\n"
            f"وضعیت: {'✅ فعال' if sec.get('enabled') else '❌ غیرفعال'} | تعداد: {len(sec.get('items',[]))}",
            reply_markup=section_btns_kb(key))

    elif data.startswith("btn_tg_"):
        key = data[7:]
        sec = get_section_buttons(key)
        sec["enabled"] = not sec.get("enabled", True)
        await save_buttons()
        await query.answer("✅ فعال" if sec["enabled"] else "❌ غیرفعال", show_alert=True)
        await query.message.edit_text(
            f"🔘 دکمه‌های: {SECTION_NAMES.get(key,key)}\nوضعیت: {'✅' if sec['enabled'] else '❌'}",
            reply_markup=section_btns_kb(key))

    elif data.startswith("btn_add_"):
        key = data[8:]
        context.user_data.update({"mode":"btn_add_title","btn_key":key})
        await query.message.reply_text(
            f"➕ دکمه جدید برای «{SECTION_NAMES.get(key,key)}»\n\nعنوان دکمه:",
            reply_markup=admin_cancel_menu())

    elif data.startswith("btn_edt_"):
        parts = data[8:].split("_",1)
        key, bid = parts[0], parts[1]
        sec  = get_section_buttons(key)
        item = next((x for x in sec.get("items",[]) if x["id"]==bid), None)
        if not item: await query.answer("یافت نشد!", show_alert=True); return
        context.user_data.update({"mode":"btn_edit_title","btn_key":key,"btn_id":bid})
        await query.message.reply_text(
            f"✏️ ویرایش «{item['title']}»\n\nعنوان جدید (یا . بدون تغییر):",
            reply_markup=admin_cancel_menu())

    elif data.startswith("btn_del_"):
        parts = data[8:].split("_",1)
        key, bid = parts[0], parts[1]
        sec = get_section_buttons(key)
        sec["items"] = [x for x in sec.get("items",[]) if x["id"]!=bid]
        await save_buttons()
        await query.answer("🗑 حذف شد.", show_alert=True)
        await query.message.edit_text(
            f"🔘 دکمه‌های: {SECTION_NAMES.get(key,key)}",
            reply_markup=section_btns_kb(key))

    # ── تنظیمات ──
    elif data == "settings_menu":
        await query.message.edit_text("⚙️ تنظیمات ربات:", reply_markup=settings_kb())

    elif data.startswith("stg_"):
        key = data[4:]
        settings[key] = not get_setting(key)
        await save_settings()
        await query.answer("✅ ذخیره شد", show_alert=True)
        await query.message.edit_text("⚙️ تنظیمات ربات:", reply_markup=settings_kb())

    # ── ساعت کاری ──
    elif data == "workhours_menu":
        en = "✅ فعال" if workhours.get("enabled") else "❌ غیرفعال"
        await query.message.edit_text(
            f"🕐 ساعت کاری — {en}\n\n{workhours_full_summary()}",
            reply_markup=workhours_kb())

    elif data == "wh_toggle":
        workhours["enabled"] = not workhours.get("enabled", True)
        await save_workhours()
        await query.answer("✅ فعال" if workhours["enabled"] else "❌ غیرفعال", show_alert=True)
        await query.message.edit_text(
            f"🕐 ساعت کاری\n{workhours_full_summary()}", reply_markup=workhours_kb())

    elif data.startswith("wh_day_"):
        day_key  = data[7:]
        day      = workhours["schedule"].get(day_key, {"open":False,"shifts":[]})
        shifts_t = "\n".join([f"  • {s['from']} تا {s['to']}" for s in day.get("shifts",[])]) or "  ندارد"
        await query.message.edit_text(
            f"🕐 {DAY_NAMES.get(day_key,day_key)}\n"
            f"وضعیت: {'✅ باز' if day.get('open') else '❌ تعطیل'}\n"
            f"ساعت‌ها:\n{shifts_t}",
            reply_markup=workhours_day_kb(day_key))

    elif data.startswith("wh_dtg_"):
        day_key = data[7:]
        day     = workhours["schedule"].get(day_key, {"open":False,"shifts":[]})
        day["open"] = not day.get("open", False)
        workhours["schedule"][day_key] = day
        await save_workhours()
        await query.answer("✅ باز شد" if day["open"] else "❌ تعطیل شد", show_alert=True)
        await query.message.edit_text(
            f"🕐 وضعیت: {'✅ باز' if day['open'] else '❌ تعطیل'}",
            reply_markup=workhours_day_kb(day_key))

    elif data.startswith("wh_shifts_"):
        day_key = data[10:]
        context.user_data.update({"mode":"wh_set_shifts","wh_day":day_key})
        await query.message.reply_text(
            f"🕐 ساعت‌های {DAY_NAMES.get(day_key,day_key)}:\nفرمت: HH:MM-HH:MM\nمثال: 11:00-14:00,17:00-23:00",
            reply_markup=admin_cancel_menu())

    elif data == "wh_msg_open":
        context.user_data["mode"] = "wh_set_msg_open"
        await query.message.reply_text(
            f"✏️ پیام باز بودن:\n\n{workhours.get('msg_open','')}\n\nپیام جدید:",
            reply_markup=admin_cancel_menu())

    elif data == "wh_msg_closed":
        context.user_data["mode"] = "wh_set_msg_closed"
        await query.message.reply_text(
            f"✏️ پیام بسته بودن:\n\n{workhours.get('msg_closed','')}\n\nپیام جدید:",
            reply_markup=admin_cancel_menu())

# ======================================
# TEXT HANDLER
# ======================================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    await save_user(user)

    if not await anti_spam(user.id):
        return await update.message.reply_text("🐢 لطفاً آرام‌تر پیام دهید.")

    if text == "❌ لغو عملیات":
        context.user_data.clear()
        return await update.message.reply_text("❌ لغو شد.", reply_markup=main_menu())

    mode = context.user_data.get("mode")

    if user.id == ADMIN_ID:

        if mode == "edit_text":
            key = context.user_data.pop("edit_key", None)
            context.user_data.pop("mode", None)
            if key: responses[key] = text; await save_data()
            await update.message.reply_text("✅ متن ذخیره شد.", reply_markup=main_menu()); return

        if mode == "broadcast":
            context.user_data.pop("mode", None)
            await update.message.reply_text("📤 در حال ارسال...")
            await send_broadcast(context, text); return

        if mode == "users_search":
            context.user_data.pop("mode", None)
            rows = await search_users(text)
            if not rows:
                await update.message.reply_text("❌ کاربری یافت نشد.", reply_markup=main_menu()); return
            lines = [f"{'🚫 ' if r[4] else ''}{r[1] or '—'} | {r[0]} | {'@'+r[2] if r[2] else '—'}" for r in rows]
            await update.message.reply_text("🔍 نتایج:\n\n" + "\n".join(lines), reply_markup=main_menu()); return

        if mode == "btn_add_title":
            context.user_data.update({"btn_title":text,"mode":"btn_add_url"})
            await update.message.reply_text("🔗 لینک دکمه (https://...):", reply_markup=admin_cancel_menu()); return

        if mode == "btn_add_url":
            key   = context.user_data.pop("btn_key", None)
            title = context.user_data.pop("btn_title", "دکمه")
            context.user_data.pop("mode", None)
            url   = text if text.startswith("http") else f"https://{text}"
            sec   = get_section_buttons(key)
            sec["items"].append({"id":f"b{int(time.time())}","title":title,"url":url})
            await save_buttons()
            await update.message.reply_text(f"✅ دکمه «{title}» اضافه شد.", reply_markup=main_menu()); return

        if mode == "btn_edit_title":
            context.user_data.update({"btn_new_title": None if text=="." else text,"mode":"btn_edit_url"})
            await update.message.reply_text("🔗 لینک جدید (یا . بدون تغییر):", reply_markup=admin_cancel_menu()); return

        if mode == "btn_edit_url":
            key       = context.user_data.pop("btn_key", None)
            bid       = context.user_data.pop("btn_id", None)
            new_title = context.user_data.pop("btn_new_title", None)
            context.user_data.pop("mode", None)
            sec = get_section_buttons(key)
            for item in sec.get("items",[]):
                if item["id"] == bid:
                    if new_title: item["title"] = new_title
                    if text != ".": item["url"] = text if text.startswith("http") else f"https://{text}"
            await save_buttons()
            await update.message.reply_text("✅ ویرایش شد.", reply_markup=main_menu()); return

        if mode == "wh_set_shifts":
            day_key = context.user_data.pop("wh_day", None)
            context.user_data.pop("mode", None)
            try:
                shifts = []
                for part in text.split(","):
                    fr, to = part.strip().split("-")
                    shifts.append({"from":fr.strip(),"to":to.strip()})
                workhours["schedule"][day_key]["shifts"] = shifts
                await save_workhours()
                await update.message.reply_text("✅ ساعت‌ها ذخیره شد.", reply_markup=main_menu())
            except Exception:
                await update.message.reply_text("❌ فرمت اشتباه!\nمثال: 11:00-14:00,17:00-23:00", reply_markup=main_menu())
            return

        if mode == "wh_set_msg_open":
            context.user_data.pop("mode", None)
            workhours["msg_open"] = text; await save_workhours()
            await update.message.reply_text("✅ ذخیره شد.", reply_markup=main_menu()); return

        if mode == "wh_set_msg_closed":
            context.user_data.pop("mode", None)
            workhours["msg_closed"] = text; await save_workhours()
            await update.message.reply_text("✅ ذخیره شد.", reply_markup=main_menu()); return

    # ── منوی کاربر ──
    if text == "🕐 ساعت کاری":
        await record_stat("workhours_page")
        now    = datetime.now(IRAN_TZ)
        j_now  = jdatetime.datetime.fromgregorian(datetime=now)
        today  = DAY_NAMES.get(str(j_now.weekday()), "")
        st     = "🟢 الان باز است" if is_open_now() else "🔴 الان بسته است"
        footer = f"\n🕒 {shamsi_now()}" if get_setting("show_datetime_footer") else ""
        if not workhours.get("enabled", True):
            await update.message.reply_text(f"🕐 ساعت کاری\n──────────────\nساعت کاری تنظیم نشده{footer}", reply_markup=main_menu()); return
        full = (
            f"🕐 ساعت کاری استوک لند\n──────────────\n"
            f"{workhours_full_summary()}\n──────────────\n"
            f"📅 امروز {today}\n{st}{footer}"
        )
        await update.message.reply_text(full, reply_markup=main_menu()); return

    for k, v in MENU_ITEMS.items():
        if text == v:
            await record_stat(k)
            content = responses.get(k, "تنظیم نشده")
            full    = build_message(v, content, k)
            kb      = user_section_kb(k)
            await send_with_banner(update.message, full, k, reply_markup=kb)
            return

    await update.message.reply_text("⚠️ گزینه نامعتبر است.", reply_markup=main_menu())

# ======================================
# PHOTO HANDLER
# ======================================
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID: return
    mode = context.user_data.get("mode")

    if mode == "banner_upload":
        key = context.user_data.pop("banner_key", None)
        context.user_data.pop("mode", None)
        if not key: await update.message.reply_text("❌ خطا.", reply_markup=main_menu()); return
        photo = update.message.photo[-1]
        get_banner(key)
        banners[key]["file_id"] = photo.file_id
        banners[key]["active"]  = True
        await save_banners()
        await update.message.reply_text(f"✅ بنر «{SECTION_NAMES.get(key,key)}» آپلود شد!", reply_markup=main_menu()); return

    if mode == "broadcast":
        context.user_data.pop("mode", None)
        photo   = update.message.photo[-1]
        caption = update.message.caption or ""
        await update.message.reply_text("📤 در حال ارسال...")
        await send_broadcast(context, caption, photo_id=photo.file_id); return

# ======================================
# MAIN
# ======================================
async def post_init(app):
    await init_db()
    await load_data()
    await load_banners()
    await load_workhours()
    await load_buttons()
    await load_settings()
    await load_stats()
    logger.info("✅ ربات راه‌اندازی شد")

def main():
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print("🚀 ربات در حال اجراست...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
