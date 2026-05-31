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

# ======================================
# DISABLE PROXY
# ======================================
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("ALL_PROXY", None)
os.environ["NO_PROXY"] = "*"

# ======================================
# CONFIG
# ======================================
TOKEN = os.getenv("BOT_TOKEN", "8792062012:AAGXforSa1IY45AuC-yOHs2PsdzudvtdD44")
ADMIN_ID = int(os.getenv("ADMIN_ID", "638469407"))

DATA_FILE      = "data.json"
DB_FILE        = "users.db"
BANNER_FILE    = "banner.json"
CONTACTS_FILE  = "contacts.json"
WORKHOURS_FILE = "workhours.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ======================================
# TIME
# ======================================
IRAN_TZ = pytz.timezone("Asia/Tehran")

def shamsi_now():
    now = datetime.now(IRAN_TZ)
    j_now = jdatetime.datetime.fromgregorian(datetime=now)
    return j_now.strftime("%Y/%m/%d - %H:%M")

def gregorian_now():
    return datetime.now(IRAN_TZ).strftime("%Y-%m-%d %H:%M:%S")

# ======================================
# MENU — برای گزینه جدید فقط اینجا اضافه کن
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
}

# ======================================
# GLOBALS
# ======================================
responses = None
banners   = {}

DEFAULT_CONTACTS = [
    {"id": "c1", "icon": "📞", "title": "تلفن اول",  "type": "phone",    "value": "09999653739"},
    {"id": "c2", "icon": "📞", "title": "تلفن دوم",  "type": "phone",    "value": "09050323217"},
    {"id": "c3", "icon": "💬", "title": "واتساپ",    "type": "whatsapp", "value": "009809050323217"},
    {"id": "c4", "icon": "✈️", "title": "تلگرام",    "type": "telegram", "value": "stland_shop"},
]
contacts = []

DEFAULT_WORKHOURS = {
    "enabled": True,
    "schedule": {
        "0": {"open": True,  "shifts": [{"from": "11:00", "to": "14:00"}, {"from": "17:00", "to": "23:00"}]},
        "1": {"open": True,  "shifts": [{"from": "11:00", "to": "14:00"}, {"from": "17:00", "to": "23:00"}]},
        "2": {"open": True,  "shifts": [{"from": "11:00", "to": "14:00"}, {"from": "17:00", "to": "23:00"}]},
        "3": {"open": True,  "shifts": [{"from": "11:00", "to": "14:00"}, {"from": "17:00", "to": "23:00"}]},
        "4": {"open": True,  "shifts": [{"from": "11:00", "to": "14:00"}, {"from": "17:00", "to": "23:00"}]},
        "5": {"open": True,  "shifts": [{"from": "11:00", "to": "14:00"}, {"from": "17:00", "to": "23:00"}]},
        "6": {"open": True,  "shifts": [{"from": "17:00", "to": "23:00"}]},
    },
    "msg_open":   "✅ فروشگاه استوک لند الان باز است!\nخوش آمدید 🛍",
    "msg_closed": "🕐 فروشگاه الان تعطیل است.\n\n⏰ ساعات کاری:\nشنبه تا پنجشنبه: ۱۱-۱۴ و ۱۷-۲۳\nجمعه: ۱۷-۲۳",
}
workhours = {}

# ======================================
# HELPERS
# ======================================
def get_banner(key: str) -> dict:
    if key not in banners:
        banners[key] = {"file_id": None, "active": False}
    return banners[key]

def make_contact_link(c: dict):
    """فقط لینک https برمیگردونه - tel: در تلگرام کار نمیکنه"""
    t = c.get("type", "")
    v = c.get("value", "")
    if t == "phone":
        return None
    elif t == "whatsapp":
        num = v.replace("+", "").replace("00", "", 1)
        return f"https://wa.me/{num}"
    elif t == "telegram":
        return f"https://t.me/{v.lstrip('@')}"
    elif t == "url":
        return v
    return None

def is_open_now() -> bool:
    if not workhours.get("enabled", True):
        return False
    now    = datetime.now(IRAN_TZ)
    j_now  = jdatetime.datetime.fromgregorian(datetime=now)
    day    = workhours.get("schedule", {}).get(str(j_now.weekday()), {})
    if not day.get("open", False):
        return False
    now_str = now.strftime("%H:%M")
    for shift in day.get("shifts", []):
        if shift["from"] <= now_str <= shift["to"]:
            return True
    return False

def workhours_summary() -> str:
    day_names = {
        "0": "شنبه", "1": "یکشنبه", "2": "دوشنبه",
        "3": "سه‌شنبه", "4": "چهارشنبه", "5": "پنجشنبه", "6": "جمعه"
    }
    lines = []
    for k, name in day_names.items():
        day = workhours.get("schedule", {}).get(k, {})
        if not day.get("open"):
            lines.append(f"• {name}: تعطیل")
        else:
            shifts = " و ".join([f"{s['from']} تا {s['to']}" for s in day.get("shifts", [])])
            lines.append(f"• {name}: {shifts}")
    return "\n".join(lines)

