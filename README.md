# ربات تلگرام استوک لند — مستندات کامل پروژه

> **نسخه:** نهایی (بهینه‌سازی‌شده)  
> **استفاده:** این فایل را به Claude بدهید تا بدون نیاز به توضیح مجدد، پروژه را کامل بشناسد.

-----

## ۱. معرفی پروژه

ربات تلگرام فروشگاه موبایل **استوک لند** (`stland.ir`)

- زبان: **Python 3.13**
- کتابخانه اصلی: **python-telegram-bot 22.7**
- استقرار: **Railway**
- فروشگاه: **WooCommerce** روی `stland.ir`
- معماری: Bot polling + Flask web panel در یک پروسه (`app.py`)

-----

## ۲. ساختار فایل‌ها

```
├── bot.py          # ربات اصلی — 1756 خط — تمام منطق ربات اینجاست
├── woo.py          # اتصال به WooCommerce API — 304 خط
├── web.py          # پنل وب Flask — 434 خط
├── templates.py    # HTML پنل وب — 553 خط
├── app.py          # نقطه شروع — هر دو bot و web را اجرا می‌کند
├── requirements.txt
│
├── data.json       # متن بخش‌های ربات (پشتیبانی، آدرس، ...)
├── banner.json     # بنرهای هر بخش (file_id + active)
├── workhours.json  # ساعت کاری
├── buttons.json    # دکمه‌های inline هر بخش
├── settings.json   # تنظیمات (notify_new_user, store_open)
├── stats.json      # آمار بازدید بخش‌ها و محصولات
├── menu.json       # ترتیب و label دکمه‌های منوی اصلی
├── photomap.json   # cache عکس‌های محصول (URL → Telegram file_id)
└── users.db        # SQLite — کاربران و درخواست‌ها
```

-----

## ۳. متغیرهای محیطی (Railway Environment Variables)

|متغیر          |اجباری |توضیح                                               |
|---------------|-------|----------------------------------------------------|
|`BOT_TOKEN`    |✅      |توکن ربات از BotFather                              |
|`ADMIN_ID`     |✅      |آیدی عددی ادمین تلگرام                              |
|`WOO_URL`      |✅      |آدرس سایت — مثلاً `https://stland.ir`                |
|`WOO_KEY`      |✅      |WooCommerce Consumer Key (`ck_xxx`)                 |
|`WOO_SECRET`   |✅      |WooCommerce Consumer Secret (`cs_xxx`)              |
|`WEB_PASSWORD` |✅      |رمز ورود به پنل وب                                  |
|`WOO_CACHE_TTL`|اختیاری|مدت cache ووکامرس به ثانیه — پیش‌فرض: `3600` (۱ ساعت)|
|`WOO_HIDE_OOS` |اختیاری|مخفی‌کردن محصولات ناموجود — پیش‌فرض: `1`              |

-----

## ۴. پایگاه داده SQLite (`users.db`)

### جدول `users`

```sql
user_id INTEGER PRIMARY KEY
username TEXT
first_name TEXT
joined_at TEXT
last_seen TEXT
is_blocked INTEGER DEFAULT 0

INDEX: idx_ls ON (last_seen)
```

### جدول `requests`

```sql
id INTEGER PRIMARY KEY AUTOINCREMENT
user_id INTEGER
username TEXT
first_name TEXT
phone TEXT
product_id INTEGER
product_name TEXT
status TEXT DEFAULT 'new'   -- 'new' | 'done'
created_at TEXT

INDEX: idx_req_uid ON (user_id, product_id, created_at)
INDEX: idx_req_st ON (status)
```

### جداول `categories` و `products`

موجود در DB ولی استفاده نمی‌شوند (legacy از نسخه قبلی با local DB).  
ووکامرس اکنون مستقیم از API خوانده می‌شود.

-----

## ۵. فایل‌های JSON — ساختار داده

### `banner.json`

```json
{
  "catalog":   {"file_id": "AgAC...", "active": true},
  "welcome":   {"file_id": null,      "active": false},
  "1":         {"file_id": "AgAC...", "active": true},
  "workhours": {"file_id": null,      "active": false}
}
```

کلیدها همان `SECTION_NAMES` هستند.

### `data.json`

