import os, re, json, time, asyncio, logging, aiosqlite, jdatetime, pytz, zipfile, io, csv, html, secrets, traceback
from datetime import datetime, timedelta
import aiofiles
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from telegram.error import Forbidden, BadRequest, Conflict
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                           CallbackQueryHandler, ContextTypes, filters)

os.environ.pop("HTTP_PROXY", None); os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("ALL_PROXY", None); os.environ["NO_PROXY"] = "*"

def _env(name):
    v = (os.environ.get(name) or "").strip()
    if not v:
        raise SystemExit(
            f"❌ متغیر محیطی {name} تنظیم نشده است.\n"
            f"   فایل .env کنار bot.py را بسازید و مقداردهی کنید:\n"
            f"       BOT_TOKEN=...\n"
            f"       ADMIN_ID=...\n"
            f"   (در systemd باید EnvironmentFile=/opt/telegram-bot/.env باشد)")
    return v

TOKEN = _env("BOT_TOKEN")
try:
    ADMIN_ID = int(_env("ADMIN_ID"))
except ValueError:
    raise SystemExit("❌ ADMIN_ID باید عدد باشد (آیدی عددی تلگرام، نه یوزرنیم).")
DATA_FILE = "data.json"; DB_FILE = "users.db"; BANNER_FILE = "banner.json"
WORKHOURS_FILE = "workhours.json"; BUTTONS_FILE = "buttons.json"
MENU_FILE = "menu.json"; BACKUPS_FILE = "backups.json"
SETTINGS_FILE = "settings.json"; STATS_FILE = "stats.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
IRAN_TZ = pytz.timezone("Asia/Tehran")

# ── زمان
_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
# ارقام فارسی/عربی → انگلیسی (کاربر ممکن است شماره را با کیبورد فارسی بنویسد)
FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
CONTACT_DEFAULT_TEXT = ("📝 درخواست تماس\n"
                        "شماره خود را بگذارید تا همکاران ما در اولین فرصت با شما تماس بگیرند.")
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
    {"key":"contact","label":"📝 درخواست تماس","order":5,"enabled":True,"width":"full"},
    {"key":"workhours","label":"🕐 ساعت کاری","order":6,"enabled":True,"width":"half"},
    {"key":"4","label":"📞 پشتیبانی","order":7,"enabled":True,"width":"half"},
    {"key":"6","label":"🔖 دکمه ذخیره ۱","order":8,"enabled":False,"width":"half"},
    {"key":"7","label":"🔖 دکمه ذخیره ۲","order":9,"enabled":False,"width":"half"},
]
menu_cfg = []

