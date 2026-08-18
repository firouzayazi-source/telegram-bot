# ربات تلگرام استوک لند — مستندات کامل پروژه

> **نسخه:** نهایی (بهینه‌سازی‌شده)  
> **استفاده:** این فایل را به Claude بدهید تا بدون نیاز به توضیح مجدد، پروژه را کامل بشناسد.

-----

## ۱. معرفی پروژه

ربات تلگرام فروشگاه موبایل **استوک لند** (`stland.ir`)

- زبان: **Python 3.13**
- کتابخانه اصلی: **python-telegram-bot 22.7**
- استقرار: **وی‌پی‌اس اختصاصی** (systemd) — بدون Railway
- معماری: Bot polling — یک پروسه‌ی تنها (`bot.py`)
- **هیچ پورتی روی سرور باز نمی‌کند** — فقط خروجی به تلگرام

-----

## ۲. ساختار فایل‌ها

```
├── bot.py          # ربات اصلی — تمام منطق ربات اینجاست
├── requirements.txt
│
├── data.json       # متن بخش‌های ربات (پشتیبانی، آدرس، ...)
├── banner.json     # بنرهای هر بخش (file_id + active)
├── workhours.json  # ساعت کاری
├── buttons.json    # دکمه‌های inline هر بخش
├── settings.json   # تنظیمات (notify_new_user, store_open)
├── stats.json      # آمار بازدید بخش‌ها
├── menu.json       # ترتیب و label دکمه‌های منوی اصلی
└── users.db        # SQLite — کاربران و درخواست‌ها
```

-----

## ۳. متغیرهای محیطی

|متغیر          |اجباری |توضیح                                               |
|---------------|-------|----------------------------------------------------|
|`BOT_TOKEN`    |✅      |توکن ربات از BotFather                              |
|`ADMIN_ID`     |✅      |آیدی عددی ادمین تلگرام                              |

همین دو متغیر کافی است. ربات پورتی باز نمی‌کند، رمزی نمی‌خواهد و هیچ سرویسی روی اینترنت expose نمی‌کند — تمام مدیریت از پنل ادمین داخل خود تلگرام (`/admin`) انجام می‌شود.

-----

## ۳.۱. استقرار روی وی‌پی‌اس (systemd)

این پروژه با گیت‌هاب و اجرای مستقیم روی وی‌پی‌اس (بدون Railway/Heroku) کار می‌کند و **کاملاً مستقل از سایر پروژه‌های همان سرور** است — فقط منابع سرور مشترک است، نه فایل‌ها، دیتابیس، یا پورت.

```bash
# ۱) کلون در مسیر اختصاصی خودِ همین پروژه
git clone <repo-url> /opt/telegram-bot
cd /opt/telegram-bot

# ۲) محیط پایتون مجزا
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# ۳) فایل .env با BOT_TOKEN و ADMIN_ID
cp .env.example .env   # سپس مقداردهی کنید
```

نمونه سرویس systemd در `deploy/telegram-bot.service` آماده است — فقط مسیرها و `User` را مطابق سرور خودتان تنظیم کنید:

```bash
sudo cp deploy/telegram-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-bot
sudo journalctl -u telegram-bot -f
```

برای آپدیت بعدی:

```bash
cd /opt/telegram-bot && git pull && sudo systemctl restart telegram-bot
```

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

درخواست‌های کاربران (پشتیبانی/تماس) — از طریق پنل ادمین مدیریت می‌شود.

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

-----

## ۵. فایل‌های JSON — ساختار داده

### `banner.json`

```json
{
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
  {"key": "1", "label": "📞 پشتیبانی", "order": 1, "enabled": true, "width": "half"},
  ...
]
```

-----

## ۶. بخش‌های ربات (SECTION_NAMES)