```json
{
  "welcome": "✨ خوش آمدید...",
  "1": "📞 پشتیبانی: ...",
  "2": "🌐 سایت: ...",
  "3": "📍 آدرس: ...",
  "4": "💰 اقساط: ...",
  "5": "📋 شرایط: ..."
}
```

### `buttons.json`

```json
{
  "1": {
    "enabled": true,
    "items": [
      {"id": "abc123", "text": "📞 تماس", "url": "https://..."}
    ]
  }
}
```

### `settings.json`

```json
{
  "notify_new_user": true,
  "store_open": true,
  "section_workhours": {"0": true, "1": true, ...}
}
```

### `menu.json`

```json
[
  {"key": "catalog", "label": "🛍 محصولات", "order": 1, "enabled": true, "width": "full"},
  {"key": "1",       "label": "📞 پشتیبانی", "order": 2, "enabled": true, "width": "half"},
  ...
]
```

-----

## ۶. بخش‌های ربات (SECTION_NAMES)

|کلید       |نام پیش‌فرض     |نوع               |
|-----------|---------------|------------------|
|`welcome`  |خوش‌آمدگویی     |متن استاتیک       |
|`catalog`  |محصولات        |از WooCommerce API|
|`1`        |شبکه‌های اجتماعی|متن استاتیک       |
|`2`        |سایت استوک لند |متن استاتیک       |
|`3`        |آدرس فروشگاه   |متن استاتیک       |
|`4`        |شرایط اقساط    |متن استاتیک       |
|`5`        |پشتیبانی       |متن استاتیک       |
|`workhours`|ساعت کاری      |محاسبه شده        |
|`6`        |(قابل تنظیم)   |متن استاتیک       |
|`7`        |(قابل تنظیم)   |متن استاتیک       |

**نکته:** بخش `catalog` متن ثابت و دکمه‌های inline **ندارد** — داده از WooCommerce می‌آید.

-----

## ۷. Callback Data های ربات

### مسیرهای کاربری (`_USER_CB_PREFIXES`)

|Prefix         |عملکرد                             |
|---------------|-----------------------------------|
|`cr_{id}`      |ورود به دسته ریشه                  |
|`cs_{id}`      |ورود به زیردسته                    |
|`prd_{id}`     |نمایش محصول                        |
|`req_{id}`     |درخواست خرید (بررسی is_open قبل)   |
|`pre_{id}`     |درخواست پیش‌خرید (بررسی is_open قبل)|
|`cat_back`     |بازگشت به کاتالوگ                  |
|`cat_search`   |جستجوی محصول                       |
|`wh_weekly`    |نمایش ساعت کاری هفتگی              |
|`wh_back_today`|بازگشت به ساعت امروز               |

### مسیرهای ادمین

|Callback                            |عملکرد                          |
|------------------------------------|--------------------------------|
|`back_to_admin`                     |پنل اصلی ادمین                  |
|`dash`                              |داشبورد آمار (asyncio.gather)   |
|`users_menu`                        |مدیریت کاربران                  |
|`admin_reqs` / `admin_reqs_{offset}`|لیست درخواست‌ها با pagination    |
|`rq_{id}`                           |جزئیات درخواست                  |
|`rq_done_{id}`                      |پیگیری درخواست + notify کاربر   |
|`rq_msg_{uid}`                      |پیام مستقیم به کاربر            |
|`export_reqs`                       |دانلود CSV همه درخواست‌ها        |
|`broadcast`                         |شروع پخش همگانی                 |
|`broadcast_cancel`                  |توقف پخش در حال اجرا            |
|`backup`                            |منوی بکاپ                       |
|`backup_get`                        |دریافت بکاپ فوری                |
|`backup_import`                     |بازگردانی از فایل               |
|`backup_auto_{i}`                   |بازگردانی یک‌کلیکه از بکاپ خودکار|
|`sections`                          |مدیریت بخش‌های ربات              |
|`sec_text_{key}`                    |ویرایش متن بخش                  |
|`sec_ban_{key}`                     |مدیریت بنر بخش                  |
|`sec_btns_{key}`                    |مدیریت دکمه‌های بخش              |
|`woo_status`                        |وضعیت اتصال WooCommerce         |
|`woo_refresh`                       |پاک کردن cache ووکامرس          |
|`noop`                              |دکمه غیرفعال (بدون عمل)         |

**نکته:** `sec_text_catalog` و `sec_btns_catalog` block هستند — catalog از API می‌خواند.

