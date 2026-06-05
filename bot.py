# ─────────────────────────────────────────────────
#  STOCKLAND TELEGRAM BOT — Production Ready
#  Architecture: Single-file modular structure
# ─────────────────────────────────────────────────
import os, json, time, asyncio, logging, aiosqlite, jdatetime, pytz
from datetime import datetime
from collections import defaultdict, deque
import aiofiles
from telegram import (Update, ReplyKeyboardMarkup, InlineKeyboardMarkup,
                       InlineKeyboardButton)
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                           CallbackQueryHandler, ContextTypes, filters)

# ── env ──────────────────────────────────────────
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("ALL_PROXY", None)
os.environ["NO_PROXY"] = "*"

TOKEN    = os.getenv("BOT_TOKEN", "8792062012:AAGXforSa1IY45AuC-yOHs2PsdzudvtdD44")
ADMIN_ID = int(os.getenv("ADMIN_ID", "638469407"))

DATA_FILE      = "data.json"
DB_FILE        = "users.db"
BANNER_FILE    = "banner.json"
WORKHOURS_FILE = "workhours.json"
BUTTONS_FILE   = "buttons.json"
SETTINGS_FILE  = "settings.json"
STATS_FILE     = "stats.json"

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
IRAN_TZ = pytz.timezone("Asia/Tehran")

# ════════════════════════════════════════════════
#  TIME UTILITIES
# ════════════════════════════════════════════════
_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
MONTH_FA = {1:"فروردین",2:"اردیبهشت",3:"خرداد",4:"تیر",5:"مرداد",
            6:"شهریور",7:"مهر",8:"آبان",9:"آذر",10:"دی",11:"بهمن",12:"اسفند"}
DAY_NAMES = {"0":"شنبه","1":"یکشنبه","2":"دوشنبه","3":"سه‌شنبه",
             "4":"چهارشنبه","5":"پنجشنبه","6":"جمعه"}

def to_fa(v): return str(v).translate(_FA)
def fmt_t(t): return to_fa(t)

def shamsi_now():
    now = datetime.now(IRAN_TZ)
    j   = jdatetime.datetime.fromgregorian(datetime=now)
    return f"{to_fa(j.day)} {MONTH_FA[j.month]} {to_fa(j.year)} — {to_fa(now.strftime('%H:%M'))}"

def gregorian_now():
    return datetime.now(IRAN_TZ).strftime("%Y-%m-%d %H:%M:%S")

# ════════════════════════════════════════════════
#  MENU STRUCTURE
# ════════════════════════════════════════════════
MENU_ITEMS = {
    "1": "🌐 شبکه‌های اجتماعی",
    "2": "🌐 سایت استوک لند",
    "3": "💰 شرایط اقساط",
    "4": "📞 پشتیبانی",
    "5": "📍 آدرس فروشگاه",
}
SECTION_NAMES = {
    "welcome":        "🏠 خوش‌آمدگویی",
    "1":              "🌐 شبکه‌های اجتماعی",
    "2":              "🌐 سایت استوک لند",
    "3":              "💰 شرایط اقساط",
    "4":              "📞 پشتیبانی",
    "5":              "📍 آدرس فروشگاه",
    "workhours_page": "🕐 ساعت کاری",
}

# ════════════════════════════════════════════════
#  GLOBAL STATE
# ════════════════════════════════════════════════
responses    = None
banners      = {}
workhours    = {}
buttons      = {}
settings     = {}
stats        = {}
active_chats = {}    # {user_id: True}  — loaded from DB on startup

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
    "msg_open":   "✅ هم‌اکنون باز است",
    "msg_closed": "🔴 هم‌اکنون بسته است",
}
DEFAULT_SETTINGS = {
    "show_workhours_in_sections": True,
    "show_datetime_footer":       True,
    "show_workhours_menu":        True,
    "show_catalog_menu":          True,
    "notify_new_user":            False,
    "store_open":                 True,
}
DEFAULT_SEC_WH = {k: True for k in SECTION_NAMES}
DEFAULT_SEC_WH["workhours_page"] = False

# ════════════════════════════════════════════════
#  HELPER ACCESSORS
# ════════════════════════════════════════════════
def get_banner(key):
    banners.setdefault(key, {"file_id": None, "active": False})
    return banners[key]

def get_section_buttons(key):
    buttons.setdefault(key, {"enabled": True, "items": []})
    return buttons[key]

def get_setting(key):
    return settings.get(key, DEFAULT_SETTINGS.get(key, False))

def get_section_wh(key):
    if not get_setting("show_workhours_in_sections"): return False
    return settings.get("section_workhours", DEFAULT_SEC_WH).get(key, True)

def set_section_wh(key, val):
    settings.setdefault("section_workhours", dict(DEFAULT_SEC_WH))[key] = val

# ════════════════════════════════════════════════
#  WORKHOURS LOGIC
# ════════════════════════════════════════════════
def is_open_now():
    if not get_setting("store_open"): return False
    if not workhours.get("enabled", True): return True
    now    = datetime.now(IRAN_TZ)
    j      = jdatetime.datetime.fromgregorian(datetime=now)
    day    = workhours.get("schedule", {}).get(str(j.weekday()), {})
    if not day.get("open", False): return False
    ns = now.strftime("%H:%M")
    return any(s["from"] <= ns <= s["to"] for s in day.get("shifts", []))

def today_workhours_block():
    if not workhours.get("enabled", True): return None
    now    = datetime.now(IRAN_TZ)
    j      = jdatetime.datetime.fromgregorian(datetime=now)
    wd     = str(j.weekday())
    day    = workhours.get("schedule", {}).get(wd, {})
    name   = DAY_NAMES.get(wd, "")
    opened = is_open_now()
    status = workhours.get("msg_open", "✅ باز") if opened else workhours.get("msg_closed", "🔴 بسته")
    o_icons = ["☀️","🌙","🌃","🕯"]
    c_icons = ["⚫️","⚫️","⚫️","⚫️"]
    labels  = ["شیفت اول","شیفت دوم","شیفت سوم","شیفت چهارم"]
    lines = ["━━━━━━━━━━━━━━━", "🏪 وضعیت فروشگاه", f"📅 امروز {name}", ""]
    if not day.get("open"):
        lines.append("❌ امروز تعطیل است")
    else:
        icons = o_icons if opened else c_icons
        for i, s in enumerate(day.get("shifts", [])):
            ic = icons[i] if i < len(icons) else "🕐"
            lb = labels[i] if i < len(labels) else f"شیفت {to_fa(i+1)}"
            lines.append(f"{ic} {lb}   {fmt_t(s['from'])} — {fmt_t(s['to'])}")
    lines += ["", status, "━━━━━━━━━━━━━━━"]
    return "\n".join(lines)

def workhours_full_table():
    rows = []
    for k, name in DAY_NAMES.items():
        day = workhours.get("schedule", {}).get(k, {})
        if not day.get("open"):
            rows.append(f"❌ {name}: تعطیل")
        else:
            sh = " و ".join(f"{fmt_t(s['from'])} تا {fmt_t(s['to'])}" for s in day.get("shifts", []))
            rows.append(f"✅ {name}: {sh}")
    return "\n".join(rows)

def build_message(title, content, section_key):
    wh = today_workhours_block() if get_section_wh(section_key) else None
    ft = f"⏱ {shamsi_now()}" if get_setting("show_datetime_footer") else ""
    lines = [f"📌 {title}", "──────────────", content, "──────────────"]
    if wh:  lines += ["", wh]
    if ft:  lines += ["", "─────────────────", ft]
    return "\n".join(lines)

def progress_bar(v, t, n=8):
    if t == 0: return "░" * n
    f = int(n * v / t)
    return "▓" * f + "░" * (n - f)

def section_page_text(key):
    name = SECTION_NAMES.get(key, key)
    cont = responses.get(key, "") if responses else ""
    b    = get_banner(key)
    sec  = get_section_buttons(key)
    wh   = get_section_wh(key)
    return (f"📋 بخش: {name}\n──────────────\n"
            f"✏️ متن: {'✅ تنظیم شده' if cont and cont not in ('تنظیم نشده','') else '❌ ندارد'}\n"
            f"🖼 بنر: {'✅ فعال' if b.get('active') and b.get('file_id') else ('⏸ غیرفعال' if b.get('file_id') else '➕ ندارد')}\n"
            f"🔘 دکمه‌ها: {len(sec.get('items',[]))} {'✅' if sec.get('enabled') else '❌'}\n"
            f"🕐 ساعت کاری: {'✅' if wh else '❌'}\n──────────────")

# ════════════════════════════════════════════════
#  STATS
# ════════════════════════════════════════════════
async def record_stat(key):
    stats[key] = stats.get(key, 0) + 1
    await save_stats()

# ════════════════════════════════════════════════
#  LOAD / SAVE — JSON FILES
# ════════════════════════════════════════════════
async def _read_json(path, default):
    try:
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            return json.loads(await f.read())
    except Exception:
        return default() if callable(default) else default

async def _write_json(path, data):
    try:
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.error(f"write {path}: {e}")

async def load_data():
    global responses
    responses = await _read_json(DATA_FILE, lambda: dict(MENU_ITEMS, welcome="✨ خوش آمدید به ربات استوک لند"))

async def save_data(): await _write_json(DATA_FILE, responses)

async def load_banners():
    global banners
    banners = await _read_json(BANNER_FILE, dict)
    for k in SECTION_NAMES:
        banners.setdefault(k, {"file_id": None, "active": False})

async def save_banners(): await _write_json(BANNER_FILE, banners)

async def load_workhours():
    global workhours
    workhours = await _read_json(WORKHOURS_FILE, dict)
    if not workhours: workhours = dict(DEFAULT_WORKHOURS); await save_workhours()

async def save_workhours(): await _write_json(WORKHOURS_FILE, workhours)

async def load_buttons():
    global buttons
    buttons = await _read_json(BUTTONS_FILE, dict)
    for k in SECTION_NAMES:
        buttons.setdefault(k, {"enabled": True, "items": []})

