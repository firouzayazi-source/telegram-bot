import os, json, time, asyncio, logging, aiosqlite, jdatetime, pytz, zipfile, io
from datetime import datetime
from collections import defaultdict, deque
import aiofiles
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                           CallbackQueryHandler, ContextTypes, filters)

os.environ.pop("HTTP_PROXY", None); os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("ALL_PROXY", None); os.environ["NO_PROXY"] = "*"

TOKEN = os.environ["BOT_TOKEN"].strip()
ADMIN_ID = int(os.environ["ADMIN_ID"].strip())
DATA_FILE = "data.json"; DB_FILE = "users.db"; BANNER_FILE = "banner.json"
WORKHOURS_FILE = "workhours.json"; BUTTONS_FILE = "buttons.json"
MENU_FILE = "menu.json"
SETTINGS_FILE = "settings.json"; STATS_FILE = "stats.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
IRAN_TZ = pytz.timezone("Asia/Tehran")

# ── زمان
_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
MONTH_FA = {1:"فروردین",2:"اردیبهشت",3:"خرداد",4:"تیر",5:"مرداد",6:"شهریور",
            7:"مهر",8:"آبان",9:"آذر",10:"دی",11:"بهمن",12:"اسفند"}
DAY_FA   = {"0":"شنبه","1":"یکشنبه","2":"دوشنبه","3":"سه‌شنبه",
            "4":"چهارشنبه","5":"پنجشنبه","6":"جمعه"}

def to_fa(v): return str(v).translate(_FA)

def shamsi_now():
    now = datetime.now(IRAN_TZ); j = jdatetime.datetime.fromgregorian(datetime=now)
    return f"{to_fa(j.day)} {MONTH_FA[j.month]} {to_fa(j.year)} — {to_fa(now.strftime('%H:%M'))}"

def gregorian_now(): return datetime.now(IRAN_TZ).strftime("%Y-%m-%d %H:%M:%S")

# ── منو
MENU_ITEMS = {"1":"🌐 شبکه‌های اجتماعی","2":"🌐 سایت استوک لند",
              "3":"💰 شرایط اقساط","4":"📞 پشتیبانی","5":"📍 آدرس فروشگاه",
              "6":"🔖 دکمه ذخیره ۱","7":"🔖 دکمه ذخیره ۲"}
# پیکربندی منوی اصلی — قابل تغییر از پنل ادمین (menu.json)
# هر آیتم: key (ثابت), label (قابل تغییر), order (ترتیب), enabled (روشن/خاموش)
DEFAULT_MENU = [
    {"key":"1","label":"🌐 شبکه‌های اجتماعی","order":1,"enabled":True,"width":"half"},
    {"key":"2","label":"🌐 سایت استوک لند","order":2,"enabled":True,"width":"half"},
    {"key":"3","label":"💰 شرایط اقساط","order":3,"enabled":True,"width":"half"},
    {"key":"5","label":"📍 آدرس فروشگاه","order":4,"enabled":True,"width":"half"},
    {"key":"catalog","label":"🛍 محصولات","order":5,"enabled":True,"width":"full"},
    {"key":"workhours","label":"🕐 ساعت کاری","order":6,"enabled":True,"width":"half"},
    {"key":"4","label":"📞 پشتیبانی","order":7,"enabled":True,"width":"half"},
    {"key":"6","label":"🔖 دکمه ذخیره ۱","order":8,"enabled":False,"width":"half"},
    {"key":"7","label":"🔖 دکمه ذخیره ۲","order":9,"enabled":False,"width":"half"},
]
menu_cfg = []

SECTION_NAMES = {"welcome":"🏠 خوش‌آمدگویی",
                 "catalog":"🛍 محصولات","workhours":"🕐 ساعت کاری",
                 "1":"🌐 شبکه‌های اجتماعی","2":"🌐 سایت استوک لند",
                 "3":"💰 شرایط اقساط","4":"📞 پشتیبانی","5":"📍 آدرس فروشگاه",
                 "6":"🔖 دکمه ذخیره ۱","7":"🔖 دکمه ذخیره ۲"}

# ── state
responses=None; banners={}; workhours={}; buttons={}; settings={}; stats={}

