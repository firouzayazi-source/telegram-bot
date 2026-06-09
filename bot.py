import os, json, time, asyncio, logging, aiosqlite, jdatetime, pytz
from datetime import datetime
from collections import defaultdict, deque
import aiofiles
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                           CallbackQueryHandler, ContextTypes, filters)

os.environ.pop("HTTP_PROXY", None); os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("ALL_PROXY", None); os.environ["NO_PROXY"] = "*"

TOKEN    = os.getenv("BOT_TOKEN", "8792062012:AAGXforSa1IY45AuC-yOHs2PsdzudvtdD44")
ADMIN_ID = int(os.getenv("ADMIN_ID", "638469407"))
DATA_FILE = "data.json"; DB_FILE = "users.db"; BANNER_FILE = "banner.json"
WORKHOURS_FILE = "workhours.json"; BUTTONS_FILE = "buttons.json"
SETTINGS_FILE = "settings.json"; STATS_FILE = "stats.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
IRAN_TZ = pytz.timezone("Asia/Tehran")

# ── زمان ──────────────────────────────────────────
_FA = str.maketrans("0123456789", "\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9")
MONTH_FA = {1:"\u0641\u0631\u0648\u0631\u062f\u06cc\u0646",2:"\u0627\u0631\u062f\u06cc\u0628\u0647\u0634\u062a",3:"\u062e\u0631\u062f\u0627\u062f",
            4:"\u062a\u06cc\u0631",5:"\u0645\u0631\u062f\u0627\u062f",6:"\u0634\u0647\u0631\u06cc\u0648\u0631",7:"\u0645\u0647\u0631",
            8:"\u0622\u0628\u0627\u0646",9:"\u0622\u0630\u0631",10:"\u062f\u06cc",11:"\u0628\u0647\u0645\u0646",12:"\u0627\u0633\u0641\u0646\u062f"}
DAY_FA   = {"0":"\u0634\u0646\u0628\u0647","1":"\u06cc\u06a9\u0634\u0646\u0628\u0647","2":"\u062f\u0648\u0634\u0646\u0628\u0647",
            "3":"\u0633\u0647\u200c\u0634\u0646\u0628\u0647","4":"\u0686\u0647\u0627\u0631\u0634\u0646\u0628\u0647",
            "5":"\u067e\u0646\u062c\u0634\u0646\u0628\u0647","6":"\u062c\u0645\u0639\u0647"}

def to_fa(v): return str(v).translate(_FA)
def fmt_t(t): return to_fa(t)

def shamsi_now():
    now = datetime.now(IRAN_TZ); j = jdatetime.datetime.fromgregorian(datetime=now)
    return f"{to_fa(j.day)} {MONTH_FA[j.month]} {to_fa(j.year)} \u2014 {to_fa(now.strftime('%H:%M'))}"

def gregorian_now(): return datetime.now(IRAN_TZ).strftime("%Y-%m-%d %H:%M:%S")

# ── منو ───────────────────────────────────────────
MENU_ITEMS = {"1":"\U0001f310 \u0634\u0628\u06a9\u0647\u200c\u0647\u0627\u06cc \u0627\u062c\u062a\u0645\u0627\u0639\u06cc",
              "2":"\U0001f310 \u0633\u0627\u06cc\u062a \u0627\u0633\u062a\u0648\u06a9 \u0644\u0646\u062f",
              "3":"\U0001f4b0 \u0634\u0631\u0627\u06cc\u0637 \u0627\u0642\u0633\u0627\u0637",
              "4":"\U0001f4de \u067e\u0634\u062a\u06cc\u0628\u0627\u0646\u06cc",
              "5":"\U0001f4cd \u0622\u062f\u0631\u0633 \u0641\u0631\u0648\u0634\u06af\u0627\u0647"}
SECTION_NAMES = {"welcome":"\U0001f3e0 \u062e\u0648\u0634\u200c\u0622\u0645\u062f\u06af\u0648\u06cc\u06cc",
                 "1":"\U0001f310 \u0634\u0628\u06a9\u0647\u200c\u0647\u0627\u06cc \u0627\u062c\u062a\u0645\u0627\u0639\u06cc",
                 "2":"\U0001f310 \u0633\u0627\u06cc\u062a \u0627\u0633\u062a\u0648\u06a9 \u0644\u0646\u062f",
                 "3":"\U0001f4b0 \u0634\u0631\u0627\u06cc\u0637 \u0627\u0642\u0633\u0627\u0637",
                 "4":"\U0001f4de \u067e\u0634\u062a\u06cc\u0628\u0627\u0646\u06cc",
                 "5":"\U0001f4cd \u0622\u062f\u0631\u0633 \u0641\u0631\u0648\u0634\u06af\u0627\u0647"}

# ── state ─────────────────────────────────────────
responses=None; banners={}; workhours={}; buttons={}; settings={}; stats={}
active_chats={}  # {user_id: True}