-----

## ۸. حالت‌های `ctx.user_data` (User State Machine)

|mode            |جریان                     |داده‌های ذخیره‌شده                 |
|----------------|--------------------------|---------------------------------|
|`req_phone`     |ثبت درخواست خرید/پیش‌خرید  |`req_pid`, `req_name`, `req_type`|
|`cat_search`    |جستجوی محصول              |—                                |
|`broadcast`     |پخش همگانی                |—                                |
|`backup_restore`|بازگردانی بکاپ            |—                                |
|`admin_msg`     |پیام مستقیم ادمین به کاربر|`admin_msg_uid`                  |
|`edit_text`     |ویرایش متن بخش            |`edit_key`                       |
|`menu_rename`   |تغییر نام دکمه منو        |`menu_key`                       |
|`ban_up`        |آپلود بنر                 |`ban_key`                        |
|`btn_add_t`     |افزودن دکمه — مرحله متن   |`btn_key`                        |
|`btn_add_u`     |افزودن دکمه — مرحله URL   |`btn_key`, `btn_text`            |
|`btn_ed_t`      |ویرایش دکمه — مرحله متن   |`btn_key`, `btn_id`              |
|`btn_ed_u`      |ویرایش دکمه — مرحله URL   |`btn_key`, `btn_id`, `btn_text`  |
|`wh_shifts`     |تنظیم ساعت روز            |`wh_day`                         |
|`wh_mop`        |پیام باز                  |—                                |
|`wh_mcl`        |پیام بسته                 |—                                |
|`users_search`  |جستجوی کاربر              |—                                |

-----

## ۹. سیستم Anti-Spam (دو فازی)

```python
_rate:       dict  # uid → [timestamps]
_warned:     dict  # uid → زمان اولین هشدار
_hard_block: dict  # uid → blocked_until
_RATE_MAX = 8      # حداکثر کلیک در پنجره
_RATE_WIN = 10.0   # پنجره ۱۰ ثانیه
_HARD_BLOCK = 10.0 # ۱۰ ثانیه بلاک سخت
```

**جریان:**

1. کلیک ۱-۸ در ۱۰ ثانیه → مجاز
1. کلیک ۹ام → **warn** → popup «آرامتر کلیک کنید» — ریپلای نمی‌آید
1. کلیک بعد از warn → **block** → ۱۰ ثانیه بی‌صدا

**استثناها:**

- `ADMIN_ID`: از همه چک‌ها معاف
- `req_` و `pre_` callbacks: از spam_check معاف (درخواست خرید نباید بلاک شود)
- `req_phone` mode در text_handler: از spam_check معاف (حین ثبت شماره)

**Cleanup:** هر ۶ ساعت توسط `_spam_cleanup_loop` — `_rate`, `_warned`, `_hard_block`, `_block_cache`, `_seen_uids` پاک می‌شوند.

-----

## ۱۰. سیستم Cache ووکامرس (woo.py)

```
CACHE_TTL      = 3600  # ۱ ساعت
WARM_INTERVAL  = 600   # ۱۰ دقیقه بین دو warm
VERSION_CHECK  = 60    # ۱ دقیقه بین دو version check
```

**جریان warm cache:**

```
any user interaction
  → _trigger_warm() [background, non-blocking]
  → maybe_warm_cache()
    → if now - _last_warm_time < 600: return  # skip
    → _clean_cache()  # حذف expired
    → warm_cache()
      → get_categories() → cache cats
      → برای هر subcategory: get_products_by_category() [5 موازی با Semaphore]
```

**Keys در `_cache`:**

- `cats` — لیست دسته‌بندی‌ها
- `root_cats` — دسته‌های ریشه
- `subcats_{id}` — زیردسته‌های هر دسته
- `cat_{id}` — اطلاعات یک دسته
- `prods_{cat_id}` — محصولات یک دسته
- `prod_{pid}` — یک محصول
- `search_{q}` — نتیجه جستجو
- `visible_cats` — آیدی دسته‌های مجاز (از افزونه)

**HTTP Session:**
یک `aiohttp.ClientSession` دائمی با connection pool (limit=10).  
در صورت خطا: `_reset_session()` → بازسازی خودکار.  
در shutdown: بسته می‌شود توسط `post_shutdown`.

-----

## ۱۱. Background Tasks (asyncio.ensure_future در post_init)

