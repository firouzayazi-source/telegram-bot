import os, json, time, asyncio, logging, aiosqlite, jdatetime, pytz
from datetime import datetime
from collections import defaultdict, deque
import aiofiles
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

os.environ.pop("HTTP_PROXY", None); os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("ALL_PROXY", None); os.environ["NO_PROXY"] = "*"

TOKEN     = os.getenv("BOT_TOKEN", "8792062012:AAGXforSa1IY45AuC-yOHs2PsdzudvtdD44")
ADMIN_ID  = int(os.getenv("ADMIN_ID", "638469407"))
DATA_FILE = "data.json"; DB_FILE = "users.db"; BANNER_FILE = "banner.json"
WORKHOURS_FILE = "workhours.json"; BUTTONS_FILE = "buttons.json"
SETTINGS_FILE = "settings.json"; STATS_FILE = "stats.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
IRAN_TZ = pytz.timezone("Asia/Tehran")

def to_fa(t): return str(t).translate(str.maketrans("0123456789","۰۱۲۳۴۵۶۷۸۹"))
def fmt_time(t): return to_fa(t)

MONTH_FA={1:"فروردین",2:"اردیبهشت",3:"خرداد",4:"تیر",5:"مرداد",6:"شهریور",
          7:"مهر",8:"آبان",9:"آذر",10:"دی",11:"بهمن",12:"اسفند"}
DAY_NAMES={"0":"شنبه","1":"یکشنبه","2":"دوشنبه","3":"سه‌شنبه","4":"چهارشنبه","5":"پنجشنبه","6":"جمعه"}

def shamsi_now():
    now=datetime.now(IRAN_TZ); j=jdatetime.datetime.fromgregorian(datetime=now)
    return f"{to_fa(j.day)} {MONTH_FA[j.month]} {to_fa(j.year)} — {to_fa(now.strftime('%H:%M'))}"

def gregorian_now(): return datetime.now(IRAN_TZ).strftime("%Y-%m-%d %H:%M:%S")

MENU_ITEMS={"1":"🌐 شبکه‌های اجتماعی","2":"🌐 سایت استوک لند","3":"💰 شرایط اقساط","4":"📞 پشتیبانی","5":"📍 آدرس فروشگاه"}
SECTION_NAMES={"welcome":"🏠 خوش‌آمدگویی","1":"🌐 شبکه‌های اجتماعی","2":"🌐 سایت استوک لند",
               "3":"💰 شرایط اقساط","4":"📞 پشتیبانی","5":"📍 آدرس فروشگاه","workhours_page":"🕐 ساعت کاری"}

responses=None; banners={}; workhours={}; buttons={}; settings={}; stats={}
active_chats={}  # {user_id: True} — چت‌های فعال

