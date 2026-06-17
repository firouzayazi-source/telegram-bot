"""
ماژول اتصال به ووکامرس (WooCommerce REST API)
محصولات و دسته‌ها را زنده از stland.ir می‌خواند و cache می‌کند.
فقط خواندنی — هیچ چیزی روی سایت تغییر نمی‌دهد.
"""
import os, time, logging, asyncio
import aiohttp

logger = logging.getLogger("woo")

WOO_URL    = os.environ.get("WOO_URL", "").strip().rstrip("/")   # مثل https://stland.ir
WOO_KEY    = os.environ.get("WOO_KEY", "").strip()               # ck_xxx
WOO_SECRET = os.environ.get("WOO_SECRET", "").strip()            # cs_xxx
CACHE_TTL  = int(os.environ.get("WOO_CACHE_TTL", "3600"))        # ۱ ساعت
HIDE_OUT_OF_STOCK = os.environ.get("WOO_HIDE_OOS", "1") == "1"   # مخفی‌سازی ناموجود

def is_configured():
    return bool(WOO_URL and WOO_KEY and WOO_SECRET)

# ── cache ساده در حافظه ────────────────────────────
_cache = {}   # key -> (timestamp, data)
_last_sync_version = None
_version_cache_time = 0
VERSION_CHECK_INTERVAL = 60

# ── Interval-Based Warm ─────────────────────────────
_last_warm_time: float = 0.0
WARM_INTERVAL: int = 600   # ۱۰ دقیقه — حداقل فاصله بین دو warm کامل

def _get_cache(key):
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
    return None

def _set_cache(key, data):
    _cache[key] = (time.time(), data)

def clear_cache():
    _cache.clear()

def is_cats_cached():
    """آیا دسته‌ها در cache گرم هستند؟"""
    return _get_cache("cats") is not None

async def warm_cache():
    """Cache گرم‌کردن هنگام استارت ربات — دسته‌ها و محصولات همه دسته‌ها را
    از قبل می‌گیرد تا کاربر هیچ‌جا منتظر نماند."""
    try:
        logger.info("woo: گرم کردن cache شروع شد...")
        cats = await get_categories()
        if not cats:
            logger.warning("woo: دسته‌ای پیدا نشد (اتصال/تنظیمات را بررسی کنید)")
            return
        roots = [c for c in cats if c["parent"] == 0]
        logger.info(f"woo: {len(cats)} دسته cache شد ({len(roots)} اصلی)")
        # محصولات همه دسته‌ها را هم از قبل بگیر (کلیک روی دسته فوری شود)
        import asyncio
        async def _warm_cat(c):
            try: await get_products_by_category(c["id"])
            except Exception: pass
        # موازی بگیر (سریع‌تر) ولی محدود به ۵ تا همزمان (فشار نیاد روی سایت)
        sem = asyncio.Semaphore(5)
        async def _bounded(c):
            async with sem: await _warm_cat(c)
        await asyncio.gather(*[_bounded(c) for c in cats])
        logger.info(f"woo: محصولات {len(cats)} دسته هم cache شد — آماده!")
    except Exception as e:
        logger.error(f"woo warm_cache: {e}")

async def maybe_warm_cache():
    """اگر ۱۰ دقیقه از آخرین warm کامل گذشته باشد، cache را گرم می‌کند.
    در غیر این صورت فوراً برمی‌گردد — صفر overhead برای کاربر."""
    global _last_warm_time
    now = time.time()
    if now - _last_warm_time < WARM_INTERVAL:
        return   # هنوز ۱۰ دقیقه نگذشته
    _last_warm_time = now   # فوری ست کن تا فراخوانی‌های همزمان بلاک شوند
    await warm_cache()

# ── درخواست به API ──────────────────────────────────
async def _fetch(path, params=None):
    if not is_configured():
        logger.warning("WooCommerce تنظیم نشده")
        return None
    url = f"{WOO_URL}/wp-json/wc/v3/{path}"
    p = dict(params or {})
    p.update({"consumer_key": WOO_KEY, "consumer_secret": WOO_SECRET})
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.get(url, params=p) as r:
                if r.status != 200:
                    logger.error(f"woo {path}: HTTP {r.status}")
                    return None
                return await r.json()
    except Exception as e:
        logger.error(f"woo fetch {path}: {e}")
        return None