|تابع                    |فرکانس             |کار                             |
|------------------------|-------------------|--------------------------------|
|`_trigger_warm()`       |یک‌بار هنگام startup|warm اولیه cache                |
|`_spam_cleanup_loop()`  |هر ۶ ساعت          |پاک کردن dicts anti-spam        |
|`_stats_flush_loop()`   |هر ۳۰ ثانیه        |ذخیره stats و photomap اگر dirty|
|`_auto_backup_loop(bot)`|هر شب ۳ بامداد     |بکاپ خودکار به ادمین            |

-----

## ۱۲. سیستم Backup

**بکاپ دستی:** دکمه «💾 دریافت پشتیبان» در پنل ادمین  
**بکاپ خودکار:** هر شب ساعت ۳ بامداد به وقت تهران

**محتوای بکاپ (ZIP):**
`data.json`, `banner.json`, `workhours.json`, `buttons.json`,
`settings.json`, `stats.json`, `menu.json`, `users.db`

**Rotation:** حداکثر ۵ بکاپ در چت ادمین — ششمی که بیاید اولی حذف می‌شود.  
نگهداری `_backup_registry = [{"msg_id", "file_id", "date"}]`

**بازگردانی:**

- از فایل: دکمه «📥 بارگذاری فایل» → فایل ZIP ارسال
- یک‌کلیکه: دکمه‌های «♻️ تاریخ» برای هر بکاپ خودکار

-----

## ۱۳. سیستم Broadcast

```python
_broadcast_active = False  # جلوگیری از پخش دوگانه
_broadcast_cancel = False  # توقف اضطراری
```

- نرخ: `0.05s` بین هر پیام (~۲۰ msg/s، زیر حد Telegram)
- RetryAfter: اگر Telegram flood گفت، صبر می‌کند
- دکمه «🛑 توقف پخش» روی status message
- Progress: هر ۲۰ پیام آپدیت می‌شود

-----

## ۱۴. درخواست خرید — جریان کامل

```
کاربر روی «📋 درخواست خرید» کلیک می‌کند
  → بررسی is_open() [قبل از query.answer]
    → بسته: popup «فروشگاه بسته» → تمام
    → باز: ادامه
  → mode = req_phone
  → کاربر شماره تماس می‌فرستد
    → بررسی spam (req_phone mode معاف)
    → validate شماره
    → بررسی تکراری (۲۴ ساعت)
      → تکراری: پیام «قبلاً ثبت کرده‌اید» → تمام
    → save_request() → rid
    → اعلان به ادمین با دکمه‌های inline:
      [✅ پیگیری شد] [💬 پیام به کاربر]
    → پیام تأیید به کاربر
```

**پس از پیگیری:**

- از اعلان notification: دکمه‌ها حذف می‌شوند (پیام اعلان باقی می‌ماند)
- از پنل مدیریت: برگشت به لیست درخواست‌های به‌روزشده
- در هر دو حالت: پیام «درخواست شما پیگیری شد» به کاربر
- جلوگیری از double-done: بررسی `status == 'done'` قبل از عمل

-----

## ۱۵. بهینه‌سازی‌های انجام‌شده

### bot.py

|بهینه‌سازی                         |توضیح                                           |
|----------------------------------|------------------------------------------------|
|`asyncio.gather` در dashboard     |۶ query موازی به جای sequential                 |
|`save_user` throttle 5 دقیقه      |`_seen_uids` — ۹۵٪ کمتر DB write                |
|`_photo_fileids` → `photomap.json`|cache عکس بین restart‌ها حفظ می‌شود               |
|Index روی requests                |`(user_id, product_id, created_at)` و `(status)`|
|SQLite 4 PRAGMA                   |WAL + NORMAL + cache_size=8MB + MEMORY temp     |
|Atomic JSON write                 |write به `.tmp` سپس `os.replace`                |
|`_stats_flush_loop`               |dirty flag + flush هر ۳۰ ثانیه                  |
|`is_blocked` cache                |`_block_cache` با TTL=60s — یک DB query در دقیقه|
|`_photo_fileids` limit 500        |eviction قدیمی‌ترین ورودی                        |
|`post_shutdown`                   |flush stats + photomap + close HTTP session     |
|جستجو با شماره تلفن               |از جدول requests، نه فقط users                  |
|Export CSV                        |BOM برای Excel، `io.StringIO`                   |
|Graceful shutdown                 |`post_shutdown` در PTB                          |