DEFAULT_WH = {"enabled":True,"schedule":{
    "0":{"open":True,"shifts":[{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
    "1":{"open":True,"shifts":[{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
    "2":{"open":True,"shifts":[{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
    "3":{"open":True,"shifts":[{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
    "4":{"open":True,"shifts":[{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
    "5":{"open":True,"shifts":[{"from":"11:00","to":"14:00"},{"from":"17:00","to":"23:00"}]},
    "6":{"open":True,"shifts":[{"from":"17:00","to":"23:00"}]}},
    "msg_open":"\u2705 \u0647\u0645\u200c\u0627\u06a9\u0646\u0648\u0646 \u0628\u0627\u0632 \u0627\u0633\u062a",
    "msg_closed":"\U0001f534 \u0647\u0645\u200c\u0627\u06a9\u0646\u0648\u0646 \u0628\u0633\u062a\u0647 \u0627\u0633\u062a"}

# پیش‌فرض همه قابلیت‌ها غیرفعال
DEFAULT_SETTINGS = {"show_workhours_in_sections":False,"show_datetime_footer":False,
                    "show_workhours_menu":False,"show_catalog_menu":False,
                    "notify_new_user":False,"store_open":True}
DEFAULT_SEC_WH = {k:False for k in SECTION_NAMES}

# ── helpers ───────────────────────────────────────
def get_banner(k): banners.setdefault(k,{"file_id":None,"active":False}); return banners[k]
def get_sec_btns(k): buttons.setdefault(k,{"enabled":False,"items":[]}); return buttons[k]
def get_setting(k): return settings.get(k,DEFAULT_SETTINGS.get(k,False))
def get_sec_wh(k):
    if not get_setting("show_workhours_in_sections"): return False
    return settings.get("section_workhours",DEFAULT_SEC_WH).get(k,False)
def set_sec_wh(k,v): settings.setdefault("section_workhours",dict(DEFAULT_SEC_WH))[k]=v

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
    status=workhours.get("msg_open","\u2705 \u0628\u0627\u0632") if opened else workhours.get("msg_closed","\U0001f534 \u0628\u0633\u062a\u0647")
    oi=["\u2600\ufe0f","\U0001f319","\U0001f303","\U0001f56f"]; ci=["\u26ab\ufe0f"]*4
    sl=["\u0634\u06cc\u0641\u062a \u0627\u0648\u0644","\u0634\u06cc\u0641\u062a \u062f\u0648\u0645","\u0634\u06cc\u0641\u062a \u0633\u0648\u0645","\u0634\u06cc\u0641\u062a \u0686\u0647\u0627\u0631\u0645"]
    lines=["\u2501"*15,"\U0001f3ea \u0648\u0636\u0639\u06cc\u062a \u0641\u0631\u0648\u0634\u06af\u0627\u0647",f"\U0001f4c5 \u0627\u0645\u0631\u0648\u0632 {DAY_FA.get(wd,'')}",""]
    if not day.get("open"): lines.append("\u274c \u0627\u0645\u0631\u0648\u0632 \u062a\u0639\u0637\u06cc\u0644 \u0627\u0633\u062a")
    else:
        icons=oi if opened else ci
        for i,s in enumerate(day.get("shifts",[])):
            lines.append(f"{icons[i] if i<len(icons) else '\U0001f550'} {sl[i] if i<len(sl) else ''}   {fmt_t(s['from'])} \u2014 {fmt_t(s['to'])}")
    lines+=["",status,"\u2501"*15]; return "\n".join(lines)

def wh_full_table():
    rows=[]
    for k,name in DAY_FA.items():
        day=workhours.get("schedule",{}).get(k,{})
        if not day.get("open"): rows.append(f"\u274c {name}: \u062a\u0639\u0637\u06cc\u0644")
        else:
            sh=" \u0648 ".join(f"{fmt_t(s['from'])} \u062a\u0627 {fmt_t(s['to'])}" for s in day.get("shifts",[]))
            rows.append(f"\u2705 {name}: {sh}")
    return "\n".join(rows)

def build_msg(title,content,sec_key):
    wh=wh_today_block() if get_sec_wh(sec_key) else None
    ft=f"\u23f1 {shamsi_now()}" if get_setting("show_datetime_footer") else ""
    lines=[f"\U0001f4cc {title}","\u2500"*14,content,"\u2500"*14]
    if wh: lines+=["",wh]
    if ft: lines+=["","\u2500"*17,ft]
    return "\n".join(lines)

def progress_bar(v,t,n=8):
    if t==0: return "\u2591"*n
    f=int(n*v/t); return "\u2593"*f+"\u2591"*(n-f)

# ── stats ─────────────────────────────────────────
async def record_stat(k): stats[k]=stats.get(k,0)+1; await save_stats()

# ── load/save json ────────────────────────────────
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
    responses=await _rj(DATA_FILE,lambda:dict(MENU_ITEMS,welcome="\u2728 \u062e\u0648\u0634 \u0622\u0645\u062f\u06cc\u062f \u0628\u0647 \u0631\u0628\u0627\u062a \u0627\u0633\u062a\u0648\u06a9 \u0644\u0646\u062f"))

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
    for k in SECTION_NAMES: buttons.setdefault(k,{"enabled":False,"items":[]})

async def save_buttons(): await _wj(BUTTONS_FILE,buttons)

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

# ── database ──────────────────────────────────────
db=None

async def init_db():
    global db
    db=await aiosqlite.connect(DB_FILE)
    await db.execute("PRAGMA journal_mode=WAL")
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,username TEXT,first_name TEXT,
            joined_at TEXT,last_seen TEXT,is_blocked INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS categories(
            id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,icon TEXT DEFAULT '\U0001f4e6',
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
        CREATE TABLE IF NOT EXISTS active_chats(
            user_id INTEGER PRIMARY KEY,started_at TEXT);
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

# ── catalog db ────────────────────────────────────
# Schema: id(0),name(1),icon(2),parent_id(3),is_active(4)
async def get_root_cats(active_only=True):
    w="AND is_active=1" if active_only else ""
    async with db.execute(f"SELECT id,name,icon,parent_id,is_active FROM categories WHERE parent_id IS NULL {w} ORDER BY id") as c: return await c.fetchall()

async def get_subcats(parent_id,active_only=True):
    w="AND is_active=1" if active_only else ""
    async with db.execute(f"SELECT id,name,icon,parent_id,is_active FROM categories WHERE parent_id=? {w} ORDER BY id",(parent_id,)) as c: return await c.fetchall()

async def get_cat(cat_id):
    async with db.execute("SELECT id,name,icon,parent_id,is_active FROM categories WHERE id=?",(cat_id,)) as c: return await c.fetchone()

# ── product db ────────────────────────────────────
# Schema: id(0),name(1),price(2),description(3),photo_id(4),site_url(5),is_active(6),category_id(7)
async def get_products(cat_id,active_only=True):
    w="AND is_active=1" if active_only else ""
    async with db.execute(f"SELECT id,name,price,description,photo_id,site_url,is_active,category_id FROM products WHERE category_id=? {w} ORDER BY id",(cat_id,)) as c: return await c.fetchall()

async def get_product(pid):
    async with db.execute("SELECT id,name,price,description,photo_id,site_url,is_active,category_id FROM products WHERE id=?",(pid,)) as c: return await c.fetchone()

async def search_products(q):
    q=f"%{q}%"
    async with db.execute("SELECT id,name,price,description,photo_id,site_url,is_active,category_id FROM products WHERE(name LIKE ? OR description LIKE ?) AND is_active=1 ORDER BY name LIMIT 20",(q,q)) as c: return await c.fetchall()

# ── chat db ───────────────────────────────────────
async def load_active_chats():
    async with db.execute("SELECT user_id FROM active_chats") as c:
        for r in await c.fetchall(): active_chats[r[0]]=True

async def open_chat(uid):
    await db.execute("INSERT OR REPLACE INTO active_chats VALUES(?,?)",(uid,gregorian_now()))
    await db.commit(); active_chats[uid]=True

async def close_chat(uid):
    await db.execute("DELETE FROM active_chats WHERE user_id=?",(uid,))
    await db.commit(); active_chats.pop(uid,None)

# ── requests db ───────────────────────────────────
async def save_request(uid,username,first_name,phone,pid,pname):
    await db.execute("INSERT INTO requests(user_id,username,first_name,phone,product_id,product_name,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (uid,username or"",first_name or"",phone,pid,pname,"new",gregorian_now()))
    await db.commit()

async def get_requests():
    async with db.execute("SELECT id,user_id,username,first_name,phone,product_name,status,created_at FROM requests ORDER BY id DESC LIMIT 30") as c: return await c.fetchall()

async def done_request(rid): await db.execute("UPDATE requests SET status='done' WHERE id=?",(rid,)); await db.commit()

# ── anti-spam ─────────────────────────────────────
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
    keys=list(MENU_ITEMS.keys()); rows=[]
    for i in range(0,len(keys),2):
        row=[MENU_ITEMS[keys[i]]]
        if i+1<len(keys): row.append(MENU_ITEMS[keys[i+1]])
        rows.append(row)
    extra=[]
    if get_setting("show_workhours_menu"): extra.append("\U0001f550 \u0633\u0627\u0639\u062a \u06a9\u0627\u0631\u06cc")
    if get_setting("show_catalog_menu"):   extra.append("\U0001f6cd \u0645\u062d\u0635\u0648\u0644\u0627\u062a")
    if extra: rows.append(extra)
    return ReplyKeyboardMarkup(rows,resize_keyboard=True)

def chat_menu(): return ReplyKeyboardMarkup([["\u274c \u067e\u0627\u06cc\u0627\u0646 \u0686\u062a"]],resize_keyboard=True)
def cancel_menu(): return ReplyKeyboardMarkup([["\u274c \u0644\u063a\u0648 \u0639\u0645\u0644\u06cc\u0627\u062a"]],resize_keyboard=True)

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

def support_kb():
    chat_row=[InlineKeyboardButton("\U0001f4ac \u0634\u0631\u0648\u0639 \u06af\u0641\u062a\u06af\u0648 \u0628\u0627 \u067e\u0634\u062a\u06cc\u0628\u0627\u0646\u06cc",callback_data="start_chat")]
    sec_kb=user_sec_kb("4")
    rows=[chat_row]+(sec_kb.inline_keyboard if sec_kb else [])
    return InlineKeyboardMarkup(rows)

# ── catalog keyboards (user) ──────────────────────
def cat_root_kb(cats):
    btns=[[InlineKeyboardButton(f"{c[2]} {c[1]}",callback_data=f"cr_{c[0]}")] for c in cats]
    btns.append([InlineKeyboardButton("\U0001f50d \u062c\u0633\u062a\u062c\u0648\u06cc \u0645\u062d\u0635\u0648\u0644",callback_data="cat_search")])
    return InlineKeyboardMarkup(btns)

def cat_sub_kb(subs,root_id):
    btns=[[InlineKeyboardButton(f"{s[2]} {s[1]}",callback_data=f"cs_{s[0]}")] for s in subs]
    btns.append([InlineKeyboardButton("\U0001f519 \u0628\u0631\u06af\u0634\u062a",callback_data="cat_back")])
    return InlineKeyboardMarkup(btns)

def cat_products_kb(products,sub_id):
    btns=[[InlineKeyboardButton(f"\U0001f4f1 {p[1]}",callback_data=f"prd_{p[0]}")] for p in products]
    btns.append([InlineKeyboardButton("\U0001f519 \u0628\u0631\u06af\u0634\u062a",callback_data=f"cr_back_{sub_id}")])
    return InlineKeyboardMarkup(btns)

def product_kb(p):
    # p: id(0),name(1),price(2),desc(3),photo(4),url(5),active(6),cat_id(7)
    btns=[]
    if p[5]: btns.append([InlineKeyboardButton("\U0001f310 \u0645\u0634\u0627\u0647\u062f\u0647 / \u062e\u0631\u06cc\u062f \u0627\u0632 \u0633\u0627\u06cc\u062a",url=p[5])])
    btns.append([InlineKeyboardButton("\U0001f4cb \u062f\u0631\u062e\u0648\u0627\u0633\u062a \u062e\u0631\u06cc\u062f",callback_data=f"req_{p[0]}")])
    btns.append([InlineKeyboardButton("\U0001f519 \u0628\u0631\u06af\u0634\u062a",callback_data=f"cs_back_{p[7]}")])
    return InlineKeyboardMarkup(btns)

# ── admin keyboards ───────────────────────────────
def back_admin(): return InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f519 \u0628\u0631\u06af\u0634\u062a \u0628\u0647 \u067e\u0646\u0644",callback_data="back_to_admin")]])

def admin_menu():
    op=is_open(); st="\U0001f7e2" if op else "\U0001f534"
    tg="\U0001f534 \u0628\u0633\u062a\u0646 \u0641\u0631\u0648\u0634\u06af\u0627\u0647" if op else "\U0001f7e2 \u0628\u0627\u0632 \u06a9\u0631\u062f\u0646"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f4ca \u062f\u0627\u0634\u0628\u0648\u0631\u062f",callback_data="dash"),
         InlineKeyboardButton("\U0001f465 \u06a9\u0627\u0631\u0628\u0631\u0627\u0646",callback_data="users_menu")],
        [InlineKeyboardButton("\U0001f4cb \u0645\u062f\u06cc\u0631\u06cc\u062a \u0628\u062e\u0634\u200c\u0647\u0627",callback_data="sections")],
        [InlineKeyboardButton("\U0001f6cd \u06a9\u0627\u062a\u0627\u0644\u0648\u06af",callback_data="admin_catalog"),
         InlineKeyboardButton("\U0001f4e8 \u062f\u0631\u062e\u0648\u0627\u0633\u062a\u200c\u0647\u0627",callback_data="admin_reqs")],
        [InlineKeyboardButton("\U0001f4ac \u0686\u062a\u200c\u0647\u0627\u06cc \u0641\u0639\u0627\u0644",callback_data="chats_list")],
        [InlineKeyboardButton("\U0001f550 \u0633\u0627\u0639\u062a \u06a9\u0627\u0631\u06cc",callback_data="wh_menu"),
         InlineKeyboardButton("\u2699\ufe0f \u062a\u0646\u0638\u06cc\u0645\u0627\u062a",callback_data="settings_menu")],
        [InlineKeyboardButton("\U0001f4e2 \u067e\u062e\u0634 \u0647\u0645\u06af\u0627\u0646\u06cc",callback_data="broadcast"),
         InlineKeyboardButton("\U0001f4be \u0628\u06a9\u200c\u0622\u067e",callback_data="backup")],
        [InlineKeyboardButton(f"{st} {tg}",callback_data="quick_toggle")],
    ])

def sections_kb():
    btns=[]
    for key,name in SECTION_NAMES.items():
        cont=responses.get(key,"") if responses else ""
        b=get_banner(key); sec=get_sec_btns(key)
        ti="\u2705" if cont and cont not in("\u062a\u0646\u0638\u06cc\u0645 \u0646\u0634\u062f\u0647","") else "\u2795"
        bi="\U0001f5bc" if b.get("active") and b.get("file_id") else "\u25cb"
        si=f"\U0001f518{len(sec.get('items',[]))}" if sec.get("enabled") else "\u25cb"
        btns.append([InlineKeyboardButton(f"{name}  {ti}{bi}{si}",callback_data=f"sec_{key}")])
    btns.append([InlineKeyboardButton("\U0001f519 \u0628\u0631\u06af\u0634\u062a",callback_data="back_to_admin")])
    return InlineKeyboardMarkup(btns)

def section_kb(key):
    b=get_banner(key); sec=get_sec_btns(key); wh=get_sec_wh(key)
    bs="\U0001f5bc\u2705" if b.get("active") and b.get("file_id") else("\U0001f5bc\u23f8" if b.get("file_id") else"\U0001f5bc\u2795")
    bn=f"\U0001f518\u2705({len(sec.get('items',[]))})" if sec.get("enabled") else f"\U0001f518\u274c({len(sec.get('items',[]))})"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\u270f\ufe0f \u0648\u06cc\u0631\u0627\u06cc\u0634 \u0645\u062a\u0646",callback_data=f"sec_text_{key}")],
        [InlineKeyboardButton(f"{bs} \u0628\u0646\u0631",callback_data=f"sec_ban_{key}")],
        [InlineKeyboardButton(f"{bn} \u062f\u06a9\u0645\u0647\u200c\u0647\u0627",callback_data=f"sec_btns_{key}")],
        [InlineKeyboardButton(f"\U0001f550{'\u2705' if wh else '\u274c'} \u0633\u0627\u0639\u062a \u06a9\u0627\u0631\u06cc",callback_data=f"sec_wh_{key}")],
        [InlineKeyboardButton("\U0001f519 \u0628\u0631\u06af\u0634\u062a",callback_data="sections")],
    ])

def banner_kb(key):
    b=get_banner(key); tg="\U0001f534 \u063a\u06cc\u0631\u0641\u0639\u0627\u0644" if b.get("active") else "\U0001f7e2 \u0641\u0639\u0627\u0644"
    btns=[[InlineKeyboardButton("\U0001f4e4 \u0622\u067e\u0644\u0648\u062f",callback_data=f"ban_up_{key}")],
          [InlineKeyboardButton(tg,callback_data=f"ban_tg_{key}")]]
    if b.get("file_id"): btns.append([InlineKeyboardButton("\U0001f5d1 \u062d\u0630\u0641",callback_data=f"ban_dl_{key}")])
    btns.append([InlineKeyboardButton("\U0001f519",callback_data=f"sec_{key}")]); return InlineKeyboardMarkup(btns)

def sec_btns_kb(key):
    sec=get_sec_btns(key); tg="\U0001f534 \u063a\u06cc\u0631\u0641\u0639\u0627\u0644" if sec.get("enabled") else "\U0001f7e2 \u0641\u0639\u0627\u0644"
    btns=[[InlineKeyboardButton(tg,callback_data=f"btn_tg_{key}")]]
    for it in sec.get("items",[]):
        btns.append([InlineKeyboardButton(f"\U0001f517 {it['title']}",callback_data=f"btn_ed_{key}_{it['id']}"),
                     InlineKeyboardButton("\U0001f5d1",callback_data=f"btn_dl_{key}_{it['id']}")])
    btns.append([InlineKeyboardButton("\u2795 \u062f\u06a9\u0645\u0647 \u062c\u062f\u06cc\u062f",callback_data=f"btn_add_{key}"),
                 InlineKeyboardButton("\U0001f519",callback_data=f"sec_{key}")])
    return InlineKeyboardMarkup(btns)

def wh_kb():
    en=workhours.get("enabled",True)
    btns=[[InlineKeyboardButton("\U0001f534 \u063a\u06cc\u0631\u0641\u0639\u0627\u0644" if en else "\U0001f7e2 \u0641\u0639\u0627\u0644",callback_data="wh_toggle")]]
    for k,name in DAY_FA.items():
        day=workhours.get("schedule",{}).get(k,{})
        btns.append([InlineKeyboardButton(f"{'\u2705' if day.get('open') else '\u274c'} {name}",callback_data=f"wh_day_{k}")])
    btns+=[[InlineKeyboardButton("\u270f\ufe0f \u067e\u06cc\u0627\u0645 \u0628\u0627\u0632",callback_data="wh_mop")],
           [InlineKeyboardButton("\u270f\ufe0f \u067e\u06cc\u0627\u0645 \u0628\u0633\u062a\u0647",callback_data="wh_mcl")],
           [InlineKeyboardButton("\U0001f519",callback_data="back_to_admin")]]
    return InlineKeyboardMarkup(btns)

def wh_day_kb(dk):
    day=workhours.get("schedule",{}).get(dk,{})
    tg="\U0001f534 \u062a\u0639\u0637\u06cc\u0644" if day.get("open") else "\U0001f7e2 \u0628\u0627\u0632 \u06a9\u0631\u062f\u0646"
    return InlineKeyboardMarkup([[InlineKeyboardButton(tg,callback_data=f"wh_dtg_{dk}")],
        [InlineKeyboardButton("\u270f\ufe0f \u0633\u0627\u0639\u062a\u200c\u0647\u0627",callback_data=f"wh_sh_{dk}")],
        [InlineKeyboardButton("\U0001f519",callback_data="wh_menu")]])

def settings_kb():
    def t(k): return"\u2705" if get_setting(k) else"\u274c"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{t('show_workhours_in_sections')} \u0633\u0627\u0639\u062a \u06a9\u0627\u0631\u06cc \u062f\u0631 \u0628\u062e\u0634\u200c\u0647\u0627",callback_data="stg_show_workhours_in_sections")],
        [InlineKeyboardButton(f"{t('show_datetime_footer')} \u062a\u0627\u0631\u06cc\u062e \u0648 \u0633\u0627\u0639\u062a \u067e\u0627\u06cc\u06cc\u0646",callback_data="stg_show_datetime_footer")],
        [InlineKeyboardButton(f"{t('show_workhours_menu')} \u0633\u0627\u0639\u062a \u06a9\u0627\u0631\u06cc \u062f\u0631 \u0645\u0646\u0648",callback_data="stg_show_workhours_menu")],
        [InlineKeyboardButton(f"{t('show_catalog_menu')} \u0645\u062d\u0635\u0648\u0644\u0627\u062a \u062f\u0631 \u0645\u0646\u0648",callback_data="stg_show_catalog_menu")],
        [InlineKeyboardButton(f"{t('notify_new_user')} \u0627\u0639\u0644\u0627\u0646 \u0639\u0636\u0648 \u062c\u062f\u06cc\u062f",callback_data="stg_notify_new_user")],
        [InlineKeyboardButton("\U0001f519",callback_data="back_to_admin")],
    ])

def users_menu_kb(): return InlineKeyboardMarkup([
    [InlineKeyboardButton("\U0001f465 \u0647\u0645\u0647",callback_data="ul_all_0"),InlineKeyboardButton("\U0001f4c5 \u0627\u0645\u0631\u0648\u0632",callback_data="ul_today_0")],
    [InlineKeyboardButton("\U0001f4c6 \u0647\u0641\u062a\u0647",callback_data="ul_week_0"),InlineKeyboardButton("\U0001f6ab \u0628\u0644\u0627\u06a9",callback_data="ul_blocked_0")],
    [InlineKeyboardButton("\U0001f50d \u062c\u0633\u062a\u062c\u0648",callback_data="users_search")],
    [InlineKeyboardButton("\U0001f519",callback_data="back_to_admin")]])

def users_list_kb(rows,off,ft,total):
    btns=[[InlineKeyboardButton(f"{'\U0001f6ab ' if r[4] else ''}{r[1] or '\u2014'} | {r[0]}",callback_data=f"uv_{r[0]}")] for r in rows]
    nav=[]
    if off>0: nav.append(InlineKeyboardButton("\u25c0\ufe0f",callback_data=f"ul_{ft}_{off-15}"))
    if off+15<total: nav.append(InlineKeyboardButton("\u25b6\ufe0f",callback_data=f"ul_{ft}_{off+15}"))
    if nav: btns.append(nav)
    btns.append([InlineKeyboardButton("\U0001f519",callback_data="users_menu")]); return InlineKeyboardMarkup(btns)

def udetail_kb(uid,is_bl): return InlineKeyboardMarkup([
    [InlineKeyboardButton("\u2705 \u0631\u0641\u0639 \u0628\u0644\u0627\u06a9" if is_bl else "\U0001f6ab \u0628\u0644\u0627\u06a9",callback_data=f"utog_{uid}")],
    [InlineKeyboardButton("\U0001f519",callback_data="users_menu")]])

# ── catalog admin keyboards ───────────────────────
def acat_root_kb(roots):
    btns=[[InlineKeyboardButton(f"{'\u2705' if c[4] else '\u274c'} {c[2]} {c[1]}",callback_data=f"acr_{c[0]}")] for c in roots]
    btns.append([InlineKeyboardButton("\u2795 \u062f\u0633\u062a\u0647 \u0627\u0635\u0644\u06cc \u062c\u062f\u06cc\u062f",callback_data="acr_new")])
    btns.append([InlineKeyboardButton("\U0001f519",callback_data="back_to_admin")]); return InlineKeyboardMarkup(btns)

def acat_sub_kb(root_id,subs):
    btns=[[InlineKeyboardButton(f"{'\u2705' if s[4] else '\u274c'} {s[2]} {s[1]}",callback_data=f"acs_{s[0]}")] for s in subs]
    btns.append([InlineKeyboardButton("\u2795 \u0632\u06cc\u0631\u062f\u0633\u062a\u0647 \u062c\u062f\u06cc\u062f",callback_data=f"acs_new_{root_id}")])
    btns.append([InlineKeyboardButton("\u270f\ufe0f \u0646\u0627\u0645",callback_data=f"acr_ed_{root_id}"),
                 InlineKeyboardButton("\U0001f5d1 \u062d\u0630\u0641",callback_data=f"acr_dl_{root_id}")])
    btns.append([InlineKeyboardButton("\U0001f519",callback_data="admin_catalog")]); return InlineKeyboardMarkup(btns)

def acat_products_kb(sub_id,products,root_id):
    btns=[[InlineKeyboardButton(f"{'\u2705' if p[6] else '\u274c'} \U0001f4f1 {p[1]}",callback_data=f"aprd_{p[0]}")] for p in products]
    btns.append([InlineKeyboardButton("\u2795 \u0645\u062d\u0635\u0648\u0644 \u062c\u062f\u06cc\u062f",callback_data=f"aprd_new_{sub_id}")])
    btns.append([InlineKeyboardButton("\u270f\ufe0f \u0646\u0627\u0645",callback_data=f"acs_ed_{sub_id}"),
                 InlineKeyboardButton("\U0001f5d1 \u062d\u0630\u0641",callback_data=f"acs_dl_{sub_id}")])
    btns.append([InlineKeyboardButton("\U0001f519",callback_data=f"acr_{root_id}")]); return InlineKeyboardMarkup(btns)

def aprd_kb(pid,sub_id,is_active):
    tg="\U0001f534 \u063a\u06cc\u0631\u0641\u0639\u0627\u0644" if is_active else "\U0001f7e2 \u0641\u0639\u0627\u0644"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\u270f\ufe0f \u0646\u0627\u0645",callback_data=f"aprd_en_{pid}"),
         InlineKeyboardButton("\U0001f4b0 \u0642\u06cc\u0645\u062a",callback_data=f"aprd_ep_{pid}")],
        [InlineKeyboardButton("\U0001f4dd \u062a\u0648\u0636\u06cc\u062d",callback_data=f"aprd_ed_{pid}"),
         InlineKeyboardButton("\U0001f4f8 \u0639\u06a9\u0633",callback_data=f"aprd_ei_{pid}")],
        [InlineKeyboardButton("\U0001f310 \u0644\u06cc\u0646\u06a9 \u0645\u062d\u0635\u0648\u0644",callback_data=f"aprd_eu_{pid}")],
        [InlineKeyboardButton(tg,callback_data=f"aprd_etg_{pid}")],
        [InlineKeyboardButton("\U0001f5d1 \u062d\u0630\u0641",callback_data=f"aprd_del_{pid}")],
        [InlineKeyboardButton("\U0001f519",callback_data=f"acs_{sub_id}")]])

# ── requests & chats admin keyboards ─────────────
def reqs_kb(reqs):
    btns=[[InlineKeyboardButton(f"{'\U0001f195' if r[6]=='new' else '\u2705'} {r[5]} \u2014 {r[3]}",callback_data=f"rq_{r[0]}")] for r in reqs]
    btns.append([InlineKeyboardButton("\U0001f519",callback_data="back_to_admin")]); return InlineKeyboardMarkup(btns)

def req_kb(rid,status):
    btns=[]
    if status=="new": btns.append([InlineKeyboardButton("\u2705 \u067e\u06cc\u06af\u06cc\u0631\u06cc \u0634\u062f",callback_data=f"rq_done_{rid}")])
    btns.append([InlineKeyboardButton("\U0001f519",callback_data="admin_reqs")]); return InlineKeyboardMarkup(btns)

async def chats_kb():
    btns=[]
    if active_chats:
        ids=list(active_chats.keys())
        ph=",".join("?"*len(ids))
        async with db.execute(f"SELECT user_id,first_name,username FROM users WHERE user_id IN({ph})",ids) as c:
            info={r[0]:(r[1],r[2]) for r in await c.fetchall()}
        for uid in ids:
            fn,un=info.get(uid,("",""))
            label=f"\U0001f4ac {fn or '\u2014'} {'@'+un if un else str(uid)}"
            btns.append([InlineKeyboardButton(label,callback_data=f"chat_sel_{uid}")])
    btns.append([InlineKeyboardButton("\U0001f519",callback_data="back_to_admin")]); return InlineKeyboardMarkup(btns)

def chat_admin_kb(uid,name):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"\U0001f51a \u067e\u0627\u06cc\u0627\u0646 \u0686\u062a \u0628\u0627 {name}",callback_data=f"chat_end_{uid}")],
        [InlineKeyboardButton("\U0001f6ab \u0628\u0644\u0627\u06a9 \u06a9\u0627\u0631\u0628\u0631",callback_data=f"chat_block_{uid}")],
        [InlineKeyboardButton("\U0001f519",callback_data="chats_list")]])

# ════════════════════════════════════════════════
#  SEND WITH BANNER
# ════════════════════════════════════════════════
async def send_banner(msg,text,key,kb=None):
    b=get_banner(key)
    if b.get("active") and b.get("file_id"):
        try: await msg.reply_photo(photo=b["file_id"],caption=text,reply_markup=kb); return
        except Exception as e: logger.error(f"banner[{key}]: {e}")
    await msg.reply_text(text,reply_markup=kb)

# ════════════════════════════════════════════════
#  BROADCAST
# ════════════════════════════════════════════════
async def broadcast(ctx,text,photo=None):
    users=await get_all_uids(); total=len(users); ok=fail=0
    st=await ctx.bot.send_message(ADMIN_ID,f"\U0001f4e2 \u0634\u0631\u0648\u0639 \u067e\u062e\u0634 \u0628\u0647 {to_fa(total)} \u06a9\u0627\u0631\u0628\u0631...")
    for i,uid in enumerate(users,1):
        try:
            if photo: await ctx.bot.send_photo(uid,photo=photo,caption=text)
            else: await ctx.bot.send_message(uid,text)
            ok+=1
        except: fail+=1
        if i%10==0 or i==total:
            try: await st.edit_text(f"\U0001f4e2 {to_fa(ok)}\u2714\ufe0f {to_fa(fail)}\u274c {to_fa(i)}/{to_fa(total)}")
            except: pass
        await asyncio.sleep(0.2)
    await st.edit_text(f"\u2705 \u067e\u062e\u0634 \u062a\u0645\u0627\u0645 \u0634\u062f!\n\u0645\u0648\u0641\u0642: {to_fa(ok)} | \u0634\u06a9\u0633\u062a: {to_fa(fail)}")

# ════════════════════════════════════════════════
#  BACKUP
# ════════════════════════════════════════════════
async def send_backup(bot):
    ts=shamsi_now().replace(" ","_").replace("\u2014","-").replace(":","-")
    await bot.send_message(ADMIN_ID,f"\U0001f4be \u0628\u06a9\u200c\u0622\u067e \u2014 {shamsi_now()}")
    for fp,lb in[(DATA_FILE,"data"),(BANNER_FILE,"ban"),(WORKHOURS_FILE,"wh"),(BUTTONS_FILE,"btn"),(SETTINGS_FILE,"cfg"),(STATS_FILE,"stats"),(DB_FILE,"db")]:
        try:
            async with aiofiles.open(fp,"rb") as f: content=await f.read()
            await bot.send_document(ADMIN_ID,document=content,filename=f"bkp_{lb}_{ts}.{fp.split('.')[-1]}")
        except Exception as e: logger.error(f"backup {fp}: {e}")

# ════════════════════════════════════════════════
#  HANDLERS
# ════════════════════════════════════════════════
async def cmd_start(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    is_new=False
    async with db.execute("SELECT user_id FROM users WHERE user_id=?",(user.id,)) as c: is_new=(await c.fetchone()) is None
    await save_user(user)
    if get_setting("notify_new_user") and is_new:
        try: await ctx.bot.send_message(ADMIN_ID,f"\U0001f195 \u06a9\u0627\u0631\u0628\u0631 \u062c\u062f\u06cc\u062f!\n\U0001f464 {user.first_name or'\u2014'}\n{'@'+user.username if user.username else'\u2014'}\n\U0001f194 {user.id}")
        except: pass
    wt=responses.get("welcome","\u2728 \u062e\u0648\u0634 \u0622\u0645\u062f\u06cc\u062f")
    full=build_msg("\u062e\u0648\u0634\u200c\u0622\u0645\u062f\u06af\u0648\u06cc\u06cc",wt,"welcome")
    kb=user_sec_kb("welcome")
    await send_banner(update.message,full,"welcome",kb=kb or main_menu())

async def cmd_admin(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID: return await update.message.reply_text("\u26d4 \u062f\u0633\u062a\u0631\u0633\u06cc \u0646\u062f\u0627\u0631\u06cc\u062f")
    await update.message.reply_text("\U0001f451 \u067e\u0646\u0644 \u0645\u062f\u06cc\u0631\u06cc\u062a",reply_markup=admin_menu())

# ════════════════════════════════════════════════
#  USER CALLBACKS
# ════════════════════════════════════════════════
async def user_cb(query,ctx):
    data=query.data; user=query.from_user

    # ── چت ──
    if data=="start_chat":
        if active_chats.get(user.id):
            await query.message.reply_text("\U0001f4ac \u0686\u062a \u0641\u0639\u0627\u0644 \u0627\u0633\u062a.\n\u067e\u06cc\u0627\u0645 \u0628\u0641\u0631\u0633\u062a\u06cc\u062f \u06cc\u0627 \u062f\u06a9\u0645\u0647 \u067e\u0627\u06cc\u0627\u0646 \u0631\u0627 \u0628\u0632\u0646\u06cc\u062f:",reply_markup=chat_menu()); return
        try: await open_chat(user.id)
        except Exception as e:
            logger.error(f"open_chat uid={user.id}: {e}")
            await query.message.reply_text("\u274c \u062e\u0637\u0627 \u062f\u0631 \u0634\u0631\u0648\u0639 \u0686\u062a. \u062f\u0648\u0628\u0627\u0631\u0647 \u0627\u0645\u062a\u062d\u0627\u0646 \u06a9\u0646\u06cc\u062f."); return
        name=user.first_name or"\u2014"; uname=f"@{user.username}" if user.username else str(user.id)
        try:
            await ctx.bot.send_message(ADMIN_ID,
                f"\U0001f7e2 \u0686\u062a \u062c\u062f\u06cc\u062f!\n\U0001f464 {name} | {uname}\n\U0001f194 {user.id}\n\u2500"*14+"\n\u0628\u0631\u0627\u06cc \u067e\u0627\u0633\u062e \u0627\u0632 \u067e\u0646\u0644 > \u0686\u062a\u200c\u0647\u0627\u06cc \u0641\u0639\u0627\u0644 \u0627\u0646\u062a\u062e\u0627\u0628 \u06a9\u0646\u06cc\u062f.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"\U0001f4ac \u067e\u0627\u0633\u062e \u0628\u0647 {name}",callback_data=f"chat_sel_{user.id}")]]))
        except Exception as e: logger.error(f"chat notify: {e}")
        await query.message.reply_text(f"\U0001f4ac \u0686\u062a \u0634\u0631\u0648\u0639 \u0634\u062f!\n\u067e\u06cc\u0627\u0645 \u062e\u0648\u062f \u0631\u0627 \u0628\u0646\u0648\u06cc\u0633\u06cc\u062f:",reply_markup=chat_menu()); return

    # ── کاتالوگ root ──
    if data=="cat_back":
        cats=await get_root_cats()
        if not cats: await query.message.edit_text("\U0001f4ed \u0645\u062d\u0635\u0648\u0644\u06cc \u0645\u0648\u062c\u0648\u062f \u0646\u06cc\u0633\u062a."); return
        await query.message.edit_text("\U0001f6cd \u06a9\u0627\u062a\u0627\u0644\u0648\u06af \u0627\u0633\u062a\u0648\u06a9 \u0644\u0646\u062f\n\u062f\u0633\u062a\u0647\u200c\u0628\u0646\u062f\u06cc \u0631\u0627 \u0627\u0646\u062a\u062e\u0627\u0628 \u06a9\u0646\u06cc\u062f:",reply_markup=cat_root_kb(cats)); return

    if data=="cat_search":
        ctx.user_data["mode"]="cat_search"
        await query.message.reply_text("\U0001f50d \u0646\u0627\u0645 \u06cc\u0627 \u0645\u062f\u0644 \u0645\u062d\u0635\u0648\u0644 \u0631\u0627 \u0628\u0646\u0648\u06cc\u0633\u06cc\u062f:",reply_markup=cancel_menu()); return

    # ── root category ──
    if data.startswith("cr_back_"):
        sub_id=int(data[8:]); sub=await get_cat(sub_id)
        if not sub: return
        root=await get_cat(sub[3])
        subs=await get_subcats(sub[3])
        await query.message.edit_text(f"\U0001f4c1 {root[2] if root else ''} {root[1] if root else ''}",reply_markup=cat_sub_kb(sub[3],subs)); return

    if data.startswith("cr_"):
        root_id=int(data[3:]); root=await get_cat(root_id)
        if not root: return
        subs=await get_subcats(root_id)
        if not subs:
            await query.message.edit_text(f"\U0001f4c1 {root[2]} {root[1]}\n\U0001f4ed \u0632\u06cc\u0631\u062f\u0633\u062a\u0647\u200c\u0627\u06cc \u0645\u0648\u062c\u0648\u062f \u0646\u06cc\u0633\u062a.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f519",callback_data="cat_back")]])); return
        await query.message.edit_text(f"\U0001f4c1 {root[2]} {root[1]}\n\u0632\u06cc\u0631\u062f\u0633\u062a\u0647 \u0631\u0627 \u0627\u0646\u062a\u062e\u0627\u0628 \u06a9\u0646\u06cc\u062f:",reply_markup=cat_sub_kb(subs,root_id)); return

    # ── sub category ──
    if data.startswith("cs_back_"):
        sub_id=int(data[8:]); sub=await get_cat(sub_id)
        if not sub: return
        root=await get_cat(sub[3])
        products=await get_products(sub_id)
        title=f"\U0001f4e6 {sub[2]} {sub[1]}"
        if not products:
            await query.message.edit_text(f"{title}\n\U0001f4ed \u0645\u062d\u0635\u0648\u0644\u06cc \u0645\u0648\u062c\u0648\u062f \u0646\u06cc\u0633\u062a.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f519",callback_data=f"cr_{sub[3]}")]])); return
        await query.message.edit_text(f"{title}\n{to_fa(len(products))} \u0645\u062d\u0635\u0648\u0644:",reply_markup=cat_products_kb(products,sub_id)); return

    if data.startswith("cs_"):
        sub_id=int(data[3:]); sub=await get_cat(sub_id)
        if not sub: return
        products=await get_products(sub_id)
        title=f"\U0001f4e6 {sub[2]} {sub[1]}"
        if not products:
            await query.message.edit_text(f"{title}\n\U0001f4ed \u0645\u062d\u0635\u0648\u0644\u06cc \u0645\u0648\u062c\u0648\u062f \u0646\u06cc\u0633\u062a.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f519",callback_data=f"cr_{sub[3]}")]])); return
        await query.message.edit_text(f"{title}\n{to_fa(len(products))} \u0645\u062d\u0635\u0648\u0644:",reply_markup=cat_products_kb(products,sub_id)); return

    # ── product ──
    if data.startswith("prd_"):
        pid=int(data[4:]); p=await get_product(pid)
        if not p: return
        await record_stat(f"prd_{pid}")
        ft=f"\n\u2500"*17+f"\n\u23f1 {shamsi_now()}" if get_setting("show_datetime_footer") else ""
        text=f"\U0001f4f1 {p[1]}\n\U0001f4b0 \u0642\u06cc\u0645\u062a: {p[2]}"
        if p[3]: text+=f"\n\n\U0001f4dd {p[3]}"
        text+=ft; kb=product_kb(p)
        if p[4]:
            try:
                await query.message.reply_photo(photo=p[4],caption=text,reply_markup=kb)
                return
            except Exception as e:
                logger.error(f"prd photo {pid}: {e}")
        await query.message.reply_text(text,reply_markup=kb); return

    # ── درخواست خرید ──
    if data.startswith("req_"):
        pid=int(data[4:]); p=await get_product(pid)
        if not p: return
        ctx.user_data.update({"mode":"req_phone","req_pid":pid,"req_name":p[1]})
        await query.message.reply_text(f"\U0001f4cb \u062f\u0631\u062e\u0648\u0627\u0633\u062a \u062e\u0631\u06cc\u062f: {p[1]}\n\n\u0634\u0645\u0627\u0631\u0647 \u062a\u0645\u0627\u0633 \u062e\u0648\u062f \u0631\u0627 \u0648\u0627\u0631\u062f \u06a9\u0646\u06cc\u062f:",reply_markup=cancel_menu()); return