async def _fetch_plugin(path):
    """خواندن از endpoint افزونه استوک لند (نه ووکامرس استاندارد)."""
    if not WOO_URL: return None
    url = f"{WOO_URL}/wp-json/stockland/v1/{path}"
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.get(url) as r:
                if r.status != 200: return None
                return await r.json()
    except Exception as e:
        logger.error(f"plugin fetch {path}: {e}")
        return None

async def check_sync_version(force=False):
    """نسخه سینک را چک می‌کند.
    force=True → همیشه چک کن (مثلاً هنگام /start)
    force=False → فقط اگر بیشتر از VERSION_CHECK_INTERVAL گذشته باشد
    این فقط در «نقطه ورود» (start و باز کردن محصولات) صدا زده می‌شود،
    نه در هر کلیک. پس بار روی سایت حداقل است."""
    global _last_sync_version, _version_cache_time
    now = time.time()
    if not force and (now - _version_cache_time < VERSION_CHECK_INTERVAL):
        return  # اخیراً چک کردیم
    _version_cache_time = now
    data = await _fetch_plugin("version")
    if not data: return
    v = data.get("version")
    if v and v != _last_sync_version:
        if _last_sync_version is not None:
            clear_cache()
            logger.info(f"sync version changed → cache cleared (v={v})")
        _last_sync_version = v

async def get_visible_category_ids():
    """فهرست id دسته‌هایی که در افزونه تیک «نمایش در تلگرام» خورده‌اند.
    اگر افزونه نصب نباشد، None برمی‌گرداند (یعنی همه دسته‌ها نمایش داده شوند)."""
    cached = _get_cache("visible_cats")
    if cached is not None: return cached
    data = await _fetch_plugin("visible-categories")
    if not data: return None  # افزونه نیست → بدون فیلتر
    ids = data.get("category_ids", [])
    _set_cache("visible_cats", ids)
    return ids

async def _fetch_all(path, params=None):
    """همه صفحات را می‌گیرد (pagination)."""
    out = []
    page = 1
    while True:
        p = dict(params or {}); p.update({"per_page": 100, "page": page})
        data = await _fetch(path, p)
        if not data: break
        out.extend(data)
        if len(data) < 100: break
        page += 1
        if page > 20: break  # سقف ایمنی
    return out

# ── دسته‌بندی‌ها ────────────────────────────────────
async def get_categories():
    """تمام دسته‌های قابل‌نمایش (تیک‌خورده در افزونه) را برمی‌گرداند."""
    cached = _get_cache("cats")
    if cached is not None: return cached
    raw = await _fetch_all("products/categories", {"hide_empty": "false", "_fields": "id,name,parent,count,image"})
    if raw is None: return []
    # فیلتر دسته‌های تیک‌خورده (اگر افزونه نصب باشد)
    visible = await get_visible_category_ids()
    cats = []
    for c in raw:
        if visible is not None and c["id"] not in visible:
            continue  # این دسته در افزونه تیک نخورده → نمایش نده
        cats.append({
            "id": c["id"], "name": c["name"], "parent": c["parent"],
            "count": c.get("count", 0),
            "image": (c.get("image") or {}).get("src") if c.get("image") else None,
        })
    _set_cache("cats", cats)
    return cats

async def get_root_categories():
    cats = await get_categories()
    return [c for c in cats if c["parent"] == 0]

async def get_subcategories(parent_id):
    cats = await get_categories()
    return [c for c in cats if c["parent"] == parent_id]

async def get_category(cat_id):
    cats = await get_categories()
    return next((c for c in cats if c["id"] == cat_id), None)