# ======================================
# LOAD / SAVE
# ======================================
async def load_data():
    global responses
    try:
        async with aiofiles.open(DATA_FILE, "r", encoding="utf-8") as f:
            responses = json.loads(await f.read())
    except Exception:
        responses = MENU_ITEMS.copy()
        responses["welcome"] = "✨ خوش آمدید به ربات استوک لند"

async def save_data():
    try:
        async with aiofiles.open(DATA_FILE, "w", encoding="utf-8") as f:
            await f.write(json.dumps(responses, ensure_ascii=False, indent=4))
    except Exception as e:
        logger.error(f"Save error: {e}")

async def load_banners():
    global banners
    try:
        async with aiofiles.open(BANNER_FILE, "r", encoding="utf-8") as f:
            data = json.loads(await f.read())
            if isinstance(data, dict):
                banners = data
    except Exception:
        banners = {}
    for key in SECTION_NAMES:
        if key not in banners:
            banners[key] = {"file_id": None, "active": False}

async def save_banners():
    try:
        async with aiofiles.open(BANNER_FILE, "w", encoding="utf-8") as f:
            await f.write(json.dumps(banners, ensure_ascii=False, indent=4))
    except Exception as e:
        logger.error(f"Banner save error: {e}")

async def load_contacts():
    global contacts
    try:
        async with aiofiles.open(CONTACTS_FILE, "r", encoding="utf-8") as f:
            contacts = json.loads(await f.read())
    except Exception:
        contacts = DEFAULT_CONTACTS.copy()
        await save_contacts()

async def save_contacts():
    try:
        async with aiofiles.open(CONTACTS_FILE, "w", encoding="utf-8") as f:
            await f.write(json.dumps(contacts, ensure_ascii=False, indent=4))
    except Exception as e:
        logger.error(f"Contacts save error: {e}")

async def load_workhours():
    global workhours
    try:
        async with aiofiles.open(WORKHOURS_FILE, "r", encoding="utf-8") as f:
            workhours = json.loads(await f.read())
    except Exception:
        workhours = DEFAULT_WORKHOURS.copy()
        await save_workhours()