### woo.py

|بهینه‌سازی              |توضیح                                        |
|-----------------------|---------------------------------------------|
|Persistent HTTP Session|یک `ClientSession` با connection pool        |
|`_reset_session()`     |auto-reconnect در صورت connection error      |
|`_fetch` retry         |یک retry با ۱ ثانیه تأخیر                    |
|`_fetch_all` rollback  |اگر هر صفحه‌ای fail کند، `None` — نه داده ناقص|
|`_clean_cache()`       |حذف expired entries قبل از هر warm           |
|`maybe_warm_cache()`   |Interval-based (۱۰ دقیقه) — activity-driven  |
|`_trim_desc(130)`      |توضیح محصول حداکثر ۱۳۰ کاراکتر               |
|محصولات onbackorder    |همیشه نمایش — فقط outofstock مخفی            |

-----

## ۱۶. پنل وب (web.py + Flask)

آدرس: پورت ۵۰۰۰ (یا هر پورت Railway)  
ورود با `WEB_PASSWORD`

**Endpoints فعال:**

- `GET /` — صفحه اصلی پنل
- `GET /api/dashboard` — آمار کاربران (با try-except)
- `GET /api/tree` — درخت دسته‌ها (از SQLite — ممکن است خالی باشد)
- `GET /api/products/<id>` — محصولات زیردسته (از SQLite — ممکن است خالی)
- `POST /webhook/woo` — وب‌هوک WooCommerce
- `GET /api/tg-categories` — فیلتر دسته‌ها

**نکته مهم:** جداول `products` و `categories` در SQLite موجودند ولی bot از WooCommerce API مستقیم می‌خواند. پنل وب برای محصولات ممکن است خالی نشان دهد.

-----

## ۱۷. افزونه WooCommerce (stockland plugin)

Endpoint های سفارشی:

- `GET /wp-json/stockland/v1/version` — نسخه sync برای تشخیص تغییرات
- `GET /wp-json/stockland/v1/visible-categories` — دسته‌های مجاز برای نمایش
- `GET /wp-json/stockland/v1/settings` — تنظیمات (در حال حاضر استفاده نمی‌شود)

-----

## ۱۸. چیزهایی که پیاده نشده (scope خارج از پروژه)

- **چت دوطرفه کاربر↔ادمین**: توصیه می‌شود از آیدی تلگرام ادمین در بخش پشتیبانی استفاده شود
- **PostgreSQL**: در صورت رشد به ۵۰۰۰+ کاربر
- **Push notification WooCommerce**: اکنون polling هر ۱۰ دقیقه
- **Multi-admin**: فقط یک ادمین پشتیبانی می‌شود (`ADMIN_ID`)
- **سبد خرید**: درخواست‌ها تک‌محصوله هستند

-----

## ۱۹. راه‌اندازی مجدد (Redeploy)

۱. بکاپ بگیرید (پنل ادمین → تنظیمات → پشتیبان‌گیری)
۲. deploy کنید
۳. بکاپ را restore کنید («📥 بارگذاری فایل» یا «♻️» از بکاپ خودکار)

**فایل‌هایی که بعد از redeploy بازمی‌گردند:**  
`data.json`, `banner.json`, `workhours.json`, `buttons.json`,  
`settings.json`, `stats.json`, `menu.json`, `users.db`, `photomap.json`

-----

## ۲۰. نکات مهم برای توسعه آینده

1. **هر تغییر در `woo.py`:** توجه به `_http_session` singleton — نباید دو session همزمان ساخته شود
1. **اضافه کردن section جدید:** باید در `SECTION_NAMES`, `SECTION_ORDER`, `DEFAULT_MENU` و `DEFAULT_SEC_WH` اضافه شود
1. **Callback جدید برای کاربر:** باید در `_USER_CB_PREFIXES` اضافه شود
1. **ذخیره فایل JSON:** همیشه از `_wj()` استفاده کنید (atomic write)
1. **هیچ await در `spam_check` نباشد:** باید sync بماند
1. **`query.answer()` فقط یک بار:** هر callback فقط یک‌بار answer می‌زند
1. **بنر catalog:** فقط بنر دارد — متن و دکمه ثابت ندارد (guard در callback handler)