async def save_buttons(): await _write_json(BUTTONS_FILE, buttons)

async def load_settings():
    global settings
    settings = await _read_json(SETTINGS_FILE, dict)
    if not settings:
        settings = dict(DEFAULT_SETTINGS)
        settings["section_workhours"] = dict(DEFAULT_SEC_WH)
        await save_settings()

async def save_settings(): await _write_json(SETTINGS_FILE, settings)

async def load_stats():
    global stats
    stats = await _read_json(STATS_FILE, dict)

async def save_stats(): await _write_json(STATS_FILE, stats)

# ════════════════════════════════════════════════
#  DATABASE
# ════════════════════════════════════════════════
db = None

async def init_db():
    global db
    db = await aiosqlite.connect(DB_FILE)
    await db.execute("PRAGMA journal_mode=WAL")
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id    INTEGER PRIMARY KEY,
            username   TEXT,
            first_name TEXT,
            joined_at  TEXT,
            last_seen  TEXT,
            is_blocked INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS categories (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT,
            icon       TEXT DEFAULT '📦',
            parent_id  INTEGER DEFAULT NULL,
            sort_order INTEGER DEFAULT 0,
            is_active  INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS products (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            name        TEXT,
            price       TEXT,
            description TEXT,
            photo_id    TEXT,
            site_url    TEXT,
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS requests (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER,
            username     TEXT,
            first_name   TEXT,
            phone        TEXT,
            product_id   INTEGER,
            product_name TEXT,
            status       TEXT DEFAULT 'new',
            created_at   TEXT
        );
        CREATE TABLE IF NOT EXISTS active_chats (
            user_id    INTEGER PRIMARY KEY,
            started_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_lastseen ON users(last_seen);
    """)
    # migrations
    for col_sql in [
        "ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0",
        "ALTER TABLE categories ADD COLUMN parent_id INTEGER DEFAULT NULL",
    ]:
        try: await db.execute(col_sql)
        except: pass
    await db.commit()

# ── User helpers ──
async def save_user(user):
    now = gregorian_now()
    await db.execute(
        "INSERT OR IGNORE INTO users VALUES (?,?,?,?,?,0)",
        (user.id, user.username or "", user.first_name or "", now, now))
    await db.execute(
        "UPDATE users SET username=?,first_name=?,last_seen=? WHERE user_id=?",
        (user.username or "", user.first_name or "", now, user.id))
    await db.commit()

async def get_all_user_ids():
    async with db.execute("SELECT user_id FROM users WHERE is_blocked=0") as c:
        return [r[0] for r in await c.fetchall()]

async def is_user_blocked(uid):
    async with db.execute("SELECT is_blocked FROM users WHERE user_id=?", (uid,)) as c:
        r = await c.fetchone()
        return bool(r and r[0])

async def set_block(uid, val):
    await db.execute("UPDATE users SET is_blocked=? WHERE user_id=?", (val, uid))
    await db.commit()

async def search_users(q):
    q = f"%{q}%"
    async with db.execute(
        "SELECT user_id,first_name,username,last_seen,is_blocked FROM users "
        "WHERE first_name LIKE ? OR username LIKE ? OR CAST(user_id AS TEXT) LIKE ? "
        "ORDER BY last_seen DESC LIMIT 15", (q,q,q)
    ) as c: return await c.fetchall()

async def get_users_page(offset, limit=15, ft="all"):
    flt = {
        "today":   "WHERE DATE(last_seen)=DATE('now','localtime')",
        "week":    "WHERE last_seen>=datetime('now','-7 days','localtime')",
        "blocked": "WHERE is_blocked=1",
    }
    wh = flt.get(ft, "")
    async with db.execute(
        f"SELECT user_id,first_name,username,last_seen,is_blocked FROM users {wh} "
        f"ORDER BY last_seen DESC LIMIT {limit} OFFSET {offset}"
    ) as c: return await c.fetchall()

async def _count(sql, args=()):
    async with db.execute(sql, args) as c: return (await c.fetchone())[0]

async def total_users():  return await _count("SELECT COUNT(*) FROM users")
async def today_users():  return await _count("SELECT COUNT(*) FROM users WHERE DATE(last_seen)=DATE('now','localtime')")
async def week_users():   return await _count("SELECT COUNT(*) FROM users WHERE last_seen>=datetime('now','-7 days','localtime')")
async def month_users():  return await _count("SELECT COUNT(*) FROM users WHERE last_seen>=datetime('now','-30 days','localtime')")
async def new_today():    return await _count("SELECT COUNT(*) FROM users WHERE DATE(joined_at)=DATE('now','localtime')")
async def blocked_count():return await _count("SELECT COUNT(*) FROM users WHERE is_blocked=1")

# ── Category helpers ──
async def get_categories(active_only=True, parent_id=None):
    cond = "is_active=1" if active_only else "1=1"
    if parent_id is None:
        sql  = f"SELECT id,name,icon,is_active,parent_id FROM categories WHERE {cond} AND parent_id IS NULL ORDER BY sort_order,id"
        args = ()
    else:
        sql  = f"SELECT id,name,icon,is_active,parent_id FROM categories WHERE {cond} AND parent_id=? ORDER BY sort_order,id"
        args = (parent_id,)
    async with db.execute(sql, args) as c: return await c.fetchall()

async def get_category(cat_id):
    async with db.execute(
        "SELECT id,name,icon,is_active,parent_id FROM categories WHERE id=?", (cat_id,)
    ) as c: return await c.fetchone()

async def has_subcategories(cat_id):
    return await _count("SELECT COUNT(*) FROM categories WHERE parent_id=? AND is_active=1", (cat_id,)) > 0

# ── Product helpers ──
# Schema: id(0),name(1),price(2),description(3),photo_id(4),site_url(5),is_active(6),category_id(7)
async def get_products(cat_id, active_only=True):
    wh = "AND is_active=1" if active_only else ""
    async with db.execute(
        f"SELECT id,name,price,description,photo_id,site_url,is_active,category_id "
        f"FROM products WHERE category_id=? {wh} ORDER BY id", (cat_id,)
    ) as c: return await c.fetchall()

async def get_product(pid):
    async with db.execute(
        "SELECT id,name,price,description,photo_id,site_url,is_active,category_id "
        "FROM products WHERE id=?", (pid,)
    ) as c: return await c.fetchone()

async def search_products(q):
    q = f"%{q}%"
    async with db.execute(
        "SELECT id,name,price,description,photo_id,site_url,is_active,category_id "
        "FROM products WHERE (name LIKE ? OR description LIKE ?) AND is_active=1 "
        "ORDER BY name LIMIT 20", (q, q)
    ) as c: return await c.fetchall()

# ── Chat helpers (persistent) ──
async def load_active_chats():
    async with db.execute("SELECT user_id FROM active_chats") as c:
        for r in await c.fetchall():
            active_chats[r[0]] = True

async def open_chat(uid):
    await db.execute("INSERT OR REPLACE INTO active_chats VALUES (?,?)", (uid, gregorian_now()))
    await db.commit()
    active_chats[uid] = True

async def close_chat(uid):
    await db.execute("DELETE FROM active_chats WHERE user_id=?", (uid,))
    await db.commit()
    active_chats.pop(uid, None)

# ── Request helpers ──
async def save_request(uid, username, first_name, phone, pid, pname):
    await db.execute(
        "INSERT INTO requests (user_id,username,first_name,phone,product_id,product_name,status,created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (uid, username or "", first_name or "", phone, pid, pname, "new", gregorian_now()))
    await db.commit()

async def get_requests(status=None):
    wh = f"WHERE status='{status}'" if status else ""
    async with db.execute(
        f"SELECT id,user_id,username,first_name,phone,product_name,status,created_at "
        f"FROM requests {wh} ORDER BY id DESC LIMIT 30"
    ) as c: return await c.fetchall()

async def close_request(rid):
    await db.execute("UPDATE requests SET status='done' WHERE id=?", (rid,))
    await db.commit()

# ════════════════════════════════════════════════
#  ANTI-SPAM
# ════════════════════════════════════════════════
_WINDOW, _LIMIT, _BLOCK = 10, 7, 60
_spam    = defaultdict(lambda: deque(maxlen=_LIMIT))
_blocked = {}

async def anti_spam(uid):
    if uid == ADMIN_ID: return True
    if await is_user_blocked(uid): return False
    now = time.time()
    if uid in _blocked and _blocked[uid] > now: return False
    q = _spam[uid]; q.append(now)
    if len(q) >= _LIMIT and (now - q[0]) <= _WINDOW:
        _blocked[uid] = now + _BLOCK; return False
    return True

# ════════════════════════════════════════════════
#  KEYBOARDS — USER
# ════════════════════════════════════════════════
def main_menu():
    keys = list(MENU_ITEMS.keys()); rows = []
    for i in range(0, len(keys), 2):
        row = [MENU_ITEMS[keys[i]]]
        if i+1 < len(keys): row.append(MENU_ITEMS[keys[i+1]])
        rows.append(row)
    extra = []
    if get_setting("show_workhours_menu"): extra.append("🕐 ساعت کاری")
    if get_setting("show_catalog_menu"):   extra.append("🛍 محصولات")
    if extra: rows.append(extra)
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def chat_menu():
    return ReplyKeyboardMarkup([["❌ پایان چت"]], resize_keyboard=True)

def user_section_kb(key):
    sec = get_section_buttons(key)
    if not sec.get("enabled", True): return None
    items = [x for x in sec.get("items", []) if x.get("url")]
    if not items: return None
    btns = []; row = []
    for i, item in enumerate(items):
        row.append(InlineKeyboardButton(item["title"], url=item["url"]))
        if len(row) == 2 or i == len(items)-1: btns.append(row); row = []
    return InlineKeyboardMarkup(btns) if btns else None

def catalog_root_kb(cats):
    btns = [[InlineKeyboardButton(f"{c[2]} {c[1]}", callback_data=f"cat_{c[0]}")] for c in cats]
    btns.append([InlineKeyboardButton("🔍 جستجوی محصول", callback_data="catalog_search")])
    return InlineKeyboardMarkup(btns)

def catalog_subcats_kb(subcats, back_cb):
    btns = [[InlineKeyboardButton(f"{s[2]} {s[1]}", callback_data=f"cat_{s[0]}")] for s in subcats]
    btns.append([InlineKeyboardButton("🔙 برگشت", callback_data=back_cb)])
    return InlineKeyboardMarkup(btns)

def catalog_products_kb(products, back_cb):
    btns = [[InlineKeyboardButton(f"📱 {p[1]}", callback_data=f"prd_{p[0]}")] for p in products]
    btns.append([InlineKeyboardButton("🔙 برگشت", callback_data=back_cb)])
    return InlineKeyboardMarkup(btns)

def product_kb(p):
    # p: id(0),name(1),price(2),desc(3),photo_id(4),site_url(5),is_active(6),cat_id(7)
    btns = []
    if p[5]: btns.append([InlineKeyboardButton("🌐 مشاهده / خرید از سایت", url=p[5])])
    btns.append([InlineKeyboardButton("📋 درخواست خرید", callback_data=f"req_{p[0]}")])
    btns.append([InlineKeyboardButton("🔙 برگشت", callback_data=f"cat_{p[7]}")])
    return InlineKeyboardMarkup(btns)

def support_kb(key):
    """کیبورد پشتیبانی: دکمه‌های بخش + دکمه چت"""
    sec_kb = user_section_kb(key)
    chat_row = [InlineKeyboardButton("💬 شروع گفتگو با پشتیبانی", callback_data="start_chat")]
    if sec_kb:
        rows = [chat_row] + sec_kb.inline_keyboard
    else:
        rows = [chat_row]
    return InlineKeyboardMarkup(rows)

# ════════════════════════════════════════════════
#  KEYBOARDS — ADMIN
# ════════════════════════════════════════════════
def admin_cancel_menu():
    return ReplyKeyboardMarkup([["❌ لغو عملیات"]], resize_keyboard=True)

def back_admin():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت به پنل", callback_data="back_to_admin")]])

def admin_menu():
    op = is_open_now()
    st = "🟢" if op else "🔴"
    tg = "🔴 بستن فروشگاه" if op else "🟢 باز کردن فروشگاه"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 داشبورد",        callback_data="dash"),
         InlineKeyboardButton("👥 کاربران",         callback_data="users_menu")],
        [InlineKeyboardButton("📋 مدیریت بخش‌ها",  callback_data="sections")],
        [InlineKeyboardButton("🛍 کاتالوگ",        callback_data="admin_catalog"),
         InlineKeyboardButton("📨 درخواست‌ها",     callback_data="admin_requests")],
        [InlineKeyboardButton("💬 چت‌های فعال",    callback_data="active_chats_list")],
        [InlineKeyboardButton("🕐 ساعت کاری",      callback_data="workhours_menu"),
         InlineKeyboardButton("⚙️ تنظیمات",        callback_data="settings_menu")],
        [InlineKeyboardButton("📢 پخش همگانی",     callback_data="broadcast")],
        [InlineKeyboardButton("💾 بک‌آپ",          callback_data="backup"),
         InlineKeyboardButton("📊 آمار",           callback_data="sections_stats")],
        [InlineKeyboardButton(f"{st} {tg}",        callback_data="quick_toggle")],
    ])

def sections_list_kb():
    btns = []
    for key, name in SECTION_NAMES.items():
        if key == "workhours_page": continue
        cont = responses.get(key, "") if responses else ""
        b    = get_banner(key); sec = get_section_buttons(key)
        ti   = "✅" if cont and cont not in ("تنظیم نشده","") else "➕"
        bi   = "🖼" if b.get("active") and b.get("file_id") else "○"
        bti  = f"🔘{len(sec.get('items',[]))}" if sec.get("enabled") else "○"
        btns.append([InlineKeyboardButton(f"{name}  {ti}{bi}{bti}", callback_data=f"sec_{key}")])
    btns.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_to_admin")])
    return InlineKeyboardMarkup(btns)

def section_kb(key):
    b = get_banner(key); sec = get_section_buttons(key); wh = get_section_wh(key)
    bs = "🖼✅" if b.get("active") and b.get("file_id") else ("🖼⏸" if b.get("file_id") else "🖼➕")
    bn = f"🔘✅({len(sec.get('items',[]))})" if sec.get("enabled") else f"🔘❌({len(sec.get('items',[]))})"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ ویرایش متن",      callback_data=f"sec_text_{key}")],
        [InlineKeyboardButton(f"{bs} بنر",           callback_data=f"sec_banner_{key}")],
        [InlineKeyboardButton(f"{bn} دکمه‌ها",      callback_data=f"sec_btns_{key}")],
        [InlineKeyboardButton(f"🕐{'✅' if wh else '❌'} ساعت کاری", callback_data=f"sec_wh_{key}")],
        [InlineKeyboardButton("🔙 برگشت",           callback_data="sections")],
    ])

def banner_kb(key):
    b  = get_banner(key)
    tg = "🔴 غیرفعال" if b.get("active") else "🟢 فعال کردن"
    btns = [
        [InlineKeyboardButton("📤 آپلود / تغییر", callback_data=f"ban_up_{key}")],
        [InlineKeyboardButton(tg,                  callback_data=f"ban_tg_{key}")],
    ]
    if b.get("file_id"): btns.append([InlineKeyboardButton("🗑 حذف", callback_data=f"ban_dl_{key}")])
    btns.append([InlineKeyboardButton("🔙 برگشت", callback_data=f"sec_{key}")])
    return InlineKeyboardMarkup(btns)

def section_btns_kb(key):
    sec = get_section_buttons(key)
    tg  = "🔴 غیرفعال همه" if sec.get("enabled") else "🟢 فعال همه"
    btns = [[InlineKeyboardButton(tg, callback_data=f"btn_tg_{key}")]]
    for item in sec.get("items", []):
        btns.append([
            InlineKeyboardButton(f"🔗 {item['title']}", callback_data=f"btn_edt_{key}_{item['id']}"),
            InlineKeyboardButton("🗑", callback_data=f"btn_del_{key}_{item['id']}"),
        ])
    btns.append([InlineKeyboardButton("➕ دکمه جدید", callback_data=f"btn_add_{key}")])
    btns.append([InlineKeyboardButton("🔙 برگشت",    callback_data=f"sec_{key}")])
    return InlineKeyboardMarkup(btns)

def workhours_kb():
    en = workhours.get("enabled", True)
    btns = [[InlineKeyboardButton("🔴 غیرفعال" if en else "🟢 فعال", callback_data="wh_toggle")]]
    for k, name in DAY_NAMES.items():
        day = workhours.get("schedule", {}).get(k, {})
        btns.append([InlineKeyboardButton(f"{'✅' if day.get('open') else '❌'} {name}", callback_data=f"wh_day_{k}")])
    btns += [
        [InlineKeyboardButton("✏️ پیام باز بودن",  callback_data="wh_msg_open")],
        [InlineKeyboardButton("✏️ پیام بسته بودن", callback_data="wh_msg_closed")],
        [InlineKeyboardButton("🔙 برگشت",          callback_data="back_to_admin")],
    ]
    return InlineKeyboardMarkup(btns)

def workhours_day_kb(dk):
    day = workhours.get("schedule", {}).get(dk, {})
    tg  = "🔴 تعطیل" if day.get("open") else "🟢 باز کردن"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tg,                   callback_data=f"wh_dtg_{dk}")],
        [InlineKeyboardButton("✏️ تنظیم ساعت‌ها",  callback_data=f"wh_shifts_{dk}")],
        [InlineKeyboardButton("🔙 برگشت",           callback_data="workhours_menu")],
    ])

def settings_kb():
    def t(k): return "✅" if get_setting(k) else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{t('show_workhours_in_sections')} ساعت کاری در بخش‌ها", callback_data="stg_show_workhours_in_sections")],
        [InlineKeyboardButton(f"{t('show_datetime_footer')} تاریخ و ساعت",             callback_data="stg_show_datetime_footer")],
        [InlineKeyboardButton(f"{t('show_workhours_menu')} گزینه ساعت کاری در منو",   callback_data="stg_show_workhours_menu")],
        [InlineKeyboardButton(f"{t('show_catalog_menu')} گزینه محصولات در منو",       callback_data="stg_show_catalog_menu")],
        [InlineKeyboardButton(f"{t('notify_new_user')} اعلان عضو جدید",               callback_data="stg_notify_new_user")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="back_to_admin")],
    ])

def users_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 همه",    callback_data="ulist_all_0"),
         InlineKeyboardButton("📅 امروز", callback_data="ulist_today_0")],
        [InlineKeyboardButton("📆 هفته",  callback_data="ulist_week_0"),
         InlineKeyboardButton("🚫 بلاک",  callback_data="ulist_blocked_0")],
        [InlineKeyboardButton("🔍 جستجو", callback_data="users_search")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="back_to_admin")],
    ])

def users_list_kb(rows, offset, ft, total):
    btns = []
    for r in rows:
        bl = "🚫 " if r[4] else ""
        btns.append([InlineKeyboardButton(f"{bl}{r[1] or '—'} | {r[0]}", callback_data=f"uview_{r[0]}")])
    nav = []
    if offset > 0:       nav.append(InlineKeyboardButton("◀️", callback_data=f"ulist_{ft}_{offset-15}"))
    if offset+15 < total: nav.append(InlineKeyboardButton("▶️", callback_data=f"ulist_{ft}_{offset+15}"))
    if nav: btns.append(nav)
    btns.append([InlineKeyboardButton("🔙 برگشت", callback_data="users_menu")])
    return InlineKeyboardMarkup(btns)

def user_detail_kb(uid, is_bl):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ رفع بلاک" if is_bl else "🚫 بلاک", callback_data=f"utoggle_{uid}")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="users_menu")],
    ])

# ── Catalog admin keyboards ──
def admin_catalog_kb(cats):
    btns = []
    for c in cats:
        en = "✅" if c[3] else "❌"
        btns.append([InlineKeyboardButton(f"{en} {c[2]} {c[1]}", callback_data=f"acat_{c[0]}")])
    btns.append([InlineKeyboardButton("➕ دسته اصلی جدید", callback_data="acat_new_root")])
    btns.append([InlineKeyboardButton("🔙 برگشت",          callback_data="back_to_admin")])
    return InlineKeyboardMarkup(btns)

def admin_category_kb(cat_id, subcats, products, parent_id=None):
    btns = []
    for s in subcats:
        en = "✅" if s[3] else "❌"
        btns.append([InlineKeyboardButton(f"  ↳{en} {s[2]} {s[1]}", callback_data=f"acat_{s[0]}")])
    for p in products:
        en = "✅" if p[6] else "❌"
        btns.append([InlineKeyboardButton(f"  📱{en} {p[1]}", callback_data=f"aprd_{p[0]}")])
    btns.append([InlineKeyboardButton("➕ زیردسته جدید", callback_data=f"acat_new_sub_{cat_id}")])
    btns.append([InlineKeyboardButton("➕ محصول جدید",   callback_data=f"aprd_new_{cat_id}")])
    btns.append([InlineKeyboardButton("✏️ ویرایش دسته", callback_data=f"acat_edit_{cat_id}")])
    btns.append([InlineKeyboardButton("🗑 حذف دسته",    callback_data=f"acat_del_{cat_id}")])
    back_cb = "admin_catalog" if parent_id is None else f"acat_{parent_id}"
    btns.append([InlineKeyboardButton("🔙 برگشت",       callback_data=back_cb)])
    return InlineKeyboardMarkup(btns)

def admin_product_kb(pid, cat_id, is_active):
    tg = "🔴 غیرفعال" if is_active else "🟢 فعال"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ نام",         callback_data=f"aprd_ename_{pid}"),
         InlineKeyboardButton("💰 قیمت",        callback_data=f"aprd_eprice_{pid}")],
        [InlineKeyboardButton("📝 توضیح",       callback_data=f"aprd_edesc_{pid}"),
         InlineKeyboardButton("📸 عکس",         callback_data=f"aprd_ephoto_{pid}")],
        [InlineKeyboardButton("🌐 لینک محصول",  callback_data=f"aprd_esite_{pid}")],
        [InlineKeyboardButton(tg,               callback_data=f"aprd_etog_{pid}")],
        [InlineKeyboardButton("🗑 حذف",         callback_data=f"aprd_del_{pid}")],
        [InlineKeyboardButton("🔙 برگشت",       callback_data=f"acat_{cat_id}")],
    ])

def requests_kb(reqs):
    btns = []
    for r in reqs:
        st = "🆕" if r[6]=="new" else "✅"
        btns.append([InlineKeyboardButton(f"{st} {r[5]} — {r[3]}", callback_data=f"req_view_{r[0]}")])
    btns.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_to_admin")])
    return InlineKeyboardMarkup(btns)

def request_detail_kb(rid, status):
    btns = []
    if status == "new":
        btns.append([InlineKeyboardButton("✅ پیگیری شد", callback_data=f"req_done_{rid}")])
    btns.append([InlineKeyboardButton("🔙 برگشت", callback_data="admin_requests")])
    return InlineKeyboardMarkup(btns)

def active_chats_kb():
    if not active_chats:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="back_to_admin")]])
    btns = []
    for uid in active_chats:
        btns.append([InlineKeyboardButton(f"💬 کاربر {uid}", callback_data=f"chat_select_{uid}")])
    btns.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_to_admin")])
    return InlineKeyboardMarkup(btns)

# ════════════════════════════════════════════════
#  SEND WITH BANNER
# ════════════════════════════════════════════════
async def send_with_banner(msg, text, key, reply_markup=None):
    b = get_banner(key)
    if b.get("active") and b.get("file_id"):
        try:
            await msg.reply_photo(photo=b["file_id"], caption=text, reply_markup=reply_markup)
            return
        except Exception as e:
            logger.error(f"banner [{key}]: {e}")
    await msg.reply_text(text, reply_markup=reply_markup)

# ════════════════════════════════════════════════
#  BROADCAST
# ════════════════════════════════════════════════
async def send_broadcast(context, text, photo_id=None):
    users   = await get_all_user_ids()
    total   = len(users)
    success = failed = 0
    status  = await context.bot.send_message(ADMIN_ID, f"📢 شروع پخش به {to_fa(total)} کاربر...")
    for i, uid in enumerate(users, 1):
        try:
            if photo_id: await context.bot.send_photo(uid, photo=photo_id, caption=text)
            else:        await context.bot.send_message(uid, text)
            success += 1
        except:
            failed += 1
        if i % 10 == 0 or i == total:
            try: await status.edit_text(f"📢 پخش...\n✅ {to_fa(success)} | ❌ {to_fa(failed)} | {to_fa(i)}/{to_fa(total)}")
            except: pass
        await asyncio.sleep(0.2)
    await status.edit_text(f"✅ پخش تمام شد!\nموفق: {to_fa(success)} | شکست: {to_fa(failed)}")

# ════════════════════════════════════════════════
#  BACKUP
# ════════════════════════════════════════════════
async def send_backup(bot):
    ts    = shamsi_now().replace(" ","_").replace("—","-").replace(":","-")
    files = [(DATA_FILE,"data"),(BANNER_FILE,"banner"),(WORKHOURS_FILE,"workhours"),
             (BUTTONS_FILE,"buttons"),(SETTINGS_FILE,"settings"),(STATS_FILE,"stats"),(DB_FILE,"db")]
    await bot.send_message(ADMIN_ID, f"💾 بک‌آپ کامل — {shamsi_now()}")
    for fp, label in files:
        try:
            async with aiofiles.open(fp, "rb") as f: content = await f.read()
            ext = fp.split(".")[-1]
            await bot.send_document(ADMIN_ID, document=content, filename=f"bkp_{label}_{ts}.{ext}")
        except Exception as e:
            logger.error(f"backup {fp}: {e}")

# ════════════════════════════════════════════════
#  HANDLERS — START / ADMIN
# ════════════════════════════════════════════════
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
                f"{'@'+user.username if user.username else '—'}\n🆔 {user.id}")
        except: pass
    wt   = responses.get("welcome", "✨ خوش آمدید به ربات استوک لند")
    full = build_message("خوش‌آمدگویی", wt, "welcome")
    kb   = user_section_kb("welcome")
    await send_with_banner(update.message, full, "welcome", reply_markup=kb or main_menu())

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ دسترسی ندارید")
    await update.message.reply_text("👑 پنل مدیریت", reply_markup=admin_menu())

# ════════════════════════════════════════════════
#  CALLBACKS — USER (non-admin)
# ════════════════════════════════════════════════
async def handle_user_callback(query, context: ContextTypes.DEFAULT_TYPE):
    data = query.data
    user = query.from_user

    if data == "start_chat":
        if active_chats.get(user.id):
            await query.message.reply_text(
                "💬 یک چت از قبل برای شما فعال است.\nپیام بفرستید یا چت را پایان دهید.",
                reply_markup=chat_menu())
            return
        await open_chat(user.id)
        try:
            async with db.execute("SELECT first_name,username FROM users WHERE user_id=?", (user.id,)) as c:
                row = await c.fetchone()
            name  = row[0] if row else user.first_name or "—"
            uname = f"@{row[1]}" if row and row[1] else str(user.id)
            await context.bot.send_message(
                ADMIN_ID,
                f"🟢 چت جدید!\n👤 {name} | {uname}\n🆔 {user.id}\n──────────────\nبرای پاسخ از «💬 چت‌های فعال» انتخاب کنید.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(f"💬 پاسخ به {name}", callback_data=f"chat_select_{user.id}")
                ]]))
        except Exception as e:
            logger.error(f"start_chat notify: {e}")
        await query.message.reply_text(
            "💬 چت شما شروع شد!\nپیام خود را بنویسید.\nبرای پایان دکمه زیر را بزنید:",
            reply_markup=chat_menu())
        return

    if data == "catalog_back":
        cats = await get_categories()
        ft   = f"\n─────────────────\n⏱ {shamsi_now()}" if get_setting("show_datetime_footer") else ""
        if not cats:
            await query.message.edit_text("📭 محصولی موجود نیست.")
            return
        await query.message.edit_text(
            f"🛍 کاتالوگ استوک لند\nدسته‌بندی را انتخاب کنید:{ft}",
            reply_markup=catalog_root_kb(cats))
        return

    if data == "catalog_search":
        context.user_data["mode"] = "catalog_search"
        await query.message.reply_text(
            "🔍 نام یا مدل محصول را بنویسید:\nمثال: سامسونگ S24، آیفون 15",
            reply_markup=ReplyKeyboardMarkup([["❌ لغو عملیات"]], resize_keyboard=True))
        return

    if data.startswith("cat_"):
        cat_id = int(data[4:])
        cat    = await get_category(cat_id)
        if not cat: return
        parent_id = cat[4]
        back_cb   = "catalog_back" if parent_id is None else f"cat_{parent_id}"
        if await has_subcategories(cat_id):
            subcats = await get_categories(active_only=True, parent_id=cat_id)
            await query.message.edit_text(
                f"🛍 {cat[2]} {cat[1]}\nدسته‌بندی را انتخاب کنید:",
                reply_markup=catalog_subcats_kb(subcats, back_cb))
        else:
            products = await get_products(cat_id)
            if not products:
                await query.message.edit_text(
                    "📭 محصولی در این دسته موجود نیست.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data=back_cb)]]))
                return
            await query.message.edit_text(
                f"🛍 {cat[2]} {cat[1]}\n{to_fa(len(products))} محصول:",
                reply_markup=catalog_products_kb(products, back_cb))
        return

    if data.startswith("prd_"):
        pid = int(data[4:])
        p   = await get_product(pid)
        if not p: return
        await record_stat(f"prd_{pid}")
        ft   = f"\n─────────────────\n⏱ {shamsi_now()}" if get_setting("show_datetime_footer") else ""
        text = f"📱 {p[1]}\n💰 قیمت: {p[2]}"
        if p[3]: text += f"\n\n📝 {p[3]}"
        text += ft
        kb   = product_kb(p)
        if p[4]:
            try: await query.message.reply_photo(photo=p[4], caption=text, reply_markup=kb); return
            except: pass
        await query.message.reply_text(text, reply_markup=kb)
        return

    if data.startswith("req_"):
        pid = int(data[4:])
        p   = await get_product(pid)
        if not p: return
        context.user_data.update({"mode": "req_phone", "req_pid": pid, "req_name": p[1]})
        await query.message.reply_text(
            f"📋 درخواست خرید: {p[1]}\n\nشماره تماس خود را وارد کنید:",
            reply_markup=ReplyKeyboardMarkup([["❌ لغو عملیات"]], resize_keyboard=True))
        return

# ════════════════════════════════════════════════
#  CALLBACKS — MAIN DISPATCHER
# ════════════════════════════════════════════════
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    uid   = query.from_user.id

    # route non-admin callbacks
    if uid != ADMIN_ID:
        await handle_user_callback(query, context)
        return

    # ════ ADMIN CALLBACKS ════

    if data == "back_to_admin":
        await query.message.edit_text("👑 پنل مدیریت", reply_markup=admin_menu())

    elif data == "quick_toggle":
        settings["store_open"] = not get_setting("store_open")
        await save_settings()
        await query.answer("🟢 باز شد" if settings["store_open"] else "🔴 بسته شد", show_alert=True)
        await query.message.edit_text("👑 پنل مدیریت", reply_markup=admin_menu())

    elif data == "dash":
        t,d,w,m,nt,bl = (await total_users(), await today_users(), await week_users(),
                         await month_users(), await new_today(), await blocked_count())
        wh = today_workhours_block() or ""
        await query.message.edit_text(
            f"📊 داشبورد — {shamsi_now()}\n══════════════\n"
            f"👥 کل: {to_fa(t)}  |  🚫 بلاک: {to_fa(bl)}\n══════════════\n"
            f"🆕 عضو امروز: {to_fa(nt)}\n"
            f"📅 فعال امروز: {to_fa(d)}  {progress_bar(d,t)}\n"
            f"📆 فعال هفته: {to_fa(w)}  {progress_bar(w,t)}\n"
            f"🗓 فعال ماه: {to_fa(m)}  {progress_bar(m,t)}\n"
            f"💬 چت‌های فعال: {to_fa(len(active_chats))}\n"
            f"══════════════\n"
            f"🏪 وضعیت: {'🟢 باز' if is_open_now() else '🔴 بسته'}\n{wh}",
            reply_markup=admin_menu())

    elif data == "sections_stats":
        if not stats:
            await query.message.edit_text("📊 هنوز آماری ثبت نشده.", reply_markup=back_admin())
            return
        ss = sorted(stats.items(), key=lambda x: x[1], reverse=True)
        tv = sum(stats.values())
        lines = ["📊 آمار بازدید:\n──────────────"]
        for k, cnt in ss:
            name = SECTION_NAMES.get(k, k)
            pct  = int(100*cnt/tv) if tv else 0
            lines.append(f"{name}\n  {progress_bar(cnt,tv)} {to_fa(cnt)} ({to_fa(pct)}%)")
        lines.append(f"──────────────\nمجموع: {to_fa(tv)}")
        await query.message.edit_text("\n".join(lines), reply_markup=back_admin())

    elif data == "broadcast":
        context.user_data["mode"] = "broadcast"
        await query.message.reply_text(
            "📢 پیام پخش را ارسال کنید:\n• فقط متن → متنی\n• عکس+کپشن → با تصویر",
            reply_markup=admin_cancel_menu())

    elif data == "backup":
        await query.message.edit_text("💾 در حال ارسال...", reply_markup=back_admin())
        await send_backup(query.message._bot)
        await query.message.edit_text("✅ بک‌آپ ارسال شد.", reply_markup=back_admin())

    # ── کاربران ──
    elif data == "users_menu":
        t  = await total_users(); bl = await blocked_count()
        await query.message.edit_text(
            f"👥 مدیریت کاربران\n──────────────\nکل: {to_fa(t)} | بلاک: {to_fa(bl)}",
            reply_markup=users_menu_kb())

    elif data == "users_search":
        context.user_data["mode"] = "users_search"
        await query.message.reply_text("🔍 نام، آیدی یا یوزرنیم:", reply_markup=admin_cancel_menu())

    elif data.startswith("ulist_"):
        parts = data.split("_"); ft = parts[1]; offset = int(parts[2])
        flt   = {"today":"WHERE DATE(last_seen)=DATE('now','localtime')",
                 "week":"WHERE last_seen>=datetime('now','-7 days','localtime')",
                 "blocked":"WHERE is_blocked=1"}
        total = await _count(f"SELECT COUNT(*) FROM users {flt.get(ft,'')}")
        rows  = await get_users_page(offset, 15, ft)
        label = {"all":"همه","today":"امروز","week":"هفته","blocked":"بلاک"}.get(ft, "")
        await query.message.edit_text(
            f"👥 {label}\n{to_fa(offset+1)} تا {to_fa(min(offset+15,total))} از {to_fa(total)}:",
            reply_markup=users_list_kb(rows, offset, ft, total))

    elif data.startswith("uview_"):
        uid2 = int(data[6:])
        async with db.execute(
            "SELECT user_id,first_name,username,joined_at,last_seen,is_blocked FROM users WHERE user_id=?",
            (uid2,)
        ) as c: row = await c.fetchone()
        if not row: await query.answer("یافت نشد!", show_alert=True); return
        bl_st = "🚫 بلاک" if row[5] else "✅ فعال"
        await query.message.edit_text(
            f"👤 {row[1] or '—'}\n{'@'+row[2] if row[2] else '—'}\n🆔 {row[0]}\n"
            f"عضویت: {row[3]}\nآخرین فعالیت: {row[4]}\nوضعیت: {bl_st}",
            reply_markup=user_detail_kb(uid2, bool(row[5])))

    elif data.startswith("utoggle_"):
        uid2 = int(data[8:])
        async with db.execute("SELECT is_blocked FROM users WHERE user_id=?", (uid2,)) as c:
            row = await c.fetchone()
        if not row: return
        new_val = 0 if row[0] else 1
        await set_block(uid2, new_val)
        await query.answer("✅ رفع بلاک" if not new_val else "🚫 بلاک شد", show_alert=True)
        async with db.execute(
            "SELECT user_id,first_name,username,joined_at,last_seen,is_blocked FROM users WHERE user_id=?",
            (uid2,)
        ) as c: row = await c.fetchone()
        await query.message.edit_text(
            f"👤 {row[1] or '—'}\n🆔 {row[0]}\nوضعیت: {'🚫 بلاک' if row[5] else '✅ فعال'}",
            reply_markup=user_detail_kb(uid2, bool(row[5])))

    # ── بخش‌ها ──
    elif data == "sections":
        await query.message.edit_text("📋 مدیریت بخش‌ها:", reply_markup=sections_list_kb())

    elif data.startswith("sec_") and not any(data.startswith(p) for p in
            ["sec_text_","sec_banner_","sec_btns_","sec_wh_"]):
        key = data[4:]
        await query.message.edit_text(section_page_text(key), reply_markup=section_kb(key))

    elif data.startswith("sec_text_"):
        key = data[9:]; context.user_data.update({"mode":"edit_text","edit_key":key})
        await query.message.reply_text(
            f"✏️ متن فعلی:\n\n{responses.get(key,'تنظیم نشده')}\n\nمتن جدید:",
            reply_markup=admin_cancel_menu())

    elif data.startswith("sec_wh_"):
        key = data[7:]; set_section_wh(key, not get_section_wh(key)); await save_settings()
        await query.answer("✅ تغییر کرد", show_alert=True)
        await query.message.edit_text(section_page_text(key), reply_markup=section_kb(key))

    elif data.startswith("sec_banner_"):
        key = data[11:]; b = get_banner(key)
        await query.message.edit_text(
            f"🖼 بنر: {SECTION_NAMES.get(key,key)}\n"
            f"عکس: {'✅' if b.get('file_id') else '❌'}\n"
            f"وضعیت: {'✅ فعال' if b.get('active') else '❌ غیرفعال'}",
            reply_markup=banner_kb(key))

    elif data.startswith("ban_up_"):
        key = data[7:]; context.user_data.update({"mode":"banner_upload","banner_key":key})
        await query.message.reply_text(
            f"📤 عکس بنر «{SECTION_NAMES.get(key,key)}» را ارسال کنید:",
            reply_markup=admin_cancel_menu())

    elif data.startswith("ban_tg_"):
        key = data[7:]; b = get_banner(key)
        if not b.get("file_id"): await query.answer("ابتدا عکس آپلود کنید!", show_alert=True); return
        b["active"] = not b.get("active", False); await save_banners()
        await query.answer("✅ فعال" if b["active"] else "❌ غیرفعال", show_alert=True)
        await query.message.edit_text(
            f"🖼 {SECTION_NAMES.get(key,key)}\nوضعیت: {'✅ فعال' if b['active'] else '❌ غیرفعال'}",
            reply_markup=banner_kb(key))

    elif data.startswith("ban_dl_"):
        key = data[7:]; banners[key] = {"file_id":None,"active":False}; await save_banners()
        await query.answer("🗑 حذف شد.", show_alert=True)
        await query.message.edit_text(f"🖼 {SECTION_NAMES.get(key,key)}\nعکس: ❌", reply_markup=banner_kb(key))

    elif data.startswith("sec_btns_"):
        key = data[9:]; sec = get_section_buttons(key)
        await query.message.edit_text(
            f"🔘 دکمه‌های: {SECTION_NAMES.get(key,key)}\n"
            f"وضعیت: {'✅' if sec.get('enabled') else '❌'} | تعداد: {len(sec.get('items',[]))}",
            reply_markup=section_btns_kb(key))

    elif data.startswith("btn_tg_"):
        key = data[7:]; sec = get_section_buttons(key)
        sec["enabled"] = not sec.get("enabled", True); await save_buttons()
        await query.answer("✅ فعال" if sec["enabled"] else "❌ غیرفعال", show_alert=True)
        await query.message.edit_text(
            f"🔘 {SECTION_NAMES.get(key,key)}\nوضعیت: {'✅' if sec['enabled'] else '❌'}",
            reply_markup=section_btns_kb(key))

    elif data.startswith("btn_add_"):
        key = data[8:]; context.user_data.update({"mode":"btn_add_title","btn_key":key})
        await query.message.reply_text(
            f"➕ دکمه جدید برای «{SECTION_NAMES.get(key,key)}»\nعنوان:",
            reply_markup=admin_cancel_menu())

    elif data.startswith("btn_edt_"):
        parts = data[8:].split("_", 1); key, bid = parts[0], parts[1]
        sec = get_section_buttons(key)
        item = next((x for x in sec.get("items",[]) if x["id"]==bid), None)
        if not item: await query.answer("یافت نشد!", show_alert=True); return
        context.user_data.update({"mode":"btn_edit_title","btn_key":key,"btn_id":bid})
        await query.message.reply_text(
            f"✏️ «{item['title']}»\nعنوان جدید (یا . بدون تغییر):",
            reply_markup=admin_cancel_menu())

    elif data.startswith("btn_del_"):
        parts = data[8:].split("_", 1); key, bid = parts[0], parts[1]
        sec = get_section_buttons(key)
        sec["items"] = [x for x in sec.get("items",[]) if x["id"] != bid]; await save_buttons()
        await query.answer("🗑 حذف شد.", show_alert=True)
        await query.message.edit_text(f"🔘 {SECTION_NAMES.get(key,key)}", reply_markup=section_btns_kb(key))

    # ── کاتالوگ ادمین ──
    elif data == "admin_catalog":
        cats = await get_categories(active_only=False)
        await query.message.edit_text("🛍 مدیریت کاتالوگ:", reply_markup=admin_catalog_kb(cats))

    elif data == "acat_new_root":
        context.user_data.update({"mode":"acat_new_icon","cat_parent":None})
        await query.message.reply_text("🎨 آیکون دسته اصلی (مثال: 📱 💻 🎧):", reply_markup=admin_cancel_menu())

    elif data.startswith("acat_new_sub_"):
        parent_id = int(data[13:])
        context.user_data.update({"mode":"acat_new_icon","cat_parent":parent_id})
        await query.message.reply_text("🎨 آیکون زیردسته:", reply_markup=admin_cancel_menu())

    elif data.startswith("acat_edit_"):
        cat_id = int(data[10:]); context.user_data.update({"mode":"acat_edit_name","cat_id":cat_id})
        await query.message.reply_text("✏️ نام جدید دسته‌بندی:", reply_markup=admin_cancel_menu())

    elif data.startswith("acat_del_"):
        cat_id = int(data[9:])
        cat    = await get_category(cat_id)
        parent = cat[4] if cat else None
        await db.execute("UPDATE categories SET is_active=0 WHERE id=?", (cat_id,)); await db.commit()
        await query.answer("🗑 دسته غیرفعال شد.", show_alert=True)
        cats = await get_categories(active_only=False, parent_id=parent)
        if parent is None:
            await query.message.edit_text("🛍 مدیریت کاتالوگ:", reply_markup=admin_catalog_kb(cats))
        else:
            parent_cat = await get_category(parent)
            subcats  = await get_categories(active_only=False, parent_id=parent)
            products = await get_products(parent, active_only=False)
            await query.message.edit_text(
                f"🛍 {parent_cat[2]} {parent_cat[1]}",
                reply_markup=admin_category_kb(parent, subcats, products, parent_cat[4]))

    elif data.startswith("acat_"):
        cat_id   = int(data[5:])
        cat      = await get_category(cat_id)
        if not cat: return
        subcats  = await get_categories(active_only=False, parent_id=cat_id)
        products = await get_products(cat_id, active_only=False)
        en       = "✅ فعال" if cat[3] else "❌ غیرفعال"
        await query.message.edit_text(
            f"🛍 {cat[2]} {cat[1]}\nوضعیت: {en}\n"
            f"زیردسته: {to_fa(len(subcats))} | محصول: {to_fa(len(products))}",
            reply_markup=admin_category_kb(cat_id, subcats, products, cat[4]))

    elif data.startswith("aprd_new_"):
        cat_id = int(data[9:]); context.user_data.update({"mode":"aprd_new_name","cat_id":cat_id})
        await query.message.reply_text("📱 نام محصول:", reply_markup=admin_cancel_menu())

    elif data.startswith("aprd_etog_"):
        pid = int(data[10:]); p = await get_product(pid)
        if not p: return
        new_a = 0 if p[6] else 1
        await db.execute("UPDATE products SET is_active=? WHERE id=?", (new_a, pid)); await db.commit()
        await query.answer("✅ فعال" if new_a else "❌ غیرفعال", show_alert=True)
        p = await get_product(pid)
        await query.message.edit_text(
            f"📱 {p[1]}\n💰 {p[2]}\nوضعیت: {'✅' if p[6] else '❌'}",
            reply_markup=admin_product_kb(pid, p[7], bool(p[6])))

    elif data.startswith("aprd_del_"):
        pid = int(data[9:]); p = await get_product(pid)
        cat_id = p[7] if p else 0
        await db.execute("DELETE FROM products WHERE id=?", (pid,)); await db.commit()
        await query.answer("🗑 محصول حذف شد.", show_alert=True)
        cat = await get_category(cat_id)
        if cat:
            subcats  = await get_categories(active_only=False, parent_id=cat_id)
            products = await get_products(cat_id, active_only=False)
            await query.message.edit_text(
                f"🛍 {cat[2]} {cat[1]}",
                reply_markup=admin_category_kb(cat_id, subcats, products, cat[4]))

    elif data.startswith("aprd_ename_"):
        pid = int(data[11:]); context.user_data.update({"mode":"aprd_edit_name","edit_pid":pid})
        await query.message.reply_text("✏️ نام جدید:", reply_markup=admin_cancel_menu())
    elif data.startswith("aprd_eprice_"):
        pid = int(data[12:]); context.user_data.update({"mode":"aprd_edit_price","edit_pid":pid})
        await query.message.reply_text("💰 قیمت جدید:", reply_markup=admin_cancel_menu())
    elif data.startswith("aprd_edesc_"):
        pid = int(data[11:]); context.user_data.update({"mode":"aprd_edit_desc","edit_pid":pid})
        await query.message.reply_text("📝 توضیح جدید (یا . برای حذف):", reply_markup=admin_cancel_menu())
    elif data.startswith("aprd_ephoto_"):
        pid = int(data[12:]); context.user_data.update({"mode":"aprd_edit_photo","edit_pid":pid})
        await query.message.reply_text("📸 عکس جدید:", reply_markup=admin_cancel_menu())
    elif data.startswith("aprd_esite_"):
        pid = int(data[11:]); context.user_data.update({"mode":"aprd_edit_site","edit_pid":pid})
        await query.message.reply_text("🌐 لینک محصول (یا . برای حذف):", reply_markup=admin_cancel_menu())

    elif data.startswith("aprd_"):
        pid = int(data[5:]); p = await get_product(pid)
        if not p: return
        await query.message.edit_text(
            f"📱 {p[1]}\n💰 {p[2]}\n📝 {p[3] or '—'}\nوضعیت: {'✅' if p[6] else '❌'}",
            reply_markup=admin_product_kb(pid, p[7], bool(p[6])))

    # ── درخواست‌های خرید ──
    elif data == "admin_requests":
        reqs = await get_requests()
        if not reqs:
            await query.message.edit_text("📋 هیچ درخواستی وجود ندارد.", reply_markup=back_admin())
            return
        new_c = sum(1 for r in reqs if r[6]=="new")
        await query.message.edit_text(
            f"📋 درخواست‌های خرید\n🆕 جدید: {to_fa(new_c)} | کل: {to_fa(len(reqs))}",
            reply_markup=requests_kb(reqs))

    elif data.startswith("req_view_"):
        rid = int(data[9:])
        async with db.execute(
            "SELECT id,user_id,username,first_name,phone,product_name,status,created_at FROM requests WHERE id=?",
            (rid,)
        ) as c: r = await c.fetchone()
        if not r: return
        st = "🆕 جدید" if r[6]=="new" else "✅ پیگیری شد"
        await query.message.edit_text(
            f"📋 درخواست #{to_fa(r[0])}\n"
            f"📱 محصول: {r[5]}\n"
            f"👤 {r[3] or '—'} | {'@'+r[2] if r[2] else r[1]}\n"
            f"📞 {r[4]}\n🆔 {r[1]}\n"
            f"🕒 {r[7]}\nوضعیت: {st}",
            reply_markup=request_detail_kb(rid, r[6]))

    elif data.startswith("req_done_"):
        rid = int(data[9:]); await close_request(rid)
        await query.answer("✅ ثبت شد.", show_alert=True)
        await query.message.edit_text("✅ درخواست پیگیری شد.", reply_markup=back_admin())

    # ── چت ادمین ──
    elif data == "active_chats_list":
        await query.message.edit_text(
            f"💬 چت‌های فعال ({to_fa(len(active_chats))}):",
            reply_markup=active_chats_kb())

    elif data.startswith("chat_select_"):
        cuid = int(data[12:])
        async with db.execute("SELECT first_name,username FROM users WHERE user_id=?", (cuid,)) as c:
            row = await c.fetchone()
        name  = row[0] if row else "—"
        uname = f"@{row[1]}" if row and row[1] else str(cuid)
        context.user_data["chat_target"] = cuid
        await query.message.edit_text(
            f"💬 چت با {name} ({uname})\n🆔 {cuid}\n──────────────\n✅ هر پیامی بنویسید مستقیم به کاربر می‌رسد.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔚 پایان چت",         callback_data=f"end_chat_{cuid}")],
                [InlineKeyboardButton("🚫 توقف پاسخ‌دهی",   callback_data="clear_chat_target")],
                [InlineKeyboardButton("🔙 برگشت",            callback_data="active_chats_list")],
            ]))

    elif data == "clear_chat_target":
        context.user_data.pop("chat_target", None)
        await query.answer("✅ پاسخ‌دهی متوقف شد.", show_alert=True)
        await query.message.edit_text("👑 پنل مدیریت", reply_markup=admin_menu())

    elif data.startswith("end_chat_"):
        cuid = int(data[9:]); await close_chat(cuid)
        if context.user_data.get("chat_target") == cuid:
            context.user_data.pop("chat_target", None)
        await query.answer("✅ چت پایان یافت.", show_alert=True)
        try:
            await context.bot.send_message(
                cuid,
                "🔴 پشتیبانی چت را پایان داد.\nمی‌توانید از بخش پشتیبانی دوباره شروع کنید.",
                reply_markup=main_menu())
        except: pass
        await query.message.edit_text("👑 پنل مدیریت", reply_markup=admin_menu())

    # ── تنظیمات ──
    elif data == "settings_menu":
        await query.message.edit_text("⚙️ تنظیمات:", reply_markup=settings_kb())

    elif data.startswith("stg_"):
        key = data[4:]; settings[key] = not get_setting(key); await save_settings()
        await query.answer("✅ ذخیره شد", show_alert=True)
        await query.message.edit_text("⚙️ تنظیمات:", reply_markup=settings_kb())

    # ── ساعت کاری ──
    elif data == "workhours_menu":
        en = "✅ فعال" if workhours.get("enabled") else "❌ غیرفعال"
        await query.message.edit_text(
            f"🕐 ساعت کاری — {en}\n\n{workhours_full_table()}",
            reply_markup=workhours_kb())

    elif data == "wh_toggle":
        workhours["enabled"] = not workhours.get("enabled", True); await save_workhours()
        await query.answer("✅ فعال" if workhours["enabled"] else "❌ غیرفعال", show_alert=True)
        await query.message.edit_text(
            f"🕐 ساعت کاری\n{workhours_full_table()}", reply_markup=workhours_kb())

    elif data.startswith("wh_day_"):
        dk  = data[7:]; day = workhours["schedule"].get(dk, {"open":False,"shifts":[]})
        st  = "\n".join(f"  • {fmt_t(s['from'])} تا {fmt_t(s['to'])}" for s in day.get("shifts",[])) or "  ندارد"
        await query.message.edit_text(
            f"🕐 {DAY_NAMES.get(dk,dk)}\n"
            f"وضعیت: {'✅ باز' if day.get('open') else '❌ تعطیل'}\nساعت‌ها:\n{st}",
            reply_markup=workhours_day_kb(dk))

    elif data.startswith("wh_dtg_"):
        dk  = data[7:]; day = workhours["schedule"].get(dk, {"open":False,"shifts":[]})
        day["open"] = not day.get("open", False); workhours["schedule"][dk] = day; await save_workhours()
        await query.answer("✅ باز شد" if day["open"] else "❌ تعطیل شد", show_alert=True)
        await query.message.edit_text(
            f"🕐 {'✅ باز' if day['open'] else '❌ تعطیل'}", reply_markup=workhours_day_kb(dk))

    elif data.startswith("wh_shifts_"):
        dk = data[10:]; context.user_data.update({"mode":"wh_set_shifts","wh_day":dk})
        await query.message.reply_text(
            f"🕐 {DAY_NAMES.get(dk,dk)}:\nمثال: 11:00-14:00,17:00-23:00",
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

# ════════════════════════════════════════════════
#  TEXT HANDLER
# ════════════════════════════════════════════════
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

    # ════ ADMIN TEXT MODES ════
    if user.id == ADMIN_ID:

        if mode == "edit_text":
            key = context.user_data.pop("edit_key", None); context.user_data.pop("mode", None)
            if key: responses[key] = text; await save_data()
            await update.message.reply_text("✅ متن ذخیره شد.", reply_markup=main_menu()); return

        if mode == "broadcast":
            context.user_data.pop("mode", None)
            await update.message.reply_text("📤 در حال ارسال...")
            await send_broadcast(context, text); return

        if mode == "users_search":
            context.user_data.pop("mode", None)
            rows = await search_users(text)
            if not rows: await update.message.reply_text("❌ یافت نشد.", reply_markup=main_menu()); return
            lines = [f"{'🚫 ' if r[4] else ''}{r[1] or '—'} | {r[0]} | {'@'+r[2] if r[2] else '—'}" for r in rows]
            await update.message.reply_text("🔍 نتایج:\n\n" + "\n".join(lines), reply_markup=main_menu()); return

        if mode == "btn_add_title":
            context.user_data.update({"btn_title": text, "mode": "btn_add_url"})
            await update.message.reply_text("🔗 لینک (https://...):", reply_markup=admin_cancel_menu()); return

        if mode == "btn_add_url":
            key   = context.user_data.pop("btn_key", None)
            title = context.user_data.pop("btn_title", "دکمه")
            context.user_data.pop("mode", None)
            url   = text if text.startswith("http") else f"https://{text}"
            sec   = get_section_buttons(key)
            sec["items"].append({"id": f"b{int(time.time())}", "title": title, "url": url})
            await save_buttons()
            await update.message.reply_text(f"✅ دکمه «{title}» اضافه شد.", reply_markup=main_menu()); return

        if mode == "btn_edit_title":
            context.user_data.update({"btn_new_title": None if text=="." else text, "mode": "btn_edit_url"})
            await update.message.reply_text("🔗 لینک جدید (یا . بدون تغییر):", reply_markup=admin_cancel_menu()); return

        if mode == "btn_edit_url":
            key       = context.user_data.pop("btn_key", None)
            bid       = context.user_data.pop("btn_id", None)
            new_title = context.user_data.pop("btn_new_title", None)
            context.user_data.pop("mode", None)
            sec = get_section_buttons(key)
            for item in sec.get("items", []):
                if item["id"] == bid:
                    if new_title: item["title"] = new_title
                    if text != ".": item["url"] = text if text.startswith("http") else f"https://{text}"
            await save_buttons()
            await update.message.reply_text("✅ ویرایش شد.", reply_markup=main_menu()); return

        if mode == "wh_set_shifts":
            dk = context.user_data.pop("wh_day", None); context.user_data.pop("mode", None)
            try:
                shifts = []
                for part in text.split(","):
                    fr, to = part.strip().split("-")
                    shifts.append({"from": fr.strip(), "to": to.strip()})
                workhours["schedule"][dk]["shifts"] = shifts; await save_workhours()
                await update.message.reply_text("✅ ساعت‌ها ذخیره شد.", reply_markup=main_menu())
            except:
                await update.message.reply_text("❌ فرمت اشتباه!\nمثال: 11:00-14:00,17:00-23:00", reply_markup=main_menu())
            return

        if mode == "wh_set_msg_open":
            context.user_data.pop("mode", None); workhours["msg_open"] = text; await save_workhours()
            await update.message.reply_text("✅ ذخیره شد.", reply_markup=main_menu()); return

        if mode == "wh_set_msg_closed":
            context.user_data.pop("mode", None); workhours["msg_closed"] = text; await save_workhours()
            await update.message.reply_text("✅ ذخیره شد.", reply_markup=main_menu()); return

        if mode == "acat_new_icon":
            context.user_data.update({"cat_icon": text, "mode": "acat_new_name"})
            await update.message.reply_text("✏️ نام دسته‌بندی:", reply_markup=admin_cancel_menu()); return

        if mode == "acat_new_name":
            icon      = context.user_data.pop("cat_icon", "📦")
            parent_id = context.user_data.pop("cat_parent", None)
            context.user_data.pop("mode", None)
            await db.execute(
                "INSERT INTO categories (name,icon,parent_id,sort_order,is_active) VALUES (?,?,?,0,1)",
                (text, icon, parent_id)); await db.commit()
            label = "زیردسته" if parent_id else "دسته اصلی"
            await update.message.reply_text(f"✅ {label} «{icon} {text}» اضافه شد.", reply_markup=main_menu()); return

        if mode == "acat_edit_name":
            cat_id = context.user_data.pop("cat_id", None); context.user_data.pop("mode", None)
            await db.execute("UPDATE categories SET name=? WHERE id=?", (text, cat_id)); await db.commit()
            await update.message.reply_text("✅ نام ذخیره شد.", reply_markup=main_menu()); return

        if mode == "aprd_new_name":
            context.user_data.update({"prd_name": text, "mode": "aprd_new_price"})
            await update.message.reply_text("💰 قیمت محصول:", reply_markup=admin_cancel_menu()); return

        if mode == "aprd_new_price":
            context.user_data.update({"prd_price": text, "mode": "aprd_new_desc"})
            await update.message.reply_text("📝 توضیح (یا . برای بدون توضیح):", reply_markup=admin_cancel_menu()); return

        if mode == "aprd_new_desc":
            context.user_data.update({"prd_desc": None if text=="." else text, "mode": "aprd_new_site"})
            await update.message.reply_text("🌐 لینک محصول در سایت (یا . برای بدون لینک):", reply_markup=admin_cancel_menu()); return

        if mode == "aprd_new_site":
            context.user_data.update({"prd_site": None if text=="." else text, "mode": "aprd_new_photo"})
            await update.message.reply_text("📸 عکس محصول ارسال کنید (یا . برای بدون عکس):", reply_markup=admin_cancel_menu()); return

        if mode == "aprd_new_photo" and text == ".":
            cat_id = context.user_data.pop("cat_id", None)
            name   = context.user_data.pop("prd_name", "")
            price  = context.user_data.pop("prd_price", "")
            desc   = context.user_data.pop("prd_desc", None)
            site   = context.user_data.pop("prd_site", None)
            context.user_data.pop("mode", None)
            await db.execute(
                "INSERT INTO products (category_id,name,price,description,photo_id,site_url,is_active,created_at) VALUES (?,?,?,?,?,?,1,?)",
                (cat_id, name, price, desc, None, site, gregorian_now()))
            await db.commit()
            await update.message.reply_text(f"✅ محصول «{name}» اضافه شد.", reply_markup=main_menu()); return

        if mode == "aprd_edit_name":
            pid = context.user_data.pop("edit_pid", None); context.user_data.pop("mode", None)
            await db.execute("UPDATE products SET name=? WHERE id=?", (text, pid)); await db.commit()
            await update.message.reply_text("✅ ذخیره شد.", reply_markup=main_menu()); return

        if mode == "aprd_edit_price":
            pid = context.user_data.pop("edit_pid", None); context.user_data.pop("mode", None)
            await db.execute("UPDATE products SET price=? WHERE id=?", (text, pid)); await db.commit()
            await update.message.reply_text("✅ ذخیره شد.", reply_markup=main_menu()); return

        if mode == "aprd_edit_desc":
            pid = context.user_data.pop("edit_pid", None); context.user_data.pop("mode", None)
            await db.execute("UPDATE products SET description=? WHERE id=?", (None if text=="." else text, pid)); await db.commit()
            await update.message.reply_text("✅ ذخیره شد.", reply_markup=main_menu()); return

        if mode == "aprd_edit_site":
            pid = context.user_data.pop("edit_pid", None); context.user_data.pop("mode", None)
            await db.execute("UPDATE products SET site_url=? WHERE id=?", (None if text=="." else text, pid)); await db.commit()
            await update.message.reply_text("✅ ذخیره شد.", reply_markup=main_menu()); return

        # ── پاسخ ادمین به چت فعال ──
        chat_target = context.user_data.get("chat_target")
        if chat_target and chat_target in active_chats:
            ft = f"\n─────────────────\n⏱ {shamsi_now()}" if get_setting("show_datetime_footer") else ""
            try:
                await context.bot.send_message(chat_target, f"📩 پشتیبانی:\n──────────────\n{text}{ft}")
                async with db.execute("SELECT first_name FROM users WHERE user_id=?", (chat_target,)) as c:
                    row = await c.fetchone()
                await update.message.reply_text(f"✅ پیام به {row[0] if row else chat_target} ارسال شد.")
            except Exception as e:
                logger.error(f"chat reply: {e}")
                await update.message.reply_text("❌ ارسال ناموفق.")
            return

        # admin falls through to user menu (intentional — no return)

    # ════ USER — active chat ════
    if active_chats.get(user.id):
        if text == "❌ پایان چت":
            await close_chat(user.id)
            try:
                await context.bot.send_message(
                    ADMIN_ID, f"🔴 {user.first_name or user.id} چت را پایان داد.\n🆔 {user.id}")
            except: pass
            await update.message.reply_text("✅ چت پایان یافت.", reply_markup=main_menu())
            return
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"💬 {user.first_name or '—'} | {'@'+user.username if user.username else str(user.id)}\n"
                f"🆔 {user.id}\n──────────────\n📝 {text}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(f"💬 پاسخ", callback_data=f"chat_select_{user.id}")
                ]]))
        except Exception as e:
            logger.error(f"chat fwd: {e}")
        await update.message.reply_text("📨 پیام ارسال شد.", reply_markup=chat_menu())
        return

    # ════ USER — catalog search ════
    if mode == "catalog_search":
        context.user_data.pop("mode", None)
        results = await search_products(text)
        if not results:
            await update.message.reply_text(
                f"🔍 نتیجه‌ای برای «{text}» یافت نشد.", reply_markup=main_menu()); return
        btns = [[InlineKeyboardButton(f"📱 {p[1]} — {p[2]}", callback_data=f"prd_{p[0]}")] for p in results]
        btns.append([InlineKeyboardButton("🔙 کاتالوگ", callback_data="catalog_back")])
        await update.message.reply_text(
            f"🔍 {to_fa(len(results))} نتیجه برای «{text}»:",
            reply_markup=InlineKeyboardMarkup(btns)); return

    # ════ USER — purchase request phone ════
    if mode == "req_phone":
        pid      = context.user_data.pop("req_pid", None)
        prd_name = context.user_data.pop("req_name", "نامشخص")
        context.user_data.pop("mode", None)
        digits   = text.replace("-","").replace(" ","").replace("+","")
        if not digits.isdigit() or len(digits) < 10:
            context.user_data.update({"mode":"req_phone","req_pid":pid,"req_name":prd_name})
            await update.message.reply_text(
                "❌ شماره تماس معتبر نیست. دوباره وارد کنید:",
                reply_markup=ReplyKeyboardMarkup([["❌ لغو عملیات"]], resize_keyboard=True)); return
        await save_request(user.id, user.username, user.first_name, text, pid, prd_name)
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"📋 درخواست خرید جدید!\n"
                f"📱 محصول: {prd_name}\n"
                f"👤 {user.first_name or '—'} | {'@'+user.username if user.username else '—'}\n"
                f"📞 {text}\n🆔 {user.id}\n──────────────\n⏱ {shamsi_now()}")
        except Exception as e:
            logger.error(f"request notify: {e}")
        await update.message.reply_text(
            f"✅ درخواست خرید «{prd_name}» ثبت شد!\nپشتیبانی به زودی با شما تماس می‌گیرد.",
            reply_markup=main_menu()); return

    # ════ USER MENU ════
    if text == "🕐 ساعت کاری":
        await record_stat("workhours_page")
        ft = f"\n─────────────────\n⏱ {shamsi_now()}" if get_setting("show_datetime_footer") else ""
        if not workhours.get("enabled", True):
            await update.message.reply_text("🕐 ساعت کاری هنوز تنظیم نشده.", reply_markup=main_menu()); return
        wh = today_workhours_block() or ""
        await update.message.reply_text(
            f"🕐 ساعت کاری استوک لند\n━━━━━━━━━━━━━━━\n{workhours_full_table()}\n━━━━━━━━━━━━━━━\n{wh}{ft}",
            reply_markup=main_menu()); return

    if text == "🛍 محصولات":
        await record_stat("catalog")
        cats = await get_categories()
        if not cats:
            await update.message.reply_text("📭 محصولی موجود نیست.", reply_markup=main_menu()); return
        ft = f"\n─────────────────\n⏱ {shamsi_now()}" if get_setting("show_datetime_footer") else ""
        await update.message.reply_text(
            f"🛍 کاتالوگ استوک لند\n──────────────\nدسته‌بندی را انتخاب کنید:{ft}",
            reply_markup=catalog_root_kb(cats)); return

    for k, v in MENU_ITEMS.items():
        if text == v:
            await record_stat(k)
            content = responses.get(k, "تنظیم نشده")
            full    = build_message(v, content, k)
            kb      = support_kb(k) if k == "4" else user_section_kb(k)
            await send_with_banner(update.message, full, k, reply_markup=kb)
            return

    await update.message.reply_text("⚠️ گزینه نامعتبر است.", reply_markup=main_menu())

# ════════════════════════════════════════════════
#  PHOTO HANDLER
# ════════════════════════════════════════════════
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID: return
    mode  = context.user_data.get("mode")
    photo = update.message.photo[-1]

    if mode == "banner_upload":
        key = context.user_data.pop("banner_key", None); context.user_data.pop("mode", None)
        if not key: await update.message.reply_text("❌ خطا.", reply_markup=main_menu()); return
        get_banner(key)
        banners[key]["file_id"] = photo.file_id; banners[key]["active"] = True; await save_banners()
        await update.message.reply_text(f"✅ بنر «{SECTION_NAMES.get(key,key)}» آپلود شد!", reply_markup=main_menu()); return

    if mode == "broadcast":
        context.user_data.pop("mode", None); caption = update.message.caption or ""
        await update.message.reply_text("📤 در حال ارسال...")
        await send_broadcast(context, caption, photo_id=photo.file_id); return

    if mode == "aprd_new_photo":
        cat_id = context.user_data.pop("cat_id", None)
        name   = context.user_data.pop("prd_name", "")
        price  = context.user_data.pop("prd_price", "")
        desc   = context.user_data.pop("prd_desc", None)
        site   = context.user_data.pop("prd_site", None)
        context.user_data.pop("mode", None)
        await db.execute(
            "INSERT INTO products (category_id,name,price,description,photo_id,site_url,is_active,created_at) VALUES (?,?,?,?,?,?,1,?)",
            (cat_id, name, price, desc, photo.file_id, site, gregorian_now()))
        await db.commit()
        await update.message.reply_text(f"✅ محصول «{name}» با عکس اضافه شد.", reply_markup=main_menu()); return

    if mode == "aprd_edit_photo":
        pid = context.user_data.pop("edit_pid", None); context.user_data.pop("mode", None)
        await db.execute("UPDATE products SET photo_id=? WHERE id=?", (photo.file_id, pid)); await db.commit()
        await update.message.reply_text("✅ عکس ذخیره شد.", reply_markup=main_menu()); return

    # ادمین عکس reply می‌کند به چت کاربر
    chat_target = context.user_data.get("chat_target")
    if chat_target and chat_target in active_chats:
        try:
            await context.bot.send_photo(
                chat_target, photo=photo.file_id,
                caption=f"📩 پشتیبانی:\n{update.message.caption or ''}")
            await update.message.reply_text("✅ عکس ارسال شد.")
        except Exception as e:
            logger.error(f"chat photo: {e}")

# ════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════
async def post_init(app):
    await init_db()
    await load_data()
    await load_banners()
    await load_workhours()
    await load_buttons()
    await load_settings()
    await load_stats()
    await load_active_chats()
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
