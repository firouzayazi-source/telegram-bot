"""
پنل وب مدیریت استوک لند
به همان دیتابیس و فایل‌های بات وصل است.
"""
import os, json, sqlite3, time, secrets, functools, io, hmac, hashlib
from datetime import datetime
from flask import (Flask, request, session, redirect, url_for, jsonify,
                   render_template_string, send_from_directory, abort)
import asyncio

# ── مسیرها (هماهنگ با bot.py) ───────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
DB_FILE       = os.path.join(BASE, "users.db")
DATA_FILE     = os.path.join(BASE, "data.json")
WORKHOURS_FILE= os.path.join(BASE, "workhours.json")
BUTTONS_FILE  = os.path.join(BASE, "buttons.json")
SETTINGS_FILE = os.path.join(BASE, "settings.json")
BANNER_FILE   = os.path.join(BASE, "banner.json")
UPLOAD_DIR    = os.path.join(BASE, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

PANEL_USER         = os.environ.get("PANEL_USER", "admin")
WOO_WEBHOOK_SECRET = os.environ.get("WOO_WEBHOOK_SECRET", "")
PANEL_PASS         = os.environ.get("PANEL_PASS", "stockland")

app = Flask(__name__)
app.secret_key = os.environ.get("PANEL_SECRET", secrets.token_hex(16))

# تابعی که bot.py برای آپلود عکس به تلگرام تنظیمش می‌کند (file_id می‌گیرد)
TG_UPLOADER = None
def set_tg_uploader(fn): 
    global TG_UPLOADER; TG_UPLOADER = fn

SECTION_NAMES = {"welcome":"🏠 خوش‌آمدگویی","1":"🌐 شبکه‌های اجتماعی",
                 "2":"🌐 سایت استوک لند","3":"💰 شرایط اقساط",
                 "4":"📞 پشتیبانی","5":"📍 آدرس فروشگاه",
                 "catalog":"🛍 محصولات","workhours":"🕐 ساعت کاری"}
SECTION_ORDER = ["welcome","1","2","3","4","5","catalog","workhours"]
DAY_FA = {"0":"شنبه","1":"یکشنبه","2":"دوشنبه","3":"سه‌شنبه","4":"چهارشنبه","5":"پنجشنبه","6":"جمعه"}


def _verify_sig(req):
    if not WOO_WEBHOOK_SECRET:
        return True
    sig = req.headers.get("X-Webhook-Signature", "")
    body = req.get_data()
    expected = "sha256=" + hmac.new(WOO_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)

def _upsert_product(p):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cat_id = p.get('category_ids', [None])[0] if p.get('category_ids') else None
    price = p.get('price') or p.get('regular_price') or ''
    if price and str(price).replace('.','').isdigit():
        price = f"{int(float(price)):,} تومان"
    dbq("""INSERT OR REPLACE INTO products(id, category_id, name, price, description, photo_id, site_url, is_active, created_at)
           VALUES(?,?,?,?,?,?,?,?,?)""",
        (p['id'], cat_id, p['name'], price, p.get('description',''),
         p.get('image_url'), p.get('permalink'),
         1 if p.get('stock_status')=='instock' and p.get('status')=='publish' else 0,
         now), commit=True)

def _upsert_category(c):
    icon = '📂' if not c.get('parent_id') else '📦'
    dbq("""INSERT OR REPLACE INTO categories(id, name, icon, parent_id, is_active) VALUES(?,?,?,?,1)""",
        (c['id'], c['name'], icon, c.get('parent_id') or None), commit=True)

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

# ════════════════════════════════════════════════
#  API — محصولات (از SQLite)
# ════════════════════════════════════════════════
@app.get("/api/tree")
@login_required
def api_tree():
    try:
        roots = dbq("SELECT id,name,icon FROM categories WHERE parent_id IS NULL AND is_active=1 ORDER BY id")
        out = []
        for r in roots:
            subs = dbq("SELECT id,name,icon,is_active FROM categories WHERE parent_id=? AND is_active=1 ORDER BY id", (r["id"],))
            sub_list = [{"id":s["id"],"name":s["name"],"icon":s["icon"],"active":bool(s["is_active"]),
                         "product_count": dbq("SELECT COUNT(*) c FROM products WHERE category_id=? AND is_active=1",(s["id"],),one=True)["c"]} for s in subs]
            out.append({"id":r["id"],"name":r["name"],"icon":r["icon"],"active":True,"subs":sub_list})
        return jsonify(out)
    except Exception as e:
        return jsonify([])

@app.get("/api/products/<int:sub_id>")
@login_required
def api_products(sub_id):
    try:
        prods = dbq("SELECT id,name,price,description,site_url,is_active,photo_id FROM products WHERE category_id=? ORDER BY id", (sub_id,))
        out = []
        for p in prods:
            out.append({"id":p["id"],"name":p["name"],"price":p["price"],"description":p["description"],
                        "site_url":p["site_url"],"active":bool(p["is_active"]),"photo_url":p["photo_id"]})
        return jsonify(out)
    except Exception:
        return jsonify([])

@app.get("/api/woo-status")
@login_required
def api_woo_status():
    return jsonify({"status": "push-based", "ok": True})

@app.post("/api/woo-refresh")
@login_required
def api_woo_refresh():
    return jsonify({"ok": True, "message": "push-based, no refresh needed"})

def _handle_photo(req):
    """عکس آپلودی را ذخیره می‌کند؛ اگر uploader تلگرام تنظیم شده، file_id می‌گیرد."""
    if "photo" not in req.files: return None
    f = req.files["photo"]
    if not f or not f.filename: return None
    ext = os.path.splitext(f.filename)[1].lower() or ".jpg"
    if ext not in (".jpg",".jpeg",".png",".webp"): ext = ".jpg"
    fname = f"web_{int(time.time())}_{secrets.token_hex(4)}{ext}"
    fpath = os.path.join(UPLOAD_DIR, fname)
    f.save(fpath)
    # اگر uploader تلگرام موجود است، file_id بگیر تا بات هم بتواند نشان دهد
    if TG_UPLOADER:
        try:
            fid = TG_UPLOADER(fpath)
            if fid:
                # نگاشت file_id ↔ فایل محلی برای نمایش وب
                _save_photo_map(fid, fname)
                return fid
        except Exception as e:
            print(f"[web] tg upload failed: {e}")
    return fname  # fallback: فقط فایل محلی

def _save_photo_map(fid, fname):
    mp = rj(os.path.join(BASE,"photomap.json"), {})
    mp[fid] = fname; wj(os.path.join(BASE,"photomap.json"), mp)

@app.get("/uploads/<path:fname>")
@login_required
def serve_upload(fname):
    # اگر file_id تلگرام بود، از نگاشت فایل محلی پیدا کن
    mp = rj(os.path.join(BASE,"photomap.json"), {})
    if fname in mp: fname = mp[fname]
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
    prods = c("SELECT COUNT(*) c FROM products")
    cats = c("SELECT COUNT(*) c FROM categories WHERE parent_id IS NULL")
    return jsonify({"total":total,"today":today,"week":week,"month":month,"new_today":new_t,
                    "blocked":blocked,"reqs_new":reqs_new,"reqs_total":reqs_total,
                    "products":prods,"categories":cats})

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
    if request.form.get("u")==PANEL_USER and request.form.get("p")==PANEL_PASS:
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

# ════════════════════════════════════════════════
#  Telegram-visible categories — JSON file storage
# ════════════════════════════════════════════════
TG_CATS_FILE = os.path.join(BASE, "tg_cats.json")

def _read_tg_cats():
    """Return list of allowed category IDs (ints)."""
    return rj(TG_CATS_FILE, [])

def _write_tg_cats(cat_ids):
    """Persist allowed category IDs."""
    wj(TG_CATS_FILE, [int(c) for c in cat_ids])

@app.get("/api/tg-categories")
@login_required
def api_tg_cats_get():
    """Return the list of Telegram-visible WooCommerce category IDs."""
    return jsonify({"cat_ids": _read_tg_cats()})

@app.put("/api/tg-categories")
@login_required
def api_tg_cats_put():
    """Replace the list of Telegram-visible category IDs.

    Body: {"cat_ids": [1, 2, 3]}
    """
    data = request.get_json(silent=True) or {}
    cat_ids = data.get("cat_ids", [])
    if not isinstance(cat_ids, list):
        return jsonify({"error": "cat_ids must be an array"}), 400
    _write_tg_cats(cat_ids)
    return jsonify({"ok": True, "cat_ids": _read_tg_cats()})

# ════════════════════════════════════════════════
#  WooCommerce webhooks — public but HMAC-signed
# ════════════════════════════════════════════════

@app.post("/webhook/woo")
def webhook_woo():
    if not _verify_sig(request):
        return jsonify({"error": "invalid signature"}), 403
    data = request.get_json(force=True, silent=True) or {}
    event = data.get('event', '')
    if event == 'product.updated':
        _upsert_product(data['product'])
    elif event == 'product.deleted':
        pid = data.get('product', {}).get('id')
        if pid:
            dbq("DELETE FROM products WHERE id=?", (pid,), commit=True)
    elif event == 'categories.sync':
        for c in data.get('categories', []):
            _upsert_category(c)
    return jsonify({"ok": True})

@app.post("/webhook/woo/clear-all")
def webhook_woo_clear_all():
    if not _verify_sig(request):
        return jsonify({"error": "invalid signature"}), 403
    return jsonify({"ok": True})

@app.post("/webhook/woo/sync-cats")
def webhook_woo_sync_cats():
    if not _verify_sig(request):
        return jsonify({"error": "invalid signature"}), 403
    data = request.get_json(force=True, silent=True) or {}
    for c in data.get('categories', []):
        _upsert_category(c)
    return jsonify({"ok": True})


def run_web(host="0.0.0.0", port=None):
    port = port or int(os.environ.get("PORT", 8080))
    app.run(host=host, port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    run_web()
