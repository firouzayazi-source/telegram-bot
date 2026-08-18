"""
پنل وب مدیریت استوک لند
به همان دیتابیس و فایل‌های بات وصل است.
"""
import os, json, sqlite3, time, secrets, functools, hmac, logging
from flask import (Flask, request, session, redirect, url_for, jsonify,
                   render_template_string, send_from_directory, abort)

# ── مسیرها (هماهنگ با bot.py) ───────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
DB_FILE       = os.path.join(BASE, "users.db")
DATA_FILE     = os.path.join(BASE, "data.json")
WORKHOURS_FILE= os.path.join(BASE, "workhours.json")
BUTTONS_FILE  = os.path.join(BASE, "buttons.json")
SETTINGS_FILE = os.path.join(BASE, "settings.json")
STATS_FILE    = os.path.join(BASE, "stats.json")
BANNER_FILE   = os.path.join(BASE, "banner.json")
BANNERMAP_FILE= os.path.join(BASE, "banner_files.json")  # file_id تلگرام → فایل محلی (پیش‌نمایش پنل)
UPLOAD_DIR    = os.path.join(BASE, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

logger = logging.getLogger("web")

# ── احراز هویت پنل ───────────────────────────────
# WEB_PASSWORD نام اصلی است؛ PANEL_PASS فقط برای سازگاری با نصب‌های قدیمی
# خوانده می‌شود. رمز پیش‌فرض عمداً وجود ندارد — پنل روی اینترنت باز است.
PANEL_USER = (os.environ.get("PANEL_USER") or "admin").strip()
PANEL_PASS = (os.environ.get("WEB_PASSWORD") or os.environ.get("PANEL_PASS") or "").strip()

if not PANEL_PASS:
    raise SystemExit(
        "❌ رمز پنل وب تنظیم نشده است.\n"
        "   پنل روی اینترنت در دسترس است و بدون رمز بالا نمی‌آید.\n"
        "   یک رمز قوی ست کنید:\n"
        "       export WEB_PASSWORD='یک-رمز-قوی'\n"
        "   (در systemd: Environment=WEB_PASSWORD=...)"
    )

app = Flask(__name__)
# اگر PANEL_SECRET ست نشود، هر ری‌استارت کلید جدید می‌سازد و همه لاگ‌اوت می‌شوند.
_panel_secret = (os.environ.get("PANEL_SECRET") or "").strip()
if not _panel_secret:
    _panel_secret = secrets.token_hex(16)
    logger.warning("PANEL_SECRET ست نشده — با هر ری‌استارت از پنل خارج می‌شوید. "
                   "برای رفع: export PANEL_SECRET=$(openssl rand -hex 32)")
app.secret_key = _panel_secret

# تابعی که bot.py برای آپلود عکس به تلگرام تنظیمش می‌کند (file_id می‌گیرد)
TG_UPLOADER = None
def set_tg_uploader(fn): 
    global TG_UPLOADER; TG_UPLOADER = fn

SECTION_NAMES = {"welcome":"🏠 خوش‌آمدگویی","1":"🌐 شبکه‌های اجتماعی",
                 "2":"🌐 سایت استوک لند","3":"💰 شرایط اقساط",
                 "4":"📞 پشتیبانی","5":"📍 آدرس فروشگاه",
                 "contact":"📝 درخواست تماس","workhours":"🕐 ساعت کاری"}
SECTION_ORDER = ["welcome","1","2","3","4","5","contact","workhours"]
DAY_FA = {"0":"شنبه","1":"یکشنبه","2":"دوشنبه","3":"سه‌شنبه","4":"چهارشنبه","5":"پنجشنبه","6":"جمعه"}


# ── دیتابیس ───────────────────────────────────
def dbq(sql, args=(), one=False, commit=False):
    con = sqlite3.connect(DB_FILE); con.row_factory = sqlite3.Row
    cur = con.execute(sql, args)
    if commit:
        con.commit(); rid = cur.lastrowid; con.close(); return rid
    rows = cur.fetchall(); con.close()
    return (rows[0] if rows else None) if one else rows

def rj(path, default):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except: return default

def wj(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── احراز هویت ────────────────────────────────
def login_required(f):
    @functools.wraps(f)
    def wrap(*a, **k):
        if not session.get("auth"):
            if request.path.startswith("/api/"): return jsonify({"error":"unauthorized"}), 401
            return redirect(url_for("login"))
        return f(*a, **k)
    return wrap

def _handle_photo(req):
    """عکس آپلودی را ذخیره و به تلگرام می‌فرستد تا بات هم بتواند نشانش دهد.

    خروجی: file_id تلگرام (یا None اگر آپلود ناموفق بود).
    """
    if "photo" not in req.files: return None
    f = req.files["photo"]
    if not f or not f.filename: return None
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in (".jpg",".jpeg",".png",".webp"): ext = ".jpg"
    fname = f"web_{int(time.time())}_{secrets.token_hex(4)}{ext}"
    fpath = os.path.join(UPLOAD_DIR, fname)
    f.save(fpath)
    if not TG_UPLOADER:
        os.remove(fpath)
        return None
    try:
        fid = TG_UPLOADER(fpath)
    except Exception as e:
        logger.error(f"tg upload failed: {e}"); fid = None
    if not fid:
        os.remove(fpath)
        return None
    # نگاشت file_id ↔ فایل محلی، فقط برای پیش‌نمایش داخل پنل
    mp = rj(BANNERMAP_FILE, {}); mp[fid] = fname; wj(BANNERMAP_FILE, mp)
    return fid

@app.get("/uploads/<path:fname>")
@login_required
def serve_upload(fname):
    # ورودی می‌تواند file_id تلگرام باشد → از نگاشت، فایل محلی را پیدا کن
    mp = rj(BANNERMAP_FILE, {})
    fname = mp.get(fname, fname)
    # جلوگیری از path traversal — فقط نام فایل ساده مجاز است
    if fname != os.path.basename(fname): abort(404)
    if not os.path.exists(os.path.join(UPLOAD_DIR, fname)): abort(404)
    return send_from_directory(UPLOAD_DIR, fname)

# ════════════════════════════════════════════════
#  API — بخش‌ها (متن، بنر، دکمه‌ها)
# ════════════════════════════════════════════════
@app.get("/api/sections")
@login_required
def api_sections():
    responses = rj(DATA_FILE, {}); buttons = rj(BUTTONS_FILE, {}); banners = rj(BANNER_FILE, {})
    out = []
    for k in SECTION_ORDER:
        b = banners.get(k, {}); sec = buttons.get(k, {})
        out.append({"key":k,"name":SECTION_NAMES[k],
                    "text":responses.get(k,""),
                    "has_banner":bool(b.get("file_id")),"banner_active":bool(b.get("active")),
                    "banner_url":(f"/uploads/{b['file_id']}" if b.get("file_id") else None),
                    "buttons_enabled":bool(sec.get("enabled")),
                    "buttons":sec.get("items",[])})
    return jsonify(out)

@app.put("/api/section/<key>/text")
@login_required
def api_section_text(key):
    responses = rj(DATA_FILE, {})
    responses[key] = request.json.get("text","")
    wj(DATA_FILE, responses)
    return jsonify({"ok":True})

@app.post("/api/section/<key>/button")
@login_required
def api_section_btn_add(key):
    d = request.json
    title = (d.get("title") or "").strip(); url = (d.get("url") or "").strip()
    if not (title and url): return jsonify({"error":"عنوان و لینک لازم است"}), 400
    if not url.startswith("http"): url = "https://" + url
    buttons = rj(BUTTONS_FILE, {})
    sec = buttons.setdefault(key, {"enabled":True,"items":[]})
    sec["items"].append({"id":f"b{int(time.time())}","title":title,"url":url})
    sec["enabled"] = True
    wj(BUTTONS_FILE, buttons)
    return jsonify({"ok":True})

@app.delete("/api/section/<key>/button/<bid>")
@login_required
def api_section_btn_del(key, bid):
    buttons = rj(BUTTONS_FILE, {})
    sec = buttons.get(key, {})
    sec["items"] = [x for x in sec.get("items",[]) if x["id"]!=bid]
    wj(BUTTONS_FILE, buttons)
    return jsonify({"ok":True})

@app.put("/api/section/<key>/buttons-toggle")
@login_required
def api_section_btn_toggle(key):
    buttons = rj(BUTTONS_FILE, {})
    sec = buttons.setdefault(key, {"enabled":False,"items":[]})
    sec["enabled"] = not sec.get("enabled", False)
    wj(BUTTONS_FILE, buttons)
    return jsonify({"ok":True,"enabled":sec["enabled"]})

@app.put("/api/section/<key>/banner-toggle")
@login_required
def api_section_banner_toggle(key):
    banners = rj(BANNER_FILE, {})
    b = banners.setdefault(key, {"file_id":None,"active":False})
    if not b.get("file_id"): return jsonify({"error":"ابتدا بنر آپلود کنید"}), 400
    b["active"] = not b.get("active", False)
    wj(BANNER_FILE, banners)
    return jsonify({"ok":True,"active":b["active"]})

@app.post("/api/section/<key>/banner")
@login_required
def api_section_banner_upload(key):
    if key not in SECTION_NAMES: return jsonify({"error":"بخش نامعتبر"}), 404
    if not TG_UPLOADER:
        return jsonify({"error":"آپلود به تلگرام در دسترس نیست — بات در حال اجرا نیست"}), 503
    fid = _handle_photo(request)
    if not fid: return jsonify({"error":"آپلود تصویر ناموفق بود"}), 400
    banners = rj(BANNER_FILE, {})
    banners[key] = {"file_id": fid, "active": True}
    wj(BANNER_FILE, banners)
    return jsonify({"ok":True,"file_id":fid,"active":True})

@app.delete("/api/section/<key>/banner")
@login_required
def api_section_banner_delete(key):
    banners = rj(BANNER_FILE, {})
    banners[key] = {"file_id":None,"active":False}
    wj(BANNER_FILE, banners)
    return jsonify({"ok":True})

# ════════════════════════════════════════════════
#  API — درخواست‌ها
# ════════════════════════════════════════════════
@app.get("/api/requests")
@login_required
def api_requests():
    rows = dbq("SELECT id,user_id,username,first_name,phone,product_name,status,created_at FROM requests ORDER BY id DESC LIMIT 100")
    return jsonify([dict(r) for r in rows])

@app.put("/api/request/<int:rid>/done")
@login_required
def api_request_done(rid):
    dbq("UPDATE requests SET status='done' WHERE id=?", (rid,), commit=True)
    return jsonify({"ok":True})

# ════════════════════════════════════════════════
#  API — کاربران
# ════════════════════════════════════════════════
@app.get("/api/users")
@login_required
def api_users():
    ft = request.args.get("filter","all"); q = request.args.get("q","").strip()
    where = ""
    if ft=="today": where="WHERE DATE(last_seen)=DATE('now','localtime')"
    elif ft=="week": where="WHERE last_seen>=datetime('now','-7 days','localtime')"
    elif ft=="blocked": where="WHERE is_blocked=1"
    if q:
        like=f"%{q}%"
        rows = dbq("SELECT user_id,first_name,username,last_seen,is_blocked FROM users WHERE first_name LIKE ? OR username LIKE ? OR CAST(user_id AS TEXT) LIKE ? ORDER BY last_seen DESC LIMIT 50",(like,like,like))
    else:
        rows = dbq(f"SELECT user_id,first_name,username,last_seen,is_blocked FROM users {where} ORDER BY last_seen DESC LIMIT 50")
    return jsonify([dict(r) for r in rows])

@app.put("/api/user/<int:uid>/block")
@login_required
def api_user_block(uid):
    cur = dbq("SELECT is_blocked FROM users WHERE user_id=?", (uid,), one=True)
    if not cur: return jsonify({"error":"یافت نشد"}), 404
    nv = 0 if cur["is_blocked"] else 1
    dbq("UPDATE users SET is_blocked=? WHERE user_id=?", (nv,uid), commit=True)
    return jsonify({"ok":True,"blocked":bool(nv)})

# ════════════════════════════════════════════════
#  API — داشبورد
# ════════════════════════════════════════════════
@app.get("/api/dashboard")
@login_required
def api_dashboard():
    def c(sql):
        try: return dbq(sql, one=True)["c"]
        except: return 0
    total = c("SELECT COUNT(*) c FROM users")
    today = c("SELECT COUNT(*) c FROM users WHERE DATE(last_seen)=DATE('now','localtime')")
    week  = c("SELECT COUNT(*) c FROM users WHERE last_seen>=datetime('now','-7 days','localtime')")
    month = c("SELECT COUNT(*) c FROM users WHERE last_seen>=datetime('now','-30 days','localtime')")
    new_t = c("SELECT COUNT(*) c FROM users WHERE DATE(joined_at)=DATE('now','localtime')")
    blocked = c("SELECT COUNT(*) c FROM users WHERE is_blocked=1")
    reqs_new = c("SELECT COUNT(*) c FROM requests WHERE status='new'")
    reqs_total = c("SELECT COUNT(*) c FROM requests")
    return jsonify({"total":total,"today":today,"week":week,"month":month,"new_today":new_t,
                    "blocked":blocked,"reqs_new":reqs_new,"reqs_total":reqs_total})

@app.get("/api/stats")
@login_required
def api_stats():
    """بازدید هر بخش — از stats.json که بات می‌نویسد."""
    labels = dict(SECTION_NAMES); labels["wh_page"] = "🕐 ساعت کاری"
    raw = rj(STATS_FILE, {})
    rows = [{"key":k,"name":labels.get(k,k),"count":v}
            for k,v in raw.items() if isinstance(v,int) and v]
    rows.sort(key=lambda r: -r["count"])
    return jsonify({"rows":rows,"total":sum(r["count"] for r in rows)})

# ════════════════════════════════════════════════
#  API — ساعت کاری
# ════════════════════════════════════════════════
@app.get("/api/workhours")
@login_required
def api_wh_get():
    return jsonify(rj(WORKHOURS_FILE, {}))

@app.put("/api/workhours")
@login_required
def api_wh_set():
    wj(WORKHOURS_FILE, request.json)
    return jsonify({"ok":True})

# ════════════════════════════════════════════════
#  API — تنظیمات
# ════════════════════════════════════════════════
@app.get("/api/settings")
@login_required
def api_settings_get():
    return jsonify(rj(SETTINGS_FILE, {}))

@app.put("/api/settings")
@login_required
def api_settings_set():
    s = rj(SETTINGS_FILE, {}); s.update(request.json); wj(SETTINGS_FILE, s)
    return jsonify({"ok":True})

# ════════════════════════════════════════════════
#  Routes — صفحات
# ════════════════════════════════════════════════
@app.get("/login")
def login():
    if session.get("auth"): return redirect(url_for("index"))
    return render_template_string(LOGIN_HTML, error=request.args.get("e"))

@app.post("/login")
def do_login():
    # compare_digest تا زمان پاسخ، رمز را لو ندهد
    ok_u = hmac.compare_digest(request.form.get("u") or "", PANEL_USER)
    ok_p = hmac.compare_digest(request.form.get("p") or "", PANEL_PASS)
    if ok_u and ok_p:
        session["auth"]=True; session.permanent=True
        return redirect(url_for("index"))
    return redirect(url_for("login", e="1"))

@app.get("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

@app.get("/")
@login_required
def index():
    return render_template_string(PANEL_HTML)

# HTML در فایل جدا import می‌شود
from templates import LOGIN_HTML, PANEL_HTML

# ── تنظیمات شبکه پنل وب ──────────────────────────
# روی وی‌پی‌اس مشترک، متغیر عمومی PORT ممکن است متعلق به پروژه دیگری باشد.
# به همین دلیل ابتدا متغیر اختصاصی این پروژه خوانده می‌شود و PORT فقط
# به‌عنوان آخرین گزینه (سازگاری با Railway/Heroku) استفاده می‌گردد.
PORT_ENV_VARS = ("STOCKLAND_PORT", "WEB_PORT", "PORT")
DEFAULT_PORT  = 8080
DEFAULT_HOST  = "0.0.0.0"


def resolve_port():
    """پورت پنل را از متغیرهای محیطی (به ترتیب اولویت) برمی‌گرداند.

    خروجی: (port, source) که source نام متغیر استفاده‌شده است.
    """
    for var in PORT_ENV_VARS:
        raw = (os.environ.get(var) or "").strip()
        if not raw:
            continue
        try:
            port = int(raw)
        except ValueError:
            raise SystemExit(
                f"❌ مقدار متغیر {var} یک عدد معتبر نیست: {raw!r}"
            )
        if not (1 <= port <= 65535):
            raise SystemExit(
                f"❌ مقدار متغیر {var} باید بین ۱ تا ۶۵۵۳۵ باشد: {port}"
            )
        return port, var
    return DEFAULT_PORT, "پیش‌فرض"


def check_port_free(host, port):
    """اگر پورت اشغال باشد با پیام واضح خارج می‌شود (به‌جای تریس‌بک خام Flask)."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError as e:
            raise SystemExit(
                f"❌ پورت {port} روی {host} در دسترس نیست ({e.strerror}).\n"
                f"   احتمالاً سرویس دیگری روی همین وی‌پی‌اس از این پورت استفاده می‌کند.\n"
                f"   یک پورت آزاد و اختصاصی برای این پروژه ست کنید، مثلاً:\n"
                f"       export WEB_PORT=8471\n"
                f"   (در systemd: Environment=WEB_PORT=8471)"
            )


def run_web(host=None, port=None):
    host = host or os.environ.get("WEB_HOST", DEFAULT_HOST)
    if port is None:
        port, source = resolve_port()
    else:
        source = "پارامتر ورودی"
    check_port_free(host, port)
    logger.info("🌐 پنل وب روی %s:%s اجرا می‌شود (منبع پورت: %s)", host, port, source)
    app.run(host=host, port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    run_web()