DEFAULT_WORKHOURS={"enabled":True,"schedule":{
    "0":{"open":True,"shifts":[{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
    "1":{"open":True,"shifts":[{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
    "2":{"open":True,"shifts":[{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
    "3":{"open":True,"shifts":[{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
    "4":{"open":True,"shifts":[{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
    "5":{"open":True,"shifts":[{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
    "6":{"open":True,"shifts":[{"from":"17:00","to":"23:00"}]}},
    "msg_open":"✅ هم‌اکنون باز است","msg_closed":"🔴 هم‌اکنون بسته است"}

DEFAULT_SETTINGS={"show_workhours_in_sections":True,"show_datetime_footer":True,
    "show_workhours_menu":True,"show_catalog_menu":True,
    "notify_new_user":False,"store_open":True}
DEFAULT_SEC_WH={"welcome":True,"1":True,"2":True,"3":True,"4":True,"5":True,"workhours_page":False}

def get_banner(k):
    if k not in banners: banners[k]={"file_id":None,"active":False}
    return banners[k]
def get_section_buttons(k):
    if k not in buttons: buttons[k]={"enabled":True,"items":[]}
    return buttons[k]
def get_setting(k): return settings.get(k,DEFAULT_SETTINGS.get(k,False))
def get_section_wh(k):
    if not get_setting("show_workhours_in_sections"): return False
    return settings.get("section_workhours",DEFAULT_SEC_WH).get(k,True)
def set_section_wh(k,v):
    if "section_workhours" not in settings: settings["section_workhours"]=DEFAULT_SEC_WH.copy()
    settings["section_workhours"][k]=v

def is_open_now():
    if not get_setting("store_open"): return False
    if not workhours.get("enabled",True): return True
    now=datetime.now(IRAN_TZ); j=jdatetime.datetime.fromgregorian(datetime=now)
    day=workhours.get("schedule",{}).get(str(j.weekday()),{})
    if not day.get("open",False): return False
    ns=now.strftime("%H:%M")
    for s in day.get("shifts",[]):
        if s["from"]<=ns<=s["to"]: return True
    return False

def today_workhours_text():
    if not workhours.get("enabled",True): return None
    now=datetime.now(IRAN_TZ); j=jdatetime.datetime.fromgregorian(datetime=now)
    wd=str(j.weekday()); day=workhours.get("schedule",{}).get(wd,{})
    name=DAY_NAMES.get(wd,""); opened=is_open_now()
    status=workhours.get("msg_open","✅ هم‌اکنون باز است") if opened else workhours.get("msg_closed","🔴 هم‌اکنون بسته است")
    oi=["☀️","🌙","🌃","🕯"]; ci=["⚫️","⚫️","⚫️","⚫️"]
    sl=["شیفت اول","شیفت دوم","شیفت سوم","شیفت چهارم"]
    lines=["━━━━━━━━━━━━━━━","🏪 وضعیت فروشگاه",f"📅 امروز {name}",""]
    if not day.get("open"): lines.append("❌ امروز تعطیل است")
    else:
        shifts=day.get("shifts",[]); icons=oi if opened else ci
        for i,s in enumerate(shifts):
            icon=icons[i] if i<len(icons) else "🕐"; label=sl[i] if i<len(sl) else f"شیفت {to_fa(i+1)}"
            lines.append(f"{icon} {label}   {fmt_time(s['from'])} — {fmt_time(s['to'])}")
    lines+=["",status,"━━━━━━━━━━━━━━━"]
    return "\n".join(lines)

def workhours_full_summary():
    lines=[]
    for k,name in DAY_NAMES.items():
        day=workhours.get("schedule",{}).get(k,{})
        if not day.get("open"): lines.append(f"❌ {name}: تعطیل")
        else:
            sh=" و ".join([f"{fmt_time(s['from'])} تا {fmt_time(s['to'])}" for s in day.get("shifts",[])])
            lines.append(f"✅ {name}: {sh}")
    return "\n".join(lines)

def build_message(title,content,key):
    wh=today_workhours_text() if get_section_wh(key) else None
    ft=f"⏱ {shamsi_now()}" if get_setting("show_datetime_footer") else ""
    lines=[f"📌 {title}","──────────────",content,"──────────────"]
    if wh: lines+=["",wh]
    if ft: lines+=["","─────────────────",ft]
    return "\n".join(lines)

def progress_bar(v,t,n=8):
    if t==0: return "░"*n
    return "▓"*int(n*v/t)+"░"*(n-int(n*v/t))

def section_page_text(key):
    name=SECTION_NAMES.get(key,key); c=responses.get(key,"") if responses else ""
    b=get_banner(key); sec=get_section_buttons(key); wh=get_section_wh(key)
    return (f"📋 بخش: {name}\n──────────────\n"
            f"✏️ متن: {'✅ تنظیم شده' if c and c not in ('تنظیم نشده','') else '❌ ندارد'}\n"
            f"🖼 بنر: {'✅ فعال' if b.get('active') and b.get('file_id') else ('⏸ غیرفعال' if b.get('file_id') else '➕ ندارد')}\n"
            f"🔘 دکمه‌ها: {len(sec.get('items',[]))} {'✅' if sec.get('enabled') else '❌'}\n"
            f"🕐 ساعت کاری: {'✅ نمایش دارد' if wh else '❌ ندارد'}\n──────────────")

async def record_stat(k): stats[k]=stats.get(k,0)+1; await save_stats()
async def load_stats():
    global stats
    try:
        async with aiofiles.open(STATS_FILE,"r",encoding="utf-8") as f: stats=json.loads(await f.read())
    except: stats={}
async def save_stats():
    try:
        async with aiofiles.open(STATS_FILE,"w",encoding="utf-8") as f: await f.write(json.dumps(stats,ensure_ascii=False,indent=4))
    except Exception as e: logger.error(f"save_stats: {e}")

async def load_data():
    global responses
    try:
        async with aiofiles.open(DATA_FILE,"r",encoding="utf-8") as f: responses=json.loads(await f.read())
    except:
        responses=MENU_ITEMS.copy(); responses["welcome"]="✨ خوش آمدید به ربات استوک لند"
async def save_data():
    try:
        async with aiofiles.open(DATA_FILE,"w",encoding="utf-8") as f: await f.write(json.dumps(responses,ensure_ascii=False,indent=4))
    except Exception as e: logger.error(f"save_data: {e}")

async def load_banners():
    global banners
    try:
        async with aiofiles.open(BANNER_FILE,"r",encoding="utf-8") as f:
            d=json.loads(await f.read());
            if isinstance(d,dict): banners=d
    except: banners={}
    for k in SECTION_NAMES:
        if k not in banners: banners[k]={"file_id":None,"active":False}
async def save_banners():
    try:
        async with aiofiles.open(BANNER_FILE,"w",encoding="utf-8") as f: await f.write(json.dumps(banners,ensure_ascii=False,indent=4))
    except Exception as e: logger.error(f"save_banners: {e}")

async def load_workhours():
    global workhours
    try:
        async with aiofiles.open(WORKHOURS_FILE,"r",encoding="utf-8") as f: workhours=json.loads(await f.read())
    except: workhours=DEFAULT_WORKHOURS.copy(); await save_workhours()
async def save_workhours():
    try:
        async with aiofiles.open(WORKHOURS_FILE,"w",encoding="utf-8") as f: await f.write(json.dumps(workhours,ensure_ascii=False,indent=4))
    except Exception as e: logger.error(f"save_workhours: {e}")

async def load_buttons():
    global buttons
    try:
        async with aiofiles.open(BUTTONS_FILE,"r",encoding="utf-8") as f: buttons=json.loads(await f.read())
    except: buttons={}
    for k in SECTION_NAMES:
        if k not in buttons: buttons[k]={"enabled":True,"items":[]}
async def save_buttons():
    try:
        async with aiofiles.open(BUTTONS_FILE,"w",encoding="utf-8") as f: await f.write(json.dumps(buttons,ensure_ascii=False,indent=4))
    except Exception as e: logger.error(f"save_buttons: {e}")

async def load_settings():
    global settings
    try:
        async with aiofiles.open(SETTINGS_FILE,"r",encoding="utf-8") as f: settings=json.loads(await f.read())
    except:
        settings=DEFAULT_SETTINGS.copy(); settings["section_workhours"]=DEFAULT_SEC_WH.copy(); await save_settings()
async def save_settings():
    try:
        async with aiofiles.open(SETTINGS_FILE,"w",encoding="utf-8") as f: await f.write(json.dumps(settings,ensure_ascii=False,indent=4))
    except Exception as e: logger.error(f"save_settings: {e}")

db=None
async def init_db():
    global db
    db=await aiosqlite.connect(DB_FILE)
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        joined_at TEXT, last_seen TEXT, is_blocked INTEGER DEFAULT 0)""")
    await db.execute("""CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        username TEXT, first_name TEXT, message TEXT, msg_id INTEGER,
        status TEXT DEFAULT 'open', created_at TEXT)""")
    await db.execute("""CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT,
        icon TEXT DEFAULT '📦', sort_order INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1)""")
    await db.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER,
        name TEXT, price TEXT, description TEXT, photo_id TEXT,
        buy_url TEXT, site_url TEXT, is_active INTEGER DEFAULT 1, created_at TEXT)""")
    try: await db.execute("ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0")
    except: pass
    await db.commit()

async def save_user(user):
    now=gregorian_now()
    await db.execute("INSERT OR IGNORE INTO users VALUES (?,?,?,?,?,0)",(user.id,user.username or "",user.first_name or "",now,now))
    await db.execute("UPDATE users SET username=?,first_name=?,last_seen=? WHERE user_id=?",(user.username or "",user.first_name or "",now,user.id))
    await db.commit()

async def get_all_users():
    async with db.execute("SELECT user_id FROM users WHERE is_blocked=0") as c: return [r[0] for r in await c.fetchall()]
async def is_blocked(uid):
    async with db.execute("SELECT is_blocked FROM users WHERE user_id=?",(uid,)) as c:
        r=await c.fetchone(); return bool(r and r[0])
async def block_user(uid): await db.execute("UPDATE users SET is_blocked=1 WHERE user_id=?",(uid,)); await db.commit()
async def unblock_user(uid): await db.execute("UPDATE users SET is_blocked=0 WHERE user_id=?",(uid,)); await db.commit()

async def search_users(q):
    q=f"%{q}%"
    async with db.execute("SELECT user_id,first_name,username,last_seen,is_blocked FROM users WHERE first_name LIKE ? OR username LIKE ? OR CAST(user_id AS TEXT) LIKE ? ORDER BY last_seen DESC LIMIT 15",(q,q,q)) as c: return await c.fetchall()

async def get_users_page(offset=0,limit=15,ft="all"):
    fmap={"today":"WHERE DATE(last_seen)=DATE('now','localtime')","week":"WHERE last_seen>=datetime('now','-7 days','localtime')","blocked":"WHERE is_blocked=1"}
    async with db.execute(f"SELECT user_id,first_name,username,last_seen,is_blocked FROM users {fmap.get(ft,'')} ORDER BY last_seen DESC LIMIT {limit} OFFSET {offset}") as c: return await c.fetchall()

async def total_users():
    async with db.execute("SELECT COUNT(*) FROM users") as c: return (await c.fetchone())[0]
async def today_users():
    async with db.execute("SELECT COUNT(*) FROM users WHERE DATE(last_seen)=DATE('now','localtime')") as c: return (await c.fetchone())[0]
async def week_users():
    async with db.execute("SELECT COUNT(*) FROM users WHERE last_seen>=datetime('now','-7 days','localtime')") as c: return (await c.fetchone())[0]
async def month_users():
    async with db.execute("SELECT COUNT(*) FROM users WHERE last_seen>=datetime('now','-30 days','localtime')") as c: return (await c.fetchone())[0]
async def new_today():
    async with db.execute("SELECT COUNT(*) FROM users WHERE DATE(joined_at)=DATE('now','localtime')") as c: return (await c.fetchone())[0]
async def blocked_count():
    async with db.execute("SELECT COUNT(*) FROM users WHERE is_blocked=1") as c: return (await c.fetchone())[0]

async def get_categories(active_only=True):
    q="WHERE is_active=1" if active_only else ""
    async with db.execute(f"SELECT id,name,icon,is_active FROM categories {q} ORDER BY sort_order,id") as c: return await c.fetchall()
async def get_products(cat_id,active_only=True):
    q="AND is_active=1" if active_only else ""
    async with db.execute(f"SELECT id,name,price,description,photo_id,buy_url,site_url,is_active FROM products WHERE category_id=? {q} ORDER BY id",(cat_id,)) as c: return await c.fetchall()
async def get_product(pid):
    async with db.execute("SELECT id,name,price,description,photo_id,buy_url,site_url,is_active,category_id FROM products WHERE id=?",(pid,)) as c: return await c.fetchone()

WINDOW,LIMIT,BLOCK=10,7,60
spam=defaultdict(lambda: deque(maxlen=LIMIT)); blocked_temp={}
async def anti_spam(uid):
    if uid==ADMIN_ID: return True
    if await is_blocked(uid): return False
    now=time.time()
    if uid in blocked_temp and blocked_temp[uid]>now: return False
    q=spam[uid]; q.append(now)
    if len(q)>=LIMIT and (now-q[0])<=WINDOW: blocked_temp[uid]=now+BLOCK; return False
    return True

def main_menu():
    keys=list(MENU_ITEMS.keys()); rows=[]
    for i in range(0,len(keys),2):
        row=[MENU_ITEMS[keys[i]]]
        if i+1<len(keys): row.append(MENU_ITEMS[keys[i+1]])
        rows.append(row)
    extra=[]
    if get_setting("show_workhours_menu"): extra.append("🕐 ساعت کاری")
    if get_setting("show_catalog_menu"):   extra.append("🛍 محصولات")

    if extra: rows.append(extra)
    return ReplyKeyboardMarkup(rows,resize_keyboard=True)

def admin_menu():
    op=is_open_now(); st="🟢" if op else "🔴"
    tg="🔴 بستن فروشگاه" if op else "🟢 باز کردن فروشگاه"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 داشبورد",callback_data="dash"),InlineKeyboardButton("👥 کاربران",callback_data="users_menu")],
        [InlineKeyboardButton("📋 مدیریت بخش‌ها",callback_data="sections")],
        [InlineKeyboardButton("🛍 کاتالوگ",callback_data="admin_catalog"),InlineKeyboardButton("📨 تیکت‌ها",callback_data="admin_tickets")],
        [InlineKeyboardButton("🕐 ساعت کاری",callback_data="workhours_menu"),InlineKeyboardButton("⚙️ تنظیمات",callback_data="settings_menu")],
        [InlineKeyboardButton("📢 پخش همگانی",callback_data="broadcast"),InlineKeyboardButton("💬 چت‌های فعال",callback_data="active_chats_list")],
        [InlineKeyboardButton("💾 بک‌آپ",callback_data="backup"),InlineKeyboardButton("📊 آمار",callback_data="sections_stats")],
        [InlineKeyboardButton(f"{st} {tg}",callback_data="quick_toggle")],
    ])

def back_admin(): return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت",callback_data="back_to_admin")]])
def admin_cancel_menu(): return ReplyKeyboardMarkup([["❌ لغو عملیات"]],resize_keyboard=True)

def user_section_kb(key):
    sec=get_section_buttons(key)
    if not sec.get("enabled",True): return None
    items=[x for x in sec.get("items",[]) if x.get("url")]
    if not items: return None
    btns=[]; row=[]
    for i,item in enumerate(items):
        row.append(InlineKeyboardButton(item["title"],url=item["url"]))
        if len(row)==2 or i==len(items)-1: btns.append(row); row=[]
    return InlineKeyboardMarkup(btns) if btns else None

def catalog_categories_kb(cats):
    btns=[[InlineKeyboardButton(f"{c[2]} {c[1]}",callback_data=f"cat_{c[0]}")] for c in cats]
    return InlineKeyboardMarkup(btns) if btns else None

def catalog_products_kb(products,cat_id):
    btns=[[InlineKeyboardButton(f"📱 {p[1]}",callback_data=f"prd_{p[0]}")] for p in products]
    btns.append([InlineKeyboardButton("🔙 برگشت",callback_data="catalog_back")])
    return InlineKeyboardMarkup(btns)

def product_kb(p):
    btns=[]; row=[]
    if p[5]: row.append(InlineKeyboardButton("🛒 خرید",url=p[5]))
    if p[6]: row.append(InlineKeyboardButton("🌐 مشاهده در سایت",url=p[6]))
    if row: btns.append(row)
    btns.append([InlineKeyboardButton("🔙 برگشت",callback_data=f"cat_{p[8]}")])
    return InlineKeyboardMarkup(btns)

def admin_catalog_kb(cats):
    btns=[]
    for c in cats:
        en="✅" if c[3] else "❌"
        btns.append([InlineKeyboardButton(f"{en} {c[2]} {c[1]}",callback_data=f"acat_{c[0]}")])
    btns.append([InlineKeyboardButton("➕ دسته‌بندی جدید",callback_data="acat_new")])
    btns.append([InlineKeyboardButton("🔙 برگشت",callback_data="back_to_admin")])
    return InlineKeyboardMarkup(btns)

def admin_category_kb(cat_id,products):
    btns=[]
    for p in products:
        en="✅" if p[7] else "❌"
        btns.append([InlineKeyboardButton(f"{en} {p[1]}",callback_data=f"aprd_{p[0]}")])
    btns.append([InlineKeyboardButton("➕ محصول جدید",callback_data=f"aprd_new_{cat_id}")])
    btns.append([InlineKeyboardButton("✏️ ویرایش دسته",callback_data=f"acat_edit_{cat_id}"),InlineKeyboardButton("🗑 حذف دسته",callback_data=f"acat_del_{cat_id}")])
    btns.append([InlineKeyboardButton("🔙 برگشت",callback_data="admin_catalog")])
    return InlineKeyboardMarkup(btns)

def admin_product_kb(pid,cat_id,is_active):
    tg="🔴 غیرفعال" if is_active else "🟢 فعال"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ نام",callback_data=f"aprd_ename_{pid}"),InlineKeyboardButton("💰 قیمت",callback_data=f"aprd_eprice_{pid}")],
        [InlineKeyboardButton("📝 توضیح",callback_data=f"aprd_edesc_{pid}"),InlineKeyboardButton("📸 عکس",callback_data=f"aprd_ephoto_{pid}")],
        [InlineKeyboardButton("🛒 لینک خرید",callback_data=f"aprd_ebuy_{pid}"),InlineKeyboardButton("🌐 لینک سایت",callback_data=f"aprd_esite_{pid}")],
        [InlineKeyboardButton(tg,callback_data=f"aprd_etog_{pid}")],
        [InlineKeyboardButton("🗑 حذف",callback_data=f"aprd_del_{pid}")],
        [InlineKeyboardButton("🔙 برگشت",callback_data=f"acat_{cat_id}")],
    ])

def admin_tickets_kb(tickets):
    btns=[]
    for t in tickets:
        st="🟡" if t[6]=="open" else "✅"
        btns.append([InlineKeyboardButton(f"{st} {t[3] or '—'} | {t[2] or t[1]}",callback_data=f"atkt_{t[0]}")])
    btns.append([InlineKeyboardButton("🔙 برگشت",callback_data="back_to_admin")])
    return InlineKeyboardMarkup(btns)

def admin_ticket_detail_kb(tid,status):
    btns=[]
    if status=="open": btns.append([InlineKeyboardButton("✅ بستن تیکت",callback_data=f"atkt_close_{tid}")])
    btns.append([InlineKeyboardButton("🔙 برگشت",callback_data="admin_tickets")])
    return InlineKeyboardMarkup(btns)

def sections_list_kb():
    btns=[]
    for key,name in SECTION_NAMES.items():
        if key=="workhours_page": continue
        c=responses.get(key,"") if responses else ""; b=get_banner(key); sec=get_section_buttons(key)
        ti="✅" if c and c not in ("تنظیم نشده","") else "➕"
        bi="🖼" if b.get("active") and b.get("file_id") else "○"
        bti=f"🔘{len(sec.get('items',[]))}" if sec.get("enabled") else "○"
        btns.append([InlineKeyboardButton(f"{name}  {ti}{bi}{bti}",callback_data=f"sec_{key}")])
    btns.append([InlineKeyboardButton("🔙 برگشت",callback_data="back_to_admin")])
    return InlineKeyboardMarkup(btns)

def section_kb(key):
    b=get_banner(key); sec=get_section_buttons(key); wh=get_section_wh(key)
    bst="🖼✅" if b.get("active") and b.get("file_id") else ("🖼⏸" if b.get("file_id") else "🖼➕")
    bbt=f"🔘✅({len(sec.get('items',[]))})" if sec.get("enabled") else f"🔘❌({len(sec.get('items',[]))})"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ ویرایش متن",callback_data=f"sec_text_{key}")],
        [InlineKeyboardButton(f"{bst} بنر",callback_data=f"sec_banner_{key}")],
        [InlineKeyboardButton(f"{bbt} دکمه‌ها",callback_data=f"sec_btns_{key}")],
        [InlineKeyboardButton(f"🕐{'✅' if wh else '❌'} ساعت کاری",callback_data=f"sec_wh_{key}")],
        [InlineKeyboardButton("🔙 برگشت",callback_data="sections")],
    ])

def banner_kb(key):
    b=get_banner(key); tg="🔴 غیرفعال" if b.get("active") else "🟢 فعال"
    btns=[[InlineKeyboardButton("📤 آپلود",callback_data=f"ban_up_{key}")],[InlineKeyboardButton(tg,callback_data=f"ban_tg_{key}")]]
    if b.get("file_id"): btns.append([InlineKeyboardButton("🗑 حذف",callback_data=f"ban_dl_{key}")])
    btns.append([InlineKeyboardButton("🔙 برگشت",callback_data=f"sec_{key}")]); return InlineKeyboardMarkup(btns)

def section_btns_kb(key):
    sec=get_section_buttons(key); tg="🔴 غیرفعال همه" if sec.get("enabled") else "🟢 فعال همه"
    btns=[[InlineKeyboardButton(tg,callback_data=f"btn_tg_{key}")]]
    for item in sec.get("items",[]):
        btns.append([InlineKeyboardButton(f"🔗 {item['title']}",callback_data=f"btn_edt_{key}_{item['id']}"),InlineKeyboardButton("🗑",callback_data=f"btn_del_{key}_{item['id']}")])
    btns.append([InlineKeyboardButton("➕ دکمه جدید",callback_data=f"btn_add_{key}"),InlineKeyboardButton("🔙 برگشت",callback_data=f"sec_{key}")])
    return InlineKeyboardMarkup(btns)

def workhours_kb():
    en=workhours.get("enabled",True); tg="🔴 غیرفعال" if en else "🟢 فعال"
    btns=[[InlineKeyboardButton(tg,callback_data="wh_toggle")]]
    for k,name in DAY_NAMES.items():
        day=workhours.get("schedule",{}).get(k,{}); st="✅" if day.get("open") else "❌"
        btns.append([InlineKeyboardButton(f"{st} {name}",callback_data=f"wh_day_{k}")])
    btns+=[[InlineKeyboardButton("✏️ پیام باز بودن",callback_data="wh_msg_open")],[InlineKeyboardButton("✏️ پیام بسته بودن",callback_data="wh_msg_closed")],[InlineKeyboardButton("🔙 برگشت",callback_data="back_to_admin")]]
    return InlineKeyboardMarkup(btns)

def workhours_day_kb(dk):
    day=workhours.get("schedule",{}).get(dk,{}); tg="🔴 تعطیل" if day.get("open") else "🟢 باز کردن"
    return InlineKeyboardMarkup([[InlineKeyboardButton(tg,callback_data=f"wh_dtg_{dk}")],[InlineKeyboardButton("✏️ تنظیم ساعت‌ها",callback_data=f"wh_shifts_{dk}")],[InlineKeyboardButton("🔙 برگشت",callback_data="workhours_menu")]])

def settings_kb():
    def t(k): return "✅" if get_setting(k) else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{t('show_workhours_in_sections')} ساعت کاری در بخش‌ها",callback_data="stg_show_workhours_in_sections")],
        [InlineKeyboardButton(f"{t('show_datetime_footer')} تاریخ و ساعت پایین پیام‌ها",callback_data="stg_show_datetime_footer")],
        [InlineKeyboardButton(f"{t('show_workhours_menu')} گزینه ساعت کاری در منو",callback_data="stg_show_workhours_menu")],
        [InlineKeyboardButton(f"{t('show_catalog_menu')} گزینه محصولات در منو",callback_data="stg_show_catalog_menu")],
        [InlineKeyboardButton(f"{t('notify_new_user')} اعلان عضو جدید",callback_data="stg_notify_new_user")],
        [InlineKeyboardButton("🔙 برگشت",callback_data="back_to_admin")],
    ])

def users_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 همه",callback_data="ulist_all_0"),InlineKeyboardButton("📅 امروز",callback_data="ulist_today_0")],
        [InlineKeyboardButton("📆 هفته",callback_data="ulist_week_0"),InlineKeyboardButton("🚫 بلاک",callback_data="ulist_blocked_0")],
        [InlineKeyboardButton("🔍 جستجو",callback_data="users_search")],
        [InlineKeyboardButton("🔙 برگشت",callback_data="back_to_admin")],
    ])

def users_list_kb(rows,offset,ft,total):
    btns=[]
    for r in rows:
        bl="🚫 " if r[4] else ""
        btns.append([InlineKeyboardButton(f"{bl}{r[1] or '—'} | {r[0]}",callback_data=f"uview_{r[0]}")])
    nav=[]
    if offset>0: nav.append(InlineKeyboardButton("◀️",callback_data=f"ulist_{ft}_{offset-15}"))
    if offset+15<total: nav.append(InlineKeyboardButton("▶️",callback_data=f"ulist_{ft}_{offset+15}"))
    if nav: btns.append(nav)
    btns.append([InlineKeyboardButton("🔙 برگشت",callback_data="users_menu")]); return InlineKeyboardMarkup(btns)

def user_detail_kb(uid,is_bl):
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ رفع بلاک" if is_bl else "🚫 بلاک",callback_data=f"utoggle_{uid}")],[InlineKeyboardButton("🔙 برگشت",callback_data="users_menu")]])

async def send_with_banner(msg,text,key,reply_markup=None):
    b=get_banner(key)
    if b.get("active") and b.get("file_id"):
        try: await msg.reply_photo(photo=b["file_id"],caption=text,reply_markup=reply_markup); return
        except Exception as e: logger.error(f"banner [{key}]: {e}")
    await msg.reply_text(text,reply_markup=reply_markup)

async def send_broadcast(context,text,photo_id=None):
    users=await get_all_users(); total=len(users); success=failed=0
    status=await context.bot.send_message(ADMIN_ID,f"📢 شروع پخش به {total} کاربر...")
    for i,uid in enumerate(users,1):
        try:
            if photo_id: await context.bot.send_photo(uid,photo=photo_id,caption=text)
            else: await context.bot.send_message(uid,text)
            success+=1
        except: failed+=1
        if i%10==0 or i==total:
            try: await status.edit_text(f"📢 پخش...\n✅ {success} | ❌ {failed} | {i}/{total}")
            except: pass
        await asyncio.sleep(0.2)
    await status.edit_text(f"✅ پخش تمام شد!\nموفق: {success} | شکست: {failed}")

async def send_backup(bot):
    now=shamsi_now().replace(" ","_").replace("—","-").replace(":","-")
    files=[(DATA_FILE,"data"),(BANNER_FILE,"banner"),(WORKHOURS_FILE,"workhours"),
           (BUTTONS_FILE,"buttons"),(SETTINGS_FILE,"settings"),(STATS_FILE,"stats"),(DB_FILE,"users_db")]
    await bot.send_message(ADMIN_ID,f"💾 بک‌آپ کامل — {shamsi_now()}")
    for fp,label in files:
        try:
            async with aiofiles.open(fp,"rb") as f: content=await f.read()
            ext=fp.split(".")[-1]
            await bot.send_document(ADMIN_ID,document=content,filename=f"backup_{label}_{now}.{ext}")
        except Exception as e: logger.error(f"backup {fp}: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user; is_new=False
    async with db.execute("SELECT user_id FROM users WHERE user_id=?",(user.id,)) as c: is_new=(await c.fetchone()) is None
    await save_user(user)
    if get_setting("notify_new_user") and is_new:
        try: await context.bot.send_message(ADMIN_ID,f"🆕 کاربر جدید!\n👤 {user.first_name or '—'}\n{'@'+user.username if user.username else '—'}\n🆔 {user.id}")
        except: pass
    wt=responses.get("welcome","✨ خوش آمدید به ربات استوک لند")
    full=build_message("خوش‌آمدگویی",wt,"welcome")
    kb=user_section_kb("welcome")
    await send_with_banner(update.message,full,"welcome",reply_markup=kb or main_menu())

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID: return await update.message.reply_text("⛔ دسترسی ندارید")
    await update.message.reply_text("👑 پنل مدیریت",reply_markup=admin_menu())

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query; await query.answer()
    if query.from_user.id!=ADMIN_ID: return
    data=query.data

    if data=="back_to_admin": await query.message.edit_text("👑 پنل مدیریت",reply_markup=admin_menu())
    elif data=="quick_toggle":
        settings["store_open"]=not get_setting("store_open"); await save_settings()
        await query.answer("🟢 باز شد" if settings["store_open"] else "🔴 بسته شد",show_alert=True)
        await query.message.edit_text("👑 پنل مدیریت",reply_markup=admin_menu())
    elif data=="dash":
        t,d,w,m,nt,bl=(await total_users(),await today_users(),await week_users(),await month_users(),await new_today(),await blocked_count())
        op="🟢 باز" if is_open_now() else "🔴 بسته"; wh=today_workhours_text() or ""; chats=len(active_chats)
        await query.message.edit_text(
            f"📊 داشبورد — {shamsi_now()}\n══════════════\n"
            f"👥 کل: {t}  |  🚫 بلاک: {bl}\n══════════════\n"
            f"🆕 عضو امروز: {nt}\n📅 فعال امروز: {d}  {progress_bar(d,t)}\n"
            f"📆 فعال هفته: {w}  {progress_bar(w,t)}\n🗓 فعال ماه: {m}  {progress_bar(m,t)}\n"
            f"══════════════\n🏪 وضعیت: {op}\n💬 چت‌های فعال: {chats}\n{wh}",reply_markup=admin_menu())
    elif data=="sections_stats":
        if not stats: await query.message.edit_text("📊 هنوز آماری ثبت نشده.",reply_markup=back_admin()); return
        ss=sorted(stats.items(),key=lambda x:x[1],reverse=True); tv=sum(stats.values())
        lines=["📊 آمار بازدید:\n──────────────"]
        for k,cnt in ss:
            name=SECTION_NAMES.get(k,k); pct=int(100*cnt/tv) if tv else 0
            lines.append(f"{name}\n  {progress_bar(cnt,tv,8)} {to_fa(cnt)} ({to_fa(pct)}%)")
        lines.append(f"──────────────\nمجموع: {to_fa(tv)}")
        await query.message.edit_text("\n".join(lines),reply_markup=back_admin())
    elif data=="broadcast":
        context.user_data["mode"]="broadcast"
        await query.message.reply_text("📢 پیام پخش را ارسال کنید:",reply_markup=admin_cancel_menu())
    elif data=="active_chats_list":
        if not active_chats:
            await query.message.edit_text("💬 هیچ چت فعالی وجود ندارد.",reply_markup=back_admin()); return
        btns=[]
        for uid in active_chats:
            async with db.execute("SELECT first_name,username FROM users WHERE user_id=?",(uid,)) as c2:
                row=await c2.fetchone()
            name=row[0] if row else "—"; uname=f"@{row[1]}" if row and row[1] else str(uid)
            btns.append([InlineKeyboardButton(f"💬 {name} | {uname}",callback_data=f"chat_select_{uid}")])
        btns.append([InlineKeyboardButton("🔙 برگشت",callback_data="back_to_admin")])
        await query.message.edit_text(f"💬 چت‌های فعال ({len(active_chats)}):",reply_markup=InlineKeyboardMarkup(btns))

    elif data.startswith("chat_select_"):
        uid=int(data[12:])
        async with db.execute("SELECT first_name,username FROM users WHERE user_id=?",(uid,)) as c2:
            row=await c2.fetchone()
        name=row[0] if row else "—"; uname=f"@{row[1]}" if row and row[1] else str(uid)
        await query.message.edit_text(
            f"💬 چت با {name} ({uname})\n🆔 {uid}\n──────────────\nهر پیامی بفرستید به این کاربر می‌رسد.\nیا /to_{uid} بنویسید.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ پایان چت",callback_data=f"end_chat_{uid}")],
                [InlineKeyboardButton("🔙 برگشت",callback_data="active_chats_list")],
            ]))

    elif data=="backup":
        await query.message.edit_text("💾 در حال ارسال...",reply_markup=back_admin())
        await send_backup(query.message._bot)
        await query.message.edit_text("✅ بک‌آپ ارسال شد.",reply_markup=back_admin())

    elif data=="admin_catalog":
        cats=await get_categories(active_only=False)
        await query.message.edit_text("🛍 مدیریت کاتالوگ:",reply_markup=admin_catalog_kb(cats))
    elif data=="acat_new":
        context.user_data["mode"]="acat_new_icon"
        await query.message.reply_text("🎨 آیکون دسته (مثال: 📱 💻 🎧):",reply_markup=admin_cancel_menu())
    elif data.startswith("acat_edit_"):
        cat_id=int(data[10:]); context.user_data.update({"mode":"acat_edit_name","cat_id":cat_id})
        await query.message.reply_text("✏️ نام جدید دسته:",reply_markup=admin_cancel_menu())
    elif data.startswith("acat_del_"):
        cat_id=int(data[9:])
        await db.execute("DELETE FROM categories WHERE id=?",(cat_id,))
        await db.execute("DELETE FROM products WHERE category_id=?",(cat_id,)); await db.commit()
        await query.answer("🗑 حذف شد.",show_alert=True)
        cats=await get_categories(active_only=False)
        await query.message.edit_text("🛍 مدیریت کاتالوگ:",reply_markup=admin_catalog_kb(cats))
    elif data.startswith("acat_"):
        cat_id=int(data[5:])
        async with db.execute("SELECT id,name,icon,is_active FROM categories WHERE id=?",(cat_id,)) as c: cat=await c.fetchone()
        if not cat: return
        products=await get_products(cat_id,active_only=False)
        en="✅ فعال" if cat[3] else "❌ غیرفعال"
        await query.message.edit_text(f"🛍 {cat[2]} {cat[1]}\nوضعیت: {en} | محصولات: {len(products)}",reply_markup=admin_category_kb(cat_id,products))
    elif data.startswith("aprd_new_"):
        cat_id=int(data[9:]); context.user_data.update({"mode":"aprd_new_name","cat_id":cat_id})
        await query.message.reply_text("📱 نام محصول:",reply_markup=admin_cancel_menu())
    elif data.startswith("aprd_etog_"):
        pid=int(data[10:]); p=await get_product(pid)
        if not p: return
        new_a=0 if p[7] else 1
        await db.execute("UPDATE products SET is_active=? WHERE id=?",(new_a,pid)); await db.commit()
        await query.answer("✅ فعال" if new_a else "❌ غیرفعال",show_alert=True)
        p=await get_product(pid)
        await query.message.edit_text(f"📱 {p[1]}\n💰 {p[2]}",reply_markup=admin_product_kb(pid,p[8],bool(p[7])))
    elif data.startswith("aprd_del_"):
        pid=int(data[9:]); p=await get_product(pid); cat_id=p[8] if p else 0
        await db.execute("DELETE FROM products WHERE id=?",(pid,)); await db.commit()
        await query.answer("🗑 حذف شد.",show_alert=True)
        products=await get_products(cat_id,active_only=False)
        async with db.execute("SELECT id,name,icon,is_active FROM categories WHERE id=?",(cat_id,)) as c: cat=await c.fetchone()
        await query.message.edit_text(f"🛍 {cat[2] if cat else ''} {cat[1] if cat else ''}",reply_markup=admin_category_kb(cat_id,products))
    elif data.startswith("aprd_ename_"): pid=int(data[11:]); context.user_data.update({"mode":"aprd_edit_name","edit_pid":pid}); await query.message.reply_text("✏️ نام جدید:",reply_markup=admin_cancel_menu())
    elif data.startswith("aprd_eprice_"): pid=int(data[12:]); context.user_data.update({"mode":"aprd_edit_price","edit_pid":pid}); await query.message.reply_text("💰 قیمت جدید:",reply_markup=admin_cancel_menu())
    elif data.startswith("aprd_edesc_"): pid=int(data[11:]); context.user_data.update({"mode":"aprd_edit_desc","edit_pid":pid}); await query.message.reply_text("📝 توضیح جدید (یا . برای حذف):",reply_markup=admin_cancel_menu())
    elif data.startswith("aprd_ephoto_"): pid=int(data[12:]); context.user_data.update({"mode":"aprd_edit_photo","edit_pid":pid}); await query.message.reply_text("📸 عکس جدید:",reply_markup=admin_cancel_menu())
    elif data.startswith("aprd_ebuy_"): pid=int(data[10:]); context.user_data.update({"mode":"aprd_edit_buy","edit_pid":pid}); await query.message.reply_text("🛒 لینک خرید (یا . برای حذف):",reply_markup=admin_cancel_menu())
    elif data.startswith("aprd_esite_"): pid=int(data[11:]); context.user_data.update({"mode":"aprd_edit_site","edit_pid":pid}); await query.message.reply_text("🌐 لینک سایت (یا . برای حذف):",reply_markup=admin_cancel_menu())
    elif data.startswith("aprd_"):
        pid=int(data[5:]); p=await get_product(pid)
        if not p: return
        en="✅ فعال" if p[7] else "❌ غیرفعال"
        await query.message.edit_text(f"📱 {p[1]}\n💰 {p[2]}\n📝 {p[3] or '—'}\nوضعیت: {en}",reply_markup=admin_product_kb(pid,p[8],bool(p[7])))

    elif data=="catalog_back":
        cats=await get_categories()
        await query.message.edit_text("🛍 کاتالوگ:\nدسته‌بندی را انتخاب کنید:",reply_markup=catalog_categories_kb(cats))
    elif data.startswith("cat_"):
        cat_id=int(data[4:])
        async with db.execute("SELECT id,name,icon FROM categories WHERE id=? AND is_active=1",(cat_id,)) as c: cat=await c.fetchone()
        if not cat: return
        products=await get_products(cat_id)
        if not products:
            await query.message.edit_text("📭 محصولی موجود نیست.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت",callback_data="catalog_back")]])); return
        await query.message.edit_text(f"🛍 {cat[2]} {cat[1]}\n{len(products)} محصول:",reply_markup=catalog_products_kb(products,cat_id))
    elif data.startswith("prd_"):
        pid=int(data[4:]); p=await get_product(pid)
        if not p: return
        ft=f"\n─────────────────\n⏱ {shamsi_now()}" if get_setting("show_datetime_footer") else ""
        text=f"📱 {p[1]}\n💰 قیمت: {p[2]}"
        if p[3]: text+=f"\n\n📝 {p[3]}"
        text+=ft; kb=product_kb(p)
        if p[4]:
            try: await query.message.reply_photo(photo=p[4],caption=text,reply_markup=kb); return
            except: pass
        await query.message.reply_text(text,reply_markup=kb)

    elif data=="admin_tickets":
        async with db.execute("SELECT id,user_id,username,first_name,message,msg_id,status,created_at FROM tickets ORDER BY id DESC LIMIT 20") as c: tickets=await c.fetchall()
        if not tickets: await query.message.edit_text("📭 تیکتی وجود ندارد.",reply_markup=back_admin()); return
        await query.message.edit_text("📨 تیکت‌ها:",reply_markup=admin_tickets_kb(tickets))
    elif data.startswith("atkt_close_"):
        tid=int(data[11:]); await db.execute("UPDATE tickets SET status='closed' WHERE id=?",(tid,)); await db.commit()
        await query.answer("✅ بسته شد.",show_alert=True)
        async with db.execute("SELECT id,user_id,username,first_name,message,status FROM tickets WHERE id=?",(tid,)) as c: t=await c.fetchone()
        if t: await query.message.edit_text(f"📨 تیکت #{t[0]}\n👤 {t[3] or '—'}\nوضعیت: ✅ بسته",reply_markup=admin_ticket_detail_kb(tid,"closed"))
    elif data.startswith("atkt_"):
        tid=int(data[5:])
        async with db.execute("SELECT id,user_id,username,first_name,message,msg_id,status,created_at FROM tickets WHERE id=?",(tid,)) as c: t=await c.fetchone()
        if not t: return
        st="🟡 باز" if t[6]=="open" else "✅ بسته"
        await query.message.edit_text(
            f"📨 تیکت #{t[0]}\n👤 {t[3] or '—'} | {'@'+t[2] if t[2] else t[1]}\n🆔 {t[1]}\n📝 {t[4]}\n🕒 {t[7]}\nوضعیت: {st}\n\nبرای پاسخ، reply کنید.",
            reply_markup=admin_ticket_detail_kb(tid,t[6]))

    elif data=="users_menu":
        t=await total_users(); bl=await blocked_count()
        await query.message.edit_text(f"👥 کاربران\n──────────────\nکل: {t} | بلاک: {bl}",reply_markup=users_menu_kb())
    elif data=="users_search":
        context.user_data["mode"]="users_search"; await query.message.reply_text("🔍 نام، آیدی یا یوزرنیم:",reply_markup=admin_cancel_menu())
    elif data.startswith("ulist_"):
        parts=data.split("_"); ft=parts[1]; offset=int(parts[2])
        fmap={"today":"WHERE DATE(last_seen)=DATE('now','localtime')","week":"WHERE last_seen>=datetime('now','-7 days','localtime')","blocked":"WHERE is_blocked=1"}
        async with db.execute(f"SELECT COUNT(*) FROM users {fmap.get(ft,'')}") as c: total=(await c.fetchone())[0]
        rows=await get_users_page(offset,15,ft); label={"all":"همه","today":"امروز","week":"هفته","blocked":"بلاک"}.get(ft,"")
        await query.message.edit_text(f"👥 {label}\n{offset+1} تا {min(offset+15,total)} از {total}:",reply_markup=users_list_kb(rows,offset,ft,total))
    elif data.startswith("uview_"):
        uid=int(data[6:])
        async with db.execute("SELECT user_id,first_name,username,joined_at,last_seen,is_blocked FROM users WHERE user_id=?",(uid,)) as c: row=await c.fetchone()
        if not row: await query.answer("یافت نشد!",show_alert=True); return
        bl_st="🚫 بلاک" if row[5] else "✅ فعال"
        await query.message.edit_text(f"👤 {row[1] or '—'}\n{'@'+row[2] if row[2] else '—'}\n🆔 {row[0]}\nعضویت: {row[3]}\nآخرین فعالیت: {row[4]}\nوضعیت: {bl_st}",reply_markup=user_detail_kb(uid,bool(row[5])))
    elif data.startswith("utoggle_"):
        uid=int(data[8:])
        async with db.execute("SELECT is_blocked FROM users WHERE user_id=?",(uid,)) as c: row=await c.fetchone()
        if not row: return
        if row[0]: await unblock_user(uid); await query.answer("✅ رفع بلاک",show_alert=True)
        else: await block_user(uid); await query.answer("🚫 بلاک شد",show_alert=True)
        async with db.execute("SELECT user_id,first_name,username,joined_at,last_seen,is_blocked FROM users WHERE user_id=?",(uid,)) as c: row=await c.fetchone()
        await query.message.edit_text(f"👤 {row[1] or '—'}\n🆔 {row[0]}\nوضعیت: {'🚫 بلاک' if row[5] else '✅ فعال'}",reply_markup=user_detail_kb(uid,bool(row[5])))

    elif data=="sections": await query.message.edit_text("📋 مدیریت بخش‌ها:",reply_markup=sections_list_kb())
    elif data.startswith("sec_") and not any(data.startswith(p) for p in ["sec_text_","sec_banner_","sec_btns_","sec_wh_"]):
        key=data[4:]; await query.message.edit_text(section_page_text(key),reply_markup=section_kb(key))
    elif data.startswith("sec_text_"):
        key=data[9:]; context.user_data.update({"mode":"edit_text","edit_key":key})
        await query.message.reply_text(f"✏️ متن فعلی:\n\n{responses.get(key,'تنظیم نشده')}\n\nمتن جدید:",reply_markup=admin_cancel_menu())
    elif data.startswith("sec_wh_"):
        key=data[7:]; set_section_wh(key,not get_section_wh(key)); await save_settings()
        await query.answer("✅ تغییر کرد",show_alert=True); await query.message.edit_text(section_page_text(key),reply_markup=section_kb(key))
    elif data.startswith("sec_banner_"):
        key=data[11:]; b=get_banner(key)
        await query.message.edit_text(f"🖼 بنر: {SECTION_NAMES.get(key,key)}\nعکس: {'✅' if b.get('file_id') else '❌'}\nوضعیت: {'✅ فعال' if b.get('active') else '❌ غیرفعال'}",reply_markup=banner_kb(key))
    elif data.startswith("ban_up_"):
        key=data[7:]; context.user_data.update({"mode":"banner_upload","banner_key":key})
        await query.message.reply_text(f"📤 عکس بنر «{SECTION_NAMES.get(key,key)}»:",reply_markup=admin_cancel_menu())
    elif data.startswith("ban_tg_"):
        key=data[7:]; b=get_banner(key)
        if not b.get("file_id"): await query.answer("ابتدا عکس آپلود کنید!",show_alert=True); return
        b["active"]=not b.get("active",False); await save_banners()
        await query.answer("✅ فعال" if b["active"] else "❌ غیرفعال",show_alert=True)
        await query.message.edit_text(f"🖼 {SECTION_NAMES.get(key,key)}\nوضعیت: {'✅ فعال' if b['active'] else '❌ غیرفعال'}",reply_markup=banner_kb(key))
    elif data.startswith("ban_dl_"):
        key=data[7:]; banners[key]={"file_id":None,"active":False}; await save_banners()
        await query.answer("🗑 حذف شد.",show_alert=True)
        await query.message.edit_text(f"🖼 {SECTION_NAMES.get(key,key)}\nعکس: ❌",reply_markup=banner_kb(key))
    elif data.startswith("sec_btns_"):
        key=data[9:]; sec=get_section_buttons(key)
        await query.message.edit_text(f"🔘 دکمه‌های: {SECTION_NAMES.get(key,key)}\nوضعیت: {'✅' if sec.get('enabled') else '❌'} | تعداد: {len(sec.get('items',[]))}",reply_markup=section_btns_kb(key))
    elif data.startswith("btn_tg_"):
        key=data[7:]; sec=get_section_buttons(key); sec["enabled"]=not sec.get("enabled",True); await save_buttons()
        await query.answer("✅ فعال" if sec["enabled"] else "❌ غیرفعال",show_alert=True)
        await query.message.edit_text(f"🔘 {SECTION_NAMES.get(key,key)}\nوضعیت: {'✅' if sec['enabled'] else '❌'}",reply_markup=section_btns_kb(key))
    elif data.startswith("btn_add_"):
        key=data[8:]; context.user_data.update({"mode":"btn_add_title","btn_key":key})
        await query.message.reply_text(f"➕ دکمه جدید برای «{SECTION_NAMES.get(key,key)}»\nعنوان:",reply_markup=admin_cancel_menu())
    elif data.startswith("btn_edt_"):
        parts=data[8:].split("_",1); key,bid=parts[0],parts[1]; sec=get_section_buttons(key)
        item=next((x for x in sec.get("items",[]) if x["id"]==bid),None)
        if not item: await query.answer("یافت نشد!",show_alert=True); return
        context.user_data.update({"mode":"btn_edit_title","btn_key":key,"btn_id":bid})
        await query.message.reply_text(f"✏️ «{item['title']}»\nعنوان جدید (یا . بدون تغییر):",reply_markup=admin_cancel_menu())
    elif data.startswith("btn_del_"):
        parts=data[8:].split("_",1); key,bid=parts[0],parts[1]; sec=get_section_buttons(key)
        sec["items"]=[x for x in sec.get("items",[]) if x["id"]!=bid]; await save_buttons()
        await query.answer("🗑 حذف شد.",show_alert=True); await query.message.edit_text(f"🔘 {SECTION_NAMES.get(key,key)}",reply_markup=section_btns_kb(key))

    elif data=="settings_menu": await query.message.edit_text("⚙️ تنظیمات:",reply_markup=settings_kb())
    elif data.startswith("stg_"):
        key=data[4:]; settings[key]=not get_setting(key); await save_settings()
        await query.answer("✅ ذخیره شد",show_alert=True); await query.message.edit_text("⚙️ تنظیمات:",reply_markup=settings_kb())

    elif data=="start_chat":
        user=query.from_user
        if user.id in active_chats and active_chats[user.id]:
            await query.message.reply_text("💬 یک چت از قبل برای شما فعال است.",
                reply_markup=ReplyKeyboardMarkup([["❌ پایان چت"]],resize_keyboard=True)); return
        active_chats[user.id]=True
        try:
            await context.bot.send_message(ADMIN_ID,
                f"🟢 چت جدید!\n👤 {user.first_name or '—'} | {'@'+user.username if user.username else str(user.id)}\n🆔 {user.id}\n──────────────\nبرای پاسخ بنویسید:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ پایان چت",callback_data=f"end_chat_{user.id}")]]))
        except Exception as e: logger.error(f"start_chat: {e}")
        await query.message.reply_text(
            "💬 چت شما شروع شد!\nپیام خود را بنویسید.\nبرای پایان دکمه زیر را بزنید:",
            reply_markup=ReplyKeyboardMarkup([["❌ پایان چت"]],resize_keyboard=True)); return

    elif data.startswith("end_chat_"):
        uid=int(data[9:])
        active_chats.pop(uid,None)
        await query.answer("✅ چت پایان یافت.",show_alert=True)
        try: await context.bot.send_message(uid,"🔴 پشتیبانی چت را پایان داد.",reply_markup=ReplyKeyboardMarkup([["❌ لغو"]],resize_keyboard=True))
        except: pass
        try:
            from telegram import ReplyKeyboardRemove
            await context.bot.send_message(uid,"می‌توانید دوباره از بخش پشتیبانی چت جدید شروع کنید.",reply_markup=ReplyKeyboardMarkup([["📞 پشتیبانی"]],resize_keyboard=True))
        except: pass

    elif data=="workhours_menu":
        en="✅ فعال" if workhours.get("enabled") else "❌ غیرفعال"
        await query.message.edit_text(f"🕐 ساعت کاری — {en}\n\n{workhours_full_summary()}",reply_markup=workhours_kb())
    elif data=="wh_toggle":
        workhours["enabled"]=not workhours.get("enabled",True); await save_workhours()
        await query.answer("✅ فعال" if workhours["enabled"] else "❌ غیرفعال",show_alert=True)
        await query.message.edit_text(f"🕐 ساعت کاری\n{workhours_full_summary()}",reply_markup=workhours_kb())
    elif data.startswith("wh_day_"):
        dk=data[7:]; day=workhours["schedule"].get(dk,{"open":False,"shifts":[]})
        st="\n".join([f"  • {fmt_time(s['from'])} تا {fmt_time(s['to'])}" for s in day.get("shifts",[])]) or "  ندارد"
        await query.message.edit_text(f"🕐 {DAY_NAMES.get(dk,dk)}\nوضعیت: {'✅ باز' if day.get('open') else '❌ تعطیل'}\nساعت‌ها:\n{st}",reply_markup=workhours_day_kb(dk))
    elif data.startswith("wh_dtg_"):
        dk=data[7:]; day=workhours["schedule"].get(dk,{"open":False,"shifts":[]}); day["open"]=not day.get("open",False)
        workhours["schedule"][dk]=day; await save_workhours()
        await query.answer("✅ باز شد" if day["open"] else "❌ تعطیل شد",show_alert=True)
        await query.message.edit_text(f"🕐 {'✅ باز' if day['open'] else '❌ تعطیل'}",reply_markup=workhours_day_kb(dk))
    elif data.startswith("wh_shifts_"):
        dk=data[10:]; context.user_data.update({"mode":"wh_set_shifts","wh_day":dk})
        await query.message.reply_text(f"🕐 {DAY_NAMES.get(dk,dk)}:\nمثال: 11:00-14:00,17:00-23:00",reply_markup=admin_cancel_menu())
    elif data=="wh_msg_open":
        context.user_data["mode"]="wh_set_msg_open"
        await query.message.reply_text(f"✏️ پیام باز بودن:\n\n{workhours.get('msg_open','')}\n\nپیام جدید:",reply_markup=admin_cancel_menu())
    elif data=="wh_msg_closed":
        context.user_data["mode"]="wh_set_msg_closed"
        await query.message.reply_text(f"✏️ پیام بسته بودن:\n\n{workhours.get('msg_closed','')}\n\nپیام جدید:",reply_markup=admin_cancel_menu())

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user; text=update.message.text.strip()
    await save_user(user)
    if not await anti_spam(user.id): return await update.message.reply_text("🐢 لطفاً آرام‌تر پیام دهید.")
    if text=="❌ لغو عملیات":
        context.user_data.clear(); return await update.message.reply_text("❌ لغو شد.",reply_markup=main_menu())
    mode=context.user_data.get("mode")

    if user.id==ADMIN_ID:
        if mode=="edit_text":
            key=context.user_data.pop("edit_key",None); context.user_data.pop("mode",None)
            if key: responses[key]=text; await save_data()
            await update.message.reply_text("✅ ذخیره شد.",reply_markup=main_menu()); return
        if mode=="broadcast":
            context.user_data.pop("mode",None); await update.message.reply_text("📤 در حال ارسال...")
            await send_broadcast(context,text); return
        if mode=="users_search":
            context.user_data.pop("mode",None); rows=await search_users(text)
            if not rows: await update.message.reply_text("❌ یافت نشد.",reply_markup=main_menu()); return
            lines=[f"{'🚫 ' if r[4] else ''}{r[1] or '—'} | {r[0]} | {'@'+r[2] if r[2] else '—'}" for r in rows]
            await update.message.reply_text("🔍 نتایج:\n\n"+"\n".join(lines),reply_markup=main_menu()); return
        if mode=="btn_add_title":
            context.user_data.update({"btn_title":text,"mode":"btn_add_url"})
            await update.message.reply_text("🔗 لینک (https://...):",reply_markup=admin_cancel_menu()); return
        if mode=="btn_add_url":
            key=context.user_data.pop("btn_key",None); title=context.user_data.pop("btn_title","دکمه"); context.user_data.pop("mode",None)
            url=text if text.startswith("http") else f"https://{text}"
            sec=get_section_buttons(key); sec["items"].append({"id":f"b{int(time.time())}","title":title,"url":url})
            await save_buttons(); await update.message.reply_text(f"✅ دکمه «{title}» اضافه شد.",reply_markup=main_menu()); return
        if mode=="btn_edit_title":
            context.user_data.update({"btn_new_title":None if text=="." else text,"mode":"btn_edit_url"})
            await update.message.reply_text("🔗 لینک جدید (یا . بدون تغییر):",reply_markup=admin_cancel_menu()); return
        if mode=="btn_edit_url":
            key=context.user_data.pop("btn_key",None); bid=context.user_data.pop("btn_id",None)
            nt=context.user_data.pop("btn_new_title",None); context.user_data.pop("mode",None)
            sec=get_section_buttons(key)
            for item in sec.get("items",[]):
                if item["id"]==bid:
                    if nt: item["title"]=nt
                    if text!=".": item["url"]=text if text.startswith("http") else f"https://{text}"
            await save_buttons(); await update.message.reply_text("✅ ویرایش شد.",reply_markup=main_menu()); return
        if mode=="wh_set_shifts":
            dk=context.user_data.pop("wh_day",None); context.user_data.pop("mode",None)
            try:
                shifts=[]
                for part in text.split(","):
                    fr,to=part.strip().split("-"); shifts.append({"from":fr.strip(),"to":to.strip()})
                workhours["schedule"][dk]["shifts"]=shifts; await save_workhours()
                await update.message.reply_text("✅ ساعت‌ها ذخیره شد.",reply_markup=main_menu())
            except: await update.message.reply_text("❌ فرمت اشتباه!\nمثال: 11:00-14:00,17:00-23:00",reply_markup=main_menu())
            return
        if mode=="wh_set_msg_open":
            context.user_data.pop("mode",None); workhours["msg_open"]=text; await save_workhours()
            await update.message.reply_text("✅ ذخیره شد.",reply_markup=main_menu()); return
        if mode=="wh_set_msg_closed":
            context.user_data.pop("mode",None); workhours["msg_closed"]=text; await save_workhours()
            await update.message.reply_text("✅ ذخیره شد.",reply_markup=main_menu()); return
        if mode=="acat_new_icon":
            context.user_data.update({"cat_icon":text,"mode":"acat_new_name"})
            await update.message.reply_text("✏️ نام دسته‌بندی:",reply_markup=admin_cancel_menu()); return
        if mode=="acat_new_name":
            icon=context.user_data.pop("cat_icon","📦"); context.user_data.pop("mode",None)
            await db.execute("INSERT INTO categories (name,icon,sort_order,is_active) VALUES (?,?,0,1)",(text,icon)); await db.commit()
            await update.message.reply_text(f"✅ دسته «{icon} {text}» اضافه شد.",reply_markup=main_menu()); return
        if mode=="acat_edit_name":
            cat_id=context.user_data.pop("cat_id",None); context.user_data.pop("mode",None)
            await db.execute("UPDATE categories SET name=? WHERE id=?",(text,cat_id)); await db.commit()
            await update.message.reply_text("✅ نام ذخیره شد.",reply_markup=main_menu()); return
        if mode=="aprd_new_name":
            context.user_data.update({"prd_name":text,"mode":"aprd_new_price"})
            await update.message.reply_text("💰 قیمت:",reply_markup=admin_cancel_menu()); return
        if mode=="aprd_new_price":
            context.user_data.update({"prd_price":text,"mode":"aprd_new_desc"})
            await update.message.reply_text("📝 توضیح (یا . برای بدون توضیح):",reply_markup=admin_cancel_menu()); return
        if mode=="aprd_new_desc":
            context.user_data.update({"prd_desc":None if text=="." else text,"mode":"aprd_new_buy"})
            await update.message.reply_text("🛒 لینک خرید (یا . برای بدون لینک):",reply_markup=admin_cancel_menu()); return
        if mode=="aprd_new_buy":
            context.user_data.update({"prd_buy":None if text=="." else text,"mode":"aprd_new_site"})
            await update.message.reply_text("🌐 لینک سایت (یا . برای بدون لینک):",reply_markup=admin_cancel_menu()); return
        if mode=="aprd_new_site":
            context.user_data.update({"prd_site":None if text=="." else text,"mode":"aprd_new_photo"})
            await update.message.reply_text("📸 عکس محصول (یا . برای بدون عکس):",reply_markup=admin_cancel_menu()); return
        if mode=="aprd_new_photo" and text==".":
            cat_id=context.user_data.pop("cat_id",None); name=context.user_data.pop("prd_name","")
            price=context.user_data.pop("prd_price",""); desc=context.user_data.pop("prd_desc",None)
            buy=context.user_data.pop("prd_buy",None); site=context.user_data.pop("prd_site",None)
            context.user_data.pop("mode",None)
            await db.execute("INSERT INTO products (category_id,name,price,description,photo_id,buy_url,site_url,is_active,created_at) VALUES (?,?,?,?,?,?,?,1,?)",
                (cat_id,name,price,desc,None,buy,site,gregorian_now()))
            await db.commit(); await update.message.reply_text(f"✅ محصول «{name}» اضافه شد.",reply_markup=main_menu()); return
        if mode=="aprd_edit_name":
            pid=context.user_data.pop("edit_pid",None); context.user_data.pop("mode",None)
            await db.execute("UPDATE products SET name=? WHERE id=?",(text,pid)); await db.commit()
            await update.message.reply_text("✅ ذخیره شد.",reply_markup=main_menu()); return
        if mode=="aprd_edit_price":
            pid=context.user_data.pop("edit_pid",None); context.user_data.pop("mode",None)
            await db.execute("UPDATE products SET price=? WHERE id=?",(text,pid)); await db.commit()
            await update.message.reply_text("✅ ذخیره شد.",reply_markup=main_menu()); return
        if mode=="aprd_edit_desc":
            pid=context.user_data.pop("edit_pid",None); context.user_data.pop("mode",None)
            await db.execute("UPDATE products SET description=? WHERE id=?",(None if text=="." else text,pid)); await db.commit()
            await update.message.reply_text("✅ ذخیره شد.",reply_markup=main_menu()); return
        if mode=="aprd_edit_buy":
            pid=context.user_data.pop("edit_pid",None); context.user_data.pop("mode",None)
            await db.execute("UPDATE products SET buy_url=? WHERE id=?",(None if text=="." else text,pid)); await db.commit()
            await update.message.reply_text("✅ ذخیره شد.",reply_markup=main_menu()); return
        if mode=="aprd_edit_site":
            pid=context.user_data.pop("edit_pid",None); context.user_data.pop("mode",None)
            await db.execute("UPDATE products SET site_url=? WHERE id=?",(None if text=="." else text,pid)); await db.commit()
            await update.message.reply_text("✅ ذخیره شد.",reply_markup=main_menu()); return

        # ── پاسخ ادمین به چت فعال ──
        # اگه ادمین /to_ID بنویسه یا اگه فقط یه چت فعال باشه
        target_uid = None
        if text.startswith("/to_"):
            try: target_uid=int(text.split("_")[1])
            except: pass
        elif len(active_chats)==1:
            target_uid=list(active_chats.keys())[0]
        elif update.message.reply_to_message:
            rt=update.message.reply_to_message.text or ""
            for line in rt.split("\n"):
                if "🆔" in line:
                    try: target_uid=int(line.replace("🆔","").strip()); break
                    except: pass

        if target_uid and target_uid in active_chats:
            ft=f"\n─────────────────\n⏱ {shamsi_now()}" if get_setting("show_datetime_footer") else ""
            try:
                await context.bot.send_message(target_uid,f"📩 پشتیبانی:\n──────────────\n{text}{ft}")
                await update.message.reply_text(f"✅ پیام به کاربر {target_uid} ارسال شد.")
            except Exception as e: logger.error(f"chat reply: {e}"); await update.message.reply_text("❌ ارسال ناموفق.")
            return
        elif update.message.reply_to_message:
            rt=update.message.reply_to_message.text or ""
            if "🆔" in rt:
                for line in rt.split("\n"):
                    if "🆔" in line:
                        try:
                            uid=int(line.replace("🆔","").strip())
                            ft=f"\n─────────────────\n⏱ {shamsi_now()}" if get_setting("show_datetime_footer") else ""
                            await context.bot.send_message(uid,f"📩 پاسخ پشتیبانی:\n──────────────\n{text}{ft}")
                            await update.message.reply_text("✅ پاسخ ارسال شد.")
                        except Exception as e: logger.error(f"reply: {e}"); await update.message.reply_text("❌ ارسال ناموفق.")
                        break
                return

    # ── تیکت کاربر ──
    if mode=="ticket_wait":
        context.user_data.pop("mode",None)
        await db.execute("INSERT INTO tickets (user_id,username,first_name,message,msg_id,status,created_at) VALUES (?,?,?,?,?,?,?)",
            (user.id,user.username or "",user.first_name or "",text,update.message.message_id,"open",gregorian_now()))
        await db.commit()
        try:
            await context.bot.send_message(ADMIN_ID,
                f"📨 تیکت جدید!\n👤 {user.first_name or '—'} | {'@'+user.username if user.username else '—'}\n🆔 {user.id}\n──────────────\n📝 {text}\n──────────────\nبرای پاسخ، reply کنید.")
        except Exception as e: logger.error(f"ticket: {e}")
        await update.message.reply_text("✅ پیام شما ارسال شد!\nپشتیبانی به زودی پاسخ می‌دهد.",reply_markup=main_menu()); return

    # ── منوی کاربر ──
    if text=="🕐 ساعت کاری":
        await record_stat("workhours_page")
        ft=f"\n─────────────────\n⏱ {shamsi_now()}" if get_setting("show_datetime_footer") else ""
        if not workhours.get("enabled",True):
            await update.message.reply_text(f"🕐 ساعت کاری\n──────────────\nساعت کاری تنظیم نشده{ft}",reply_markup=main_menu()); return
        wh=today_workhours_text() or ""
        await update.message.reply_text(f"🕐 ساعت کاری استوک لند\n━━━━━━━━━━━━━━━\n{workhours_full_summary()}\n━━━━━━━━━━━━━━━\n{wh}{ft}",reply_markup=main_menu()); return

    if text=="🛍 محصولات":
        await record_stat("catalog"); cats=await get_categories()
        if not cats: await update.message.reply_text("📭 محصولی موجود نیست.",reply_markup=main_menu()); return
        ft=f"\n─────────────────\n⏱ {shamsi_now()}" if get_setting("show_datetime_footer") else ""
        await update.message.reply_text(f"🛍 کاتالوگ استوک لند\n──────────────\nدسته‌بندی را انتخاب کنید:{ft}",reply_markup=catalog_categories_kb(cats)); return

    if text=="💬 گفتگو با پشتیبانی":
        await record_stat("ticket"); context.user_data["mode"]="ticket_wait"
        await update.message.reply_text("💬 پیام خود را بنویسید:\nپشتیبانی به زودی پاسخ می‌دهد.",reply_markup=admin_cancel_menu()); return

    for k,v in MENU_ITEMS.items():
        if text==v:
            await record_stat(k); content=responses.get(k,"تنظیم نشده")
            full=build_message(v,content,k)
            # بخش پشتیبانی — دکمه چت اضافه میشه
            if k=="4":
                chat_btn=InlineKeyboardMarkup([[InlineKeyboardButton("💬 شروع گفتگو با پشتیبانی",callback_data="start_chat")]])
                sec_kb=user_section_kb(k)
                if sec_kb:
                    rows=chat_btn.inline_keyboard+sec_kb.inline_keyboard
                    kb=InlineKeyboardMarkup(rows)
                else:
                    kb=chat_btn
            else:
                kb=user_section_kb(k)
            await send_with_banner(update.message,full,k,reply_markup=kb); return

    await update.message.reply_text("⚠️ گزینه نامعتبر است.",reply_markup=main_menu())


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user; mode=context.user_data.get("mode")

    if user.id==ADMIN_ID:
        if mode=="banner_upload":
            key=context.user_data.pop("banner_key",None); context.user_data.pop("mode",None)
            if not key: await update.message.reply_text("❌ خطا.",reply_markup=main_menu()); return
            photo=update.message.photo[-1]; get_banner(key)
            banners[key]["file_id"]=photo.file_id; banners[key]["active"]=True; await save_banners()
            await update.message.reply_text(f"✅ بنر «{SECTION_NAMES.get(key,key)}» آپلود شد!",reply_markup=main_menu()); return
        if mode=="broadcast":
            context.user_data.pop("mode",None); photo=update.message.photo[-1]; caption=update.message.caption or ""
            await update.message.reply_text("📤 در حال ارسال...")
            await send_broadcast(context,caption,photo_id=photo.file_id); return
        if mode=="aprd_new_photo":
            cat_id=context.user_data.pop("cat_id",None); name=context.user_data.pop("prd_name","")
            price=context.user_data.pop("prd_price",""); desc=context.user_data.pop("prd_desc",None)
            buy=context.user_data.pop("prd_buy",None); site=context.user_data.pop("prd_site",None)
            context.user_data.pop("mode",None); photo=update.message.photo[-1]
            await db.execute("INSERT INTO products (category_id,name,price,description,photo_id,buy_url,site_url,is_active,created_at) VALUES (?,?,?,?,?,?,?,1,?)",
                (cat_id,name,price,desc,photo.file_id,buy,site,gregorian_now()))
            await db.commit(); await update.message.reply_text(f"✅ محصول «{name}» با عکس اضافه شد.",reply_markup=main_menu()); return
        if mode=="aprd_edit_photo":
            pid=context.user_data.pop("edit_pid",None); context.user_data.pop("mode",None); photo=update.message.photo[-1]
            await db.execute("UPDATE products SET photo_id=? WHERE id=?",(photo.file_id,pid)); await db.commit()
            await update.message.reply_text("✅ عکس ذخیره شد.",reply_markup=main_menu()); return
        # ── reply عکس ادمین به تیکت ──
        if update.message.reply_to_message:
            rt=update.message.reply_to_message.text or ""
            if "🆔" in rt:
                for line in rt.split("\n"):
                    if "🆔" in line:
                        try:
                            uid=int(line.replace("🆔","").strip())
                            await context.bot.send_photo(uid,photo=update.message.photo[-1],caption=f"📩 پاسخ پشتیبانی:\n{update.message.caption or ''}")
                            await update.message.reply_text("✅ پاسخ ارسال شد.")
                        except Exception as e: logger.error(f"reply photo: {e}")
                        break


async def post_init(app):
    await init_db(); await load_data(); await load_banners()
    await load_workhours(); await load_buttons(); await load_settings(); await load_stats()
    logger.info("✅ ربات راه‌اندازی شد")

def main():
    app=ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("admin",admin_cmd))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND,photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler))
    print("🚀 ربات در حال اجراست...")
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    main()