SECTION_NAMES = {"welcome":"🏠 خوش‌آمدگویی",
                 "contact":"📝 درخواست تماس","workhours":"🕐 ساعت کاری",
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
DEFAULT_SETTINGS = {"notify_new_user":True,"store_open":True,"forward_user_msgs":True}

# ── helpers
def get_banner(k): banners.setdefault(k,{"file_id":None,"active":False}); return banners[k]
def get_sec_btns(k): buttons.setdefault(k,{"enabled":True,"items":[]}); return buttons[k]
def get_setting(k): return settings.get(k,DEFAULT_SETTINGS.get(k,True))

HHMM_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

def valid_shift(sh):
    return bool(HHMM_RE.match(sh.get("from","")) and HHMM_RE.match(sh.get("to","")))

def in_shift(ns, sh):
    """آیا ساعت ns داخل شیفت است؟ شیفت‌های نیمه‌شب‌گذر (۲۲:۰۰ تا ۰۲:۰۰) هم پشتیبانی می‌شوند."""
    if not valid_shift(sh): return False
    f,t = sh["from"], sh["to"]
    if f <= t: return f <= ns <= t          # شیفت عادی
    return ns >= f or ns <= t                # از نیمه‌شب رد می‌شود

def is_open():
    if not get_setting("store_open"): return False
    if not workhours.get("enabled",True): return True
    now=datetime.now(IRAN_TZ); j=jdatetime.datetime.fromgregorian(datetime=now)
    ns=now.strftime("%H:%M")
    # شیفتی که از نیمه‌شب گذشته، متعلق به «دیروز» است
    today=str(j.weekday()); yday=str((j.weekday()-1) % 7)
    sched=workhours.get("schedule",{})
    d=sched.get(today,{})
    if d.get("open",False) and any(in_shift(ns,sh) for sh in d.get("shifts",[])
                                   if sh.get("from","") <= sh.get("to","")):
        return True
    for key in (today,yday):
        dd=sched.get(key,{})
        if not dd.get("open",False): continue
        for sh in dd.get("shifts",[]):
            if sh.get("from","") > sh.get("to","") and in_shift(ns,sh): return True
    return False

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

def new_btn_id():
    """شناسه یکتا — time.time() ثانیه‌ای بود و دو دکمه در یک ثانیه شناسه یکسان می‌گرفتند."""
    return "b" + secrets.token_hex(4)

# طرح‌های مجاز برای دکمه‌های لینک؛ لینک نامعتبر باعث می‌شود تلگرام کل پیام
# آن بخش را رد کند و بخش برای همه کاربران از کار بیفتد.
# میزبان باید حداقل یک نقطه و یک TLD حرفی داشته باشد، وگرنه چیزی مثل
# «https://سلام» هم قبول می‌شد و دکمه در تلگرام رد می‌شد.
_URL_RE = re.compile(
    r"^https?://"                       # طرح
    r"(?:[^\s:@/]+(?::[^\s@/]*)?@)?"     # user:pass اختیاری
    r"[\w\u0080-\uffff-]+"              # برچسب اول دامنه
    r"(?:\.[\w\u0080-\uffff-]+)*"      # برچسب‌های میانی
    r"\.[A-Za-z\u0080-\uffff]{2,}"      # TLD
    r"(?::\d{1,5})?"                    # پورت اختیاری
    r"(?:[/?#]\S*)?$",                  # مسیر اختیاری
    re.IGNORECASE)

def normalize_url(text):
    """لینک را نرمال و اعتبارسنجی می‌کند. اگر معتبر نبود None برمی‌گرداند."""
    t=(text or "").strip()
    if not t: return None
    if t.startswith(("tg://","mailto:")): return t
    if not t.lower().startswith(("http://","https://")): t="https://"+t
    return t if _URL_RE.match(t) and len(t)<=2048 else None

def build_msg(title,content,sec_key):
    lines=[f"✦ {title}","",content]
    msg="\n".join(lines)
    return msg[:4000]+"..." if len(msg)>4000 else msg

def progress_bar(v,t,n=8):
    if t==0: return "░"*n
    f=int(n*v/t); return "▓"*f+"░"*(n-f)

_stats_dirty = False
_last_err_report = 0.0      # زمان آخرین گزارش خطا به ادمین
_ERR_REPORT_GAP  = 60.0     # حداقل فاصله بین دو گزارش (ثانیه)

async def record_stat(k):
    global _stats_dirty
    stats[k]=stats.get(k,0)+1
    _stats_dirty=True   # فقط flag — بدون disk write

async def _stats_flush_loop():
    """هر ۳۰ ثانیه اگر آمار تغییر کرده باشد، ذخیره می‌کند."""
    global _stats_dirty
    while True:
        await asyncio.sleep(30)
        if _stats_dirty: await save_stats(); _stats_dirty=False

# ── load/save
async def _rj(path,default):
    """خواندن JSON. فایلِ خراب قرنطینه می‌شود تا ذخیره‌ی بعدی رویش ننویسد."""
    try:
        async with aiofiles.open(path,"r",encoding="utf-8") as f:
            return json.loads(await f.read())
    except FileNotFoundError:
        pass                      # اولین اجرا — طبیعی است
    except Exception as e:
        # فایل هست ولی خراب است. اگر کاری نکنیم، ذخیره‌ی بعدی محتوای
        # فروشگاه را با پیش‌فرض بازنویسی و برای همیشه نابود می‌کند.
        bad=f"{path}.corrupt"
        try:
            os.replace(path,bad)
            logger.error(f"⚠️ {path} خراب بود ({e}) — به {bad} منتقل شد و پیش‌فرض بارگذاری شد.")
        except Exception as e2:
            logger.error(f"⚠️ {path} خراب است ({e}) و قرنطینه هم نشد: {e2}")
    return default() if callable(default) else default

async def _wj(path,data):
    """نوشتن اتمیک. در صورت شکست False برمی‌گرداند تا فراخوان بتواند خبر بدهد."""
    tmp=path+".tmp"
    try:
        async with aiofiles.open(tmp,"w",encoding="utf-8") as f:
            await f.write(json.dumps(data,ensure_ascii=False,indent=2))
        os.replace(tmp,path)   # atomic — اگر crash کند فایل اصلی سالم می‌ماند
        return True
    except Exception as e:
        logger.error(f"write {path}: {e}")
        try: os.unlink(tmp)
        except Exception: pass
        return False

async def load_data():
    global responses
    responses=await _rj(DATA_FILE,lambda:dict(MENU_ITEMS,welcome="✨ خوش آمدید به ربات استوک لند"))
async def save_data(): return await _wj(DATA_FILE,responses)

async def load_banners():
    global banners
    banners=await _rj(BANNER_FILE,dict)
    # migration: فرمت قدیمی flat (show_on, caption) → فرمت section-based
    if "show_on" in banners or "caption" in banners:
        old=banners.copy(); banners={}
        for k in SECTION_NAMES:
            if k in old and isinstance(old[k],dict):
                banners[k]=old[k]
        logger.info("banner.json: فرمت قدیمی شناسایی و migrate شد")
        await save_banners()
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
        valid = {d["key"] for d in DEFAULT_MENU}
        # حذف کلیدهایی که دیگر وجود ندارند (مثلاً catalog از نسخه‌های قبلی)
        # وگرنه دکمه‌ای در منو می‌ماند که هیچ هندلری ندارد.
        dropped = [m["key"] for m in menu_cfg if m.get("key") not in valid]
        if dropped:
            menu_cfg = [m for m in menu_cfg if m.get("key") in valid]
            logger.info(f"menu: دکمه‌های منسوخ حذف شدند → {dropped}")
        # اطمینان از وجود همه کلیدها (اگر نسخه قدیمی بود)
        existing = {m["key"] for m in menu_cfg}
        for d in DEFAULT_MENU:
            if d["key"] not in existing: menu_cfg.append(dict(d))
        for m in menu_cfg:
            m.setdefault("width","half")
        if dropped: await save_menu()

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
        settings=dict(DEFAULT_SETTINGS)
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
    # بهینه‌سازی SQLite — ایمن و سریع‌تر
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA synchronous=NORMAL")   # ایمن با WAL، سریع‌تر از FULL
    await db.execute("PRAGMA cache_size=-8000")     # ۸ مگابایت cache در RAM
    await db.execute("PRAGMA temp_store=MEMORY")    # عملیات موقت در RAM
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,username TEXT,first_name TEXT,
            joined_at TEXT,last_seen TEXT,is_blocked INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,
            username TEXT,first_name TEXT,phone TEXT,
            product_id INTEGER,product_name TEXT,
            status TEXT DEFAULT 'new',created_at TEXT);
        CREATE INDEX IF NOT EXISTS idx_ls ON users(last_seen);
        CREATE INDEX IF NOT EXISTS idx_req_uid ON requests(user_id,product_id,created_at);
        CREATE INDEX IF NOT EXISTS idx_req_st ON requests(status);
    """)
    for sql in ["ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0",
                "ALTER TABLE users ADD COLUMN has_left INTEGER DEFAULT 0"]:
        try: await db.execute(sql)
        except Exception as e:
            # «ستون تکراری» یعنی مهاجرت قبلاً انجام شده — بقیه خطاها واقعی‌اند
            if "duplicate column" not in str(e).lower():
                logger.error(f"مهاجرت دیتابیس ناموفق: {sql} → {e}")
    await db.commit()
    # تست واقعی نوشتن — بهتر است همین‌جا با پیام واضح بمیریم تا اینکه بعداً
    # موقع اولین /start کاربر بترکد و ربات ظاهراً «بی‌صدا» شود
    try:
        await db.execute("CREATE TABLE IF NOT EXISTS _wtest(x INTEGER)")
        await db.execute("DROP TABLE IF EXISTS _wtest")
        await db.commit()
    except Exception as e:
        raise SystemExit(
            f"❌ دیتابیس قابل نوشتن نیست: {e}\n"
            f"   مسیر: {os.path.abspath(DB_FILE)}\n"
            f"   کاربرِ اجراکننده‌ی سرویس باید اجازه نوشتن در این پوشه را داشته باشد\n"
            f"   (SQLite علاوه بر فایل دیتابیس، به نوشتن در خودِ پوشه هم نیاز دارد).\n"
            f"   رفع سریع:  sudo chown -R $(whoami) {os.path.dirname(os.path.abspath(DB_FILE))}")

_seen_uids: dict = {}   # uid → زمان آخرین save_user
_SEEN_TTL  = 300        # 5 دقیقه — اگر اخیراً ذخیره شده، skip کن

async def save_user(u):
    now_ts=time.time()
    if u.id in _seen_uids and now_ts-_seen_uids[u.id]<_SEEN_TTL: return
    now=gregorian_now()
    # نام ستون‌ها صریح نوشته می‌شود تا افزودن ستون جدید این کوئری را نشکند
    await db.execute(
        "INSERT OR IGNORE INTO users(user_id,username,first_name,joined_at,last_seen)"
        " VALUES(?,?,?,?,?)",
        (u.id,u.username or"",u.first_name or"",now,now))
    await db.execute("UPDATE users SET username=?,first_name=?,last_seen=? WHERE user_id=?",
        (u.username or"",u.first_name or"",now,u.id))
    await db.commit()
    _seen_uids[u.id]=now_ts

async def get_all_uids():
    async with db.execute("SELECT user_id FROM users WHERE is_blocked=0 AND has_left=0") as c: return[r[0] for r in await c.fetchall()]

async def mark_left(uid, left=1):
    """کاربری که ربات را بلاک/حذف کرده. جدا از is_blocked (که بلاکِ ادمین است)."""
    await db.execute("UPDATE users SET has_left=? WHERE user_id=?",(left,uid)); await db.commit()

async def left_count(): return await _cnt("SELECT COUNT(*) FROM users WHERE has_left=1")

_block_cache: dict = {}   # uid → (is_blocked: bool, expires: float)
_BLOCK_CACHE_TTL = 60     # ثانیه — بعد از این مدت مجدداً از DB خوانده می‌شود

async def is_blocked(uid):
    now=time.time()
    cached=_block_cache.get(uid)
    if cached and cached[1]>now: return cached[0]
    async with db.execute("SELECT is_blocked FROM users WHERE user_id=?",(uid,)) as c:
        r=await c.fetchone()
    result=bool(r and r[0])
    _block_cache[uid]=(result,now+_BLOCK_CACHE_TTL)
    return result

async def set_block(uid,v):
    await db.execute("UPDATE users SET is_blocked=? WHERE user_id=?",(v,uid)); await db.commit()
    _block_cache[uid]=(bool(v),time.time()+_BLOCK_CACHE_TTL)  # فوری cache را آپدیت کن

async def search_users(q):
    q_like=f"%{q}%"
    async with db.execute(
        "SELECT user_id,first_name,username,last_seen,is_blocked FROM users WHERE first_name LIKE ? OR username LIKE ? OR CAST(user_id AS TEXT) LIKE ? ORDER BY last_seen DESC LIMIT 15",
        (q_like,q_like,q_like)) as c: rows=list(await c.fetchall())
    # جستجو با شماره تلفن در جدول درخواست‌ها
    if q.replace("-","").replace(" ","").replace("+","").isdigit():
        async with db.execute(
            "SELECT DISTINCT r.user_id,u.first_name,u.username,u.last_seen,u.is_blocked FROM requests r JOIN users u ON r.user_id=u.user_id WHERE r.phone LIKE ? LIMIT 5",
            (q_like,)) as c: phone_rows=await c.fetchall()
        seen={r[0] for r in rows}
        rows+=[r for r in phone_rows if r[0] not in seen]
    return rows[:15]

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

# ── requests db
async def save_request(uid,username,first_name,phone,topic):
    """درخواست تماس را ثبت می‌کند. اگر کاربر در ۲۴ ساعت اخیر درخواست داده باشد None."""
    async with db.execute(
        "SELECT id FROM requests WHERE user_id=? AND created_at>=datetime('now','-1 day')",
        (uid,)) as c:
        if await c.fetchone(): return None   # تکراری
    cur=await db.execute(
        "INSERT INTO requests(user_id,username,first_name,phone,product_id,product_name,status,created_at)"
        " VALUES(?,?,?,?,?,?,?,?)",
        (uid,username or"",first_name or"",phone,0,topic,"new",gregorian_now()))
    await db.commit()
    return cur.lastrowid

async def get_requests(offset=0,limit=25,only_new=False):
    where = "WHERE status='new' " if only_new else ""
    async with db.execute(
        "SELECT id,user_id,username,first_name,phone,product_name,status,created_at FROM requests "
        f"{where}ORDER BY id DESC LIMIT ? OFFSET ?",
        (limit,offset)) as c: return await c.fetchall()

async def count_requests(only_new=False):
    return await _cnt("SELECT COUNT(*) FROM requests" + (" WHERE status='new'" if only_new else ""))

async def done_request(rid): await db.execute("UPDATE requests SET status='done' WHERE id=?",(rid,)); await db.commit()

# ── anti-spam (سیستم سبک — sliding window، بدون DB query، بدون lock)
_rate:       dict = {}   # uid → [timestamps]
_warned:     dict = {}   # uid → زمان اولین هشدار
_hard_block: dict = {}   # uid → blocked_until timestamp
_RATE_MAX   = 8          # حداکثر کلیک مجاز در پنجره
_RATE_WIN   = 10.0       # پنجره زمانی (ثانیه)
_HARD_BLOCK = 10.0       # مدت بلاک سخت (ثانیه)

async def _spam_cleanup_loop():
    """هر ۶ ساعت دیکشنری‌های anti-spam را از کاربران منقضی پاک می‌کند.
    صفر تاثیر روی سرعت — فقط در زمان idle اجرا می‌شود."""
    while True:
        await asyncio.sleep(6 * 3600)
        now = time.time()
        stale = [uid for uid, ts in list(_rate.items())
                 if not ts or now - max(ts) > _RATE_WIN * 6]
        for uid in stale:
            _rate.pop(uid, None); _warned.pop(uid, None)
        for uid in [u for u, t in list(_hard_block.items()) if t < now]:
            del _hard_block[uid]
        for uid in [u for u,(v,exp) in list(_block_cache.items()) if exp<now]:
            del _block_cache[uid]
        for uid in [u for u,ts in list(_seen_uids.items()) if now-ts>_SEEN_TTL*3]:
            del _seen_uids[uid]
        if stale: logger.debug(f"spam_cleanup: {len(stale)} رکورد منقضی پاک شد")

def spam_check(uid: int) -> str:
    """کاملاً sync — بدون await، بدون DB، صفر overhead.
    بازگشتی: 'ok' | 'warn' | 'block'
      ok    → درخواست معمولی، ادامه بده
      warn  → اولین بار اسپم شناسایی شد — popup هشدار نشان بده، ریپلای نده
      block → کاربر بعد از هشدار ادامه داد — ۱۰ ثانیه بی‌صدا بلاک"""
    if uid == ADMIN_ID: return 'ok'
    now = time.time()
    # بلاک سخت فعال است؟
    if _hard_block.get(uid, 0) > now: return 'block'
    # پنجره نرخ — فقط timestamps داخل _RATE_WIN ثانیه اخیر
    ts = [t for t in _rate.get(uid, ()) if now - t < _RATE_WIN]
    if len(ts) >= _RATE_MAX:
        _rate[uid] = ts
        if uid in _warned:        # هشدار قبلاً داده شده → بلاک سخت ۱۰ ثانیه
            del _warned[uid]
            _hard_block[uid] = now + _HARD_BLOCK
            return 'block'
        _warned[uid] = now        # اولین تخطی → هشدار
        return 'warn'
    ts.append(now); _rate[uid] = ts
    _warned.pop(uid, None)        # کاربر آرام گرفت → هشدار ریست شود
    return 'ok'

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

# ── admin keyboards
def back_admin(): return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به پنل",callback_data="back_to_admin")]])

def backup_kb():
    rows=[
        [InlineKeyboardButton("💾 دریافت پشتیبان",callback_data="backup_get"),
         InlineKeyboardButton("📥 بارگذاری فایل",callback_data="backup_import")]
    ]
    if _backup_registry:
        rows.append([InlineKeyboardButton("──── بکاپ‌های خودکار ────",callback_data="noop")])
        for i,b in enumerate(reversed(_backup_registry)):
            rows.append([InlineKeyboardButton(f"♻️ {b['date']}",callback_data=f"backup_auto_{i}")])
    rows.append([InlineKeyboardButton("🔙 تنظیمات",callback_data="settings_menu")])
    return InlineKeyboardMarkup(rows)

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 داشبورد",callback_data="dash"),
         InlineKeyboardButton("👥 کاربران",callback_data="users_menu")],
        [InlineKeyboardButton("📬 درخواست‌ها",callback_data="admin_reqs")],
        [InlineKeyboardButton("🕐 ساعت کاری",callback_data="wh_menu"),
         InlineKeyboardButton("📣 پخش همگانی",callback_data="broadcast")],
        [InlineKeyboardButton("⚙️ تنظیمات",callback_data="settings_menu")],
    ])

# ترتیب نمایش بخش‌ها — دقیقاً مطابق منوی کاربر
SECTION_ORDER = ["welcome","1","2","3","4","5","contact","workhours","6","7"]

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
    b=get_banner(key)
    ban_lbl="🖼 بنر  🟢 فعال" if(b.get("active") and b.get("file_id")) else("🖼 بنر  ⏸ آپلود‌شده" if b.get("file_id") else"🖼 بنر  ➕ ندارد")
    sec=get_sec_btns(key); n=len(sec.get("items",[])); en=sec.get("enabled")
    btn_lbl=f"🔗 دکمه‌ها  {'🟢' if en else '🔴'}  ({to_fa(n)} عدد)"
    rows=[[InlineKeyboardButton("✏️ ویرایش متن",callback_data=f"sec_text_{key}")]]
    rows.append([InlineKeyboardButton(ban_lbl,callback_data=f"sec_ban_{key}")])
    rows.append([InlineKeyboardButton(btn_lbl,callback_data=f"sec_btns_{key}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت",callback_data="sections")])
    return InlineKeyboardMarkup(rows)

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
    fwd="🟢" if get_setting("forward_user_msgs") else "⚫️"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎛 مدیریت منو",callback_data="menu_mgr")],
        [InlineKeyboardButton("✏️ مدیریت بخش‌ها",callback_data="sections")],
        [InlineKeyboardButton("💾 پشتیبان‌گیری",callback_data="backup")],
        [InlineKeyboardButton(f"{notif} اعلان عضو جدید",callback_data="stg_notify_new_user")],
        [InlineKeyboardButton(f"{fwd} دریافت پیام کاربران",callback_data="stg_forward_user_msgs")],
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
    [InlineKeyboardButton("💬 پیام به کاربر",callback_data=f"rq_msg_{uid}")],
    [InlineKeyboardButton("✅ رفع بلاک" if is_bl else "🚫 بلاک",callback_data=f"utog_{uid}")],
    [InlineKeyboardButton("🔙",callback_data="users_menu")]])

def reqs_kb(reqs,offset=0,total=0,only_new=False):
    f="new" if only_new else "all"
    # نام و شماره مفیدند — product_name برای همه یکسان است و چیزی اضافه نمی‌کند
    btns=[[InlineKeyboardButton(f"{'🆕' if r[6]=='new' else '✅'} {r[3] or'—'} — {r[4]}",
                                callback_data=f"rq_{r[0]}")] for r in reqs]
    nav=[]
    if offset>0: nav.append(InlineKeyboardButton("▶️ جدیدتر",callback_data=f"arq_{f}_{offset-25}"))
    if offset+25<total: nav.append(InlineKeyboardButton("◀️ قدیمی‌تر",callback_data=f"arq_{f}_{offset+25}"))
    if nav: btns.append(nav)
    btns.append([InlineKeyboardButton("📋 همه" if only_new else "🆕 فقط جدیدها",
                                      callback_data=f"arq_{'all' if only_new else 'new'}_0")])
    btns.append([InlineKeyboardButton("📊 Export CSV",callback_data="export_reqs")])
    btns.append([InlineKeyboardButton("🔙",callback_data="back_to_admin")]); return InlineKeyboardMarkup(btns)

def req_kb(rid,status,uid=0):
    btns=[]
    if status=="new":
        btns.append([InlineKeyboardButton("✅ پیگیری شد",callback_data=f"rq_done_{rid}")])
        if uid: btns.append([InlineKeyboardButton("💬 پیام به کاربر",callback_data=f"rq_msg_{uid}")])
    else:
        btns.append([InlineKeyboardButton("☑️ پیگیری شده — بسته شد",callback_data="noop")])
    btns.append([InlineKeyboardButton("🔙",callback_data="admin_reqs")]); return InlineKeyboardMarkup(btns)

# ── send with banner
async def send_banner(msg,text,key,kb=None):
    b=get_banner(key)
    if b.get("active") and b.get("file_id"):
        try: await msg.reply_photo(photo=b["file_id"],caption=text,reply_markup=kb); return
        except Exception as e: logger.error(f"banner[{key}]: {e}")
    await msg.reply_text(text,reply_markup=kb)

# ── broadcast
_broadcast_active = False
_broadcast_cancel = False   # توقف اضطراری

async def broadcast(ctx, text, photo=None):
    global _broadcast_active, _broadcast_cancel
    if _broadcast_active:
        await ctx.bot.send_message(ADMIN_ID, "⚠️ یک پخش در حال اجراست — صبر کنید تا تمام شود.")
        return
    _broadcast_active = True; _broadcast_cancel = False
    try:
        users = await get_all_uids(); total = len(users); ok = fail = gone = 0
        cancel_kb=InlineKeyboardMarkup([[InlineKeyboardButton("🛑 توقف پخش",callback_data="broadcast_cancel")]])
        st = await ctx.bot.send_message(ADMIN_ID, f"📢 شروع پخش به {to_fa(total)} کاربر...", reply_markup=cancel_kb)
        for i, uid in enumerate(users, 1):
            if _broadcast_cancel:
                await st.edit_text(f"🛑 پخش متوقف شد!\n✔️ {to_fa(ok)} | ❌ {to_fa(fail)}",reply_markup=None)
                return
            try:
                if photo: await ctx.bot.send_photo(uid, photo=photo, caption=text)
                else:     await ctx.bot.send_message(uid, text)
                ok += 1
            except Forbidden:
                # کاربر ربات را بلاک کرده یا اکانتش حذف شده — علامت بزن تا
                # پخش‌های بعدی وقت تلف نکنند و آمار واقعی بماند
                gone += 1; fail += 1
                await mark_left(uid)
            except Exception as e:
                retry = getattr(e, "retry_after", None)
                if retry:
                    await asyncio.sleep(retry + 1)
                    try:
                        if photo: await ctx.bot.send_photo(uid, photo=photo, caption=text)
                        else:     await ctx.bot.send_message(uid, text)
                        ok += 1
                    except: fail += 1
                else: fail += 1
            await asyncio.sleep(0.05)   # همیشه — وگرنه زنجیره خطا API را می‌کوبد
            if i % 20 == 0 or i == total:
                try: await st.edit_text(f"📢 {to_fa(ok)}✔️ {to_fa(fail)}❌  {to_fa(i)}/{to_fa(total)}",reply_markup=cancel_kb if i<total else None)
                except: pass
        summary=f"✅ پخش تمام شد!\nموفق: {to_fa(ok)} | شکست: {to_fa(fail)}"
        if gone: summary+=f"\n🚪 {to_fa(gone)} کاربر ربات را بلاک/حذف کرده بود — از لیست پخش کنار گذاشته شد."
        await st.edit_text(summary, reply_markup=None)
    finally:
        _broadcast_active = False; _broadcast_cancel = False

# ── backup
_backup_registry: list = []  # [{"msg_id": int, "file_id": str, "date": str}]
MAX_BACKUPS = 5

async def load_backup_registry():
    """لیست بکاپ‌های خودکار باید ری‌استارت را دوام بیاورد — وگرنه دقیقاً وقتی
    به بازگردانی نیاز دارید (بعد از کرش) لیست خالی است."""
    global _backup_registry
    data = await _rj(BACKUPS_FILE, list)
    if isinstance(data, list): _backup_registry = data
    logger.info(f"backups: {len(_backup_registry)} بکاپ خودکار بارگذاری شد")

async def save_backup_registry(): await _wj(BACKUPS_FILE, _backup_registry)

async def send_backup(bot):
    global _backup_registry
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
    msg=await bot.send_document(ADMIN_ID,document=buf,filename=f"backup_{ts}.zip",
                                caption=f"💾 بک‌آپ — {shamsi_now()}")
    _backup_registry.append({"msg_id":msg.message_id,"file_id":msg.document.file_id,"date":shamsi_now()})
    # اگر بیشتر از MAX_BACKUPS داریم، قدیمی‌ترین را حذف کن
    while len(_backup_registry)>MAX_BACKUPS:
        old=_backup_registry.pop(0)
        try: await bot.delete_message(ADMIN_ID,old["msg_id"])
        except Exception as e: logger.debug(f"backup delete old: {e}")
    await save_backup_registry()

async def _auto_backup_loop(bot):
    """هر شب ساعت ۳ بامداد به وقت تهران، بکاپ خودکار به ادمین می‌فرستد."""
    _tz = pytz.timezone("Asia/Tehran")
    last_backup_date = None   # جلوگیری از backup تکراری در همان روز
    while True:
        try:
            now = datetime.now(_tz)
            today = now.date()
            target = now.replace(hour=3, minute=0, second=0, microsecond=0)
            if now >= target and last_backup_date != today:
                await send_backup(bot)
                last_backup_date = today
                logger.info("✅ بکاپ خودکار ارسال شد")
                await asyncio.sleep(3600)   # یک ساعت صبر کن تا دوباره چک نشود
                continue
            if now < target:
                wait = (target - now).total_seconds()
            else:
                target += timedelta(days=1)
                wait = (target - now).total_seconds()
            logger.info(f"auto_backup: بعد از {int(wait//3600)}h {int((wait%3600)//60)}m")
            await asyncio.sleep(wait)
        except Exception as e:
            logger.error(f"auto_backup: {e}")
            await asyncio.sleep(3600)

BACKUP_MAP = {"data.json":DATA_FILE,"banner.json":BANNER_FILE,"workhours.json":WORKHOURS_FILE,
              "buttons.json":BUTTONS_FILE,"settings.json":SETTINGS_FILE,"stats.json":STATS_FILE,
              "menu.json":MENU_FILE,"users.db":DB_FILE}
SQLITE_MAGIC = b"SQLite format 3\x00"
MAX_RESTORE_BYTES = 200 * 1024 * 1024   # سقف ایمنی برای فایل‌های داخل ZIP

async def _safety_snapshot():
    """قبل از بازگردانی، وضعیت فعلی را کنار می‌گذارد تا اگر بکاپ خراب بود برگردیم."""
    path = os.path.join(os.path.dirname(os.path.abspath(DB_FILE)), "pre_restore.zip")
    try:
        with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED) as zf:
            for name,fp in BACKUP_MAP.items():
                if os.path.exists(fp): zf.write(fp,name)
        return path
    except Exception as e:
        logger.warning(f"safety snapshot ناموفق: {e}"); return None

async def restore_backup(bot,file_id):
    """بازگردانی بکاپ.

    نکته حیاتی: users.db در حالت WAL باز است. اگر فایل را زیر پای اتصالِ باز
    عوض کنیم، فایل‌های users.db-wal / -shm قدیمی روی داده‌ی تازه اعمال می‌شوند
    و بازگردانی عملاً بی‌اثر می‌ماند. پس باید اتصال بسته، WAL پاک، و دوباره
    باز شود.
    """
    global db, _seen_uids, _block_cache
    try:
        f=await bot.get_file(file_id); buf=io.BytesIO()
        await f.download_to_memory(buf); buf.seek(0)
        with zipfile.ZipFile(buf,"r") as zf:
            members=[i for i in zf.infolist() if i.filename in BACKUP_MAP]
            if not members:
                return False,"این فایل ZIP هیچ‌کدام از فایل‌های بکاپ را ندارد."
            total=sum(i.file_size for i in members)
            if total>MAX_RESTORE_BYTES:
                return False,f"حجم بکاپ غیرعادی است ({total//1024//1024} مگابایت) — بازگردانی انجام نشد."
            payload={i.filename:zf.read(i.filename) for i in members}

        # اعتبارسنجی پیش از دست‌زدن به هر فایلی
        if "users.db" in payload and not payload["users.db"].startswith(SQLITE_MAGIC):
            return False,"فایل users.db داخل ZIP یک دیتابیس معتبر نیست."
        for name in ("data.json","banner.json","workhours.json","buttons.json","settings.json","stats.json","menu.json"):
            if name in payload:
                try: json.loads(payload[name].decode("utf-8"))
                except Exception: return False,f"فایل {name} داخل ZIP خراب است."

        snapshot=await _safety_snapshot()

        # اتصال را ببند تا جایگزینی users.db امن باشد
        if "users.db" in payload and db is not None:
            try: await db.close()
            except Exception as e: logger.warning(f"بستن دیتابیس: {e}")
            db=None

        restored=[]
        for name,data_bytes in payload.items():
            async with aiofiles.open(BACKUP_MAP[name],"wb") as out: await out.write(data_bytes)
            restored.append(name)

        if "users.db" in payload:
            # WAL/SHM قدیمی متعلق به دیتابیس قبلی‌اند و باید بروند
            for suffix in ("-wal","-shm"):
                try: os.remove(DB_FILE+suffix)
                except FileNotFoundError: pass
                except Exception as e: logger.warning(f"حذف {DB_FILE+suffix}: {e}")
            _seen_uids={}; _block_cache={}
            await init_db()

        await load_data(); await load_banners(); await load_workhours()
        await load_buttons(); await load_settings(); await load_stats(); await load_menu()
        # نرمال‌سازی فرمت فایل‌ها روی دیسک (جلوگیری از مشکل فرمت قدیمی بعد از restart)
        await save_banners(); await save_buttons()
        if snapshot: logger.info(f"بکاپ ایمنی پیش از بازگردانی: {snapshot}")
        return True,restored
    except Exception as e:
        logger.error(f"restore: {e}",exc_info=True)
        # اگر اتصال بسته مانده، دوباره بازش کن تا ربات فلج نشود
        if db is None:
            try: await init_db()
            except Exception as e2: logger.error(f"بازگشایی دیتابیس ناموفق: {e2}")
        return False,str(e)

# ════════════════════════════════════════════════
#  HANDLERS — cmd_start / cmd_admin
# ════════════════════════════════════════════════
async def cmd_start(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    user=update.effective_user; is_new=False
    async with db.execute("SELECT user_id FROM users WHERE user_id=?",(user.id,)) as c: is_new=(await c.fetchone()) is None
    await save_user(user)
    await mark_left(user.id,0)   # اگر قبلاً ربات را بلاک کرده بود و برگشته، دوباره فعالش کن
    if get_setting("notify_new_user") and is_new:
        try: await ctx.bot.send_message(ADMIN_ID,f"🆕 کاربر جدید!\n👤 {user.first_name or'—'}\n{'@'+user.username if user.username else'—'}\n🆔 {user.id}")
        except: pass
    wt=responses.get("welcome","✨ خوش آمدید")
    full=build_msg("خوش‌آمدگویی",wt,"welcome")
    # منوی پایین همیشه باید ست شود — تلگرام هر پیام را فقط با یک نوع کیبورد
    # می‌پذیرد، پس اگر بخش خوش‌آمد دکمه لینک داشته باشد، لینک‌ها جدا می‌روند.
    await send_banner(update.message,full,"welcome",kb=main_menu())
    links=user_sec_kb("welcome")
    if links:
        await update.message.reply_text("🔗 لینک‌های مفید:",reply_markup=links)

async def cmd_help(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    txt=("ℹ️ راهنمای ربات استوک لند\n"+"─"*18+
         "\n\n• از دکمه‌های منوی پایین استفاده کنید."
         "\n• برای درخواست تماس، «📝 درخواست تماس» را بزنید و شماره‌تان را بگذارید."
         "\n• هر سؤالی داشتید همین‌جا بنویسید — پیامتان مستقیم به پشتیبانی می‌رسد."
         "\n\n/start — شروع دوباره و نمایش منو")
    await update.message.reply_text(txt,reply_markup=main_menu())

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

# ════════════════════════════════════════════════
#  MAIN CALLBACK DISPATCHER
# ════════════════════════════════════════════════
# پیشوندهایی که هم ادمین هم کاربر دسترسی دارد
_USER_CB_PREFIXES = ("wh_weekly","wh_back_today")

async def callbacks(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    query=update.callback_query
    data=query.data; uid=query.from_user.id

    # ── محافظت اسپم
    if uid!=ADMIN_ID:
        _s=spam_check(uid)
        if _s=='block':
            await query.answer(); return
        if _s=='warn':
            await query.answer("🐢 لطفاً کمی آرام‌تر کلیک کنید.",show_alert=True); return
    if uid!=ADMIN_ID:
        if await is_blocked(uid):
            await query.answer("⛔ دسترسی شما مسدود شده است."); return

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

        elif data=="dash":
            await query.answer()
            t,d,w,m,nt,bl,lf=await asyncio.gather(
                total_users(),today_users(),week_users(),
                month_users(),new_today(),blk_count(),left_count())
            sep="─"*22
            dash=(f"📊 داشبورد — {shamsi_now()}\n{sep}"
                  f"\n👥 کل کاربران: {to_fa(t)}     🚫 بلاک: {to_fa(bl)}"
                  f"\n✅ فعال: {to_fa(t-lf)}     🚪 ترک‌کرده: {to_fa(lf)}"
                  f"\n{sep}"
                  f"\n🆕 عضو امروز:   {to_fa(nt)}"
                  f"\n📅 فعال امروز:  {to_fa(d)}   {progress_bar(d,t)}"
                  f"\n📆 فعال هفته:   {to_fa(w)}   {progress_bar(w,t)}"
                  f"\n🗓  فعال ماه:    {to_fa(m)}   {progress_bar(m,t)}"
                  f"\n{sep}")
            if len(dash)>4000: dash=dash[:3990]+"..."
            await safe_edit(query.message,dash,reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📈 آمار بخش‌ها",callback_data="stats_page")],
                [InlineKeyboardButton("🔙 پنل اصلی",callback_data="back_to_admin")]]))

        elif data=="stats_page":
            await query.answer()
            # نام قابل‌فهم برای هر کلید آماری
            labels=dict(SECTION_NAMES); labels["wh_page"]="🕐 ساعت کاری"
            rows=[(labels.get(k,k),v) for k,v in stats.items() if v]
            rows.sort(key=lambda r:-r[1])
            sep="─"*22
            if not rows:
                txt=f"📈 آمار بخش‌ها\n{sep}\n\nهنوز بازدیدی ثبت نشده است."
            else:
                top=rows[0][1]
                lines=[f"{progress_bar(v,top)}  {to_fa(v)}  {name}" for name,v in rows]
                txt=(f"📈 آمار بخش‌ها — {shamsi_now()}\n{sep}\n"
                     + "\n".join(lines)
                     + f"\n{sep}\n📊 مجموع بازدید: {to_fa(sum(v for _,v in rows))}")
            if len(txt)>4000: txt=txt[:3990]+"..."
            await safe_edit(query.message,txt,reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 صفر کردن آمار",callback_data="stats_reset")],
                [InlineKeyboardButton("🔙 داشبورد",callback_data="dash")]]))

        elif data=="stats_reset":
            stats.clear(); await save_stats()
            await query.answer("✅ آمار صفر شد",show_alert=True)
            await safe_edit(query.message,"📈 آمار بخش‌ها\n\nآمار صفر شد.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 داشبورد",callback_data="dash")]]))

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
            await send_backup(ctx.bot)
            await safe_edit(query.message,"✅ بک‌آپ ارسال شد.",reply_markup=backup_kb())

        elif data.startswith("backup_auto_"):
            # فقط تأیید — بازگردانی کل کاربران و تنظیمات را جایگزین می‌کند
            idx=int(data[12:])
            registry_rev=list(reversed(_backup_registry))
            if idx>=len(registry_rev):
                await query.answer("❌ بکاپ یافت نشد.",show_alert=True); return
            entry=registry_rev[idx]
            await query.answer()
            await safe_edit(query.message,
                f"⚠️ بازگردانی از بکاپ {entry['date']}\n"+"─"*18+
                "\n\nتمام کاربران، درخواست‌ها، متن‌ها و تنظیمات فعلی با نسخه‌ی این "
                "بکاپ جایگزین می‌شوند.\n\n"
                "(از وضعیت فعلی یک نسخه‌ی ایمنی در pre_restore.zip نگه داشته می‌شود.)",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ بله، بازگردان",callback_data=f"backup_do_{idx}")],
                    [InlineKeyboardButton("↩️ انصراف",callback_data="backup")]]))

        elif data.startswith("backup_do_"):
            idx=int(data[10:])
            registry_rev=list(reversed(_backup_registry))
            if idx>=len(registry_rev):
                await query.answer("❌ بکاپ یافت نشد.",show_alert=True); return
            entry=registry_rev[idx]
            await query.answer()
            await safe_edit(query.message,f"⏳ در حال بازگردانی از {entry['date']}...",reply_markup=None)
            ok,result=await restore_backup(ctx.bot,entry["file_id"])
            if ok:
                await safe_edit(query.message,f"✅ بازگردانی شد.\nفایل‌ها: {', '.join(result)}",reply_markup=backup_kb())
            else:
                await safe_edit(query.message,f"❌ خطا: {result}",reply_markup=backup_kb())

        elif data=="backup_import":
            await query.answer()
            ctx.user_data["mode"]="backup_restore"
            await query.message.reply_text(
                "📥 فایل ZIP بک‌آپ را ارسال کنید.\n\n"
                "⚠️ محتوای فایل جایگزین کاربران، درخواست‌ها و تنظیمات فعلی می‌شود.",
                reply_markup=cancel_menu())

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
            key=data[9:]
            await query.answer()
            ctx.user_data.update({"mode":"edit_text","edit_key":key})
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
            key=data[9:]
            await query.answer()
            sec=get_sec_btns(key)
            await safe_edit(query.message,
                f"🔘 دکمه‌های {SECTION_NAMES.get(key,key)}\n"
                f"{'✅ فعال' if sec.get('enabled') else '❌ غیرفعال'} | {to_fa(len(sec.get('items',[])))} عدد",
                reply_markup=sec_btns_kb(key))

        elif data.startswith("btn_tg_"):
            key=data[7:]
            sec=get_sec_btns(key); sec["enabled"]=not sec.get("enabled",False); await save_buttons()
            await query.answer("✅ فعال" if sec["enabled"] else"❌ غیرفعال",show_alert=True)
            await safe_edit(query.message,f"🔘 {SECTION_NAMES.get(key,key)} | {'✅' if sec['enabled'] else '❌'}",reply_markup=sec_btns_kb(key))

        elif data.startswith("btn_add_"):
            key=data[8:]
            await query.answer()
            ctx.user_data.update({"mode":"btn_add_t","btn_key":key})
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
        elif data=="admin_reqs" or data.startswith("arq_"):
            await query.answer()
            only_new=False; offset=0
            if data.startswith("arq_"):
                try:
                    _,f,off=data.split("_",2); only_new=(f=="new"); offset=max(0,int(off))
                except Exception: only_new=False; offset=0
            reqs=await get_requests(offset=offset,limit=25,only_new=only_new)
            total=await count_requests(only_new=only_new)
            new_total=await count_requests(only_new=True)
            if not reqs and offset==0:
                await safe_edit(query.message,
                    "📋 درخواست جدیدی نیست." if only_new else "📋 درخواستی وجود ندارد.",
                    reply_markup=reqs_kb([],0,0,only_new)); return
            rng=f"{to_fa(offset+1)}–{to_fa(min(offset+25,total))}"
            title="🆕 درخواست‌های جدید" if only_new else "📋 همه درخواست‌ها"
            await safe_edit(query.message,
                f"{title}  [{rng} از {to_fa(total)}]\n🆕 در انتظار پیگیری: {to_fa(new_total)}",
                reply_markup=reqs_kb(reqs,offset,total,only_new))

        elif data=="bc_go":
            txt=ctx.user_data.pop("bc_text",None); ph=ctx.user_data.pop("bc_photo",None)
            if txt is None and ph is None:
                await query.answer("❌ پیامی برای ارسال نیست.",show_alert=True); return
            await query.answer()
            await safe_edit(query.message,"📤 در حال ارسال...",reply_markup=None)
            await broadcast(ctx,txt or "",photo=ph)

        elif data=="bc_no":
            ctx.user_data.pop("bc_text",None); ctx.user_data.pop("bc_photo",None)
            await query.answer("لغو شد")
            await safe_edit(query.message,"↩️ پخش لغو شد — هیچ پیامی ارسال نشد.",
                            reply_markup=back_admin())

        elif data=="broadcast_cancel":
            global _broadcast_cancel
            _broadcast_cancel=True
            await query.answer("🛑 در حال توقف پخش...")

        elif data=="export_reqs":
            await query.answer()
            await safe_edit(query.message,"📊 در حال آماده‌سازی فایل CSV...",reply_markup=None)
            async with db.execute(
                "SELECT id,product_name,first_name,username,phone,user_id,status,created_at FROM requests ORDER BY id DESC") as c:
                rows=await c.fetchall()
            buf=io.StringIO()
            w=csv.writer(buf)
            w.writerow(["#","محصول","نام","یوزرنیم","تلفن","آیدی","وضعیت","تاریخ"])
            for r in rows:
                w.writerow([r[0],r[1],r[2],r[3] or"-",r[4],r[5],"پیگیری شده" if r[6]=="done" else"جدید",r[7]])
            fname=f"requests_{shamsi_now().replace(' ','_').replace(':','-')}.csv"
            await ctx.bot.send_document(ADMIN_ID,
                document=buf.getvalue().encode("utf-8-sig"),  # BOM برای Excel
                filename=fname,caption=f"📊 {to_fa(len(rows))} درخواست")
            await safe_edit(query.message,"✅ فایل CSV ارسال شد.",reply_markup=back_admin())

        elif data.startswith("rq_done_"):
            rid=int(data[8:])
            async with db.execute("SELECT user_id,product_name,status FROM requests WHERE id=?",(rid,)) as c:
                req_row=await c.fetchone()
            if not req_row:
                await query.answer("❌ درخواست یافت نشد.",show_alert=True); return
            if req_row[2]=="done":
                await query.answer("⚠️ این درخواست قبلاً پیگیری شده است.",show_alert=True)
                try: await query.message.edit_reply_markup(reply_markup=None)
                except: pass
                return
            await done_request(rid)
            await query.answer("✅ پیگیری شد",show_alert=False)
            # تشخیص: از اعلان (notification) یا از پنل مدیریت؟
            is_notif=query.message.reply_markup and any(
                btn.callback_data and btn.callback_data.startswith("rq_msg_")
                for row in query.message.reply_markup.inline_keyboard for btn in row)
            if is_notif:
                try: await query.message.edit_reply_markup(reply_markup=None)
                except: pass
            else:
                reqs=await get_requests(limit=25); total=await count_requests()
                nc=await count_requests(only_new=True)
                await safe_edit(query.message,
                    f"📋 درخواست‌ها — ✅ پیگیری شد\n🆕 در انتظار پیگیری: {to_fa(nc)} | کل: {to_fa(total)}",
                    reply_markup=reqs_kb(reqs,0,total))
            try:
                await ctx.bot.send_message(req_row[0],
                    "✅ درخواست شما پیگیری شد.\nبه زودی با شما تماس خواهیم گرفت. 🙏")
            except Forbidden:
                await mark_left(req_row[0])
                logger.info(f"req_done: کاربر {req_row[0]} ربات را بلاک کرده")
            except Exception as e: logger.warning(f"req_done notify: {e}")

        elif data.startswith("rq_msg_"):
            target_uid=int(data[7:])
            await query.answer()
            ctx.user_data.update({"mode":"admin_msg","admin_msg_uid":target_uid})
            await query.message.reply_text(
                f"💬 پیام برای کاربر 🆔{target_uid}\nمتن یا تصویر را ارسال کنید:",
                reply_markup=cancel_menu())

        elif data=="noop": await query.answer()

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
            await safe_edit(query.message,txt,reply_markup=req_kb(rid,r[6],r[1]))

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
            async with db.execute("SELECT user_id,first_name,username,joined_at,last_seen,is_blocked,has_left FROM users WHERE user_id=?",(uid2,)) as c: row=await c.fetchone()
            if not row: await query.answer("یافت نشد!",show_alert=True); return
            await query.answer()
            sep="─"*20
            status="🚫 بلاک‌شده توسط شما" if row[5] else ("🚪 ربات را بلاک/حذف کرده" if row[6] else "✅ فعال")
            utxt=(f"👤 {row[1] or'—'}"
                  f"\n{'@'+row[2] if row[2] else'بدون یوزرنیم'}"
                  f"\n🆔 {row[0]}"
                  f"\n{sep}"
                  f"\n📅 عضویت: {row[3]}"
                  f"\n🕐 آخرین فعالیت: {row[4]}"
                  f"\n{sep}"
                  f"\n{status}")
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
    if user.id != ADMIN_ID:
        # حین ثبت شماره تماس، spam block اعمال نشود تا درخواست گم نشود
        if ctx.user_data.get("mode")!="req_phone":
            _s=spam_check(user.id)
            if _s=='block': return
            if _s=='warn': return await update.message.reply_text("🐢 لطفاً آرام‌تر پیام دهید.")
        if await is_blocked(user.id): return
    if text=="❌ لغو عملیات":
        ctx.user_data.clear(); return await update.message.reply_text("❌ لغو شد.",reply_markup=main_menu())
    mode=ctx.user_data.get("mode")

    # ════ ADMIN ════
    if user.id==ADMIN_ID:
        if mode=="edit_text":
            key=ctx.user_data.pop("edit_key",None); ctx.user_data.pop("mode",None)
            saved=True
            if key:
                responses[key]=text; saved=await save_data()
            await update.message.reply_text(
                "✅ ذخیره شد." if saved else
                "⚠️ متن در حافظه اعمال شد ولی روی دیسک ذخیره نشد!\n"
                "فضای دیسک یا دسترسی نوشتن سرور را بررسی کنید — با ری‌استارت از بین می‌رود.",
                reply_markup=main_menu()); return
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
            ctx.user_data.pop("mode",None)
            ctx.user_data["bc_text"]=text; ctx.user_data.pop("bc_photo",None)
            n=len(await get_all_uids())
            await update.message.reply_text("👁 پیش‌نمایش پیام:",reply_markup=main_menu())
            await update.message.reply_text(text)
            await update.message.reply_text(
                f"📢 این پیام برای {to_fa(n)} کاربر ارسال می‌شود.\nتأیید می‌کنید؟",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ ارسال کن",callback_data="bc_go")],
                    [InlineKeyboardButton("↩️ انصراف",callback_data="bc_no")]]))
            return
        if mode=="admin_msg":
            target_uid=ctx.user_data.pop("admin_msg_uid",None); ctx.user_data.pop("mode",None)
            if not target_uid: await update.message.reply_text("❌ خطا.",reply_markup=main_menu()); return
            try:
                await ctx.bot.send_message(target_uid,f"📩 پیام از فروشگاه:\n\n{text}")
                await update.message.reply_text("✅ پیام ارسال شد.",reply_markup=main_menu())
            except Forbidden:
                await mark_left(target_uid)
                await update.message.reply_text(
                    "🚪 این کاربر ربات را بلاک یا حذف کرده — پیام به او نمی‌رسد.\n"
                    "از فهرست پخش همگانی کنار گذاشته شد.",reply_markup=main_menu())
            except Exception as e:
                await update.message.reply_text(f"❌ خطا در ارسال: {e}",reply_markup=main_menu())
            return
        if mode=="users_search":
            ctx.user_data.pop("mode",None); rows=await search_users(text)
            if not rows: await update.message.reply_text("❌ یافت نشد.",reply_markup=main_menu()); return
            lines=[f"{'🚫 ' if r[4] else ''}{r[1] or'—'} | {r[0]} | {'@'+r[2] if r[2] else'—'}" for r in rows]
            await update.message.reply_text("🔍 نتایج:\n\n"+"\n".join(lines),reply_markup=main_menu()); return
        if mode=="btn_add_t":
            ctx.user_data.update({"btn_title":text,"mode":"btn_add_u"})
            await update.message.reply_text("🔗 لینک:",reply_markup=cancel_menu()); return
        if mode=="btn_add_u":
            url=normalize_url(text)
            if not url:
                # حالت را نگه می‌داریم تا ادمین دوباره وارد کند — لینک نامعتبر
                # کل بخش را برای همه کاربران خراب می‌کند
                await update.message.reply_text(
                    "❌ لینک معتبر نیست.\nمثال: https://instagram.com/stockland یا t.me/stlandd",
                    reply_markup=cancel_menu()); return
            key=ctx.user_data.pop("btn_key",None); title=ctx.user_data.pop("btn_title","دکمه"); ctx.user_data.pop("mode",None)
            sec=get_sec_btns(key); sec["items"].append({"id":new_btn_id(),"title":title,"url":url})
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
            dk=ctx.user_data.get("wh_day")
            bad="❌ فرمت اشتباه!\nساعت‌ها باید به شکل HH:MM باشند.\nمثال: 11:00-14:00,17:00-23:00"
            try:
                parts=[p.strip() for p in text.translate(FA_DIGITS).split(",") if p.strip()]
                sh=[{"from":p.split("-")[0].strip(),"to":p.split("-")[1].strip()} for p in parts]
            except Exception:
                await update.message.reply_text(bad,reply_markup=cancel_menu()); return
            if not sh or not all(valid_shift(x) for x in sh):
                # حالت را نگه می‌داریم تا ادمین بتواند دوباره تلاش کند
                await update.message.reply_text(bad,reply_markup=cancel_menu()); return
            if dk not in workhours.get("schedule",{}):
                ctx.user_data.pop("mode",None); ctx.user_data.pop("wh_day",None)
                await update.message.reply_text("❌ روز نامعتبر.",reply_markup=main_menu()); return
            ctx.user_data.pop("mode",None); ctx.user_data.pop("wh_day",None)
            workhours["schedule"][dk]["shifts"]=sh; await save_workhours()
            note="\n\n🌙 شیفت نیمه‌شب‌گذر ثبت شد." if any(x["from"]>x["to"] for x in sh) else ""
            await update.message.reply_text(f"✅ ذخیره شد.{note}",reply_markup=main_menu())
            return
        if mode=="wh_mop":
            ctx.user_data.pop("mode",None); workhours["msg_open"]=text; await save_workhours()
            await update.message.reply_text("✅",reply_markup=main_menu()); return
        if mode=="wh_mcl":
            ctx.user_data.pop("mode",None); workhours["msg_closed"]=text; await save_workhours()
            await update.message.reply_text("✅",reply_markup=main_menu()); return

    # ════ درخواست تماس — دریافت شماره ════
    if mode=="req_phone":
        digits=text.replace("-","").replace(" ","").replace("+","")
        digits=digits.translate(FA_DIGITS)
        if not digits.isdigit() or not 10<=len(digits)<=13:
            await update.message.reply_text(
                "❌ شماره معتبر نیست. مثال: ۰۹۱۲۳۴۵۶۷۸۹\nدوباره وارد کنید:",
                reply_markup=cancel_menu()); return
        ctx.user_data.pop("mode",None)
        rid=await save_request(user.id,user.username,user.first_name,digits,"درخواست تماس")
        if rid is None:
            await update.message.reply_text(
                "⚠️ شما در ۲۴ ساعت گذشته درخواست ثبت کرده‌اید.\nپشتیبانی در حال بررسی است. 🙏",
                reply_markup=main_menu()); return
        try:
            req_kb=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ پیگیری شد",callback_data=f"rq_done_{rid}"),
                 InlineKeyboardButton("💬 پیام به کاربر",callback_data=f"rq_msg_{user.id}")]])
            await ctx.bot.send_message(ADMIN_ID,
                f"📝 درخواست تماس جدید!\n📞 {digits}\n"
                f"👤 {user.first_name or'—'} | {'@'+user.username if user.username else'—'}\n🆔 {user.id}",
                reply_markup=req_kb)
        except Exception as e: logger.error(f"req notify: {e}")
        await update.message.reply_text(
            "✅ درخواست شما ثبت شد!\nپشتیبانی به زودی با شما تماس می‌گیرد. 🙏",
            reply_markup=main_menu()); return

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

    if mkey=="contact":
        await record_stat("contact")
        if not is_open():
            await update.message.reply_text(
                "🔴 فروشگاه در حال حاضر بسته است.\n"
                "لطفاً در ساعات کاری دوباره تلاش کنید تا سریع‌تر پاسخ بگیرید.",
                reply_markup=main_menu()); return
        intro=responses.get("contact") or CONTACT_DEFAULT_TEXT
        ctx.user_data["mode"]="req_phone"
        await send_banner(update.message,f"{intro}\n\n📞 شماره تماس خود را وارد کنید:",
                          "contact",kb=cancel_menu()); return

    # بخش‌های متنی (۱ تا ۵)
    if mkey and mkey in MENU_ITEMS:
        await record_stat(mkey); content=responses.get(mkey,"تنظیم نشده")
        full=build_msg(text,content,mkey)
        kb=user_sec_kb(mkey)
        await send_banner(update.message,full,mkey,kb=kb); return

    # پیام آزاد کاربر — به‌جای «گزینه نامعتبر»، برای ادمین فوروارد می‌شود
    if user.id!=ADMIN_ID and get_setting("forward_user_msgs"):
        try:
            fwd=await ctx.bot.forward_message(ADMIN_ID,update.message.chat_id,
                                              update.message.message_id)
            await ctx.bot.send_message(ADMIN_ID,
                f"💬 پیام از کاربر\n👤 {user.first_name or'—'} | "
                f"{'@'+user.username if user.username else'—'}\n🆔 {user.id}",
                reply_to_message_id=fwd.message_id,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💬 پاسخ",callback_data=f"rq_msg_{user.id}")]]))
            await update.message.reply_text(
                "✅ پیام شما برای پشتیبانی ارسال شد.\nبه‌زودی پاسخ می‌دهیم. 🙏",
                reply_markup=main_menu()); return
        except Exception as e:
            logger.error(f"forward user msg: {e}")
    await update.message.reply_text(
        "لطفاً یکی از گزینه‌های منوی زیر را انتخاب کنید 👇",reply_markup=main_menu())

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
        ctx.user_data["bc_text"]=caption; ctx.user_data["bc_photo"]=photo.file_id
        n=len(await get_all_uids())
        await update.message.reply_text(
            f"👁 این تصویر برای {to_fa(n)} کاربر ارسال می‌شود.\nتأیید می‌کنید؟",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ ارسال کن",callback_data="bc_go")],
                [InlineKeyboardButton("↩️ انصراف",callback_data="bc_no")]]))
        return
    if mode=="admin_msg":
        target_uid=ctx.user_data.pop("admin_msg_uid",None); ctx.user_data.pop("mode",None)
        caption=update.message.caption or""
        if not target_uid: await update.message.reply_text("❌ خطا.",reply_markup=main_menu()); return
        try:
            await ctx.bot.send_photo(target_uid,photo=photo.file_id,
                caption=f"📩 پیام از فروشگاه:\n\n{caption}" if caption else "📩 پیام از فروشگاه")
            await update.message.reply_text("✅ تصویر ارسال شد.",reply_markup=main_menu())
        except Forbidden:
            await mark_left(target_uid)
            await update.message.reply_text(
                "🚪 این کاربر ربات را بلاک یا حذف کرده — پیام به او نمی‌رسد.",reply_markup=main_menu())
        except Exception as e:
            await update.message.reply_text(f"❌ خطا در ارسال: {e}",reply_markup=main_menu())
        return

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
    await load_stats(); await load_menu(); await load_backup_registry()
    asyncio.ensure_future(_spam_cleanup_loop())
    asyncio.ensure_future(_stats_flush_loop())
    asyncio.ensure_future(_auto_backup_loop(app.bot))
    try:
        await app.bot.set_my_commands([BotCommand("start","شروع و نمایش منو"),
                                       BotCommand("help","راهنما")])
    except Exception as e: logger.warning(f"set_my_commands: {e}")
    logger.info("✅ ربات راه‌اندازی شد")

async def on_error(update:object,ctx:ContextTypes.DEFAULT_TYPE):
    """هر خطای گرفته‌نشده — به ادمین گزارش می‌شود و کاربر بی‌پاسخ نمی‌ماند."""
    if isinstance(ctx.error,Conflict):
        logger.error("⛔ Conflict — یک نسخه دیگر از همین ربات هم‌زمان در حال اجراست. "
                     "با `systemctl status telegram-bot` و `pgrep -af bot.py` بررسی کنید "
                     "و نسخه اضافی را ببندید.")
        return
    logger.error("خطای گرفته‌نشده:",exc_info=ctx.error)
    # ۱) کاربر بی‌پاسخ نماند
    try:
        if isinstance(update,Update) and update.effective_message:
            await update.effective_message.reply_text(
                "❌ خطایی رخ داد. لطفاً دوباره تلاش کنید یا /start را بزنید.")
    except Exception: pass
    # ۲) ادمین خبردار شود (با محدودیت نرخ تا در خطای پیاپی اسپم نشود)
    global _last_err_report
    now=time.time()
    if now-_last_err_report < _ERR_REPORT_GAP: return
    _last_err_report=now
    try:
        tb="".join(traceback.format_exception(type(ctx.error),ctx.error,ctx.error.__traceback__))[-1200:]
        who=""
        if isinstance(update,Update) and update.effective_user:
            u=update.effective_user; who=f"\n👤 {u.first_name or'—'} | 🆔 {u.id}"
        await ctx.bot.send_message(ADMIN_ID,f"⚠️ خطای ربات{who}\n\n<pre>{html.escape(tb)}</pre>",
                                   parse_mode="HTML")
    except Exception as e: logger.error(f"گزارش خطا به ادمین نرسید: {e}")

async def post_shutdown(app):
    """قبل از خاموش‌شدن — داده‌های in-memory را flush کن تا چیزی گم نشود."""
    if _stats_dirty:   await save_stats();   logger.info("shutdown: stats saved")
    logger.info("✅ shutdown clean")

def main():
    app=ApplicationBuilder().token(TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()
    app.add_handler(CommandHandler("start",cmd_start))
    app.add_handler(CommandHandler("help",cmd_help))
    app.add_handler(CommandHandler("admin",cmd_admin))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND,photo_handler))
    app.add_handler(MessageHandler(filters.Document.ZIP & ~filters.COMMAND,document_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler))
    app.add_error_handler(on_error)
    print("🚀 ربات در حال اجراست...")
    app.run_polling(drop_pending_updates=True, poll_interval=0.0, timeout=30)

if __name__=="__main__":
    main()