# ── محصولات ─────────────────────────────────────────
def _map_product(p):
    """محصول ووکامرس → فرمت ساده ربات."""
    img = None
    if p.get("images"):
        img = p["images"][0].get("src")
    # قیمت: ترجیحاً price_html ساده‌شده، یا price خام
    price = p.get("price") or ""
    price_fmt = f"{price} تومان" if price and price.isdigit() else (price or "تماس بگیرید")
    # توضیح کوتاه بدون تگ HTML
    desc = p.get("short_description") or p.get("description") or ""
    desc = _trim_desc(_strip_html(desc))
    return {
        "id": p["id"], "name": p["name"], "price": price_fmt,
        "price_raw": price, "description": desc,
        "image": img, "permalink": p.get("permalink"),
        "in_stock": p.get("stock_status") in ("instock", "onbackorder"),
        "is_backorder": p.get("stock_status") == "onbackorder",
        "category_ids": [c["id"] for c in p.get("categories", [])],
    }

def _strip_html(s):
    import re
    # پایان پاراگراف و خط جدید → newline (حفظ خط‌بندی)
    s = re.sub(r"</p>|<br\s*/?>|</li>|</div>", "\n", s, flags=re.I)
    s = re.sub(r"<li[^>]*>", "• ", s, flags=re.I)  # آیتم لیست → بولت
    s = re.sub(r"<[^>]+>", "", s)  # بقیه تگ‌ها حذف
    s = re.sub(r"&nbsp;", " ", s)
    s = re.sub(r"&zwnj;", "\u200c", s)
    s = re.sub(r"&[a-z]+;", " ", s)
    # فقط خطوط غیرخالی را نگه دار (خطوط خالی اضافه حذف)
    lines = [ln.strip() for ln in s.split("\n") if ln.strip()]
    return "\n".join(lines).strip()

def _trim_desc(text: str, max_chars: int = 350) -> str:
    """توضیح را به max_chars کاراکتر محدود می‌کند.
    برش در آخرین فاصله (کلمه کامل) + راهنما.
    مستقل از تعداد \n — روی هر موبایل یکنواخت است."""
    if not text: return ""
    # خطوط خالی پشت سر هم را پاک کن
    text = "\n".join(ln for ln in text.split("\n") if ln.strip())
    if len(text) <= max_chars: return text
    cut = text.rfind(" ", 0, max_chars)
    if cut < max_chars // 2: cut = max_chars
    return text[:cut].rstrip() + "\n\n📖 ادامه توضیحات در سایت"

async def get_products_by_category(cat_id):
    """محصولات یک دسته — instock و onbackorder نمایش داده می‌شوند، outofstock حذف می‌شود."""
    key = f"prods_{cat_id}"
    cached = _get_cache(key)
    if cached is not None: return cached
    params = {
        "category": cat_id, "status": "publish",
        "orderby": "menu_order",
        "_fields": "id,name,price,regular_price,sale_price,stock_status,status,permalink,images,short_description,description,categories"
    }
    raw = await _fetch_all("products", params)
    if raw is None: return []
    # فقط outofstock حذف می‌شود — onbackorder (پیش‌خرید) همیشه نمایش داده می‌شود
    if HIDE_OUT_OF_STOCK:
        raw = [p for p in raw if p.get("stock_status") != "outofstock"]
    prods = [_map_product(p) for p in raw]
    _set_cache(key, prods)
    return prods

async def get_product(pid):
    # اول از cache محصولات
    for k, (ts, data) in list(_cache.items()):
        if k.startswith("prods_"):
            for p in data:
                if p["id"] == pid: return p
    # وگرنه مستقیم بگیر
    raw = await _fetch(f"products/{pid}")
    return _map_product(raw) if raw else None

async def search_products(query):
    """جستجوی محصول."""
    params = {"search": query, "status": "publish", "per_page": 20, "_fields": "id,name,price,regular_price,sale_price,stock_status,status,permalink,images,short_description,description,categories"}
    raw = await _fetch("products", params)
    if raw is None: return []
    if HIDE_OUT_OF_STOCK:
        raw = [p for p in raw if p.get("stock_status") != "outofstock"]
    return [_map_product(p) for p in raw]

# ── تست اتصال ───────────────────────────────────────
async def test_connection():
    """برای بررسی صحت کلیدها."""
    if not is_configured():
        return False, "متغیرهای WOO_URL / WOO_KEY / WOO_SECRET تنظیم نشده‌اند"
    data = await _fetch("products", {"per_page": 1})
    if data is None:
        return False, "اتصال برقرار نشد — URL یا کلیدها را بررسی کنید"
    return True, "اتصال موفق بود"