|کلید       |نام پیش‌فرض     |نوع               |
|-----------|---------------|------------------|
|`welcome`  |خوش‌آمدگویی     |متن استاتیک       |
|`contact`  |درخواست تماس   |فرم — شماره می‌گیرد|
|`1`        |شبکه‌های اجتماعی|متن استاتیک       |
|`2`        |سایت استوک لند |متن استاتیک       |
|`3`        |آدرس فروشگاه   |متن استاتیک       |
|`4`        |شرایط اقساط    |متن استاتیک       |
|`5`        |پشتیبانی       |متن استاتیک       |
|`workhours`|ساعت کاری      |محاسبه شده        |
|`6`        |(قابل تنظیم)   |متن استاتیک       |
|`7`        |(قابل تنظیم)   |متن استاتیک       |

-----

## ۷. Callback Data های ربات

### مسیرهای کاربری (`_USER_CB_PREFIXES`)

|Prefix         |عملکرد                             |
|---------------|-----------------------------------|
|`wh_weekly`    |نمایش ساعت کاری هفتگی              |
|`wh_back_today`|بازگشت به ساعت امروز               |

### مسیرهای ادمین

|Callback                            |عملکرد                          |
|------------------------------------|--------------------------------|
|`back_to_admin`                     |پنل اصلی ادمین                  |
|`dash`                              |داشبورد آمار (asyncio.gather)   |
|`stats_page`                        |آمار بازدید بخش‌ها               |
|`stats_reset`                       |صفر کردن آمار بازدید            |
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
|`noop`                              |دکمه غیرفعال (بدون عمل)         |

-----

## ۸. حالت‌های `ctx.user_data` (User State Machine)

|mode            |جریان                     |داده‌های ذخیره‌شده                 |
|----------------|--------------------------|---------------------------------|
|`req_phone`     |ثبت درخواست تماس          |—                                |
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
- `req_phone` mode: از spam_check معاف (حین ثبت شماره تماس نباید بلاک شود)

**Cleanup:** هر ۶ ساعت توسط `_spam_cleanup_loop` — `_rate`, `_warned`, `_hard_block`, `_block_cache`, `_seen_uids` پاک می‌شوند.

-----

## ۱۰. Background Tasks (asyncio.ensure_future در post_init)

|تابع                    |فرکانس             |کار                             |
|------------------------|-------------------|--------------------------------|
|`_spam_cleanup_loop()`  |هر ۶ ساعت          |پاک کردن dicts anti-spam        |
|`_stats_flush_loop()`   |هر ۳۰ ثانیه        |ذخیره stats اگر dirty           |
|`_auto_backup_loop(bot)`|هر شب ۳ بامداد     |بکاپ خودکار به ادمین            |

-----

## ۱۱. سیستم Backup

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

## ۱۲. سیستم Broadcast

```python
_broadcast_active = False  # جلوگیری از پخش دوگانه
_broadcast_cancel = False  # توقف اضطراری
```

- نرخ: `0.05s` بین هر پیام (~۲۰ msg/s، زیر حد Telegram)
- RetryAfter: اگر Telegram flood گفت، صبر می‌کند
- دکمه «🛑 توقف پخش» روی status message
- Progress: هر ۲۰ پیام آپدیت می‌شود

-----

## ۱۳. بهینه‌سازی‌های انجام‌شده (bot.py)

|بهینه‌سازی                     |توضیح                                           |
|-------------------------------|------------------------------------------------|
|`asyncio.gather` در dashboard  |۶ query موازی به جای sequential                 |
|`save_user` throttle 5 دقیقه   |`_seen_uids` — ۹۵٪ کمتر DB write                |
|Index روی requests             |`(user_id, product_id, created_at)` و `(status)`|
|SQLite 4 PRAGMA                |WAL + NORMAL + cache_size=8MB + MEMORY temp     |
|Atomic JSON write              |write به `.tmp` سپس `os.replace`                |
|`_stats_flush_loop`            |dirty flag + flush هر ۳۰ ثانیه                  |
|`is_blocked` cache             |`_block_cache` با TTL=60s — یک DB query در دقیقه|
|جستجو با شماره تلفن            |از جدول requests، نه فقط users                  |
|Export CSV                     |BOM برای Excel، `io.StringIO`                   |
|Graceful shutdown              |`post_shutdown` در PTB                          |

-----

## ۱۴. پنل مدیریت (داخل تلگرام)