# ════════════════════════════════════════════════
#  MAIN CALLBACK DISPATCHER
# ════════════════════════════════════════════════
async def callbacks(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    query=update.callback_query; await query.answer()
    data=query.data; uid=query.from_user.id

    if uid!=ADMIN_ID:
        try: await user_cb(query,ctx)
        except Exception as e:
            logger.error(f"user_cb uid={uid} data={data}: {e}",exc_info=True)
            try: await query.message.reply_text("\u274c \u062e\u0637\u0627. \u062f\u0648\u0628\u0627\u0631\u0647 \u0627\u0645\u062a\u062d\u0627\u0646 \u06a9\u0646\u06cc\u062f.")
            except: pass
        return

    # ════ ADMIN ════
    if data=="back_to_admin": await query.message.edit_text("\U0001f451 \u067e\u0646\u0644 \u0645\u062f\u06cc\u0631\u06cc\u062a",reply_markup=admin_menu())
    elif data=="quick_toggle":
        settings["store_open"]=not get_setting("store_open"); await save_settings()
        await query.answer("\U0001f7e2 \u0628\u0627\u0632 \u0634\u062f" if settings["store_open"] else"\U0001f534 \u0628\u0633\u062a\u0647 \u0634\u062f",show_alert=True)
        await query.message.edit_text("\U0001f451 \u067e\u0646\u0644 \u0645\u062f\u06cc\u0631\u06cc\u062a",reply_markup=admin_menu())
    elif data=="dash":
        t,d,w,m,nt,bl=(await total_users(),await today_users(),await week_users(),await month_users(),await new_today(),await blk_count())
        wh=wh_today_block() or""
        await query.message.edit_text(
            f"\U0001f4ca \u062f\u0627\u0634\u0628\u0648\u0631\u062f \u2014 {shamsi_now()}\n\u2550"*14+f"\n\U0001f465 \u06a9\u0644: {to_fa(t)}  |  \U0001f6ab \u0628\u0644\u0627\u06a9: {to_fa(bl)}\n\u2550"*14+
            f"\n\U0001f195 \u0639\u0636\u0648 \u0627\u0645\u0631\u0648\u0632: {to_fa(nt)}\n\U0001f4c5 \u0641\u0639\u0627\u0644 \u0627\u0645\u0631\u0648\u0632: {to_fa(d)}  {progress_bar(d,t)}\n\U0001f4c6 \u0641\u0639\u0627\u0644 \u0647\u0641\u062a\u0647: {to_fa(w)}  {progress_bar(w,t)}\n\U0001f5d3 \u0641\u0639\u0627\u0644 \u0645\u0627\u0647: {to_fa(m)}  {progress_bar(m,t)}\n\U0001f4ac \u0686\u062a \u0641\u0639\u0627\u0644: {to_fa(len(active_chats))}\n\u2550"*14+f"\n\U0001f3ea {'\U0001f7e2 \u0628\u0627\u0632' if is_open() else '\U0001f534 \u0628\u0633\u062a\u0647'}\n{wh}",
            reply_markup=admin_menu())
    elif data=="broadcast":
        ctx.user_data["mode"]="broadcast"
        await query.message.reply_text("\U0001f4e2 \u067e\u06cc\u0627\u0645 \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f:",reply_markup=cancel_menu())
    elif data=="backup":
        await query.message.edit_text("\U0001f4be \u0627\u0631\u0633\u0627\u0644...",reply_markup=back_admin())
        await send_backup(query.message._bot)
        await query.message.edit_text("\u2705 \u0628\u06a9\u200c\u0622\u067e \u0627\u0631\u0633\u0627\u0644 \u0634\u062f.",reply_markup=back_admin())

    # ── sections ──
    elif data=="sections": await query.message.edit_text("\U0001f4cb \u0645\u062f\u06cc\u0631\u06cc\u062a \u0628\u062e\u0634\u200c\u0647\u0627:",reply_markup=sections_kb())
    elif data.startswith("sec_") and not any(data.startswith(p) for p in["sec_text_","sec_ban_","sec_btns_","sec_wh_"]):
        key=data[4:]
        from telegram.error import BadRequest
        try: await query.message.edit_text(f"\U0001f4cb \u0628\u062e\u0634: {SECTION_NAMES.get(key,key)}\n\u2500"*14+f"\n\u270f\ufe0f \u0645\u062a\u0646: {'\u2705' if responses.get(key,'') not in('','\u062a\u0646\u0638\u06cc\u0645 \u0646\u0634\u062f\u0647') else '\u274c'}\n\U0001f5bc \u0628\u0646\u0631: {'\u2705 \u0641\u0639\u0627\u0644' if get_banner(key).get('active') and get_banner(key).get('file_id') else '\u274c'}\n\U0001f518 \u062f\u06a9\u0645\u0647: {len(get_sec_btns(key).get('items',[]))} {'\u2705' if get_sec_btns(key).get('enabled') else '\u274c'}",reply_markup=section_kb(key))
        except BadRequest: await query.message.reply_text(f"\U0001f4cb {SECTION_NAMES.get(key,key)}",reply_markup=section_kb(key))
    elif data.startswith("sec_text_"):
        key=data[9:]; ctx.user_data.update({"mode":"edit_text","edit_key":key})
        await query.message.reply_text(f"\u270f\ufe0f \u0645\u062a\u0646 \u0641\u0639\u0644\u06cc:\n\n{responses.get(key,'\u062a\u0646\u0638\u06cc\u0645 \u0646\u0634\u062f\u0647')}\n\n\u0645\u062a\u0646 \u062c\u062f\u06cc\u062f:",reply_markup=cancel_menu())
    elif data.startswith("sec_wh_"):
        key=data[7:]; set_sec_wh(key,not get_sec_wh(key)); await save_settings()
        await query.answer("\u2705",show_alert=True)
    elif data.startswith("sec_ban_"):
        key=data[8:]; b=get_banner(key)
        await query.message.edit_text(f"\U0001f5bc \u0628\u0646\u0631: {SECTION_NAMES.get(key,key)}\n{'\u2705 \u0622\u067e\u0644\u0648\u062f \u0634\u062f\u0647' if b.get('file_id') else '\u274c \u0646\u062f\u0627\u0631\u062f'} | {'\u2705 \u0641\u0639\u0627\u0644' if b.get('active') else '\u274c \u063a\u06cc\u0631\u0641\u0639\u0627\u0644'}",reply_markup=banner_kb(key))
    elif data.startswith("ban_up_"):
        key=data[7:]; ctx.user_data.update({"mode":"ban_up","ban_key":key})
        await query.message.reply_text(f"\U0001f4e4 \u0639\u06a9\u0633 \u0628\u0646\u0631 \u00ab{SECTION_NAMES.get(key,key)}\u00bb \u0631\u0627 \u0627\u0631\u0633\u0627\u0644 \u06a9\u0646\u06cc\u062f:",reply_markup=cancel_menu())
    elif data.startswith("ban_tg_"):
        key=data[7:]; b=get_banner(key)
        if not b.get("file_id"): await query.answer("\u0627\u0628\u062a\u062f\u0627 \u0639\u06a9\u0633 \u0622\u067e\u0644\u0648\u062f \u06a9\u0646\u06cc\u062f!",show_alert=True); return
        b["active"]=not b.get("active",False); await save_banners()
        await query.answer("\u2705 \u0641\u0639\u0627\u0644" if b["active"] else"\u274c \u063a\u06cc\u0631\u0641\u0639\u0627\u0644",show_alert=True)
        await query.message.edit_text(f"\U0001f5bc {SECTION_NAMES.get(key,key)} | {'\u2705 \u0641\u0639\u0627\u0644' if b['active'] else '\u274c \u063a\u06cc\u0631\u0641\u0639\u0627\u0644'}",reply_markup=banner_kb(key))
    elif data.startswith("ban_dl_"):
        key=data[7:]; banners[key]={"file_id":None,"active":False}; await save_banners()
        await query.answer("\U0001f5d1 \u062d\u0630\u0641 \u0634\u062f.",show_alert=True)
        await query.message.edit_text(f"\U0001f5bc {SECTION_NAMES.get(key,key)} | \u274c",reply_markup=banner_kb(key))
    elif data.startswith("sec_btns_"):
        key=data[9:]; sec=get_sec_btns(key)
        await query.message.edit_text(f"\U0001f518 \u062f\u06a9\u0645\u0647\u200c\u0647\u0627\u06cc {SECTION_NAMES.get(key,key)}\n{'\u2705 \u0641\u0639\u0627\u0644' if sec.get('enabled') else '\u274c \u063a\u06cc\u0631\u0641\u0639\u0627\u0644'} | {to_fa(len(sec.get('items',[])))} \u0639\u062f\u062f",reply_markup=sec_btns_kb(key))
    elif data.startswith("btn_tg_"):
        key=data[7:]; sec=get_sec_btns(key); sec["enabled"]=not sec.get("enabled",False); await save_buttons()
        await query.answer("\u2705 \u0641\u0639\u0627\u0644" if sec["enabled"] else"\u274c \u063a\u06cc\u0631\u0641\u0639\u0627\u0644",show_alert=True)
        await query.message.edit_text(f"\U0001f518 {SECTION_NAMES.get(key,key)} | {'\u2705' if sec['enabled'] else '\u274c'}",reply_markup=sec_btns_kb(key))
    elif data.startswith("btn_add_"):
        key=data[8:]; ctx.user_data.update({"mode":"btn_add_t","btn_key":key})
        await query.message.reply_text(f"\u2795 \u062f\u06a9\u0645\u0647 \u062c\u062f\u06cc\u062f \u0628\u0631\u0627\u06cc \u00ab{SECTION_NAMES.get(key,key)}\u00bb\n\u0639\u0646\u0648\u0627\u0646:",reply_markup=cancel_menu())
    elif data.startswith("btn_ed_"):
        parts=data[7:].split("_",1); key,bid=parts[0],parts[1]
        sec=get_sec_btns(key); item=next((x for x in sec.get("items",[]) if x["id"]==bid),None)
        if not item: await query.answer("\u06cc\u0627\u0641\u062a \u0646\u0634\u062f!",show_alert=True); return
        ctx.user_data.update({"mode":"btn_ed_t","btn_key":key,"btn_id":bid})
        await query.message.reply_text(f"\u270f\ufe0f \u00ab{item['title']}\u00bb\n\u0639\u0646\u0648\u0627\u0646 \u062c\u062f\u06cc\u062f (\u06cc\u0627 . \u0628\u062f\u0648\u0646 \u062a\u063a\u06cc\u06cc\u0631):",reply_markup=cancel_menu())
    elif data.startswith("btn_dl_"):
        parts=data[7:].split("_",1); key,bid=parts[0],parts[1]
        sec=get_sec_btns(key); sec["items"]=[x for x in sec.get("items",[]) if x["id"]!=bid]; await save_buttons()
        await query.answer("\U0001f5d1 \u062d\u0630\u0641 \u0634\u062f.",show_alert=True)
        await query.message.edit_text(f"\U0001f518 {SECTION_NAMES.get(key,key)}",reply_markup=sec_btns_kb(key))

    # ── catalog admin ──
    elif data=="admin_catalog":
        roots=await get_root_cats(active_only=False)
        await query.message.edit_text("\U0001f6cd \u0645\u062f\u06cc\u0631\u06cc\u062a \u06a9\u0627\u062a\u0627\u0644\u0648\u06af:",reply_markup=acat_root_kb(roots))
    elif data=="acr_new":
        ctx.user_data.update({"mode":"acr_new_ic"}); await query.message.reply_text("\U0001f3a8 \u0622\u06cc\u06a9\u0648\u0646 (\u0645\u062b\u0627\u0644: \U0001f4f1 \U0001f4bb \U0001f3a7):",reply_markup=cancel_menu())
    elif data.startswith("acr_ed_"):
        rid=int(data[7:]); ctx.user_data.update({"mode":"acr_edit","cat_id":rid})
        await query.message.reply_text("\u270f\ufe0f \u0646\u0627\u0645 \u062c\u062f\u06cc\u062f \u062f\u0633\u062a\u0647 \u0627\u0635\u0644\u06cc:",reply_markup=cancel_menu())
    elif data.startswith("acr_dl_"):
        rid=int(data[7:]); await db.execute("UPDATE categories SET is_active=0 WHERE id=?",(rid,)); await db.commit()
        await query.answer("\U0001f5d1 \u063a\u06cc\u0631\u0641\u0639\u0627\u0644 \u0634\u062f.",show_alert=True)
        roots=await get_root_cats(active_only=False); await query.message.edit_text("\U0001f6cd:",reply_markup=acat_root_kb(roots))
    elif data.startswith("acr_"):
        root_id=int(data[4:]); root=await get_cat(root_id)
        if not root: return
        subs=await get_subcats(root_id,active_only=False)
        await query.message.edit_text(f"\U0001f4c1 {root[2]} {root[1]}\n\u0632\u06cc\u0631\u062f\u0633\u062a\u0647: {to_fa(len(subs))} \u0639\u062f\u062f",reply_markup=acat_sub_kb(root_id,subs))
    elif data.startswith("acs_new_"):
        root_id=int(data[8:]); ctx.user_data.update({"mode":"acs_new_ic","root_id":root_id})
        await query.message.reply_text("\U0001f3a8 \u0622\u06cc\u06a9\u0648\u0646 \u0632\u06cc\u0631\u062f\u0633\u062a\u0647:",reply_markup=cancel_menu())
    elif data.startswith("acs_ed_"):
        sid=int(data[7:]); ctx.user_data.update({"mode":"acs_edit","cat_id":sid})
        await query.message.reply_text("\u270f\ufe0f \u0646\u0627\u0645 \u062c\u062f\u06cc\u062f \u0632\u06cc\u0631\u062f\u0633\u062a\u0647:",reply_markup=cancel_menu())
    elif data.startswith("acs_dl_"):
        sid=int(data[7:]); sub=await get_cat(sid)
        root_id=sub[3] if sub else None
        await db.execute("UPDATE categories SET is_active=0 WHERE id=?",(sid,)); await db.commit()
        await query.answer("\U0001f5d1 \u063a\u06cc\u0631\u0641\u0639\u0627\u0644 \u0634\u062f.",show_alert=True)
        if root_id:
            subs=await get_subcats(root_id,active_only=False); root=await get_cat(root_id)
            await query.message.edit_text(f"\U0001f4c1 {root[2] if root else ''} {root[1] if root else ''}",reply_markup=acat_sub_kb(root_id,subs))
    elif data.startswith("acs_"):
        sub_id=int(data[4:]); sub=await get_cat(sub_id)
        if not sub: return
        products=await get_products(sub_id,active_only=False)
        root_id=sub[3]
        await query.message.edit_text(f"\U0001f4e6 {sub[2]} {sub[1]}\n\u0645\u062d\u0635\u0648\u0644: {to_fa(len(products))} \u0639\u062f\u062f",reply_markup=acat_products_kb(sub_id,products,root_id))
    elif data.startswith("aprd_new_"):
        sub_id=int(data[9:]); ctx.user_data.update({"mode":"aprd_n_name","sub_id":sub_id})
        await query.message.reply_text("\U0001f4f1 \u0646\u0627\u0645 \u0645\u062d\u0635\u0648\u0644:",reply_markup=cancel_menu())
    elif data.startswith("aprd_etg_"):
        pid=int(data[9:]); p=await get_product(pid)
        if not p: return
        await db.execute("UPDATE products SET is_active=? WHERE id=?",(0 if p[6] else 1,pid)); await db.commit()
        await query.answer("\u2705 \u0641\u0639\u0627\u0644" if not p[6] else"\u274c \u063a\u06cc\u0631\u0641\u0639\u0627\u0644",show_alert=True)
        p=await get_product(pid); await query.message.edit_text(f"\U0001f4f1 {p[1]}\n\U0001f4b0 {p[2]}\n{'\u2705' if p[6] else '\u274c'}",reply_markup=aprd_kb(pid,p[7],bool(p[6])))
    elif data.startswith("aprd_del_"):
        pid=int(data[9:]); p=await get_product(pid); sub_id=p[7] if p else 0
        await db.execute("DELETE FROM products WHERE id=?",(pid,)); await db.commit()
        await query.answer("\U0001f5d1 \u062d\u0630\u0641 \u0634\u062f.",show_alert=True)
        sub=await get_cat(sub_id); products=await get_products(sub_id,active_only=False)
        if sub: await query.message.edit_text(f"\U0001f4e6 {sub[2]} {sub[1]}",reply_markup=acat_products_kb(sub_id,products,sub[3]))
    elif data.startswith("aprd_en_"): pid=int(data[8:]); ctx.user_data.update({"mode":"aprd_e_name","edit_pid":pid}); await query.message.reply_text("\u270f\ufe0f \u0646\u0627\u0645 \u062c\u062f\u06cc\u062f:",reply_markup=cancel_menu())
    elif data.startswith("aprd_ep_"): pid=int(data[8:]); ctx.user_data.update({"mode":"aprd_e_price","edit_pid":pid}); await query.message.reply_text("\U0001f4b0 \u0642\u06cc\u0645\u062a \u062c\u062f\u06cc\u062f:",reply_markup=cancel_menu())
    elif data.startswith("aprd_ed_"): pid=int(data[8:]); ctx.user_data.update({"mode":"aprd_e_desc","edit_pid":pid}); await query.message.reply_text("\U0001f4dd \u062a\u0648\u0636\u06cc\u062d \u062c\u062f\u06cc\u062f (\u06cc\u0627 . \u062d\u0630\u0641):",reply_markup=cancel_menu())
    elif data.startswith("aprd_ei_"): pid=int(data[8:]); ctx.user_data.update({"mode":"aprd_e_photo","edit_pid":pid}); await query.message.reply_text("\U0001f4f8 \u0639\u06a9\u0633 \u062c\u062f\u06cc\u062f:",reply_markup=cancel_menu())
    elif data.startswith("aprd_eu_"): pid=int(data[8:]); ctx.user_data.update({"mode":"aprd_e_url","edit_pid":pid}); await query.message.reply_text("\U0001f310 \u0644\u06cc\u0646\u06a9 \u062c\u062f\u06cc\u062f (\u06cc\u0627 . \u062d\u0630\u0641):",reply_markup=cancel_menu())
    elif data.startswith("aprd_"):
        pid=int(data[5:]); p=await get_product(pid)
        if not p: return
        await query.message.edit_text(f"\U0001f4f1 {p[1]}\n\U0001f4b0 {p[2]}\n\U0001f4dd {p[3] or'\u2014'}\n{'\u2705' if p[6] else '\u274c'}",reply_markup=aprd_kb(pid,p[7],bool(p[6])))

    # ── requests ──
    elif data=="admin_reqs":
        reqs=await get_requests()
        if not reqs: await query.message.edit_text("\U0001f4cb \u062f\u0631\u062e\u0648\u0627\u0633\u062a\u06cc \u0648\u062c\u0648\u062f \u0646\u062f\u0627\u0631\u062f.",reply_markup=back_admin()); return
        nc=sum(1 for r in reqs if r[6]=="new")
        await query.message.edit_text(f"\U0001f4cb \u062f\u0631\u062e\u0648\u0627\u0633\u062a\u200c\u0647\u0627\n\U0001f195 \u062c\u062f\u06cc\u062f: {to_fa(nc)} | \u06a9\u0644: {to_fa(len(reqs))}",reply_markup=reqs_kb(reqs))
    elif data.startswith("rq_done_"):
        rid=int(data[8:]); await done_request(rid); await query.answer("\u2705",show_alert=True)
        await query.message.edit_text("\u2705 \u067e\u06cc\u06af\u06cc\u0631\u06cc \u0634\u062f.",reply_markup=back_admin())
    elif data.startswith("rq_"):
        rid=int(data[3:])
        async with db.execute("SELECT id,user_id,username,first_name,phone,product_name,status,created_at FROM requests WHERE id=?",(rid,)) as c: r=await c.fetchone()
        if not r: return
        st="\U0001f195 \u062c\u062f\u06cc\u062f" if r[6]=="new" else"\u2705 \u067e\u06cc\u06af\u06cc\u0631\u06cc \u0634\u062f"
        await query.message.edit_text(f"\U0001f4cb \u062f\u0631\u062e\u0648\u0627\u0633\u062a #{to_fa(r[0])}\n\U0001f4f1 {r[5]}\n\U0001f464 {r[3] or'\u2014'} | {'@'+r[2] if r[2] else r[1]}\n\U0001f4de {r[4]}\n\U0001f194 {r[1]}\n\u23f1 {r[7]}\n{st}",reply_markup=req_kb(rid,r[6]))

    # ── چت ادمین ──
    elif data=="chats_list":
        await query.message.edit_text(f"\U0001f4ac \u0686\u062a\u200c\u0647\u0627\u06cc \u0641\u0639\u0627\u0644 ({to_fa(len(active_chats))}):",reply_markup=await chats_kb())
    elif data.startswith("chat_sel_"):
        cuid=int(data[9:])
        async with db.execute("SELECT first_name,username FROM users WHERE user_id=?",(cuid,)) as c: row=await c.fetchone()
        name=row[0] if row else"\u2014"; uname=f"@{row[1]}" if row and row[1] else str(cuid)
        ctx.user_data["chat_target"]=cuid
        await query.message.edit_text(f"\U0001f4ac \u0686\u062a \u0628\u0627 {name} ({uname})\n\U0001f194 {cuid}\n\u2500"*14+"\n\u2705 \u0647\u0631 \u067e\u06cc\u0627\u0645\u06cc \u0628\u0646\u0648\u06cc\u0633\u06cc\u062f \u0645\u0633\u062a\u0642\u06cc\u0645 \u0628\u0647 \u06a9\u0627\u0631\u0628\u0631 \u0645\u06cc\u200c\u0631\u0633\u062f.",reply_markup=chat_admin_kb(cuid,name))
    elif data=="chat_clear":
        ctx.user_data.pop("chat_target",None); await query.answer("\u2705 \u062a\u0648\u0642\u0641 \u067e\u0627\u0633\u062e\u062f\u0647\u06cc",show_alert=True)
        await query.message.edit_text("\U0001f451 \u067e\u0646\u0644 \u0645\u062f\u06cc\u0631\u06cc\u062a",reply_markup=admin_menu())
    elif data.startswith("chat_end_"):
        cuid=int(data[9:]); await close_chat(cuid)
        if ctx.user_data.get("chat_target")==cuid: ctx.user_data.pop("chat_target",None)
        await query.answer("\u2705 \u067e\u0627\u06cc\u0627\u0646 \u06cc\u0627\u0641\u062a",show_alert=True)
        try: await ctx.bot.send_message(cuid,"\U0001f534 \u067e\u0634\u062a\u06cc\u0628\u0627\u0646\u06cc \u0686\u062a \u0631\u0627 \u067e\u0627\u06cc\u0627\u0646 \u062f\u0627\u062f.\n\u0645\u06cc\u200c\u062a\u0648\u0627\u0646\u06cc\u062f \u062f\u0648\u0628\u0627\u0631\u0647 \u0627\u0632 \u0628\u062e\u0634 \u067e\u0634\u062a\u06cc\u0628\u0627\u0646\u06cc \u0634\u0631\u0648\u0639 \u06a9\u0646\u06cc\u062f.",reply_markup=main_menu())
        except: pass
        await query.message.edit_text("\U0001f451 \u067e\u0646\u0644",reply_markup=admin_menu())
    elif data.startswith("chat_block_"):
        cuid=int(data[11:]); await close_chat(cuid); await set_block(cuid,1)
        if ctx.user_data.get("chat_target")==cuid: ctx.user_data.pop("chat_target",None)
        await query.answer("\U0001f6ab \u0628\u0644\u0627\u06a9 \u0634\u062f",show_alert=True)
        try: await ctx.bot.send_message(cuid,"\u274c \u062f\u0633\u062a\u0631\u0633\u06cc \u0634\u0645\u0627 \u0645\u062d\u062f\u0648\u062f \u0634\u062f.",reply_markup=main_menu())
        except: pass
        await query.message.edit_text("\U0001f451 \u067e\u0646\u0644",reply_markup=admin_menu())

    # ── ساعت کاری ──
    elif data=="wh_menu":
        en="\u2705 \u0641\u0639\u0627\u0644" if workhours.get("enabled") else"\u274c \u063a\u06cc\u0631\u0641\u0639\u0627\u0644"
        await query.message.edit_text(f"\U0001f550 \u0633\u0627\u0639\u062a \u06a9\u0627\u0631\u06cc \u2014 {en}\n\n{wh_full_table()}",reply_markup=wh_kb())
    elif data=="wh_toggle":
        workhours["enabled"]=not workhours.get("enabled",True); await save_workhours()
        await query.answer("\u2705 \u0641\u0639\u0627\u0644" if workhours["enabled"] else"\u274c \u063a\u06cc\u0631\u0641\u0639\u0627\u0644",show_alert=True)
        await query.message.edit_text(f"\U0001f550 \u0633\u0627\u0639\u062a \u06a9\u0627\u0631\u06cc\n{wh_full_table()}",reply_markup=wh_kb())
    elif data.startswith("wh_day_"):
        dk=data[7:]; day=workhours["schedule"].get(dk,{"open":False,"shifts":[]})
        st="\n".join(f"  \u2022 {fmt_t(s['from'])} \u062a\u0627 {fmt_t(s['to'])}" for s in day.get("shifts",[])) or"  \u0646\u062f\u0627\u0631\u062f"
        await query.message.edit_text(f"\U0001f550 {DAY_FA.get(dk,dk)}\n{'\u2705 \u0628\u0627\u0632' if day.get('open') else '\u274c \u062a\u0639\u0637\u06cc\u0644'}\n{st}",reply_markup=wh_day_kb(dk))
    elif data.startswith("wh_dtg_"):
        dk=data[7:]; day=workhours["schedule"].get(dk,{"open":False,"shifts":[]})
        day["open"]=not day.get("open",False); workhours["schedule"][dk]=day; await save_workhours()
        await query.answer("\u2705 \u0628\u0627\u0632" if day["open"] else"\u274c \u062a\u0639\u0637\u06cc\u0644",show_alert=True)
        await query.message.edit_text(f"\U0001f550 {DAY_FA.get(dk,dk)} | {'\u2705 \u0628\u0627\u0632' if day['open'] else '\u274c \u062a\u0639\u0637\u06cc\u0644'}",reply_markup=wh_day_kb(dk))
    elif data.startswith("wh_sh_"): dk=data[6:]; ctx.user_data.update({"mode":"wh_shifts","wh_day":dk}); await query.message.reply_text(f"\U0001f550 {DAY_FA.get(dk,dk)}:\n\u0645\u062b\u0627\u0644: 11:00-14:00,17:00-23:00",reply_markup=cancel_menu())
    elif data=="wh_mop": ctx.user_data["mode"]="wh_mop"; await query.message.reply_text(f"\u270f\ufe0f \u067e\u06cc\u0627\u0645 \u0628\u0627\u0632:\n\n{workhours.get('msg_open','')}\n\n\u067e\u06cc\u0627\u0645 \u062c\u062f\u06cc\u062f:",reply_markup=cancel_menu())
    elif data=="wh_mcl": ctx.user_data["mode"]="wh_mcl"; await query.message.reply_text(f"\u270f\ufe0f \u067e\u06cc\u0627\u0645 \u0628\u0633\u062a\u0647:\n\n{workhours.get('msg_closed','')}\n\n\u067e\u06cc\u0627\u0645 \u062c\u062f\u06cc\u062f:",reply_markup=cancel_menu())

    # ── تنظیمات ──
    elif data=="settings_menu": await query.message.edit_text("\u2699\ufe0f \u062a\u0646\u0638\u06cc\u0645\u0627\u062a:",reply_markup=settings_kb())
    elif data.startswith("stg_"):
        key=data[4:]; settings[key]=not get_setting(key); await save_settings()
        await query.answer("\u2705 \u0630\u062e\u06cc\u0631\u0647 \u0634\u062f",show_alert=True)
        await query.message.edit_text("\u2699\ufe0f \u062a\u0646\u0638\u06cc\u0645\u0627\u062a:",reply_markup=settings_kb())

    # ── کاربران ──
    elif data=="users_menu":
        t=await total_users(); bl=await blk_count()
        await query.message.edit_text(f"\U0001f465 \u06a9\u0627\u0631\u0628\u0631\u0627\u0646\n\u06a9\u0644: {to_fa(t)} | \u0628\u0644\u0627\u06a9: {to_fa(bl)}",reply_markup=users_menu_kb())
    elif data=="users_search": ctx.user_data["mode"]="users_search"; await query.message.reply_text("\U0001f50d \u0646\u0627\u0645\u060c \u0622\u06cc\u062f\u06cc \u06cc\u0627 \u06cc\u0648\u0632\u0631\u0646\u06cc\u0645:",reply_markup=cancel_menu())
    elif data.startswith("ul_"):
        parts=data.split("_"); ft=parts[1]; off=int(parts[2])
        flt={"today":"WHERE DATE(last_seen)=DATE('now','localtime')","week":"WHERE last_seen>=datetime('now','-7 days','localtime')","blocked":"WHERE is_blocked=1"}
        total=await _cnt(f"SELECT COUNT(*) FROM users {flt.get(ft,'')}")
        rows=await get_users_page(off,15,ft)
        label={"all":"\u0647\u0645\u0647","today":"\u0627\u0645\u0631\u0648\u0632","week":"\u0647\u0641\u062a\u0647","blocked":"\u0628\u0644\u0627\u06a9"}.get(ft,"")
        await query.message.edit_text(f"\U0001f465 {label}\n{to_fa(off+1)} \u062a\u0627 {to_fa(min(off+15,total))} \u0627\u0632 {to_fa(total)}:",reply_markup=users_list_kb(rows,off,ft,total))
    elif data.startswith("uv_"):
        uid2=int(data[3:])
        async with db.execute("SELECT user_id,first_name,username,joined_at,last_seen,is_blocked FROM users WHERE user_id=?",(uid2,)) as c: row=await c.fetchone()
        if not row: await query.answer("\u06cc\u0627\u0641\u062a \u0646\u0634\u062f!",show_alert=True); return
        await query.message.edit_text(f"\U0001f464 {row[1] or'\u2014'}\n{'@'+row[2] if row[2] else'\u2014'}\n\U0001f194 {row[0]}\n\u0639\u0636\u0648\u06cc\u062a: {row[3]}\n\u0622\u062e\u0631\u06cc\u0646 \u0641\u0639\u0627\u0644\u06cc\u062a: {row[4]}\n{'\U0001f6ab \u0628\u0644\u0627\u06a9' if row[5] else '\u2705 \u0641\u0639\u0627\u0644'}",reply_markup=udetail_kb(uid2,bool(row[5])))
    elif data.startswith("utog_"):
        uid2=int(data[5:])
        async with db.execute("SELECT is_blocked FROM users WHERE user_id=?",(uid2,)) as c: row=await c.fetchone()
        if not row: return
        await set_block(uid2,0 if row[0] else 1)
        await query.answer("\u2705 \u0631\u0641\u0639 \u0628\u0644\u0627\u06a9" if row[0] else"\U0001f6ab \u0628\u0644\u0627\u06a9 \u0634\u062f",show_alert=True)
        async with db.execute("SELECT user_id,first_name,username,joined_at,last_seen,is_blocked FROM users WHERE user_id=?",(uid2,)) as c: row=await c.fetchone()
        await query.message.edit_text(f"\U0001f464 {row[1] or'\u2014'}\n\U0001f194 {row[0]}\n{'\U0001f6ab \u0628\u0644\u0627\u06a9' if row[5] else '\u2705 \u0641\u0639\u0627\u0644'}",reply_markup=udetail_kb(uid2,bool(row[5])))

# ════════════════════════════════════════════════
#  TEXT HANDLER
# ════════════════════════════════════════════════
async def text_handler(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    user=update.effective_user; text=update.message.text.strip()
    await save_user(user)
    if not await anti_spam(user.id): return await update.message.reply_text("\U0001f422 \u0644\u0637\u0641\u0627\u064b \u0622\u0631\u0627\u0645\u200c\u062a\u0631 \u067e\u06cc\u0627\u0645 \u062f\u0647\u06cc\u062f.")
    if text=="\u274c \u0644\u063a\u0648 \u0639\u0645\u0644\u06cc\u0627\u062a":
        ctx.user_data.clear(); return await update.message.reply_text("\u274c \u0644\u063a\u0648 \u0634\u062f.",reply_markup=main_menu())
    mode=ctx.user_data.get("mode")

    # ════ ADMIN ════
    if user.id==ADMIN_ID:
        if mode=="edit_text":
            key=ctx.user_data.pop("edit_key",None); ctx.user_data.pop("mode",None)
            if key: responses[key]=text; await save_data()
            await update.message.reply_text("\u2705 \u0630\u062e\u06cc\u0631\u0647 \u0634\u062f.",reply_markup=main_menu()); return
        if mode=="broadcast":
            ctx.user_data.pop("mode",None); await update.message.reply_text("\U0001f4e4 \u062f\u0631 \u062d\u0627\u0644 \u0627\u0631\u0633\u0627\u0644...")
            await broadcast(ctx,text); return
        if mode=="users_search":
            ctx.user_data.pop("mode",None); rows=await search_users(text)
            if not rows: await update.message.reply_text("\u274c \u06cc\u0627\u0641\u062a \u0646\u0634\u062f.",reply_markup=main_menu()); return
            lines=[f"{'🚫 ' if r[4] else ''}{r[1] or'\u2014'} | {r[0]} | {'@'+r[2] if r[2] else'\u2014'}" for r in rows]
            await update.message.reply_text("\U0001f50d \u0646\u062a\u0627\u06cc\u062c:\n\n"+"\n".join(lines),reply_markup=main_menu()); return
        if mode=="btn_add_t":
            ctx.user_data.update({"btn_title":text,"mode":"btn_add_u"}); await update.message.reply_text("\U0001f517 \u0644\u06cc\u0646\u06a9:",reply_markup=cancel_menu()); return
        if mode=="btn_add_u":
            key=ctx.user_data.pop("btn_key",None); title=ctx.user_data.pop("btn_title","\u062f\u06a9\u0645\u0647"); ctx.user_data.pop("mode",None)
            url=text if text.startswith("http") else f"https://{text}"
            sec=get_sec_btns(key)
            sec["items"].append({"id":f"b{int(time.time())}","title":title,"url":url})
            if not sec.get("enabled"): sec["enabled"]=True
            await save_buttons()
            await update.message.reply_text(f"\u2705 \u00ab{title}\u00bb \u0627\u0636\u0627\u0641\u0647 \u0634\u062f.",reply_markup=sec_btns_kb(key)); return
        if mode=="btn_ed_t":
            ctx.user_data.update({"btn_new_t":None if text=="." else text,"mode":"btn_ed_u"}); await update.message.reply_text("\U0001f517 \u0644\u06cc\u0646\u06a9 \u062c\u062f\u06cc\u062f (\u06cc\u0627 . \u0628\u062f\u0648\u0646 \u062a\u063a\u06cc\u06cc\u0631):",reply_markup=cancel_menu()); return
        if mode=="btn_ed_u":
            key=ctx.user_data.pop("btn_key",None); bid=ctx.user_data.pop("btn_id",None); nt=ctx.user_data.pop("btn_new_t",None); ctx.user_data.pop("mode",None)
            sec=get_sec_btns(key)
            for it in sec.get("items",[]):
                if it["id"]==bid:
                    if nt: it["title"]=nt
                    if text!=".": it["url"]=text if text.startswith("http") else f"https://{text}"
            await save_buttons(); await update.message.reply_text("\u2705 \u0648\u06cc\u0631\u0627\u06cc\u0634 \u0634\u062f.",reply_markup=main_menu()); return
        if mode=="wh_shifts":
            dk=ctx.user_data.pop("wh_day",None); ctx.user_data.pop("mode",None)
            try:
                sh=[{"from":p.split("-")[0].strip(),"to":p.split("-")[1].strip()} for p in text.split(",")]
                workhours["schedule"][dk]["shifts"]=sh; await save_workhours()
                await update.message.reply_text("\u2705 \u0630\u062e\u06cc\u0631\u0647 \u0634\u062f.",reply_markup=main_menu())
            except: await update.message.reply_text("\u274c \u0641\u0631\u0645\u062a \u0627\u0634\u062a\u0628\u0627\u0647!\n\u0645\u062b\u0627\u0644: 11:00-14:00,17:00-23:00",reply_markup=main_menu())
            return
        if mode=="wh_mop": ctx.user_data.pop("mode",None); workhours["msg_open"]=text; await save_workhours(); await update.message.reply_text("\u2705",reply_markup=main_menu()); return
        if mode=="wh_mcl": ctx.user_data.pop("mode",None); workhours["msg_closed"]=text; await save_workhours(); await update.message.reply_text("\u2705",reply_markup=main_menu()); return
        if mode=="acr_new_ic": ctx.user_data.update({"acr_ic":text,"mode":"acr_new_nm"}); await update.message.reply_text("\u270f\ufe0f \u0646\u0627\u0645 \u062f\u0633\u062a\u0647 \u0627\u0635\u0644\u06cc:",reply_markup=cancel_menu()); return
        if mode=="acr_new_nm":
            ic=ctx.user_data.pop("acr_ic","\U0001f4e6"); ctx.user_data.pop("mode",None)
            await db.execute("INSERT INTO categories(name,icon,parent_id,is_active) VALUES(?,?,NULL,1)",(text,ic)); await db.commit()
            await update.message.reply_text(f"\u2705 \u062f\u0633\u062a\u0647 \u00ab{ic} {text}\u00bb \u0627\u0636\u0627\u0641\u0647 \u0634\u062f.",reply_markup=main_menu()); return
        if mode=="acr_edit":
            cat_id=ctx.user_data.pop("cat_id",None); ctx.user_data.pop("mode",None)
            await db.execute("UPDATE categories SET name=? WHERE id=?",(text,cat_id)); await db.commit()
            await update.message.reply_text("\u2705 \u0630\u062e\u06cc\u0631\u0647 \u0634\u062f.",reply_markup=main_menu()); return
        if mode=="acs_new_ic": ctx.user_data.update({"acs_ic":text,"mode":"acs_new_nm"}); await update.message.reply_text("\u270f\ufe0f \u0646\u0627\u0645 \u0632\u06cc\u0631\u062f\u0633\u062a\u0647:",reply_markup=cancel_menu()); return
        if mode=="acs_new_nm":
            ic=ctx.user_data.pop("acs_ic","\U0001f4e6"); root_id=ctx.user_data.pop("root_id",None); ctx.user_data.pop("mode",None)
            await db.execute("INSERT INTO categories(name,icon,parent_id,is_active) VALUES(?,?,?,1)",(text,ic,root_id)); await db.commit()
            await update.message.reply_text(f"\u2705 \u0632\u06cc\u0631\u062f\u0633\u062a\u0647 \u00ab{ic} {text}\u00bb \u0627\u0636\u0627\u0641\u0647 \u0634\u062f.",reply_markup=main_menu()); return
        if mode=="acs_edit":
            cat_id=ctx.user_data.pop("cat_id",None); ctx.user_data.pop("mode",None)
            await db.execute("UPDATE categories SET name=? WHERE id=?",(text,cat_id)); await db.commit()
            await update.message.reply_text("\u2705 \u0630\u062e\u06cc\u0631\u0647 \u0634\u062f.",reply_markup=main_menu()); return
        if mode=="aprd_n_name": ctx.user_data.update({"prd_name":text,"mode":"aprd_n_price"}); await update.message.reply_text("\U0001f4b0 \u0642\u06cc\u0645\u062a:",reply_markup=cancel_menu()); return
        if mode=="aprd_n_price": ctx.user_data.update({"prd_price":text,"mode":"aprd_n_desc"}); await update.message.reply_text("\U0001f4dd \u062a\u0648\u0636\u06cc\u062d (\u06cc\u0627 . \u0628\u062f\u0648\u0646 \u062a\u0648\u0636\u06cc\u062d):",reply_markup=cancel_menu()); return
        if mode=="aprd_n_desc": ctx.user_data.update({"prd_desc":None if text=="." else text,"mode":"aprd_n_url"}); await update.message.reply_text("\U0001f310 \u0644\u06cc\u0646\u06a9 (\u06cc\u0627 . \u0628\u062f\u0648\u0646):",reply_markup=cancel_menu()); return
        if mode=="aprd_n_url": ctx.user_data.update({"prd_url":None if text=="." else text,"mode":"aprd_n_photo"}); await update.message.reply_text("\U0001f4f8 \u0639\u06a9\u0633 (\u06cc\u0627 . \u0628\u062f\u0648\u0646):",reply_markup=cancel_menu()); return
        if mode=="aprd_n_photo" and text==".":
            sub_id=ctx.user_data.pop("sub_id",None); name=ctx.user_data.pop("prd_name",""); price=ctx.user_data.pop("prd_price","")
            desc=ctx.user_data.pop("prd_desc",None); url=ctx.user_data.pop("prd_url",None); ctx.user_data.pop("mode",None)
            await db.execute("INSERT INTO products(category_id,name,price,description,photo_id,site_url,is_active,created_at) VALUES(?,?,?,?,?,?,1,?)",(sub_id,name,price,desc,None,url,gregorian_now())); await db.commit()
            await update.message.reply_text(f"\u2705 \u00ab{name}\u00bb \u0627\u0636\u0627\u0641\u0647 \u0634\u062f.",reply_markup=main_menu()); return
        if mode=="aprd_e_name":
            pid=ctx.user_data.pop("edit_pid",None); ctx.user_data.pop("mode",None)
            await db.execute("UPDATE products SET name=? WHERE id=?",(text,pid)); await db.commit()
            await update.message.reply_text("\u2705",reply_markup=main_menu()); return
        if mode=="aprd_e_price":
            pid=ctx.user_data.pop("edit_pid",None); ctx.user_data.pop("mode",None)
            await db.execute("UPDATE products SET price=? WHERE id=?",(text,pid)); await db.commit()
            await update.message.reply_text("\u2705",reply_markup=main_menu()); return
        if mode=="aprd_e_desc":
            pid=ctx.user_data.pop("edit_pid",None); ctx.user_data.pop("mode",None)
            await db.execute("UPDATE products SET description=? WHERE id=?",(None if text=="." else text,pid)); await db.commit()
            await update.message.reply_text("\u2705",reply_markup=main_menu()); return
        if mode=="aprd_e_url":
            pid=ctx.user_data.pop("edit_pid",None); ctx.user_data.pop("mode",None)
            await db.execute("UPDATE products SET site_url=? WHERE id=?",(None if text=="." else text,pid)); await db.commit()
            await update.message.reply_text("\u2705",reply_markup=main_menu()); return
        # پاسخ ادمین به چت — اگه mode نداشت و chat_target داشت، اول اینجا بیاد
        chat_target=ctx.user_data.get("chat_target")
        if not mode and chat_target and chat_target in active_chats:
            ft=f"\n\u2500"*17+f"\n\u23f1 {shamsi_now()}" if get_setting("show_datetime_footer") else""
            try:
                await ctx.bot.send_message(chat_target,f"\U0001f4e9 \u067e\u0634\u062a\u06cc\u0628\u0627\u0646\u06cc:\n\u2500"*14+f"\n{text}{ft}")
                async with db.execute("SELECT first_name FROM users WHERE user_id=?",(chat_target,)) as c:
                    row=await c.fetchone()
                await update.message.reply_text(f"\u2705 \u067e\u06cc\u0627\u0645 \u0628\u0647 {row[0] if row else chat_target} \u0627\u0631\u0633\u0627\u0644 \u0634\u062f.")
            except Exception as e: logger.error(f"chat reply: {e}"); await update.message.reply_text("\u274c \u0627\u0631\u0633\u0627\u0644 \u0646\u0627\u0645\u0648\u0641\u0642.")
            return
        # ادمین می‌تونه از منو هم استفاده کنه — fall through

    # ════ USER active chat ════
    if user.id!=ADMIN_ID and active_chats.get(user.id):
        if text=="\u274c \u067e\u0627\u06cc\u0627\u0646 \u0686\u062a":
            await close_chat(user.id)
            try: await ctx.bot.send_message(ADMIN_ID,f"\U0001f534 {user.first_name or user.id} \u0686\u062a \u0631\u0627 \u067e\u0627\u06cc\u0627\u0646 \u062f\u0627\u062f.\n\U0001f194 {user.id}")
            except: pass
            await update.message.reply_text("\u2705 \u0686\u062a \u067e\u0627\u06cc\u0627\u0646 \u06cc\u0627\u0641\u062a.",reply_markup=main_menu()); return
        try:
            await ctx.bot.send_message(ADMIN_ID,
                f"\U0001f4ac {user.first_name or'\u2014'} | {'@'+user.username if user.username else str(user.id)}\n\U0001f194 {user.id}\n\u2500"*14+f"\n{text}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"\U0001f4ac \u067e\u0627\u0633\u062e",callback_data=f"chat_sel_{user.id}")]]))
        except Exception as e: logger.error(f"chat fwd: {e}")
        await update.message.reply_text("\U0001f4e8 \u067e\u06cc\u0627\u0645 \u0627\u0631\u0633\u0627\u0644 \u0634\u062f.",reply_markup=chat_menu()); return

    # ════ catalog search ════
    if mode=="cat_search":
        ctx.user_data.pop("mode",None); results=await search_products(text)
        if not results: await update.message.reply_text(f"\U0001f50d \u0646\u062a\u06cc\u062c\u0647\u200c\u0627\u06cc \u0628\u0631\u0627\u06cc \u00ab{text}\u00bb \u06cc\u0627\u0641\u062a \u0646\u0634\u062f.",reply_markup=main_menu()); return
        btns=[[InlineKeyboardButton(f"\U0001f4f1 {p[1]} \u2014 {p[2]}",callback_data=f"prd_{p[0]}")] for p in results]
        btns.append([InlineKeyboardButton("\U0001f519 \u06a9\u0627\u062a\u0627\u0644\u0648\u06af",callback_data="cat_back")])
        await update.message.reply_text(f"\U0001f50d {to_fa(len(results))} \u0646\u062a\u06cc\u062c\u0647 \u0628\u0631\u0627\u06cc \u00ab{text}\u00bb:",reply_markup=InlineKeyboardMarkup(btns)); return

    # ════ purchase request phone ════
    if mode=="req_phone":
        pid=ctx.user_data.pop("req_pid",None); pname=ctx.user_data.pop("req_name","\u0646\u0627\u0645\u0634\u062e\u0635"); ctx.user_data.pop("mode",None)
        digits=text.replace("-","").replace(" ","").replace("+","")
        if not digits.isdigit() or len(digits)<10:
            ctx.user_data.update({"mode":"req_phone","req_pid":pid,"req_name":pname})
            await update.message.reply_text("\u274c \u0634\u0645\u0627\u0631\u0647 \u0645\u0639\u062a\u0628\u0631 \u0646\u06cc\u0633\u062a. \u062f\u0648\u0628\u0627\u0631\u0647:",reply_markup=cancel_menu()); return
        await save_request(user.id,user.username,user.first_name,text,pid,pname)
        try:
            await ctx.bot.send_message(ADMIN_ID,
                f"\U0001f4cb \u062f\u0631\u062e\u0648\u0627\u0633\u062a \u062e\u0631\u06cc\u062f!\n\U0001f4f1 {pname}\n\U0001f464 {user.first_name or'\u2014'} | {'@'+user.username if user.username else'\u2014'}\n\U0001f4de {text}\n\U0001f194 {user.id}\n\u23f1 {shamsi_now()}")
        except Exception as e: logger.error(f"req notify: {e}")
        await update.message.reply_text(f"\u2705 \u062f\u0631\u062e\u0648\u0627\u0633\u062a \u062e\u0631\u06cc\u062f \u00ab{pname}\u00bb \u062b\u0628\u062a \u0634\u062f!\n\u067e\u0634\u062a\u06cc\u0628\u0627\u0646\u06cc \u0628\u0647 \u0632\u0648\u062f\u06cc \u062a\u0645\u0627\u0633 \u0645\u06cc\u200c\u06af\u06cc\u0631\u062f.",reply_markup=main_menu()); return

    # ════ user menu ════
    if text=="\U0001f550 \u0633\u0627\u0639\u062a \u06a9\u0627\u0631\u06cc":
        await record_stat("wh_page")
        if not workhours.get("enabled",True): await update.message.reply_text("\U0001f550 \u0633\u0627\u0639\u062a \u06a9\u0627\u0631\u06cc \u062a\u0646\u0638\u06cc\u0645 \u0646\u0634\u062f\u0647.",reply_markup=main_menu()); return
        wh=wh_today_block() or""
        ft=f"\n\u2500"*17+f"\n\u23f1 {shamsi_now()}" if get_setting("show_datetime_footer") else""
        await update.message.reply_text(f"\U0001f550 \u0633\u0627\u0639\u062a \u06a9\u0627\u0631\u06cc \u0627\u0633\u062a\u0648\u06a9 \u0644\u0646\u062f\n\u2501"*15+f"\n{wh_full_table()}\n\u2501"*15+f"\n{wh}{ft}",reply_markup=main_menu()); return

    if text=="\U0001f6cd \u0645\u062d\u0635\u0648\u0644\u0627\u062a":
        await record_stat("catalog"); cats=await get_root_cats()
        if not cats: await update.message.reply_text("\U0001f4ed \u0645\u062d\u0635\u0648\u0644\u06cc \u0645\u0648\u062c\u0648\u062f \u0646\u06cc\u0633\u062a.",reply_markup=main_menu()); return
        await update.message.reply_text("\U0001f6cd \u06a9\u0627\u062a\u0627\u0644\u0648\u06af \u0627\u0633\u062a\u0648\u06a9 \u0644\u0646\u062f\n\u062f\u0633\u062a\u0647\u200c\u0628\u0646\u062f\u06cc \u0631\u0627 \u0627\u0646\u062a\u062e\u0627\u0628 \u06a9\u0646\u06cc\u062f:",reply_markup=cat_root_kb(cats)); return

    for k,v in MENU_ITEMS.items():
        if text==v:
            await record_stat(k); content=responses.get(k,"\u062a\u0646\u0638\u06cc\u0645 \u0646\u0634\u062f\u0647")
            full=build_msg(v,content,k)
            kb=support_kb() if k=="4" else user_sec_kb(k)
            await send_banner(update.message,full,k,kb=kb); return

    await update.message.reply_text("\u26a0\ufe0f \u06af\u0632\u06cc\u0646\u0647 \u0646\u0627\u0645\u0639\u062a\u0628\u0631 \u0627\u0633\u062a.",reply_markup=main_menu())

# ════════════════════════════════════════════════
#  PHOTO HANDLER
# ════════════════════════════════════════════════
async def photo_handler(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    if user.id!=ADMIN_ID: return
    mode=ctx.user_data.get("mode"); photo=update.message.photo[-1]
    if mode=="ban_up":
        key=ctx.user_data.pop("ban_key",None); ctx.user_data.pop("mode",None)
        if not key: await update.message.reply_text("\u274c \u062e\u0637\u0627.",reply_markup=main_menu()); return
        get_banner(key); banners[key]["file_id"]=photo.file_id; banners[key]["active"]=True; await save_banners()
        await update.message.reply_text(f"\u2705 \u0628\u0646\u0631 \u00ab{SECTION_NAMES.get(key,key)}\u00bb \u0622\u067e\u0644\u0648\u062f \u0634\u062f!",reply_markup=main_menu()); return
    if mode=="broadcast":
        ctx.user_data.pop("mode",None); caption=update.message.caption or""
        await update.message.reply_text("\U0001f4e4 \u062f\u0631 \u062d\u0627\u0644 \u0627\u0631\u0633\u0627\u0644...")
        await broadcast(ctx,caption,photo=photo.file_id); return
    if mode=="aprd_n_photo":
        sub_id=ctx.user_data.pop("sub_id",None); name=ctx.user_data.pop("prd_name",""); price=ctx.user_data.pop("prd_price","")
        desc=ctx.user_data.pop("prd_desc",None); url=ctx.user_data.pop("prd_url",None); ctx.user_data.pop("mode",None)
        await db.execute("INSERT INTO products(category_id,name,price,description,photo_id,site_url,is_active,created_at) VALUES(?,?,?,?,?,?,1,?)",(sub_id,name,price,desc,photo.file_id,url,gregorian_now())); await db.commit()
        await update.message.reply_text(f"\u2705 \u00ab{name}\u00bb \u0628\u0627 \u0639\u06a9\u0633 \u0627\u0636\u0627\u0641\u0647 \u0634\u062f.",reply_markup=main_menu()); return
    if mode=="aprd_e_photo":
        pid=ctx.user_data.pop("edit_pid",None); ctx.user_data.pop("mode",None)
        await db.execute("UPDATE products SET photo_id=? WHERE id=?",(photo.file_id,pid)); await db.commit()
        await update.message.reply_text("\u2705 \u0639\u06a9\u0633 \u0630\u062e\u06cc\u0631\u0647 \u0634\u062f.",reply_markup=main_menu()); return
    # ادمین عکس reply به چت
    chat_target=ctx.user_data.get("chat_target")
    if chat_target and chat_target in active_chats:
        try:
            await ctx.bot.send_photo(chat_target,photo=photo.file_id,caption=f"\U0001f4e9 \u067e\u0634\u062a\u06cc\u0628\u0627\u0646\u06cc:\n{update.message.caption or''}")
            await update.message.reply_text("\u2705 \u0639\u06a9\u0633 \u0627\u0631\u0633\u0627\u0644 \u0634\u062f.")
        except Exception as e: logger.error(f"chat photo: {e}")

# ════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════
async def post_init(app):
    await init_db(); await load_data(); await load_banners()
    await load_workhours(); await load_buttons(); await load_settings()
    await load_stats(); await load_active_chats()
    logger.info("\u2705 \u0631\u0628\u0627\u062a \u0631\u0627\u0647\u200c\u0627\u0646\u062f\u0627\u0632\u06cc \u0634\u062f")

def main():
    app=ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start",cmd_start))
    app.add_handler(CommandHandler("admin",cmd_admin))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND,photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler))
    print("\U0001f680 \u0631\u0628\u0627\u062a \u062f\u0631 \u062d\u0627\u0644 \u0627\u062c\u0631\u0627\u0633\u062a...")
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    main()
