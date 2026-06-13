"""
پنل وب مدیریت استوک لند
به همان دیتابیس و فایل‌های بات وصل است.
"""
import os, json, sqlite3, time, secrets, functools, io
from datetime import datetime
from flask import (Flask, request, session, redirect, url_for, jsonify,
                   render_template_string, send_from_directory, abort)

# ── مسیرها (هماهنگ با bot.py) ───────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
DB_FILE       = os.path.join(ROOT, "users.db")
DATA_FILE     = os.path.join(ROOT, "data.json")
WORKHOURS_FILE= os.path.join(ROOT, "workhours.json")
BUTTONS_FILE  = os.path.join(ROOT, "buttons.json")
SETTINGS_FILE = os.path.join(ROOT, "settings.json")
BANNER_FILE   = os.path.join(ROOT, "banner.json")
UPLOAD_DIR    = os.path.join(BASE, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

PANEL_USER = os.environ.get("PANEL_USER", "admin")
PANEL_PASS = os.environ.get("PANEL_PASS", "stockland")

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
#  API — محصولات
# ════════════════════════════════════════════════
@app.get("/api/tree")
@login_required
def api_tree():
    roots = dbq("SELECT id,name,icon,is_active FROM categories WHERE parent_id IS NULL ORDER BY id")
    out = []
    for r in roots:
        subs = dbq("SELECT id,name,icon,is_active FROM categories WHERE parent_id=? ORDER BY id", (r["id"],))
        sub_list = []
        for s in subs:
            pc = dbq("SELECT COUNT(*) c FROM products WHERE category_id=?", (s["id"],), one=True)["c"]
            sub_list.append({"id":s["id"],"name":s["name"],"icon":s["icon"],"active":bool(s["is_active"]),"product_count":pc})
        out.append({"id":r["id"],"name":r["name"],"icon":r["icon"],"active":bool(r["is_active"]),"subs":sub_list})
    return jsonify(out)

@app.get("/api/products/<int:sub_id>")
@login_required
def api_products(sub_id):
    rows = dbq("SELECT id,name,price,description,photo_id,site_url,is_active FROM products WHERE category_id=? ORDER BY id", (sub_id,))
    out = []
    for p in rows:
        out.append({"id":p["id"],"name":p["name"],"price":p["price"],"description":p["description"],
                    "photo_id":p["photo_id"],"site_url":p["site_url"],"active":bool(p["is_active"]),
                    "photo_url":f"/uploads/{p['photo_id']}" if p["photo_id"] and not str(p["photo_id"]).startswith("AgAC") and os.path.exists(os.path.join(UPLOAD_DIR,str(p['photo_id']))) else None})
    return jsonify(out)

@app.post("/api/category")
@login_required
def api_cat_add():
    d = request.json
    icon = d.get("icon","📦").strip() or "📦"
    name = d.get("name","").strip()
    parent = d.get("parent_id")
    if not name: return jsonify({"error":"نام لازم است"}), 400
    rid = dbq("INSERT INTO categories(name,icon,parent_id,is_active) VALUES(?,?,?,1)", (name,icon,parent), commit=True)
    return jsonify({"id":rid,"ok":True})

@app.put("/api/category/<int:cid>")
@login_required
def api_cat_edit(cid):
    d = request.json
    if "name" in d: dbq("UPDATE categories SET name=? WHERE id=?", (d["name"].strip(),cid), commit=True)
    if "icon" in d: dbq("UPDATE categories SET icon=? WHERE id=?", (d["icon"].strip() or "📦",cid), commit=True)
    if "active" in d: dbq("UPDATE categories SET is_active=? WHERE id=?", (1 if d["active"] else 0,cid), commit=True)
    return jsonify({"ok":True})

@app.delete("/api/category/<int:cid>")
@login_required
def api_cat_del(cid):
    # cascade: زیردسته‌ها و محصولاتشان
    subs = dbq("SELECT id FROM categories WHERE parent_id=?", (cid,))
    for s in subs:
        dbq("DELETE FROM products WHERE category_id=?", (s["id"],), commit=True)
        dbq("DELETE FROM categories WHERE id=?", (s["id"],), commit=True)
    dbq("DELETE FROM products WHERE category_id=?", (cid,), commit=True)
    dbq("DELETE FROM categories WHERE id=?", (cid,), commit=True)
    return jsonify({"ok":True})

@app.post("/api/product")
@login_required
def api_prod_add():
    d = request.form
    sub_id = d.get("category_id")
    name = (d.get("name") or "").strip()
    price = (d.get("price") or "").strip()
    desc = (d.get("description") or "").strip() or None
    url = (d.get("site_url") or "").strip() or None
    if not (sub_id and name and price): return jsonify({"error":"نام، قیمت و دسته لازم است"}), 400
    photo_id = _handle_photo(request)
    rid = dbq("""INSERT INTO products(category_id,name,price,description,photo_id,site_url,is_active,created_at)
                 VALUES(?,?,?,?,?,?,1,?)""",
              (sub_id,name,price,desc,photo_id,url,datetime.now().strftime("%Y-%m-%d %H:%M:%S")), commit=True)
    return jsonify({"id":rid,"ok":True})

@app.put("/api/product/<int:pid>")
@login_required
def api_prod_edit(pid):
    d = request.form
    fields, vals = [], []
    for k_form,k_db in [("name","name"),("price","price"),("description","description"),("site_url","site_url")]:
        if k_form in d:
            v = (d.get(k_form) or "").strip()
            if k_form in ("description","site_url") and not v: v = None
            fields.append(f"{k_db}=?"); vals.append(v)
    if "active" in d:
        fields.append("is_active=?"); vals.append(1 if d.get("active")=="true" else 0)
    photo_id = _handle_photo(request)
    if photo_id:
        fields.append("photo_id=?"); vals.append(photo_id)
    if fields:
        vals.append(pid)
        dbq(f"UPDATE products SET {','.join(fields)} WHERE id=?", vals, commit=True)
    return jsonify({"ok":True})

@app.delete("/api/product/<int:pid>")
@login_required
def api_prod_del(pid):
    dbq("DELETE FROM products WHERE id=?", (pid,), commit=True)
    return jsonify({"ok":True})

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
    def c(sql): return dbq(sql, one=True)["c"]
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

def run_web(host="0.0.0.0", port=None):
    port = port or int(os.environ.get("PORT", 8080))
    app.run(host=host, port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    run_web()