async def save_workhours():
    try:
        async with aiofiles.open(WORKHOURS_FILE, "w", encoding="utf-8") as f:
            await f.write(json.dumps(workhours, ensure_ascii=False, indent=4))
    except Exception as e:
        logger.error(f"Workhours save error: {e}")

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
        joined_at TEXT, last_seen TEXT)""")
    await db.execute("""CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        action TEXT, created_at TEXT)""")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_lastseen ON users(last_seen)")
    await db.commit()

async def save_user(user):
    now = gregorian_now()
    await db.execute(
        "INSERT OR IGNORE INTO users VALUES (?,?,?,?,?)",
        (user.id, user.username or "", user.first_name or "", now, now)
    )
    await db.execute(
        "UPDATE users SET username=?, first_name=?, last_seen=? WHERE user_id=?",
        (user.username or "", user.first_name or "", now, user.id)
    )
    await db.commit()

async def log_event(user_id: int, action: str):
    await db.execute(
        "INSERT INTO logs (user_id, action, created_at) VALUES (?,?,?)",
        (user_id, action, gregorian_now())
    )
    await db.commit()

async def get_all_users():
    async with db.execute("SELECT user_id FROM users") as c:
        return [r[0] for r in await c.fetchall()]

async def total_users():
    async with db.execute("SELECT COUNT(*) FROM users") as c:
        return (await c.fetchone())[0]

async def today_users():
    async with db.execute(
        "SELECT COUNT(*) FROM users WHERE DATE(last_seen)=DATE('now', 'localtime')"
    ) as c:
        return (await c.fetchone())[0]

async def week_users():
    async with db.execute(
        "SELECT COUNT(*) FROM users WHERE last_seen >= datetime('now', '-7 days', 'localtime')"
    ) as c:
        return (await c.fetchone())[0]

async def month_users():
    async with db.execute(
        "SELECT COUNT(*) FROM users WHERE last_seen >= datetime('now', '-30 days', 'localtime')"
    ) as c:
        return (await c.fetchone())[0]

async def new_today():
    async with db.execute(
        "SELECT COUNT(*) FROM users WHERE DATE(joined_at)=DATE('now', 'localtime')"
    ) as c:
        return (await c.fetchone())[0]

# ======================================
# ANTI-SPAM
# ======================================
WINDOW, LIMIT, BLOCK = 10, 7, 60
spam    = defaultdict(lambda: deque(maxlen=LIMIT))
blocked = {}

async def anti_spam(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    now = time.time()
    if user_id in blocked and blocked[user_id] > now:
        return False
    q = spam[user_id]
    q.append(now)
    if len(q) >= LIMIT and (now - q[0]) <= WINDOW:
        blocked[user_id] = now + BLOCK
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
        if i + 1 < len(keys):
            row.append(MENU_ITEMS[keys[i + 1]])
        rows.append(row)
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 داشبورد",          callback_data="dash")],
        [InlineKeyboardButton("👤 کاربران",           callback_data="users")],
        [InlineKeyboardButton("✏️ مدیریت محتوا",     callback_data="edit")],
        [InlineKeyboardButton("🖼 مدیریت بنرها",     callback_data="banner_list")],
        [InlineKeyboardButton("📞 روش‌های تماس",     callback_data="contacts_list")],
        [InlineKeyboardButton("🕐 ساعت کاری",        callback_data="workhours_menu")],
        [InlineKeyboardButton("📢 پخش همگانی",       callback_data="broadcast")],
        [InlineKeyboardButton("💾 بک‌آپ",            callback_data="backup")],
        [InlineKeyboardButton("📈 لاگ‌ها",           callback_data="logs")],
    ])

def back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="back_to_admin")]])

def admin_cancel_menu():
    return ReplyKeyboardMarkup([["❌ لغو عملیات"]], resize_keyboard=True)

def box(title: str, text: str):
    return f"📌 {title}\n──────────────\n{text}\n──────────────\n🕒 {shamsi_now()}"

# ── بنر ──
def banner_list_keyboard():
    buttons = []
    for key, name in SECTION_NAMES.items():
        b  = get_banner(key)
        hb = "🖼" if b.get("file_id") else "➕"
        ia = "✅" if b.get("active")   else "❌"
        buttons.append([InlineKeyboardButton(f"{hb} {ia} {name}", callback_data=f"bmng_{key}")])
    buttons.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_to_admin")])
    return InlineKeyboardMarkup(buttons)

def banner_section_keyboard(key: str):
    b      = get_banner(key)
    toggle = "🔴 غیرفعال کردن" if b.get("active") else "🟢 فعال کردن"
    btns   = [
        [InlineKeyboardButton("🖼 آپلود / تغییر عکس", callback_data=f"bup_{key}")],
        [InlineKeyboardButton(toggle,                  callback_data=f"btg_{key}")],
    ]
    if b.get("file_id"):
        btns.append([InlineKeyboardButton("🗑 حذف بنر", callback_data=f"bdl_{key}")])
    btns.append([InlineKeyboardButton("🔙 برگشت به لیست", callback_data="banner_list")])
    return InlineKeyboardMarkup(btns)

# ── تماس ──
def contacts_list_keyboard():
    btns = []
    for c in contacts:
        btns.append([InlineKeyboardButton(f"{c['icon']} {c['title']}", callback_data=f"cmng_{c['id']}")])
    btns.append([InlineKeyboardButton("➕ افزودن روش تماس جدید", callback_data="cadd")])
    btns.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_to_admin")])
    return InlineKeyboardMarkup(btns)

def contact_section_keyboard(cid: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ ویرایش عنوان", callback_data=f"cedit_title_{cid}")],
        [InlineKeyboardButton("🔗 ویرایش مقدار", callback_data=f"cedit_value_{cid}")],
        [InlineKeyboardButton("🎨 ویرایش آیکون", callback_data=f"cedit_icon_{cid}")],
        [InlineKeyboardButton("🗑 حذف",          callback_data=f"cdel_{cid}")],
        [InlineKeyboardButton("🔙 برگشت",        callback_data="contacts_list")],
    ])

def contact_type_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 تلفن",    callback_data="ctype_phone")],
        [InlineKeyboardButton("💬 واتساپ", callback_data="ctype_whatsapp")],
        [InlineKeyboardButton("✈️ تلگرام", callback_data="ctype_telegram")],
        [InlineKeyboardButton("🌐 لینک",   callback_data="ctype_url")],
        [InlineKeyboardButton("❌ لغو",    callback_data="contacts_list")],
    ])

# ── ساعت کاری ──
def workhours_keyboard():
    day_names = {
        "0": "شنبه", "1": "یکشنبه", "2": "دوشنبه",
        "3": "سه‌شنبه", "4": "چهارشنبه", "5": "پنجشنبه", "6": "جمعه"
    }
    enabled = workhours.get("enabled", True)
    toggle  = "🔴 غیرفعال کردن ساعت کاری" if enabled else "🟢 فعال کردن ساعت کاری"
    btns    = [[InlineKeyboardButton(toggle, callback_data="wh_toggle")]]
    for k, name in day_names.items():
        day    = workhours.get("schedule", {}).get(k, {})
        status = "✅" if day.get("open") else "❌"
        btns.append([InlineKeyboardButton(f"{status} {name}", callback_data=f"wh_day_{k}")])
    btns.append([InlineKeyboardButton("✏️ پیام باز بودن",  callback_data="wh_msg_open")])
    btns.append([InlineKeyboardButton("✏️ پیام بسته بودن", callback_data="wh_msg_closed")])
    btns.append([InlineKeyboardButton("🔙 برگشت",          callback_data="back_to_admin")])
    return InlineKeyboardMarkup(btns)

def workhours_day_keyboard(day_key: str):
    day    = workhours.get("schedule", {}).get(day_key, {})
    toggle = "🔴 تعطیل کردن" if day.get("open") else "🟢 باز کردن"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle,               callback_data=f"wh_dtg_{day_key}")],
        [InlineKeyboardButton("✏️ تنظیم ساعت‌ها", callback_data=f"wh_shifts_{day_key}")],
        [InlineKeyboardButton("🔙 برگشت",          callback_data="workhours_menu")],
    ])

# ── تماس کاربر ──
def contact_user_keyboard():
    """دکمه‌های لینک‌دار (واتساپ، تلگرام، url) — تلفن‌ها توی متن پیام میان"""
    if not contacts:
        return None
    btns = []
    row  = []
    link_contacts = [c for c in contacts if make_contact_link(c)]
    for i, c in enumerate(link_contacts):
        link = make_contact_link(c)
        row.append(InlineKeyboardButton(f"{c['icon']} {c['title']}", url=link))
        if len(row) == 2 or i == len(link_contacts) - 1:
            if row:
                btns.append(row)
            row = []
    return InlineKeyboardMarkup(btns) if btns else None

def phone_lines() -> str:
    phones = [c for c in contacts if c.get("type") == "phone"]
    if not phones:
        return ""
    lines = "\n".join([f"{c['icon']} {c['title']}: {c['value']}" for c in phones])
    return f"\n\n📞 تماس مستقیم:\n{lines}"

# ======================================
# SEND WITH BANNER
# ======================================
async def send_with_banner(msg, text: str, section_key: str, reply_markup=None):
    b = get_banner(section_key)
    if b.get("active") and b.get("file_id"):
        try:
            await msg.reply_photo(photo=b["file_id"], caption=text, reply_markup=reply_markup)
            return
        except Exception as e:
            logger.error(f"Banner send error [{section_key}]: {e}")
    await msg.reply_text(text, reply_markup=reply_markup)

# ======================================
# BROADCAST
# ======================================
async def send_broadcast(context: ContextTypes.DEFAULT_TYPE, text: str, photo_id: str = None):
    users   = await get_all_users()
    total   = len(users)
    success = failed = 0
    status  = await context.bot.send_message(ADMIN_ID, f"📢 شروع پخش به {total} کاربر...")
    for i, uid in enumerate(users, 1):
        try:
            if photo_id:
                await context.bot.send_photo(uid, photo=photo_id, caption=text)
            else:
                await context.bot.send_message(uid, text)
            success += 1
        except Exception:
            failed += 1
        if i % 10 == 0 or i == total:
            try:
                await status.edit_text(
                    f"📢 در حال پخش...\n✅ موفق: {success}\n❌ شکست: {failed}\n{i}/{total}"
                )
            except Exception:
                pass
        await asyncio.sleep(0.2)
    await status.edit_text(f"✅ پخش تمام شد!\nموفق: {success} | شکست: {failed}")

# ======================================
# BACKUP
# ======================================
async def send_backup(bot):
    now   = shamsi_now().replace("/", "-").replace(" ", "_").replace(":", "-")
    files = [
        (DATA_FILE,      f"backup_data_{now}.json"),
        (BANNER_FILE,    f"backup_banner_{now}.json"),
        (CONTACTS_FILE,  f"backup_contacts_{now}.json"),
        (WORKHOURS_FILE, f"backup_workhours_{now}.json"),
    ]
    await bot.send_message(ADMIN_ID, f"💾 بک‌آپ — {shamsi_now()}")
    for filepath, filename in files:
        try:
            async with aiofiles.open(filepath, "rb") as f:
                content = await f.read()
            await bot.send_document(ADMIN_ID, document=content, filename=filename)
        except Exception as e:
            logger.error(f"Backup error {filepath}: {e}")

# ======================================
# HANDLERS
# ======================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await save_user(user)
    await log_event(user.id, "start")
    welcome_text = responses.get("welcome", "✨ خوش آمدید به ربات استوک لند")
    await send_with_banner(update.message, welcome_text, "welcome", reply_markup=main_menu())

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
    if query.from_user.id != ADMIN_ID:
        return
    data = query.data

    if data == "back_to_admin":
        await query.message.edit_text("👑 پنل مدیریت", reply_markup=admin_menu())

    elif data == "dash":
        t  = await total_users()
        d  = await today_users()
        w  = await week_users()
        m  = await month_users()
        nt = await new_today()
        op = "✅ باز" if is_open_now() else "🔴 بسته"
        await query.message.edit_text(box("داشبورد",
            f"👥 کل کاربران: {t}\n"
            f"🆕 عضو امروز: {nt}\n"
            f"📅 فعال امروز: {d}\n"
            f"📆 فعال هفته: {w}\n"
            f"🗓 فعال ماه: {m}\n"
            f"🏪 وضعیت فروشگاه: {op}"
        ), reply_markup=admin_menu())

    elif data == "users":
        async with db.execute(
            "SELECT user_id, first_name, username, last_seen FROM users ORDER BY last_seen DESC LIMIT 20"
        ) as c:
            rows = await c.fetchall()
        lines = [f"• {r[1]} {'@'+r[2] if r[2] else '—'} | {r[0]}" for r in rows]
        await query.message.edit_text("👤 کاربران اخیر:\n\n" + "\n".join(lines), reply_markup=back_button())

    elif data == "logs":
        async with db.execute(
            "SELECT user_id, action, created_at FROM logs ORDER BY id DESC LIMIT 20"
        ) as c:
            rows = await c.fetchall()
        text = "📈 لاگ‌ها:\n\n" + "\n".join([f"• {r[1]} | {r[0]} | {r[2]}" for r in rows])
        await query.message.edit_text(text, reply_markup=back_button())

    elif data == "edit":
        buttons = []
        for key, name in SECTION_NAMES.items():
            cb = "set_welcome" if key == "welcome" else f"e_{key}"
            buttons.append([InlineKeyboardButton(name, callback_data=cb)])
        buttons.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_to_admin")])
        await query.message.edit_text(
            "✏️ مدیریت محتوا\nروی هر بخش بزنید تا ویرایش کنید:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("e_"):
        key = data[2:]
        context.user_data["edit_key"] = key
        context.user_data["mode"]     = "edit"
        current = responses.get(key, "تنظیم نشده")
        await query.message.reply_text(
            f"📝 متن فعلی:\n\n{current}\n\nمتن جدید را ارسال کنید:",
            reply_markup=admin_cancel_menu()
        )

    elif data == "set_welcome":
        context.user_data["mode"] = "set_welcome"
        current = responses.get("welcome", "پیام پیش‌فرض")
        await query.message.reply_text(
            f"📝 پیام خوش‌آمدگویی فعلی:\n\n{current}\n\nمتن جدید را ارسال کنید:",
            reply_markup=admin_cancel_menu()
        )

    elif data == "broadcast":
        context.user_data["mode"] = "broadcast"
        await query.message.reply_text(
            "📢 پیام پخش همگانی را ارسال کنید:\n\n• فقط متن → پیام متنی\n• عکس + کپشن → پیام با تصویر",
            reply_markup=admin_cancel_menu()
        )

    elif data == "backup":
        await query.message.edit_text("💾 در حال ارسال بک‌آپ...", reply_markup=back_button())
        await send_backup(query.message._bot)
        await query.message.edit_text("✅ بک‌آپ ارسال شد.", reply_markup=back_button())

    # ── بنرها ──
    elif data == "banner_list":
        await query.message.edit_text(
            "🖼 مدیریت بنرها\n──────────────\n"
            "🖼 = دارد بنر  |  ➕ = ندارد\n✅ = فعال  |  ❌ = غیرفعال",
            reply_markup=banner_list_keyboard()
        )

    elif data.startswith("bmng_"):
        key  = data[5:]
        b    = get_banner(key)
        name = SECTION_NAMES.get(key, key)
        has  = "✅ آپلود شده" if b.get("file_id") else "❌ ندارد"
        st   = "✅ فعال"      if b.get("active")   else "❌ غیرفعال"
        await query.message.edit_text(
            f"🖼 بنر بخش: {name}\n──────────────\nعکس: {has}\nوضعیت: {st}\n──────────────",
            reply_markup=banner_section_keyboard(key)
        )

    elif data.startswith("bup_"):
        key = data[4:]
        context.user_data["mode"]       = "banner_upload"
        context.user_data["banner_key"] = key
        name = SECTION_NAMES.get(key, key)
        await query.message.reply_text(
            f"🖼 عکس بنر بخش «{name}» را ارسال کنید:\n• عکس را مستقیم بفرستید (نه فایل)",
            reply_markup=admin_cancel_menu()
        )

    elif data.startswith("btg_"):
        key = data[4:]
        b   = get_banner(key)
        if not b.get("file_id"):
            await query.answer("ابتدا عکس آپلود کنید!", show_alert=True)
            return
        b["active"] = not b.get("active", False)
        await save_banners()
        await query.answer("✅ فعال شد" if b["active"] else "❌ غیرفعال شد", show_alert=True)
        name = SECTION_NAMES.get(key, key)
        has  = "✅ آپلود شده" if b.get("file_id") else "❌ ندارد"
        st   = "✅ فعال"      if b.get("active")   else "❌ غیرفعال"
        await query.message.edit_text(
            f"🖼 بنر بخش: {name}\n──────────────\nعکس: {has}\nوضعیت: {st}\n──────────────",
            reply_markup=banner_section_keyboard(key)
        )

    elif data.startswith("bdl_"):
        key = data[4:]
        banners[key] = {"file_id": None, "active": False}
        await save_banners()
        await query.answer("🗑 بنر حذف شد.", show_alert=True)
        name = SECTION_NAMES.get(key, key)
        await query.message.edit_text(
            f"🖼 بنر بخش: {name}\n──────────────\nعکس: ❌ ندارد\nوضعیت: ❌ غیرفعال\n──────────────",
            reply_markup=banner_section_keyboard(key)
        )

    # ── روش‌های تماس ──
    elif data == "contacts_list":
        await query.message.edit_text(
            "📞 مدیریت روش‌های تماس\n──────────────",
            reply_markup=contacts_list_keyboard()
        )

    elif data.startswith("cmng_"):
        cid = data[5:]
        c   = next((x for x in contacts if x["id"] == cid), None)
        if not c:
            await query.answer("یافت نشد!", show_alert=True)
            return
        await query.message.edit_text(
            f"📞 {c['icon']} {c['title']}\n──────────────\nنوع: {c['type']}\nمقدار: {c['value']}\n──────────────",
            reply_markup=contact_section_keyboard(cid)
        )

    elif data.startswith("cedit_title_"):
        cid = data[12:]
        context.user_data["mode"]       = "cedit_title"
        context.user_data["contact_id"] = cid
        await query.message.reply_text("✏️ عنوان جدید را ارسال کنید:", reply_markup=admin_cancel_menu())

    elif data.startswith("cedit_value_"):
        cid = data[12:]
        c   = next((x for x in contacts if x["id"] == cid), None)
        context.user_data["mode"]       = "cedit_value"
        context.user_data["contact_id"] = cid
        hint = {"phone": "شماره تلفن", "whatsapp": "شماره با کد کشور", "telegram": "آیدی بدون @", "url": "لینک کامل"}.get(c["type"] if c else "", "مقدار")
        await query.message.reply_text(f"🔗 {hint}:", reply_markup=admin_cancel_menu())

    elif data.startswith("cedit_icon_"):
        cid = data[11:]
        context.user_data["mode"]       = "cedit_icon"
        context.user_data["contact_id"] = cid
        await query.message.reply_text("🎨 آیکون جدید را ارسال کنید (مثال: 📞 💬 ✈️ 🌐):", reply_markup=admin_cancel_menu())

    elif data.startswith("cdel_"):
        cid = data[5:]
        contacts[:] = [x for x in contacts if x["id"] != cid]
        await save_contacts()
        await query.answer("🗑 حذف شد.", show_alert=True)
        await query.message.edit_text("📞 مدیریت روش‌های تماس\n──────────────", reply_markup=contacts_list_keyboard())

    elif data == "cadd":
        context.user_data["mode"] = "cadd_type"
        await query.message.reply_text("➕ نوع روش تماس جدید را انتخاب کنید:", reply_markup=contact_type_keyboard())

    elif data.startswith("ctype_"):
        ctype = data[6:]
        context.user_data["mode"]      = "cadd_title"
        context.user_data["new_ctype"] = ctype
        await query.message.reply_text("✏️ عنوان این روش تماس را بنویسید:", reply_markup=admin_cancel_menu())

    # ── ساعت کاری ──
    elif data == "workhours_menu":
        enabled = workhours.get("enabled", True)
        st      = "✅ فعال" if enabled else "❌ غیرفعال"
        await query.message.edit_text(
            f"🕐 مدیریت ساعت کاری\n──────────────\nوضعیت: {st}\n\n{workhours_summary()}",
            reply_markup=workhours_keyboard()
        )

    elif data == "wh_toggle":
        workhours["enabled"] = not workhours.get("enabled", True)
        await save_workhours()
        await query.answer("✅ فعال شد" if workhours["enabled"] else "❌ غیرفعال شد", show_alert=True)
        await query.message.edit_text(
            f"🕐 مدیریت ساعت کاری\n──────────────\n{workhours_summary()}",
            reply_markup=workhours_keyboard()
        )

    elif data.startswith("wh_day_"):
        day_key   = data[7:]
        day_names = {"0":"شنبه","1":"یکشنبه","2":"دوشنبه","3":"سه‌شنبه","4":"چهارشنبه","5":"پنجشنبه","6":"جمعه"}
        day       = workhours["schedule"].get(day_key, {"open": False, "shifts": []})
        name      = day_names.get(day_key, day_key)
        st        = "✅ باز" if day.get("open") else "❌ تعطیل"
        shifts_text = "\n".join([f"  • {s['from']} تا {s['to']}" for s in day.get("shifts", [])]) or "  ندارد"
        await query.message.edit_text(
            f"🕐 روز: {name}\nوضعیت: {st}\nساعت‌ها:\n{shifts_text}",
            reply_markup=workhours_day_keyboard(day_key)
        )

    elif data.startswith("wh_dtg_"):
        day_key = data[7:]
        day     = workhours["schedule"].get(day_key, {"open": False, "shifts": []})
        day["open"] = not day.get("open", False)
        workhours["schedule"][day_key] = day
        await save_workhours()
        await query.answer("✅ باز شد" if day["open"] else "❌ تعطیل شد", show_alert=True)
        await query.message.edit_text(
            f"🕐 وضعیت: {'✅ باز' if day['open'] else '❌ تعطیل'}",
            reply_markup=workhours_day_keyboard(day_key)
        )

    elif data.startswith("wh_shifts_"):
        day_key   = data[10:]
        day_names = {"0":"شنبه","1":"یکشنبه","2":"دوشنبه","3":"سه‌شنبه","4":"چهارشنبه","5":"پنجشنبه","6":"جمعه"}
        context.user_data["mode"]   = "wh_set_shifts"
        context.user_data["wh_day"] = day_key
        await query.message.reply_text(
            f"🕐 ساعت‌های {day_names.get(day_key, day_key)} را وارد کنید:\n\n"
            "فرمت: HH:MM-HH:MM\nبرای چند شیفت با کاما:\n"
            "مثال: 11:00-14:00,17:00-23:00",
            reply_markup=admin_cancel_menu()
        )

    elif data == "wh_msg_open":
        context.user_data["mode"] = "wh_set_msg_open"
        await query.message.reply_text(
            f"✏️ پیام فعلی باز بودن:\n\n{workhours.get('msg_open','')}\n\nپیام جدید:",
            reply_markup=admin_cancel_menu()
        )

    elif data == "wh_msg_closed":
        context.user_data["mode"] = "wh_set_msg_closed"
        await query.message.reply_text(
            f"✏️ پیام فعلی بسته بودن:\n\n{workhours.get('msg_closed','')}\n\nپیام جدید:",
            reply_markup=admin_cancel_menu()
        )

# ======================================
# TEXT HANDLER
# ======================================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    await save_user(user)
    await log_event(user.id, "message")

    if not await anti_spam(user.id):
        return await update.message.reply_text("🐢 لطفاً آرام‌تر پیام دهید.")

    if text == "❌ لغو عملیات":
        context.user_data.clear()
        return await update.message.reply_text("❌ عملیات لغو شد.", reply_markup=main_menu())

    mode = context.user_data.get("mode")

    if user.id == ADMIN_ID:
        if mode == "set_welcome":
            context.user_data.pop("mode", None)
            responses["welcome"] = text
            await save_data()
            await update.message.reply_text("✅ پیام خوش‌آمدگویی ذخیره شد.", reply_markup=main_menu())
            return

        if mode == "edit":
            key = context.user_data.pop("edit_key", None)
            context.user_data.pop("mode", None)
            if key:
                responses[key] = text
                await save_data()
            await update.message.reply_text("✅ محتوا ذخیره شد.", reply_markup=main_menu())
            return

        if mode == "broadcast":
            context.user_data.pop("mode", None)
            await update.message.reply_text("📤 در حال ارسال...")
            await send_broadcast(context, text)
            return

        if mode == "cedit_title":
            cid = context.user_data.pop("contact_id", None)
            context.user_data.pop("mode", None)
            for c in contacts:
                if c["id"] == cid:
                    c["title"] = text
            await save_contacts()
            await update.message.reply_text("✅ عنوان ذخیره شد.", reply_markup=main_menu())
            return

        if mode == "cedit_value":
            cid = context.user_data.pop("contact_id", None)
            context.user_data.pop("mode", None)
            for c in contacts:
                if c["id"] == cid:
                    c["value"] = text
            await save_contacts()
            await update.message.reply_text("✅ مقدار ذخیره شد.", reply_markup=main_menu())
            return

        if mode == "cedit_icon":
            cid = context.user_data.pop("contact_id", None)
            context.user_data.pop("mode", None)
            for c in contacts:
                if c["id"] == cid:
                    c["icon"] = text
            await save_contacts()
            await update.message.reply_text("✅ آیکون ذخیره شد.", reply_markup=main_menu())
            return

        if mode == "cadd_title":
            context.user_data["new_ctitle"] = text
            context.user_data["mode"]        = "cadd_value"
            ctype = context.user_data.get("new_ctype", "phone")
            hint  = {"phone":"شماره تلفن","whatsapp":"شماره با کد کشور","telegram":"آیدی بدون @","url":"لینک کامل"}.get(ctype,"مقدار")
            await update.message.reply_text(f"🔗 {hint}:", reply_markup=admin_cancel_menu())
            return

        if mode == "cadd_value":
            ctype  = context.user_data.pop("new_ctype", "phone")
            ctitle = context.user_data.pop("new_ctitle", "تماس")
            context.user_data.pop("mode", None)
            icons  = {"phone":"📞","whatsapp":"💬","telegram":"✈️","url":"🌐"}
            contacts.append({
                "id":    f"c{int(time.time())}",
                "icon":  icons.get(ctype, "📞"),
                "title": ctitle,
                "type":  ctype,
                "value": text,
            })
            
            await save_contacts()
            await update.message.reply_text("✅ روش تماس جدید اضافه شد.", reply_markup=main_menu())
            return

        if mode == "wh_set_shifts":
            day_key = context.user_data.pop("wh_day", None)
            context.user_data.pop("mode", None)
            try:
                shifts = []
                for part in text.split(","):
                    fr, to = part.strip().split("-")
                    shifts.append({"from": fr.strip(), "to": to.strip()})
                workhours["schedule"][day_key]["shifts"] = shifts
                await save_workhours()
                await update.message.reply_text("✅ ساعت‌ها ذخیره شد.", reply_markup=main_menu())
            except Exception:
                await update.message.reply_text("❌ فرمت اشتباه!\nمثال: 11:00-14:00,17:00-23:00", reply_markup=main_menu())
            return

        if mode == "wh_set_msg_open":
            context.user_data.pop("mode", None)
            workhours["msg_open"] = text
            await save_workhours()
            await update.message.reply_text("✅ پیام باز بودن ذخیره شد.", reply_markup=main_menu())
            return

        if mode == "wh_set_msg_closed":
            context.user_data.pop("mode", None)
            workhours["msg_closed"] = text
            await save_workhours()
            await update.message.reply_text("✅ پیام بسته بودن ذخیره شد.", reply_markup=main_menu())
            return

    # ── منوی کاربر ──
    for k, v in MENU_ITEMS.items():
        if text == v:
            if k == "4":
                status_line = workhours.get("msg_open", "✅ فروشگاه باز است") if is_open_now() else workhours.get("msg_closed", "🕐 فروشگاه بسته است")
                content     = responses.get(k, "")
                phones      = phone_lines()
                main_text   = box(v, content) if content and content != "تنظیم نشده" else ""
                full_text   = status_line + (f"\n\n{main_text}" if main_text else "") + phones
                kb          = contact_user_keyboard()
                b           = get_banner(k)
                if b.get("active") and b.get("file_id"):
                    try:
                        await update.message.reply_photo(photo=b["file_id"], caption=full_text, reply_markup=kb)
                        return
                    except Exception:
                        pass
                await update.message.reply_text(full_text, reply_markup=kb)
                return
            return await send_with_banner(update.message, box(v, responses.get(k, "تنظیم نشده")), k)

    await update.message.reply_text("⚠️ گزینه نامعتبر است.", reply_markup=main_menu())

# ======================================
# PHOTO HANDLER
# ======================================
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return
    mode = context.user_data.get("mode")

    if mode == "banner_upload":
        key = context.user_data.pop("banner_key", None)
        context.user_data.pop("mode", None)
        if not key:
            await update.message.reply_text("❌ خطا — دوباره امتحان کنید.", reply_markup=main_menu())
            return
        photo = update.message.photo[-1]
        get_banner(key)
        banners[key]["file_id"] = photo.file_id
        banners[key]["active"]  = True
        await save_banners()
        name = SECTION_NAMES.get(key, key)
        await update.message.reply_text(f"✅ بنر بخش «{name}» آپلود و فعال شد!", reply_markup=main_menu())
        return

    if mode == "broadcast":
        context.user_data.pop("mode", None)
        photo   = update.message.photo[-1]
        caption = update.message.caption or ""
        await update.message.reply_text("📤 در حال ارسال...")
        await send_broadcast(context, caption, photo_id=photo.file_id)
        return

# ======================================
# MAIN
# ======================================
async def post_init(app):
    await init_db()
    await load_data()
    await load_banners()
    await load_contacts()
    await load_workhours()
    logger.info("✅ ربات با موفقیت راه‌اندازی شد")

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