تمام مدیریت با دستور `/admin` در خود تلگرام انجام می‌شود — پنل وبی وجود ندارد.

|بخش              |کارها                                                     |
|-----------------|----------------------------------------------------------|
|📊 داشبورد        |آمار کاربران + دکمه «📈 آمار بخش‌ها» (بازدید هر بخش)         |
|👥 کاربران        |جستجو، بلاک/رفع بلاک، لیست امروز و بلاک‌شده‌ها               |
|📬 درخواست‌ها      |لیست با صفحه‌بندی، پیگیری، پیام مستقیم، خروجی CSV           |
|🕐 ساعت کاری      |شیفت‌های هر روز، پیام باز/بسته                             |
|📣 پخش همگانی     |ارسال به همه کاربران با نوار پیشرفت و دکمه توقف            |
|⚙️ تنظیمات        |مدیریت منو، مدیریت بخش‌ها (متن/بنر/دکمه)، پشتیبان‌گیری       |

**چرا پنل وب حذف شد:** پنل وب زیرمجموعه‌ی همین پنل بود (پخش همگانی، پشتیبان‌گیری
و مدیریت منو را هم نداشت) و در اصل برای نمایش محصولاتِ خوانده‌شده از وردپرس
ساخته شده بود که آن هم حذف شد. با حذفش ربات دیگر هیچ پورتی باز نمی‌کند، رمزی
نمی‌خواهد و روی وی‌پی‌اس مشترک با هیچ پروژه‌ای تداخل ندارد.

-----

## ۱۴.۱. درخواست تماس — جریان کامل

```
کاربر «📝 درخواست تماس» را می‌زند
  → بررسی is_open()
    → بسته: پیام «در ساعات کاری مراجعه کنید» → تمام
    → باز: متن معرفی (قابل ویرایش از پنل، بخش contact) + بنر
  → mode = req_phone
  → کاربر شماره می‌فرستد (ارقام فارسی/عربی هم پذیرفته می‌شود)
    → spam_check در این حالت معاف است
    → اعتبارسنجی: ۱۰ تا ۱۳ رقم
    → بررسی تکراری (۲۴ ساعت، بر اساس user_id)
      → تکراری: «قبلاً ثبت کرده‌اید» → تمام
    → save_request() → rid
    → اعلان به ادمین با دکمه‌های [✅ پیگیری شد] [💬 پیام به کاربر]
    → پیام تأیید به کاربر
```

-----

## ۱۵. چیزهایی که پیاده نشده (scope خارج از پروژه)

- **چت دوطرفه کاربر↔ادمین**: توصیه می‌شود از آیدی تلگرام ادمین در بخش پشتیبانی استفاده شود
- **PostgreSQL**: در صورت رشد به ۵۰۰۰+ کاربر
- **Multi-admin**: فقط یک ادمین پشتیبانی می‌شود (`ADMIN_ID`)

-----

## ۱۶. راه‌اندازی مجدد (Redeploy)

۱. بکاپ بگیرید (پنل ادمین → تنظیمات → پشتیبان‌گیری)
۲. deploy کنید
۳. بکاپ را restore کنید («📥 بارگذاری فایل» یا «♻️» از بکاپ خودکار)

**فایل‌هایی که بعد از redeploy بازمی‌گردند:**  
`data.json`, `banner.json`, `workhours.json`, `buttons.json`,  
`settings.json`, `stats.json`, `menu.json`, `users.db`

-----

## ۱۷. نکات مهم برای توسعه آینده

1. **اضافه کردن section جدید:** باید در `SECTION_NAMES`, `SECTION_ORDER`, `DEFAULT_MENU` و `DEFAULT_SEC_WH` اضافه شود
1. **Callback جدید برای کاربر:** باید در `_USER_CB_PREFIXES` اضافه شود
1. **ذخیره فایل JSON:** همیشه از `_wj()` استفاده کنید (atomic write)
1. **هیچ await در `spam_check` نباشد:** باید sync بماند
1. **`query.answer()` فقط یک بار:** هر callback فقط یک‌بار answer می‌زند