DEFAULT_WH = {"enabled":True,"schedule":{
    "0":{"open":True,"shifts":[{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
    "1":{"open":True,"shifts":[{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
    "2":{"open":True,"shifts":[{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
    "3":{"open":True,"shifts":[{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
    "4":{"open":True,"shifts":[{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
    "5":{"open":True,"shifts":[{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
    "6":{"open":True,"shifts":[{"from":"17:00","to":"23:00"}]}},
    "msg_open":"✅ هم‌اکنون باز است","msg_closed":"🔴 هم‌اکنون بسته است"}
DEFAULT_SETTINGS = {"notify_new_user":True,"store_open":True}
DEFAULT_SEC_WH = {k:True for k in SECTION_NAMES}

# ── helpers
def get_banner(k): banners.setdefault(k,{"file_id":None,"active":False}); return banners[k]
def get_sec_btns(k): buttons.setdefault(k,{"enabled":True,"items":[]}); return buttons[k]
def get_setting(k): return settings.get(k,DEFAULT_SETTINGS.get(k,True))

def is_open():
    if not get_setting("store_open"): return False
    if not workhours.get("enabled",True): return True
    now=datetime.now(IRAN_TZ); j=jdatetime.datetime.fromgregorian(datetime=now)
    day=workhours.get("schedule",{}).get(str(j.weekday()),{})
    if not day.get("open",False): return False
    ns=now.strftime("%H:%M")
    return any(s["from"]<=ns<=s["to"] for s in day.get("shifts",[]))

def wh_today_block():
    if not workhours.get("enabled",True): return None
    now=datetime.now(IRAN_TZ); j=jdatetime.datetime.fromgregorian(datetime=now)
    wd=str(j.weekday()); day=workhours.get("schedule",{}).get(wd,{})
    opened=is_open()
    status=workhours.get("msg_open","✅ باز") if opened else workhours.get("msg_closed","🔴 بسته")
    oi=["☀️","🌙","🌃","🕯"]; ci=["⚫️"]*4
    sl=["شیفت اول","شیفت دوم","شیفت سوم","شیفت چهارم"]
    lines=["━"*15,"🏪 وضعیت فروشگاه",f"📅 امروز {DAY_FA.get(wd,'')}",""]
    if not day.get("open"): lines.append("❌ امروز تعطیل است")
    else:
        icons=oi if opened else ci
        for i,s in enumerate(day.get("shifts",[])):
            lines.append(f"{icons[i] if i<len(icons) else '🕐'} {sl[i] if i<len(sl) else ''}   {to_fa(s['from'])} — {to_fa(s['to'])}")
    lines+=["",status,"━"*15]; return "\n".join(lines)

def wh_full_table():
    rows=[]
    for k,name in DAY_FA.items():
        day=workhours.get("schedule",{}).get(k,{})
        if not day.get("open"): rows.append(f"❌ {name}: تعطیل")
        else:
            sh=" و ".join(f"{to_fa(s['from'])} تا {to_fa(s['to'])}" for s in day.get("shifts",[]))
            rows.append(f"✅ {name}: {sh}")
    return "\n".join(rows)

def build_msg(title,content,sec_key):
    lines=[f"✦ {title}","",content]
    msg="\n".join(lines)
    return msg[:4000]+"..." if len(msg)>4000 else msg

def progress_bar(v,t,n=8):
    if t==0: return "░"*n
    f=int(n*v/t); return "▓"*f+"░"*(n-f)

async def record_stat(k): stats[k]=stats.get(k,0)+1; await save_stats()

# ── load/save
async def _rj(path,default):
    try:
        async with aiofiles.open(path,"r",encoding="utf-8") as f: return json.loads(await f.read())
    except: return default() if callable(default) else default

async def _wj(path,data):
    try:
        async with aiofiles.open(path,"w",encoding="utf-8") as f:
            await f.write(json.dumps(data,ensure_ascii=False,indent=2))
    except Exception as e: logger.error(f"write {path}: {e}")

async def load_data():
    global responses
    responses=await _rj(DATA_FILE,lambda:dict(MENU_ITEMS,welcome="✨ خوش آمدید به ربات استوک لند"))
async def save_data(): await _wj(DATA_FILE,responses)

async def load_banners():
    global banners
    banners=await _rj(BANNER_FILE,dict)
    for k in SECTION_NAMES: banners.setdefault(k,{"file_id":None,"active":False})
async def save_banners(): await _wj(BANNER_FILE,banners)

async def load_workhours():
    global workhours
    workhours=await _rj(WORKHOURS_FILE,dict)
    if not workhours: workhours=dict(DEFAULT_WH); await save_workhours()
async def save_workhours(): await _wj(WORKHOURS_FILE,workhours)

async def load_buttons():
    global buttons
    buttons=await _rj(BUTTONS_FILE,dict)
    for k in SECTION_NAMES: buttons.setdefault(k,{"enabled":True,"items":[]})
async def save_buttons(): await _wj(BUTTONS_FILE,buttons)

async def load_menu():
    global menu_cfg
    menu_cfg = await _rj(MENU_FILE, list)
    if not menu_cfg:
        menu_cfg = [dict(m) for m in DEFAULT_MENU]; await save_menu()
    else:
        # اطمینان از وجود همه کلیدها (اگر نسخه قدیمی بود)
        existing = {m["key"] for m in menu_cfg}
        for d in DEFAULT_MENU:
            if d["key"] not in existing: menu_cfg.append(dict(d))
        for m in menu_cfg:
            m.setdefault("width","half")

async def save_menu(): await _wj(MENU_FILE, menu_cfg)

async def reset_menu():
    global menu_cfg
    menu_cfg=[dict(m) for m in DEFAULT_MENU]
    await save_menu()

def menu_sorted():
    """آیتم‌های منو مرتب‌شده بر اساس order."""
    return sorted(menu_cfg, key=lambda m: m.get("order", 99))

def menu_item(key):
    return next((m for m in menu_cfg if m["key"] == key), None)

def menu_label(key, default=""):
    m = menu_item(key)
    return m["label"] if m else default

def menu_row_partner(key):
    """اگر این دکمه half باشد و در یک ردیف با دکمه half دیگری جفت شده،
    کلید جفتش را برمی‌گرداند؛ وگرنه None. (فقط دکمه‌های فعال)"""
    m = menu_item(key)
    if not m or m.get("width","half")!="half" or not m.get("enabled",True): return None
    items=[x for x in menu_sorted() if x.get("enabled",True)]
    # شبیه‌سازی جفت‌سازی main_menu
    pending=None
    for x in items:
        if x.get("width","half")=="full":
            pending=None
        else:
            if pending:
                if pending["key"]==key: return x["key"]
                if x["key"]==key: return pending["key"]
                pending=None
            else:
                pending=x
    return None

async def load_settings():
    global settings
    settings=await _rj(SETTINGS_FILE,dict)
    if not settings:
        settings=dict(DEFAULT_SETTINGS); settings["section_workhours"]=dict(DEFAULT_SEC_WH)
        await save_settings()
async def save_settings(): await _wj(SETTINGS_FILE,settings)
async def load_stats():
    global stats; stats=await _rj(STATS_FILE,dict)
async def save_stats(): await _wj(STATS_FILE,stats)

# ── database
db=None

async def safe_edit(msg,text,**kw):
    # اگر پیام عکس/کپشن دارد، edit_text کار نمی‌کند → پیام را حذف و پیام متنی جدید بفرست
    if getattr(msg,"photo",None) or getattr(msg,"caption",None) is not None:
        try: await msg.delete()
        except: pass
        try: await msg.reply_text(text,**kw); return
        except Exception as e: logger.error(f"safe_edit(photo): {e}"); return
    try: await msg.edit_text(text,**kw)
    except Exception as e:
        if "not modified" in str(e).lower(): return
        try: await msg.reply_text(text,**kw)
        except: logger.error(f"safe_edit: {e}")

async def init_db():
    global db
    db=await aiosqlite.connect(DB_FILE)
    await db.execute("PRAGMA journal_mode=WAL")
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,username TEXT,first_name TEXT,
            joined_at TEXT,last_seen TEXT,is_blocked INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS categories(
            id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,icon TEXT DEFAULT '📦',
            parent_id INTEGER DEFAULT NULL,is_active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY AUTOINCREMENT,category_id INTEGER,
            name TEXT,price TEXT,description TEXT,photo_id TEXT,
            site_url TEXT,is_active INTEGER DEFAULT 1,created_at TEXT);
        CREATE TABLE IF NOT EXISTS requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,
            username TEXT,first_name TEXT,phone TEXT,
            product_id INTEGER,product_name TEXT,
            status TEXT DEFAULT 'new',created_at TEXT);
        CREATE INDEX IF NOT EXISTS idx_ls ON users(last_seen);
    """)
    for sql in ["ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0",
                "ALTER TABLE categories ADD COLUMN parent_id INTEGER DEFAULT NULL"]:
        try: await db.execute(sql)
        except: pass
    await db.commit()

async def save_user(u):
    now=gregorian_now()
    await db.execute("INSERT OR IGNORE INTO users VALUES(?,?,?,?,?,0)",(u.id,u.username or"",u.first_name or"",now,now))
    await db.execute("UPDATE users SET username=?,first_name=?,last_seen=? WHERE user_id=?",(u.username or"",u.first_name or"",now,u.id))
    await db.commit()

async def get_all_uids():
    async with db.execute("SELECT user_id FROM users WHERE is_blocked=0") as c: return[r[0] for r in await c.fetchall()]

async def is_blocked(uid):
    async with db.execute("SELECT is_blocked FROM users WHERE user_id=?",(uid,)) as c:
        r=await c.fetchone(); return bool(r and r[0])

async def set_block(uid,v): await db.execute("UPDATE users SET is_blocked=? WHERE user_id=?",(v,uid)); await db.commit()

async def search_users(q):
    q=f"%{q}%"
    async with db.execute("SELECT user_id,first_name,username,last_seen,is_blocked FROM users WHERE first_name LIKE ? OR username LIKE ? OR CAST(user_id AS TEXT) LIKE ? ORDER BY last_seen DESC LIMIT 15",(q,q,q)) as c: return await c.fetchall()

async def get_users_page(offset,limit=15,ft="all"):
    flt={"today":"WHERE DATE(last_seen)=DATE('now','localtime')","week":"WHERE last_seen>=datetime('now','-7 days','localtime')","blocked":"WHERE is_blocked=1"}
    async with db.execute(f"SELECT user_id,first_name,username,last_seen,is_blocked FROM users {flt.get(ft,'')} ORDER BY last_seen DESC LIMIT {limit} OFFSET {offset}") as c: return await c.fetchall()

async def _cnt(sql,args=()):
    async with db.execute(sql,args) as c: return(await c.fetchone())[0]

async def total_users(): return await _cnt("SELECT COUNT(*) FROM users")
async def today_users(): return await _cnt("SELECT COUNT(*) FROM users WHERE DATE(last_seen)=DATE('now','localtime')")
async def week_users():  return await _cnt("SELECT COUNT(*) FROM users WHERE last_seen>=datetime('now','-7 days','localtime')")
async def month_users(): return await _cnt("SELECT COUNT(*) FROM users WHERE last_seen>=datetime('now','-30 days','localtime')")
async def new_today():   return await _cnt("SELECT COUNT(*) FROM users WHERE DATE(joined_at)=DATE('now','localtime')")
async def blk_count():   return await _cnt("SELECT COUNT(*) FROM users WHERE is_blocked=1")

# ── catalog — از ووکامرس خوانده می‌شود (woo.py)
# خروجی به فرمت tuple سازگار با کد موجود تبدیل می‌شود:
#   دسته:   id(0),name(1),icon(2),parent_id(3),is_active(4)
#   محصول:  id(0),name(1),price(2),description(3),photo_url(4),site_url(5),is_active(6),category_id(7)
import woo

def _cat_tuple(c):
    # ووکامرس آیکون ندارد → از 📁/📦 استفاده می‌کنیم
    icon = "📂" if c["parent"]==0 else "📦"
    return (c["id"], c["name"], icon, c["parent"], 1)

def _prod_tuple(p, cat_id=None):
    return (p["id"], p["name"], p["price"], p["description"],
            p["image"], p["permalink"], 1 if p["in_stock"] else 0,
            cat_id if cat_id is not None else (p["category_ids"][0] if p["category_ids"] else 0))

async def get_root_cats(active_only=True):
    cats = await woo.get_root_categories()
    return [_cat_tuple(c) for c in cats]

async def get_subcats(parent_id,active_only=True):
    cats = await woo.get_subcategories(parent_id)
    return [_cat_tuple(c) for c in cats]

async def get_cat(cat_id):
    c = await woo.get_category(cat_id)
    return _cat_tuple(c) if c else None

async def get_products(cat_id,active_only=True):
    prods = await woo.get_products_by_category(cat_id)
    return [_prod_tuple(p, cat_id) for p in prods]

async def get_product(pid):
    p = await woo.get_product(pid)
    return _prod_tuple(p) if p else None

async def search_products(q):
    prods = await woo.search_products(q)
    return [_prod_tuple(p) for p in prods]

# ── requests db
async def save_request(uid,username,first_name,phone,pid,pname):
    await db.execute("INSERT INTO requests(user_id,username,first_name,phone,product_id,product_name,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (uid,username or"",first_name or"",phone,pid,pname,"new",gregorian_now()))
    await db.commit()

async def get_requests():
    async with db.execute("SELECT id,user_id,username,first_name,phone,product_name,status,created_at FROM requests ORDER BY id DESC LIMIT 30") as c: return await c.fetchall()

async def done_request(rid): await db.execute("UPDATE requests SET status='done' WHERE id=?",(rid,)); await db.commit()

# ── anti-spam
_W,_L,_B=10,7,60; _spam=defaultdict(lambda:deque(maxlen=_L)); _blk={}

async def anti_spam(uid):
    if uid==ADMIN_ID: return True
    if await is_blocked(uid): return False
    now=time.time()
    if uid in _blk and _blk[uid]>now: return False
    q=_spam[uid]; q.append(now)
    if len(q)>=_L and(now-q[0])<=_W: _blk[uid]=now+_B; return False
    return True

# ════════════════════════════════════════════════
#  KEYBOARDS
# ════════════════════════════════════════════════
def main_menu():
    # به ترتیب order، با احترام به عرض هر دکمه:
    #   full → یک ردیف کامل | half → کنار دکمه half بعدی
    # نکته RTL: تلگرام لیست را چپ‌به‌راست می‌چیند، پس برای اینکه
    # دکمه اولِ هر جفت سمت راست بیفتد، ترتیب لیست را معکوس می‌کنیم.
    items=[m for m in menu_sorted() if m.get("enabled",True)]
    rows=[]; pending=None
    for m in items:
        if m.get("width","half")=="full":
            if pending: rows.append([pending]); pending=None
            rows.append([m["label"]])
        else:
            if pending:
                rows.append([m["label"],pending]); pending=None  # دومی چپ، اولی(pending) راست
            else:
                pending=m["label"]
    if pending: rows.append([pending])
    if not rows: rows=[["🏠 منو"]]
    return ReplyKeyboardMarkup(rows,resize_keyboard=True)

def cancel_menu(): return ReplyKeyboardMarkup([["❌ لغو عملیات"]],resize_keyboard=True)

# یکپارچه برای تمام بخش‌ها — support_kb حذف شد (تکراری بود)
def user_sec_kb(key):
    sec=get_sec_btns(key)
    if not sec.get("enabled",False): return None
    items=[x for x in sec.get("items",[]) if x.get("url")]
    if not items: return None
    btns=[]; row=[]
    for i,it in enumerate(items):
        row.append(InlineKeyboardButton(it["title"],url=it["url"]))
        if len(row)==2 or i==len(items)-1: btns.append(row); row=[]
    return InlineKeyboardMarkup(btns) if btns else None

# ── catalog keyboards (user)
def cat_root_kb(cats):
    btns=[[InlineKeyboardButton(f"{c[2]} {c[1]}",callback_data=f"cr_{c[0]}")] for c in cats]
    btns.append([InlineKeyboardButton("🔍 جستجوی محصول",callback_data="cat_search")])
    return InlineKeyboardMarkup(btns)

def cat_sub_kb(subs,root_id):
    btns=[[InlineKeyboardButton(f"{s[2]} {s[1]}",callback_data=f"cs_{s[0]}")] for s in subs]
    btns.append([InlineKeyboardButton("🔙 برگشت",callback_data="cat_back")])
    return InlineKeyboardMarkup(btns)

def cat_products_kb(products,sub_id):
    btns=[[InlineKeyboardButton(f"📱 {p[1]}",callback_data=f"prd_{p[0]}")] for p in products]
    btns.append([InlineKeyboardButton("🔙 برگشت",callback_data=f"cr_back_{sub_id}")])
    return InlineKeyboardMarkup(btns)

def product_kb(p):
    btns=[]
    if p[5]: btns.append([InlineKeyboardButton("🌐 مشاهده / خرید از سایت",url=p[5])])
    btns.append([InlineKeyboardButton("📋 درخواست خرید",callback_data=f"req_{p[0]}")])
    btns.append([InlineKeyboardButton("🔙 برگشت",callback_data=f"cs_back_{p[7]}")])
    return InlineKeyboardMarkup(btns)

# ── admin keyboards
def back_admin(): return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به پنل",callback_data="back_to_admin")]])

def backup_kb(): return InlineKeyboardMarkup([
    [InlineKeyboardButton("💾 دریافت پشتیبان",callback_data="backup_get"),
     InlineKeyboardButton("📥 بازگردانی",callback_data="backup_import")],
    [InlineKeyboardButton("🔙 تنظیمات",callback_data="settings_menu")]])

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 داشبورد",callback_data="dash"),
         InlineKeyboardButton("👥 کاربران",callback_data="users_menu")],
        [InlineKeyboardButton("🛍 محصولات سایت",callback_data="woo_status"),
         InlineKeyboardButton("📬 درخواست‌ها",callback_data="admin_reqs")],
        [InlineKeyboardButton("🕐 ساعت کاری",callback_data="wh_menu"),
         InlineKeyboardButton("📣 پخش همگانی",callback_data="broadcast")],
        [InlineKeyboardButton("⚙️ تنظیمات",callback_data="settings_menu")],
    ])

# ترتیب نمایش بخش‌ها — دقیقاً مطابق منوی کاربر
SECTION_ORDER = ["welcome","1","2","3","4","5","catalog","workhours","6","7"]

def sections_kb():
    btns=[]; row=[]
    for key in SECTION_ORDER:
        if key not in SECTION_NAMES: continue
        name=SECTION_NAMES[key]
        cont=responses.get(key,"") if responses else ""
        b=get_banner(key); sec=get_sec_btns(key)
        mark=""
        if cont and cont not in("تنظیم نشده",""): mark+="📝"
        if b.get("active") and b.get("file_id"): mark+="🖼"
        if sec.get("enabled") and sec.get("items"): mark+="🔗"
        label=f"{name}  {mark}" if mark else name
        row.append(InlineKeyboardButton(label,callback_data=f"sec_{key}"))
        if len(row)==2: btns.append(row); row=[]
    if row: btns.append(row)
    btns.append([InlineKeyboardButton("🔙 تنظیمات",callback_data="settings_menu")])
    return InlineKeyboardMarkup(btns)

def section_kb(key):
    b=get_banner(key); sec=get_sec_btns(key)
    ban_lbl="🖼 بنر  🟢 فعال" if(b.get("active") and b.get("file_id")) else("🖼 بنر  ⏸ آپلود‌شده" if b.get("file_id") else"🖼 بنر  ➕ ندارد")
    n=len(sec.get("items",[])); en=sec.get("enabled")
    btn_lbl=f"🔗 دکمه‌ها  {'🟢' if en else '🔴'}  ({to_fa(n)} عدد)"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ ویرایش متن",callback_data=f"sec_text_{key}")],
        [InlineKeyboardButton(ban_lbl,callback_data=f"sec_ban_{key}")],
        [InlineKeyboardButton(btn_lbl,callback_data=f"sec_btns_{key}")],
        [InlineKeyboardButton("🔙 بازگشت",callback_data="sections")],
    ])

def banner_kb(key):
    b=get_banner(key); tg="🔴 غیرفعال‌سازی" if b.get("active") else "🟢 فعال‌سازی"
    btns=[[InlineKeyboardButton("📤 آپلود تصویر",callback_data=f"ban_up_{key}")],
          [InlineKeyboardButton(tg,callback_data=f"ban_tg_{key}")]]
    if b.get("file_id"): btns.append([InlineKeyboardButton("🗑 حذف تصویر",callback_data=f"ban_dl_{key}")])
    btns.append([InlineKeyboardButton("🔙 بازگشت",callback_data=f"sec_{key}")]); return InlineKeyboardMarkup(btns)

def sec_btns_kb(key):
    sec=get_sec_btns(key); tg="🔴 غیرفعال‌سازی" if sec.get("enabled") else "🟢 فعال‌سازی"
    btns=[[InlineKeyboardButton(tg,callback_data=f"btn_tg_{key}")]]
    for it in sec.get("items",[]):
        btns.append([InlineKeyboardButton(f"🔗 {it['title']}",callback_data=f"btn_ed_{key}_{it['id']}"),
                     InlineKeyboardButton("🗑 حذف",callback_data=f"btn_dl_{key}_{it['id']}")])
    btns.append([InlineKeyboardButton("➕ افزودن دکمه",callback_data=f"btn_add_{key}"),
                 InlineKeyboardButton("🔙 بازگشت",callback_data=f"sec_{key}")])
    return InlineKeyboardMarkup(btns)

def wh_kb():
    en=workhours.get("enabled",True)
    tg="🔴 غیرفعال‌سازی" if en else "🟢 فعال‌سازی"
    btns=[[InlineKeyboardButton(tg,callback_data="wh_toggle")]]
    day_list=list(DAY_FA.items())
    for i in range(0,len(day_list),2):
        row=[]
        for k,name in day_list[i:i+2]:
            day=workhours.get("schedule",{}).get(k,{})
            row.append(InlineKeyboardButton(f"{'✅' if day.get('open') else '❌'} {name}",callback_data=f"wh_day_{k}"))
        btns.append(row)
    btns+=[[InlineKeyboardButton("✏️ پیام باز",callback_data="wh_mop"),
            InlineKeyboardButton("✏️ پیام بسته",callback_data="wh_mcl")],
           [InlineKeyboardButton("🔙 پنل اصلی",callback_data="back_to_admin")]]
    return InlineKeyboardMarkup(btns)

def wh_day_kb(dk):
    day=workhours.get("schedule",{}).get(dk,{})
    tg="🔴 تعطیل" if day.get("open") else "🟢 باز کردن"
    return InlineKeyboardMarkup([[InlineKeyboardButton(tg,callback_data=f"wh_dtg_{dk}")],
        [InlineKeyboardButton("✏️ ساعت‌ها",callback_data=f"wh_sh_{dk}")],
        [InlineKeyboardButton("🔙",callback_data="wh_menu")]])

def menu_mgr_kb():
    """لیست دکمه‌های منو با وضعیت، برای مدیریت."""
    btns=[]
    items=menu_sorted()
    for idx,m in enumerate(items):
        status="🟢" if m.get("enabled",True) else "⚫️"
        btns.append([InlineKeyboardButton(f"{status} {m['label']}",callback_data=f"mi_{m['key']}")])
    btns.append([InlineKeyboardButton("♻️ بازگردانی به حالت پیش‌فرض",callback_data="menu_reset")])
    btns.append([InlineKeyboardButton("🔙 تنظیمات",callback_data="settings_menu")])
    return InlineKeyboardMarkup(btns)

def menu_item_kb(key):
    """تنظیمات یک دکمه: روشن/خاموش، تغییر نام، جابجایی بالا/پایین."""
    m=menu_item(key)
    if not m: return menu_mgr_kb()
    items=menu_sorted()
    idx=next((i for i,x in enumerate(items) if x["key"]==key),0)
    en=m.get("enabled",True)
    w=m.get("width","half")
    w_lbl="📐 عرض: تمام‌صفحه" if w=="full" else "📐 عرض: نصف‌صفحه"
    rows=[
        [InlineKeyboardButton("🔴 خاموش کردن" if en else "🟢 روشن کردن",callback_data=f"mtg_{key}")],
        [InlineKeyboardButton("✏️ تغییر نام",callback_data=f"mnm_{key}")],
        [InlineKeyboardButton(w_lbl,callback_data=f"mw_{key}")],
    ]
    move=[]
    if idx>0: move.append(InlineKeyboardButton("⬆️ بالا",callback_data=f"mup_{key}"))
    if idx<len(items)-1: move.append(InlineKeyboardButton("⬇️ پایین",callback_data=f"mdn_{key}"))
    if move: rows.append(move)
    # جابجایی چپ/راست فقط وقتی این نیم‌دکمه با دکمه دیگری هم‌ردیف باشد
    if w=="half" and menu_row_partner(key):
        rows.append([InlineKeyboardButton("↔️ جابجایی چپ و راست",callback_data=f"msw_{key}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت",callback_data="menu_mgr")])
    return InlineKeyboardMarkup(rows)

def settings_kb():
    notif="🟢" if get_setting("notify_new_user") else "⚫️"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎛 مدیریت منو",callback_data="menu_mgr")],
        [InlineKeyboardButton("✏️ مدیریت بخش‌ها",callback_data="sections")],
        [InlineKeyboardButton("💾 پشتیبان‌گیری",callback_data="backup")],
        [InlineKeyboardButton(f"{notif} اعلان عضو جدید",callback_data="stg_notify_new_user")],
        [InlineKeyboardButton("🔙 پنل اصلی",callback_data="back_to_admin")],
    ])

def users_menu_kb(): return InlineKeyboardMarkup([
    [InlineKeyboardButton("👥 همه کاربران",callback_data="ul_all_0"),
     InlineKeyboardButton("🆕 امروز",callback_data="ul_today_0")],
    [InlineKeyboardButton("📆 این هفته",callback_data="ul_week_0"),
     InlineKeyboardButton("🚫 بلاک‌شده‌ها",callback_data="ul_blocked_0")],
    [InlineKeyboardButton("🔍 جستجوی کاربر",callback_data="users_search")],
    [InlineKeyboardButton("🔙 پنل اصلی",callback_data="back_to_admin")]])

def users_list_kb(rows,off,ft,total):
    btns=[[InlineKeyboardButton(f"{'🚫 ' if r[4] else ''}{r[1] or '—'} | {r[0]}",callback_data=f"uv_{r[0]}")] for r in rows]
    nav=[]
    if off>0: nav.append(InlineKeyboardButton("◀️",callback_data=f"ul_{ft}_{off-15}"))
    if off+15<total: nav.append(InlineKeyboardButton("▶️",callback_data=f"ul_{ft}_{off+15}"))
    if nav: btns.append(nav)
    btns.append([InlineKeyboardButton("🔙",callback_data="users_menu")]); return InlineKeyboardMarkup(btns)

def udetail_kb(uid,is_bl): return InlineKeyboardMarkup([
    [InlineKeyboardButton("✅ رفع بلاک" if is_bl else "🚫 بلاک",callback_data=f"utog_{uid}")],
    [InlineKeyboardButton("🔙",callback_data="users_menu")]])

def reqs_kb(reqs):
    btns=[[InlineKeyboardButton(f"{'🆕' if r[6]=='new' else '✅'} {r[5]} — {r[3]}",callback_data=f"rq_{r[0]}")] for r in reqs]
    btns.append([InlineKeyboardButton("🔙",callback_data="back_to_admin")]); return InlineKeyboardMarkup(btns)

def req_kb(rid,status):
    btns=[]
    if status=="new": btns.append([InlineKeyboardButton("✅ پیگیری شد",callback_data=f"rq_done_{rid}")])
    btns.append([InlineKeyboardButton("🔙",callback_data="admin_reqs")]); return InlineKeyboardMarkup(btns)

# ── send with banner
async def send_banner(msg,text,key,kb=None):
    b=get_banner(key)
    if b.get("active") and b.get("file_id"):
        try: await msg.reply_photo(photo=b["file_id"],caption=text,reply_markup=kb); return
        except Exception as e: logger.error(f"banner[{key}]: {e}")
    await msg.reply_text(text,reply_markup=kb)

# ── broadcast
async def broadcast(ctx,text,photo=None):
    users=await get_all_uids(); total=len(users); ok=fail=0
    st=await ctx.bot.send_message(ADMIN_ID,f"📢 شروع پخش به {to_fa(total)} کاربر...")
    for i,uid in enumerate(users,1):
        try:
            if photo: await ctx.bot.send_photo(uid,photo=photo,caption=text)
            else: await ctx.bot.send_message(uid,text)
            ok+=1
        except: fail+=1
        if i%10==0 or i==total:
            try: await st.edit_text(f"📢 {to_fa(ok)}✔️ {to_fa(fail)}❌ {to_fa(i)}/{to_fa(total)}")
            except: pass
        await asyncio.sleep(0.2)
    await st.edit_text(f"✅ پخش تمام شد!\nموفق: {to_fa(ok)} | شکست: {to_fa(fail)}")

# ── backup
async def send_backup(bot):
    ts=shamsi_now().replace(" ","_").replace("—","-").replace(":","-")
    buf=io.BytesIO()
    files=[(DATA_FILE,"data.json"),(BANNER_FILE,"banner.json"),(WORKHOURS_FILE,"workhours.json"),
           (BUTTONS_FILE,"buttons.json"),(SETTINGS_FILE,"settings.json"),(STATS_FILE,"stats.json"),(MENU_FILE,"menu.json"),(DB_FILE,"users.db")]
    with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as zf:
        for fp,name in files:
            try:
                async with aiofiles.open(fp,"rb") as f: zf.writestr(name,await f.read())
            except Exception as e: logger.warning(f"backup skip {fp}: {e}")
    buf.seek(0)
    await bot.send_message(ADMIN_ID,f"💾 بک‌آپ — {shamsi_now()}")
    await bot.send_document(ADMIN_ID,document=buf,filename=f"backup_{ts}.zip",caption="💾 بک‌آپ کامل")

async def restore_backup(bot,file_id):
    try:
        f=await bot.get_file(file_id); buf=io.BytesIO()
        await f.download_to_memory(buf); buf.seek(0)
        with zipfile.ZipFile(buf,"r") as zf:
            mapping={"data.json":DATA_FILE,"banner.json":BANNER_FILE,"workhours.json":WORKHOURS_FILE,
                     "buttons.json":BUTTONS_FILE,"settings.json":SETTINGS_FILE,"stats.json":STATS_FILE,"menu.json":MENU_FILE,"users.db":DB_FILE}
            restored=[]
            for name in zf.namelist():
                if name in mapping:
                    async with aiofiles.open(mapping[name],"wb") as out: await out.write(zf.read(name))
                    restored.append(name)
        await load_data(); await load_banners(); await load_workhours()
        await load_buttons(); await load_settings(); await load_stats(); await load_menu()
        return True,restored
    except Exception as e:
        logger.error(f"restore: {e}"); return False,str(e)

# ════════════════════════════════════════════════
#  HANDLERS — cmd_start / cmd_admin
# ════════════════════════════════════════════════
async def cmd_start(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    import asyncio
    asyncio.ensure_future(woo.check_sync_version(force=True))  # چک تازگی در پس‌زمینه
    user=update.effective_user; is_new=False
    async with db.execute("SELECT user_id FROM users WHERE user_id=?",(user.id,)) as c: is_new=(await c.fetchone()) is None
    await save_user(user)
    if get_setting("notify_new_user") and is_new:
        try: await ctx.bot.send_message(ADMIN_ID,f"🆕 کاربر جدید!\n👤 {user.first_name or'—'}\n{'@'+user.username if user.username else'—'}\n🆔 {user.id}")
        except: pass
    wt=responses.get("welcome","✨ خوش آمدید")
    full=build_msg("خوش‌آمدگویی",wt,"welcome")
    kb=user_sec_kb("welcome")
    await send_banner(update.message,full,"welcome",kb=kb or main_menu())

async def cmd_admin(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID: return await update.message.reply_text("⛔ دسترسی ندارید")
    await update.message.reply_text("👑 پنل مدیریت استوک لند",reply_markup=admin_menu())

# ════════════════════════════════════════════════
#  USER CALLBACKS
# ════════════════════════════════════════════════
async def user_cb(query,ctx):
    data=query.data

    if data=="wh_weekly":
        table=wh_full_table(); sep="━"*15
        msg=f"{sep}\n📆 ساعت کار هفتگی مجموعه\n{sep}\n{table}\n{sep}"
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت",callback_data="wh_back_today")]])
        await query.message.reply_text(msg,reply_markup=kb); return

    if data=="wh_back_today":
        wh=wh_today_block() or""
        msg=f"🕐 ساعت کاری استوک لند\n{wh}"
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("📆 ساعت کار هفتگی مجموعه",callback_data="wh_weekly")]])
        await safe_edit(query.message,msg,reply_markup=kb); return

    if data=="cat_back":
        cats=await get_root_cats()
        if not cats: await safe_edit(query.message,"📫 محصولی موجود نیست."); return
        await safe_edit(query.message,"🛍 محصولات استوک لند\nیک دسته‌بندی را انتخاب کنید:",reply_markup=cat_root_kb(cats)); return

    if data=="cat_search":
        ctx.user_data["mode"]="cat_search"
        await query.message.reply_text("🔍 نام یا مدل محصول را بنویسید:",reply_markup=cancel_menu()); return

    if data.startswith("cr_back_"):
        sub_id=int(data[8:]); sub=await get_cat(sub_id)
        if not sub: return
        root=await get_cat(sub[3]); subs=await get_subcats(sub[3])
        await safe_edit(query.message,f"📁 {root[2] if root else ''} {root[1] if root else ''}\nزیردسته را انتخاب کنید:",reply_markup=cat_sub_kb(subs,sub[3])); return

    if data.startswith("cr_"):
        root_id=int(data[3:]); root=await get_cat(root_id)
        if not root: return
        subs=await get_subcats(root_id)
        if not subs:
            await safe_edit(query.message,f"📁 {root[2]} {root[1]}\n\n📫 هنوز زیردسته‌ای ثبت نشده.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت",callback_data="cat_back")]])); return
        await safe_edit(query.message,f"📁 {root[2]} {root[1]}\nزیردسته را انتخاب کنید:",reply_markup=cat_sub_kb(subs,root_id)); return

    if data.startswith("cs_back_"):
        sub_id=int(data[8:]); sub=await get_cat(sub_id)
        if not sub: return
        products=await get_products(sub_id); title=f"📦 {sub[2]} {sub[1]}"
        if not products:
            await safe_edit(query.message,f"{title}\n\n📫 محصولی موجود نیست.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت",callback_data=f"cr_{sub[3]}")]])); return
        await safe_edit(query.message,f"{title}\n{to_fa(len(products))} محصول:",reply_markup=cat_products_kb(products,sub_id)); return

    if data.startswith("cs_"):
        sub_id=int(data[3:]); sub=await get_cat(sub_id)
        if not sub: return
        products=await get_products(sub_id); title=f"📦 {sub[2]} {sub[1]}"
        if not products:
            await safe_edit(query.message,f"{title}\n\n📫 محصولی موجود نیست.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت",callback_data=f"cr_{sub[3]}")]])); return
        await safe_edit(query.message,f"{title}\n{to_fa(len(products))} محصول:",reply_markup=cat_products_kb(products,sub_id)); return

    if data.startswith("prd_"):
        pid=int(data[4:]); p=await get_product(pid)
        if not p: return
        await record_stat(f"prd_{pid}")
        text=f"📱 {p[1]}\n{'─'*18}\n💰 قیمت:  {p[2]}"
        if p[3]: text+=f"\n\n📝 {p[3]}"
        kb=product_kb(p)
        if p[4]:
            try: await query.message.reply_photo(photo=p[4],caption=text[:1024],reply_markup=kb); return
            except Exception as e: logger.error(f"prd photo {pid}: {e}")
        if len(text)>4000: text=text[:3990]+"..."
        await query.message.reply_text(text,reply_markup=kb); return

    if data.startswith("req_"):
        pid=int(data[4:]); p=await get_product(pid)
        if not p: return
        ctx.user_data.update({"mode":"req_phone","req_pid":pid,"req_name":p[1]})
        await query.message.reply_text(f"📋 درخواست خرید: {p[1]}\n\nشماره تماس خود را وارد کنید:",reply_markup=cancel_menu()); return

# ════════════════════════════════════════════════
#  MAIN CALLBACK DISPATCHER
# ════════════════════════════════════════════════
# پیشوندهایی که هم ادمین هم کاربر دسترسی دارد
_USER_CB_PREFIXES = ("cr_","cs_","prd_","req_","cat_","wh_weekly","wh_back_today")

async def callbacks(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    query=update.callback_query
    data=query.data; uid=query.from_user.id

    # ── مسیریابی کاربران — answer یکبار اینجا فراخوانی می‌شه
    if data.startswith(_USER_CB_PREFIXES) or uid!=ADMIN_ID:
        await query.answer()
        try: await user_cb(query,ctx)
        except Exception as e:
            logger.error(f"user_cb uid={uid} data={data}: {e}",exc_info=True)
            try: await query.message.reply_text("❌ خطا. دوباره امتحان کنید.")
            except: pass
        return

    # ════ ADMIN — هر handler خودش answer می‌زنه تا show_alert درست کار کنه
    try:
        if data=="back_to_admin":
            await query.answer()
            await safe_edit(query.message,"👑 پنل مدیریت استوک لند",reply_markup=admin_menu())

        elif data=="woo_status":
            await query.answer()
            import woo
            if not woo.is_configured():
                await safe_edit(query.message,
                    "🛍 محصولات سایت\n" + "─"*18 +
                    "\n\n⚠️ اتصال به سایت تنظیم نشده.\n\n"
                    "برای فعال‌سازی، متغیرهای WOO_URL، WOO_KEY و WOO_SECRET را در تنظیمات سرور وارد کنید.",
                    reply_markup=back_admin()); return
            await safe_edit(query.message,"🛍 در حال اتصال به سایت...",reply_markup=None)
            ok,msg = await woo.test_connection()
            if not ok:
                await safe_edit(query.message,f"🛍 محصولات سایت\n{'─'*18}\n\n❌ {msg}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 تلاش مجدد",callback_data="woo_status")],
                        [InlineKeyboardButton("🔙 پنل اصلی",callback_data="back_to_admin")]])); return
            roots = await woo.get_root_categories()
            cats = await woo.get_categories()
            total_prod = sum(c["count"] for c in roots)
            txt = (f"🛍 محصولات سایت (ووکامرس)\n{'─'*18}"
                   f"\n✅ اتصال برقرار است"
                   f"\n\n📂 دسته اصلی: {to_fa(len(roots))}"
                   f"\n📁 کل دسته‌ها: {to_fa(len(cats))}"
                   f"\n📦 مجموع محصولات: {to_fa(total_prod)}"
                   f"\n\n💡 محصولات از سایت stland.ir خوانده می‌شوند."
                   f"\nبرای افزودن یا ویرایش محصول، به پنل وردپرس مراجعه کنید.")
            await safe_edit(query.message,txt,reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 بروزرسانی فوری",callback_data="woo_refresh")],
                [InlineKeyboardButton("🔙 پنل اصلی",callback_data="back_to_admin")]]))

        elif data=="woo_refresh":
            await query.answer("کش پاک شد، در حال دریافت...",show_alert=False)
            import woo
            woo.clear_cache()
            await safe_edit(query.message,"🔄 محصولات بروزرسانی شد.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛍 مشاهده وضعیت",callback_data="woo_status")],
                    [InlineKeyboardButton("🔙 پنل اصلی",callback_data="back_to_admin")]]))

        elif data=="dash":
            await query.answer()
            t,d,w,m,nt,bl=(await total_users(),await today_users(),await week_users(),
                            await month_users(),await new_today(),await blk_count())
            sep="─"*22
            dash=(f"📊 داشبورد — {shamsi_now()}\n{sep}"
                  f"\n👥 کل کاربران: {to_fa(t)}     🚫 بلاک: {to_fa(bl)}"
                  f"\n{sep}"
                  f"\n🆕 عضو امروز:   {to_fa(nt)}"
                  f"\n📅 فعال امروز:  {to_fa(d)}   {progress_bar(d,t)}"
                  f"\n📆 فعال هفته:   {to_fa(w)}   {progress_bar(w,t)}"
                  f"\n🗓  فعال ماه:    {to_fa(m)}   {progress_bar(m,t)}"
                  f"\n{sep}")
            if len(dash)>4000: dash=dash[:3990]+"..."
            await safe_edit(query.message,dash,reply_markup=admin_menu())

        elif data=="broadcast":
            await query.answer()
            ctx.user_data["mode"]="broadcast"
            await query.message.reply_text("📢 پیام ارسال کنید:",reply_markup=cancel_menu())

        elif data=="backup":
            await query.answer()
            await safe_edit(query.message,"💾 مدیریت بک‌آپ:",reply_markup=backup_kb())

        elif data=="backup_get":
            await query.answer()
            await safe_edit(query.message,"💾 در حال تهیه...",reply_markup=None)
            await send_backup(query.message._bot)
            await safe_edit(query.message,"✅ بک‌آپ ارسال شد.",reply_markup=backup_kb())

        elif data=="backup_import":
            await query.answer()
            ctx.user_data["mode"]="backup_restore"
            await query.message.reply_text("📥 فایل ZIP بک‌آپ را ارسال کنید:",reply_markup=cancel_menu())

        # ── مدیریت بخش‌ها — یکپارچه برای تمام بخش‌ها
        elif data=="sections":
            await query.answer()
            await safe_edit(query.message,"📋 مدیریت بخش‌ها:",reply_markup=sections_kb())

        # ── مدیریت منوی اصلی ──
        elif data=="menu_mgr":
            await query.answer()
            en=sum(1 for m in menu_cfg if m.get("enabled",True))
            await safe_edit(query.message,
                f"🎛 مدیریت منوی اصلی\n{'─'*18}\n"
                f"دکمه فعال: {to_fa(en)} از {to_fa(len(menu_cfg))}\n\n"
                f"روی هر دکمه بزنید تا تنظیمش کنید:",
                reply_markup=menu_mgr_kb())

        elif data.startswith("mi_"):
            await query.answer()
            key=data[3:]; m=menu_item(key)
            if not m: return
            st="🟢 فعال" if m.get("enabled",True) else "⚫️ غیرفعال"
            w_txt="تمام‌صفحه" if m.get("width","half")=="full" else "نصف‌صفحه"
            await safe_edit(query.message,
                f"🎛 دکمه: {m['label']}\n{'─'*18}\nوضعیت: {st}\nعرض: {w_txt}",
                reply_markup=menu_item_kb(key))

        elif data.startswith("mtg_"):
            key=data[4:]; m=menu_item(key)
            if not m: return
            m["enabled"]=not m.get("enabled",True); await save_menu()
            await query.answer("🟢 روشن شد" if m["enabled"] else "⚫️ خاموش شد",show_alert=True)
            st="🟢 فعال" if m["enabled"] else "⚫️ غیرفعال"
            await safe_edit(query.message,f"🎛 دکمه: {m['label']}\n{'─'*18}\nوضعیت: {st}",reply_markup=menu_item_kb(key))

        elif data.startswith("mw_"):
            key=data[3:]; m=menu_item(key)
            if not m: return
            m["width"]="full" if m.get("width","half")=="half" else "half"; await save_menu()
            await query.answer("📐 تمام‌صفحه شد" if m["width"]=="full" else "📐 نصف‌صفحه شد",show_alert=True)
            w_txt="تمام‌صفحه" if m["width"]=="full" else "نصف‌صفحه"
            st="🟢 فعال" if m.get("enabled",True) else "⚫️ غیرفعال"
            await safe_edit(query.message,f"🎛 دکمه: {m['label']}\n{'─'*18}\nوضعیت: {st}\nعرض: {w_txt}",reply_markup=menu_item_kb(key))

        elif data.startswith("mnm_"):
            await query.answer()
            key=data[4:]; m=menu_item(key)
            if not m: return
            ctx.user_data.update({"mode":"menu_rename","menu_key":key})
            await query.message.reply_text(
                f"✏️ نام فعلی: {m['label']}\n\nنام جدید را بفرستید (با ایموجی دلخواه):",
                reply_markup=cancel_menu())

        elif data.startswith("mup_") or data.startswith("mdn_"):
            key=data[4:]; up=data.startswith("mup_")
            items=menu_sorted()
            idx=next((i for i,x in enumerate(items) if x["key"]==key),None)
            if idx is None: return
            swap=idx-1 if up else idx+1
            if 0<=swap<len(items):
                items[idx]["order"],items[swap]["order"]=items[swap]["order"],items[idx]["order"]
                await save_menu()
            await query.answer("⬆️ بالا رفت" if up else "⬇️ پایین رفت")
            await safe_edit(query.message,"🎛 مدیریت منوی اصلی\nترتیب بروزرسانی شد:",reply_markup=menu_mgr_kb())

        elif data.startswith("msw_"):
            key=data[4:]; partner=menu_row_partner(key)
            if not partner:
                await query.answer("این دکمه جفت ندارد",show_alert=True); return
            m=menu_item(key); p=menu_item(partner)
            m["order"],p["order"]=p["order"],m["order"]; await save_menu()
            await query.answer("↔️ جای دو دکمه عوض شد",show_alert=True)
            st="🟢 فعال" if m.get("enabled",True) else "⚫️ غیرفعال"
            w_txt="تمام‌صفحه" if m.get("width","half")=="full" else "نصف‌صفحه"
            await safe_edit(query.message,f"🎛 دکمه: {m['label']}\n{'─'*18}\nوضعیت: {st}\nعرض: {w_txt}",reply_markup=menu_item_kb(key))

        elif data=="menu_reset":
            await query.answer()
            await safe_edit(query.message,
                "♻️ بازگردانی منو به حالت پیش‌فرض\n\n"
                "نام، ترتیب و عرض همه دکمه‌ها به حالت اولیه برمی‌گردد.\nمطمئن هستید؟",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("♻️ بله، بازگردانی کن",callback_data="menu_reset_ok")],
                    [InlineKeyboardButton("↩️ انصراف",callback_data="menu_mgr")]]))

        elif data=="menu_reset_ok":
            await reset_menu()
            await query.answer("♻️ منو به حالت پیش‌فرض برگشت",show_alert=True)
            en=sum(1 for m in menu_cfg if m.get("enabled",True))
            await safe_edit(query.message,
                f"🎛 مدیریت منوی اصلی\n{'─'*18}\nدکمه فعال: {to_fa(en)} از {to_fa(len(menu_cfg))}\n\n✅ به حالت پیش‌فرض بازگشت.",
                reply_markup=menu_mgr_kb())

        elif data.startswith("sec_") and not any(data.startswith(p) for p in["sec_text_","sec_ban_","sec_btns_"]):
            await query.answer()
            key=data[4:]
            from telegram.error import BadRequest
            txt_ok="✅" if responses.get(key,"") not in ("","تنظیم نشده") else "❌"
            ban_ok="✅ فعال" if get_banner(key).get("active") and get_banner(key).get("file_id") else "❌"
            btn_ok=f"{len(get_sec_btns(key).get('items',[]))} {'✅' if get_sec_btns(key).get('enabled') else '❌'}"
            try: await safe_edit(query.message,
                f"📋 بخش: {SECTION_NAMES.get(key,key)}\n{'─'*14}"
                f"\n✏️ متن: {txt_ok}\n🖼 بنر: {ban_ok}\n🔘 دکمه: {btn_ok}",
                reply_markup=section_kb(key))
            except BadRequest: await query.message.reply_text(f"📋 {SECTION_NAMES.get(key,key)}",reply_markup=section_kb(key))

        elif data.startswith("sec_text_"):
            await query.answer()
            key=data[9:]; ctx.user_data.update({"mode":"edit_text","edit_key":key})
            await query.message.reply_text(f"✏️ متن فعلی:\n\n{responses.get(key,'تنظیم نشده')}\n\nمتن جدید:",reply_markup=cancel_menu())

        elif data.startswith("sec_ban_"):
            await query.answer()
            key=data[8:]; b=get_banner(key)
            await safe_edit(query.message,
                f"🖼 بنر: {SECTION_NAMES.get(key,key)}\n"
                f"{'✅ آپلود شده' if b.get('file_id') else '❌ ندارد'} | {'✅ فعال' if b.get('active') else '❌ غیرفعال'}",
                reply_markup=banner_kb(key))

        elif data.startswith("ban_up_"):
            await query.answer()
            key=data[7:]; ctx.user_data.update({"mode":"ban_up","ban_key":key})
            await query.message.reply_text(f"📤 عکس بنر «{SECTION_NAMES.get(key,key)}» را ارسال کنید:",reply_markup=cancel_menu())

        elif data.startswith("ban_tg_"):
            key=data[7:]; b=get_banner(key)
            if not b.get("file_id"): await query.answer("ابتدا عکس آپلود کنید!",show_alert=True); return
            b["active"]=not b.get("active",False); await save_banners()
            await query.answer("✅ فعال" if b["active"] else"❌ غیرفعال",show_alert=True)
            await safe_edit(query.message,f"🖼 {SECTION_NAMES.get(key,key)} | {'✅ فعال' if b['active'] else '❌ غیرفعال'}",reply_markup=banner_kb(key))

        elif data.startswith("ban_dl_"):
            key=data[7:]; banners[key]={"file_id":None,"active":False}; await save_banners()
            await query.answer("🗑 حذف شد.",show_alert=True)
            await safe_edit(query.message,f"🖼 {SECTION_NAMES.get(key,key)} | ❌",reply_markup=banner_kb(key))

        elif data.startswith("sec_btns_"):
            await query.answer()
            key=data[9:]; sec=get_sec_btns(key)
            await safe_edit(query.message,
                f"🔘 دکمه‌های {SECTION_NAMES.get(key,key)}\n"
                f"{'✅ فعال' if sec.get('enabled') else '❌ غیرفعال'} | {to_fa(len(sec.get('items',[])))} عدد",
                reply_markup=sec_btns_kb(key))

        elif data.startswith("btn_tg_"):
            key=data[7:]; sec=get_sec_btns(key); sec["enabled"]=not sec.get("enabled",False); await save_buttons()
            await query.answer("✅ فعال" if sec["enabled"] else"❌ غیرفعال",show_alert=True)
            await safe_edit(query.message,f"🔘 {SECTION_NAMES.get(key,key)} | {'✅' if sec['enabled'] else '❌'}",reply_markup=sec_btns_kb(key))

        elif data.startswith("btn_add_"):
            await query.answer()
            key=data[8:]; ctx.user_data.update({"mode":"btn_add_t","btn_key":key})
            await query.message.reply_text(f"➕ دکمه جدید برای «{SECTION_NAMES.get(key,key)}»\nعنوان:",reply_markup=cancel_menu())

        elif data.startswith("btn_ed_"):
            parts=data[7:].split("_",1); key,bid=parts[0],parts[1]
            sec=get_sec_btns(key); item=next((x for x in sec.get("items",[]) if x["id"]==bid),None)
            if not item: await query.answer("یافت نشد!",show_alert=True); return
            await query.answer()
            ctx.user_data.update({"mode":"btn_ed_t","btn_key":key,"btn_id":bid})
            await query.message.reply_text(f"✏️ «{item['title']}»\nعنوان جدید (یا . بدون تغییر):",reply_markup=cancel_menu())

        elif data.startswith("btn_dl_"):
            parts=data[7:].split("_",1); key,bid=parts[0],parts[1]
            sec=get_sec_btns(key); sec["items"]=[x for x in sec.get("items",[]) if x["id"]!=bid]; await save_buttons()
            await query.answer("🗑 حذف شد.",show_alert=True)
            await safe_edit(query.message,f"🔘 {SECTION_NAMES.get(key,key)}",reply_markup=sec_btns_kb(key))

        # ── درخواست‌ها
        elif data=="admin_reqs":
            await query.answer()
            reqs=await get_requests()
            if not reqs: await safe_edit(query.message,"📋 درخواستی وجود ندارد.",reply_markup=back_admin()); return
            nc=sum(1 for r in reqs if r[6]=="new")
            await safe_edit(query.message,f"📋 درخواست‌ها\n🆕 جدید: {to_fa(nc)} | کل: {to_fa(len(reqs))}",reply_markup=reqs_kb(reqs))

        elif data.startswith("rq_done_"):
            rid=int(data[8:]); await done_request(rid)
            await query.answer("✅",show_alert=True)
            await safe_edit(query.message,"✅ پیگیری شد.",reply_markup=back_admin())

        elif data.startswith("rq_"):
            await query.answer()
            rid=int(data[3:])
            async with db.execute("SELECT id,user_id,username,first_name,phone,product_name,status,created_at FROM requests WHERE id=?",(rid,)) as c: r=await c.fetchone()
            if not r: return
            st2="🆕 جدید" if r[6]=="new" else"✅ پیگیری شد"
            sep="─"*20
            txt=(f"📋 درخواست #{to_fa(r[0])}\n{sep}"
                 f"\n📱 {r[5]}"
                 f"\n{sep}"
                 f"\n👤 {r[3] or'—'}"
                 f"\n📞 {r[4]}"
                 f"\n🆔 {r[1]}  {'@'+r[2] if r[2] else ''}"
                 f"\n⏱ {r[7]}"
                 f"\n{sep}\n{st2}")
            await safe_edit(query.message,txt,reply_markup=req_kb(rid,r[6]))

        # ── ساعت کاری
        elif data=="wh_menu":
            await query.answer()
            en="✅ فعال" if workhours.get("enabled") else"❌ غیرفعال"
            await safe_edit(query.message,f"🕐 ساعت کاری — {en}\n\n{wh_full_table()}",reply_markup=wh_kb())

        elif data=="wh_toggle":
            workhours["enabled"]=not workhours.get("enabled",True); await save_workhours()
            await query.answer("✅ فعال" if workhours["enabled"] else"❌ غیرفعال",show_alert=True)
            await safe_edit(query.message,f"🕐 ساعت کاری\n{wh_full_table()}",reply_markup=wh_kb())

        elif data.startswith("wh_day_"):
            await query.answer()
            dk=data[7:]; day=workhours["schedule"].get(dk,{"open":False,"shifts":[]})
            st2="\n".join(f"  • {to_fa(s['from'])} تا {to_fa(s['to'])}" for s in day.get("shifts",[])) or"  ندارد"
            await safe_edit(query.message,f"🕐 {DAY_FA.get(dk,dk)}\n{'✅ باز' if day.get('open') else '❌ تعطیل'}\n{st2}",reply_markup=wh_day_kb(dk))

        elif data.startswith("wh_dtg_"):
            dk=data[7:]; day=workhours["schedule"].get(dk,{"open":False,"shifts":[]})
            day["open"]=not day.get("open",False); workhours["schedule"][dk]=day; await save_workhours()
            await query.answer("✅ باز" if day["open"] else"❌ تعطیل",show_alert=True)
            await safe_edit(query.message,f"🕐 {DAY_FA.get(dk,dk)} | {'✅ باز' if day['open'] else '❌ تعطیل'}",reply_markup=wh_day_kb(dk))

        elif data.startswith("wh_sh_"):
            await query.answer()
            dk=data[6:]; ctx.user_data.update({"mode":"wh_shifts","wh_day":dk})
            await query.message.reply_text(f"🕐 {DAY_FA.get(dk,dk)}:\nمثال: 11:00-14:00,17:00-23:00",reply_markup=cancel_menu())

        elif data=="wh_mop":
            await query.answer()
            ctx.user_data["mode"]="wh_mop"
            await query.message.reply_text(f"✏️ پیام باز:\n\n{workhours.get('msg_open','')}\n\nپیام جدید:",reply_markup=cancel_menu())

        elif data=="wh_mcl":
            await query.answer()
            ctx.user_data["mode"]="wh_mcl"
            await query.message.reply_text(f"✏️ پیام بسته:\n\n{workhours.get('msg_closed','')}\n\nپیام جدید:",reply_markup=cancel_menu())

        # ── تنظیمات
        elif data=="settings_menu":
            await query.answer()
            await safe_edit(query.message,
                "⚙️ تنظیمات\n" + "─"*18 + "\nمدیریت منو، بخش‌ها و اعلان‌ها:",
                reply_markup=settings_kb())

        elif data.startswith("stg_"):
            key=data[4:]; settings[key]=not get_setting(key); await save_settings()
            await query.answer("✅ ذخیره شد",show_alert=True)
            await safe_edit(query.message,
                "⚙️ تنظیمات\n" + "─"*18 + "\nمدیریت منو، بخش‌ها و اعلان‌ها:",
                reply_markup=settings_kb())

        # ── کاربران
        elif data=="users_menu":
            await query.answer()
            t=await total_users(); bl=await blk_count()
            await safe_edit(query.message,f"👥 کاربران\nکل: {to_fa(t)} | بلاک: {to_fa(bl)}",reply_markup=users_menu_kb())

        elif data=="users_search":
            await query.answer()
            ctx.user_data["mode"]="users_search"
            await query.message.reply_text("🔍 نام، آیدی یا یوزرنیم:",reply_markup=cancel_menu())

        elif data.startswith("ul_"):
            await query.answer()
            parts=data.split("_"); ft=parts[1]; off=int(parts[2])
            flt={"today":"WHERE DATE(last_seen)=DATE('now','localtime')","week":"WHERE last_seen>=datetime('now','-7 days','localtime')","blocked":"WHERE is_blocked=1"}
            total=await _cnt(f"SELECT COUNT(*) FROM users {flt.get(ft,'')}")
            rows=await get_users_page(off,15,ft)
            label={"all":"همه","today":"امروز","week":"هفته","blocked":"بلاک"}.get(ft,"")
            await safe_edit(query.message,f"👥 {label}\n{to_fa(off+1)} تا {to_fa(min(off+15,total))} از {to_fa(total)}:",reply_markup=users_list_kb(rows,off,ft,total))

        elif data.startswith("uv_"):
            uid2=int(data[3:])
            async with db.execute("SELECT user_id,first_name,username,joined_at,last_seen,is_blocked FROM users WHERE user_id=?",(uid2,)) as c: row=await c.fetchone()
            if not row: await query.answer("یافت نشد!",show_alert=True); return
            await query.answer()
            sep="─"*20
            utxt=(f"👤 {row[1] or'—'}"
                  f"\n{'@'+row[2] if row[2] else'بدون یوزرنیم'}"
                  f"\n🆔 {row[0]}"
                  f"\n{sep}"
                  f"\n📅 عضویت: {row[3]}"
                  f"\n🕐 آخرین فعالیت: {row[4]}"
                  f"\n{sep}"
                  f"\n{'🚫 بلاک‌شده' if row[5] else '✅ فعال'}")
            await safe_edit(query.message,utxt,reply_markup=udetail_kb(uid2,bool(row[5])))

        elif data.startswith("utog_"):
            uid2=int(data[5:])
            async with db.execute("SELECT is_blocked FROM users WHERE user_id=?",(uid2,)) as c: row=await c.fetchone()
            if not row: return
            await set_block(uid2,0 if row[0] else 1)
            await query.answer("✅ رفع بلاک" if row[0] else"🚫 بلاک شد",show_alert=True)
            async with db.execute("SELECT user_id,first_name,username,joined_at,last_seen,is_blocked FROM users WHERE user_id=?",(uid2,)) as c: row=await c.fetchone()
            await safe_edit(query.message,f"👤 {row[1] or'—'}\n🆔 {row[0]}\n{'🚫 بلاک' if row[5] else '✅ فعال'}",reply_markup=udetail_kb(uid2,bool(row[5])))

        else:
            await query.answer()

    except Exception as e:
        logger.error(f"admin callback error data={data}: {e}",exc_info=True)
        try: await query.answer()
        except: pass
        try: await query.message.reply_text("❌ خطا در پردازش درخواست.")
        except: pass

# ════════════════════════════════════════════════
#  TEXT HANDLER
# ════════════════════════════════════════════════
async def text_handler(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    user=update.effective_user; text=update.message.text.strip()
    await save_user(user)
    if not await anti_spam(user.id): return await update.message.reply_text("🐢 لطفاً آرام‌تر پیام دهید.")
    if text=="❌ لغو عملیات":
        ctx.user_data.clear(); return await update.message.reply_text("❌ لغو شد.",reply_markup=main_menu())
    mode=ctx.user_data.get("mode")

    # ════ ADMIN ════
    if user.id==ADMIN_ID:
        if mode=="edit_text":
            key=ctx.user_data.pop("edit_key",None); ctx.user_data.pop("mode",None)
            if key: responses[key]=text; await save_data()
            await update.message.reply_text("✅ ذخیره شد.",reply_markup=main_menu()); return
        if mode=="menu_rename":
            key=ctx.user_data.pop("menu_key",None); ctx.user_data.pop("mode",None)
            m=menu_item(key)
            if m and text:
                m["label"]=text; await save_menu()
                await update.message.reply_text(f"✅ نام دکمه به «{text}» تغییر کرد.",reply_markup=main_menu())
                await update.message.reply_text(f"🎛 دکمه: {m['label']}",reply_markup=menu_item_kb(key))
            else:
                await update.message.reply_text("✅ ذخیره شد.",reply_markup=main_menu())
            return
        if mode=="broadcast":
            ctx.user_data.pop("mode",None); await update.message.reply_text("📤 در حال ارسال...")
            await broadcast(ctx,text); return
        if mode=="users_search":
            ctx.user_data.pop("mode",None); rows=await search_users(text)
            if not rows: await update.message.reply_text("❌ یافت نشد.",reply_markup=main_menu()); return
            lines=[f"{'🚫 ' if r[4] else ''}{r[1] or'—'} | {r[0]} | {'@'+r[2] if r[2] else'—'}" for r in rows]
            await update.message.reply_text("🔍 نتایج:\n\n"+"\n".join(lines),reply_markup=main_menu()); return
        if mode=="btn_add_t":
            ctx.user_data.update({"btn_title":text,"mode":"btn_add_u"})
            await update.message.reply_text("🔗 لینک:",reply_markup=cancel_menu()); return
        if mode=="btn_add_u":
            key=ctx.user_data.pop("btn_key",None); title=ctx.user_data.pop("btn_title","دکمه"); ctx.user_data.pop("mode",None)
            url=text if text.startswith("http") else f"https://{text}"
            sec=get_sec_btns(key); sec["items"].append({"id":f"b{int(time.time())}","title":title,"url":url})
            if not sec.get("enabled"): sec["enabled"]=True
            await save_buttons()
            await update.message.reply_text(f"✅ «{title}» اضافه شد.",reply_markup=sec_btns_kb(key)); return
        if mode=="btn_ed_t":
            ctx.user_data.update({"btn_new_t":None if text=="." else text,"mode":"btn_ed_u"})
            await update.message.reply_text("🔗 لینک جدید (یا . بدون تغییر):",reply_markup=cancel_menu()); return
        if mode=="btn_ed_u":
            key=ctx.user_data.pop("btn_key",None); bid=ctx.user_data.pop("btn_id",None)
            nt=ctx.user_data.pop("btn_new_t",None); ctx.user_data.pop("mode",None)
            sec=get_sec_btns(key)
            for it in sec.get("items",[]):
                if it["id"]==bid:
                    if nt: it["title"]=nt
                    if text!=".": it["url"]=text if text.startswith("http") else f"https://{text}"
            await save_buttons(); await update.message.reply_text("✅ ویرایش شد.",reply_markup=main_menu()); return
        if mode=="wh_shifts":
            dk=ctx.user_data.pop("wh_day",None); ctx.user_data.pop("mode",None)
            try:
                sh=[{"from":p.split("-")[0].strip(),"to":p.split("-")[1].strip()} for p in text.split(",")]
                workhours["schedule"][dk]["shifts"]=sh; await save_workhours()
                await update.message.reply_text("✅ ذخیره شد.",reply_markup=main_menu())
            except: await update.message.reply_text("❌ فرمت اشتباه!\nمثال: 11:00-14:00,17:00-23:00",reply_markup=main_menu())
            return
        if mode=="wh_mop":
            ctx.user_data.pop("mode",None); workhours["msg_open"]=text; await save_workhours()
            await update.message.reply_text("✅",reply_markup=main_menu()); return
        if mode=="wh_mcl":
            ctx.user_data.pop("mode",None); workhours["msg_closed"]=text; await save_workhours()
            await update.message.reply_text("✅",reply_markup=main_menu()); return
    # ════ catalog search ════
    if mode=="cat_search":
        ctx.user_data.pop("mode",None); results=await search_products(text)
        if not results: await update.message.reply_text(f"🔍 نتیجه‌ای برای «{text}» یافت نشد.",reply_markup=main_menu()); return
        btns=[[InlineKeyboardButton(f"📱 {p[1]} — {p[2]}",callback_data=f"prd_{p[0]}")] for p in results]
        btns.append([InlineKeyboardButton("🔙 کاتالوگ",callback_data="cat_back")])
        await update.message.reply_text(f"🔍 {to_fa(len(results))} نتیجه برای «{text}»:",reply_markup=InlineKeyboardMarkup(btns)); return

    # ════ purchase request phone ════
    if mode=="req_phone":
        pid=ctx.user_data.pop("req_pid",None); pname=ctx.user_data.pop("req_name","نامشخص"); ctx.user_data.pop("mode",None)
        digits=text.replace("-","").replace(" ","").replace("+","")
        if not digits.isdigit() or len(digits)<10:
            ctx.user_data.update({"mode":"req_phone","req_pid":pid,"req_name":pname})
            await update.message.reply_text("❌ شماره معتبر نیست. دوباره:",reply_markup=cancel_menu()); return
        await save_request(user.id,user.username,user.first_name,text,pid,pname)
        try:
            await ctx.bot.send_message(ADMIN_ID,
                f"📋 درخواست خرید!\n📱 {pname}\n👤 {user.first_name or'—'} | {'@'+user.username if user.username else'—'}\n📞 {text}\n🆔 {user.id}")
        except Exception as e: logger.error(f"req notify: {e}")
        await update.message.reply_text(f"✅ درخواست خرید «{pname}» ثبت شد!\nپشتیبانی به زودی تماس می‌گیرد.",reply_markup=main_menu()); return

    # ════ user menu ════
    # تشخیص دکمه از روی label (که ممکن است ادمین تغییرش داده باشد)
    pressed = next((m for m in menu_cfg if m["label"]==text and m.get("enabled",True)), None)
    mkey = pressed["key"] if pressed else None

    if mkey=="workhours":
        await record_stat("wh_page")
        if not workhours.get("enabled",True): await update.message.reply_text("🕐 ساعت کاری تنظیم نشده.",reply_markup=main_menu()); return
        wh=wh_today_block() or""
        msg=f"🕐 ساعت کاری استوک لند\n{wh}"
        if len(msg)>4000: msg=msg[:3990]+"..."
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("📆 ساعت کار هفتگی مجموعه",callback_data="wh_weekly")]])
        await send_banner(update.message,msg,"workhours",kb=kb); return

    if mkey=="catalog":
        await record_stat("catalog")
        await woo.check_sync_version()  # ورود به محصولات → چک تازگی (هر ۱۰ دقیقه)
        cats=await get_root_cats()
        if not cats: await update.message.reply_text("📫 در حال حاضر محصولی موجود نیست.",reply_markup=main_menu()); return
        msg="🛍 محصولات استوک لند\nیک دسته‌بندی را انتخاب کنید:"
        await send_banner(update.message,msg,"catalog",kb=cat_root_kb(cats)); return

    # بخش‌های متنی (۱ تا ۵)
    if mkey and mkey in MENU_ITEMS:
        await record_stat(mkey); content=responses.get(mkey,"تنظیم نشده")
        full=build_msg(text,content,mkey)
        kb=user_sec_kb(mkey)
        await send_banner(update.message,full,mkey,kb=kb); return

    await update.message.reply_text("⚠️ گزینه نامعتبر است.",reply_markup=main_menu())

# ════════════════════════════════════════════════
#  PHOTO HANDLER
# ════════════════════════════════════════════════
async def photo_handler(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    if user.id!=ADMIN_ID: return
    mode=ctx.user_data.get("mode"); photo=update.message.photo[-1]
    if mode=="ban_up":
        key=ctx.user_data.pop("ban_key",None); ctx.user_data.pop("mode",None)
        if not key: await update.message.reply_text("❌ خطا.",reply_markup=main_menu()); return
        get_banner(key); banners[key]["file_id"]=photo.file_id; banners[key]["active"]=True; await save_banners()
        await update.message.reply_text(f"✅ بنر «{SECTION_NAMES.get(key,key)}» آپلود شد!",reply_markup=main_menu()); return
    if mode=="broadcast":
        ctx.user_data.pop("mode",None); caption=update.message.caption or""
        await update.message.reply_text("📤 در حال ارسال...")
        await broadcast(ctx,caption,photo=photo.file_id); return

# ════════════════════════════════════════════════
#  DOCUMENT HANDLER (backup import)
# ════════════════════════════════════════════════
async def document_handler(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    if user.id!=ADMIN_ID: return
    mode=ctx.user_data.get("mode")
    if mode!="backup_restore": return
    ctx.user_data.pop("mode",None)
    doc=update.message.document
    if not doc.file_name.endswith(".zip"):
        await update.message.reply_text("❌ فقط فایل ZIP قابل قبول است.",reply_markup=main_menu()); return
    await update.message.reply_text("⏳ در حال بازگردانی...")
    ok,result=await restore_backup(ctx.bot,doc.file_id)
    if ok: await update.message.reply_text(f"✅ بک‌آپ بازگردانی شد.\nفایل‌ها: {', '.join(result)}",reply_markup=main_menu())
    else: await update.message.reply_text(f"❌ خطا: {result}",reply_markup=main_menu())

# ════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════
async def post_init(app):
    await init_db(); await load_data(); await load_banners()
    await load_workhours(); await load_buttons(); await load_settings()
    await load_stats(); await load_menu()
    # Cache ووکامرس را گرم کن تا اولین کاربر منتظر نماند
    import asyncio
    asyncio.ensure_future(woo.warm_cache())
    logger.info("✅ ربات راه‌اندازی شد")

def main():
    app=ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start",cmd_start))
    app.add_handler(CommandHandler("admin",cmd_admin))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND,photo_handler))
    app.add_handler(MessageHandler(filters.Document.ZIP & ~filters.COMMAND,document_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler))
    print("🚀 ربات در حال اجراست...")
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    main()
