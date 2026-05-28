import os
import json
import time
import asyncio
import logging
import aiosqlite
import jdatetime
import pytz
from datetime import datetime
from collections import defaultdict, deque
import aiofiles

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.error import TelegramError

# ======================================
# DISABLE PROXY
# ======================================
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("ALL_PROXY", None)
os.environ["NO_PROXY"] = "*"

# ======================================
# CONFIG
# ======================================
TOKEN = os.getenv("BOT_TOKEN", "8792062012:AAGXforSa1IY45AuC-yOHs2PsdzudvtdD44")
ADMIN_ID = int(os.getenv("ADMIN_ID", "638469407"))

DATA_FILE = "data.json"
DB_FILE = "users.db"
BANNER_FILE = "banner.json"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ======================================
# TIME
# ======================================
IRAN_TZ = pytz.timezone("Asia/Tehran")

def shamsi_now():
    now = datetime.now(IRAN_TZ)
    j_now = jdatetime.datetime.fromgregorian(datetime=now)
    return j_now.strftime("%Y/%m/%d - %H:%M")

def gregorian_now():
    return datetime.now(IRAN_TZ).strftime("%Y-%m-%d %H:%M:%S")

# ======================================
# MENU
# ======================================
MENU_ITEMS = {
    "1": "🌐 شبکه‌های اجتماعی",
    "2": "🌐 سایت استوک لند",
    "3": "💰 شرایط اقساط",
    "4": "📞 پشتیبانی",
    "5": "📍 آدرس فروشگاه"
}

# ======================================
# GLOBAL
# ======================================
responses = None

# ساختار بنر:
# {
#   "file_id": "...",          # file_id عکس در تلگرام
#   "caption": "...",          # کپشن اختیاری
#   "active": true/false,      # فعال یا غیرفعال
#   "show_on": ["welcome", "1", "2", "3", "4", "5"]  # کجاها نمایش داده شود
# }
banner = {
    "file_id": None,
    "caption": "",
    "active": False,
    "show_on": ["welcome", "1", "2", "3", "4", "5"]
}

async def load_data():
    global responses
    try:
        async with aiofiles.open(DATA_FILE, "r", encoding="utf-8") as f:
            responses = json.loads(await f.read())
    except:
        responses = MENU_ITEMS.copy()
        responses["welcome"] = "✨ خوش آمدید به ربات استوک لند"

async def save_data():
    try:
        async with aiofiles.open(DATA_FILE, "w", encoding="utf-8") as f:
            await f.write(json.dumps(responses, ensure_ascii=False, indent=4))
    except Exception as e:
        logger.error(f"Save error: {e}")

async def load_banner():
    global banner
    try:
        async with aiofiles.open(BANNER_FILE, "r", encoding="utf-8") as f:
            banner = json.loads(await f.read())
    except:
        pass  # از مقدار پیش‌فرض استفاده می‌شود

async def save_banner():
    try:
        async with aiofiles.open(BANNER_FILE, "w", encoding="utf-8") as f:
            await f.write(json.dumps(banner, ensure_ascii=False, indent=4))
    except Exception as e:
        logger.error(f"Banner save error: {e}")

# ======================================
# DATABASE
# ======================================
db = None

async def init_db():
    global db
    db = await aiosqlite.connect(DB_FILE)
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        joined_at TEXT, last_seen TEXT)""")
    await db.execute("""CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        action TEXT, created_at TEXT)""")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_lastseen ON users(last_seen)")
    await db.commit()

async def save_user(user):
    now = gregorian_now()
    await db.execute("INSERT OR IGNORE INTO users VALUES (?,?,?,?,?)",
                     (user.id, user.username or "", user.first_name or "", now, now))
    await db.execute("UPDATE users SET username=?, first_name=?, last_seen=? WHERE user_id=?",
                     (user.username or "", user.first_name or "", now, user.id))
    await db.commit()

async def log_event(user_id: int, action: str):
    await db.execute("INSERT INTO logs (user_id, action, created_at) VALUES (?,?,?)",
                     (user_id, action, gregorian_now()))
    await db.commit()

async def get_all_users():
    async with db.execute("SELECT user_id FROM users") as c:
        return [r[0] for r in await c.fetchall()]

# ======================================
# ANALYTICS + ANTISPAM
# ======================================
async def total_users():
    async with db.execute("SELECT COUNT(*) FROM users") as c:
        return (await c.fetchone())[0]

async def today_users():
    async with db.execute("SELECT COUNT(*) FROM users WHERE DATE(last_seen)=DATE('now')") as c:
        return (await c.fetchone())[0]

WINDOW, LIMIT, BLOCK = 10, 7, 60
spam = defaultdict(lambda: deque(maxlen=LIMIT))
blocked = {}

async def anti_spam(user_id: int) -> bool:
    if user_id == ADMIN_ID: return True
    now = time.time()
    if user_id in blocked and blocked[user_id] > now: return False
    q = spam[user_id]
    q.append(now)
    if len(q) >= LIMIT and (now - q[0]) <= WINDOW:
        blocked[user_id] = now + BLOCK
        return False
    return True

# ======================================
# KEYBOARDS
# ======================================
def main_menu():
    return ReplyKeyboardMarkup([
        [MENU_ITEMS["1"], MENU_ITEMS["2"]],
        [MENU_ITEMS["3"], MENU_ITEMS["4"]],
        [MENU_ITEMS["5"]]
    ], resize_keyboard=True)

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 داشبورد", callback_data="dash")],
        [InlineKeyboardButton("👤 کاربران", callback_data="users")],
        [InlineKeyboardButton("✏️ مدیریت محتوا", callback_data="edit")],
        [InlineKeyboardButton("🖼 مدیریت بنر", callback_data="banner_menu")],
        [InlineKeyboardButton("📢 پخش همگانی", callback_data="broadcast")],
        [InlineKeyboardButton("📈 لاگ‌ها", callback_data="logs")]
    ])

def back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="back_to_admin")]])

def admin_cancel_menu():
    return ReplyKeyboardMarkup([["❌ لغو عملیات"]], resize_keyboard=True)

def box(title: str, text: str):
    return f"""
📌 {title}
──────────────
{text}
──────────────
🕒 {shamsi_now()}
"""

def banner_menu_keyboard():
    status = "✅ فعال" if banner.get("active") else "❌ غیرفعال"
    toggle_label = "🔴 غیرفعال کردن بنر" if banner.get("active") else "🟢 فعال کردن بنر"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"وضعیت بنر: {status}", callback_data="banner_status_info")],
        [InlineKeyboardButton("🖼 آپلود / تغییر عکس بنر", callback_data="banner_upload")],
        [InlineKeyboardButton("📍 انتخاب محل نمایش بنر", callback_data="banner_locations")],
        [InlineKeyboardButton(toggle_label, callback_data="banner_toggle")],
        [InlineKeyboardButton("🗑 حذف بنر", callback_data="banner_delete")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="back_to_admin")]
    ])

def banner_locations_keyboard():
    """کیبورد انتخاب محل نمایش بنر"""
    show_on = banner.get("show_on", [])
    location_map = {
        "welcome": "🏠 خوش‌آمدگویی",
        "1": "🌐 شبکه‌های اجتماعی",
        "2": "🌐 سایت استوک لند",
        "3": "💰 شرایط اقساط",
        "4": "📞 پشتیبانی",
        "5": "📍 آدرس فروشگاه"
    }
    buttons = []
    for key, label in location_map.items():
        check = "✅" if key in show_on else "⬜️"
        buttons.append([InlineKeyboardButton(f"{check} {label}", callback_data=f"banner_loc_{key}")])
    buttons.append([InlineKeyboardButton("🔙 برگشت به بنر", callback_data="banner_menu")])
    return InlineKeyboardMarkup(buttons)

# ======================================
# BANNER SENDER
# ======================================
async def send_with_banner(update_or_message, text: str, section_key: str, reply_markup=None):
    """
    ارسال پیام یکپارچه — اگر بنر فعال باشد:
      عکس بنر + متن منو به عنوان کپشن = یک پیام واحد (مثل poll تلگرام)
    در غیر این صورت فقط متن ارسال می‌شود.
    """
    msg = update_or_message if hasattr(update_or_message, 'reply_text') else update_or_message.message

    should_show_banner = (
        banner.get("active")
        and banner.get("file_id")
        and section_key in banner.get("show_on", [])
    )

    if should_show_banner:
        try:
            # متن منو مستقیماً کپشن عکس میشه — یک پیام واحد
            await msg.reply_photo(
                photo=banner["file_id"],
                caption=text,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Banner send error: {e}")
            # اگر خطا داشت، fallback به متن ساده
            if reply_markup:
                await msg.reply_text(text, reply_markup=reply_markup)
            else:
                await msg.reply_text(text)
    else:
        # بدون بنر — فقط متن
        if reply_markup:
            await msg.reply_text(text, reply_markup=reply_markup)
        else:
            await msg.reply_text(text)

# ======================================
# BROADCAST
# ======================================
async def send_broadcast(context: ContextTypes.DEFAULT_TYPE, text: str):
    users = await get_all_users()
    total = len(users)
    success = failed = 0
    status = await context.bot.send_message(ADMIN_ID, f"📢 شروع پخش به {total} کاربر...")

    for i, uid in enumerate(users, 1):
        try:
            await context.bot.send_message(uid, text)
            success += 1
        except:
            failed += 1
        if i % 10 == 0 or i == total:
            await status.edit_text(f"📢 در حال پخش...\n✅ موفق: {success}\n❌ شکست: {failed}\n{i}/{total}")
        await asyncio.sleep(0.2)

    await status.edit_text(f"✅ پخش تمام شد!\nموفق: {success} | شکست: {failed}")

# ======================================
# HANDLERS
# ======================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await save_user(user)
    await log_event(user.id, "start")

    welcome_text = responses.get("welcome", "✨ خوش آمدید به ربات استوک لند")
    await send_with_banner(update.message, welcome_text, "welcome", reply_markup=main_menu())

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ دسترسی ندارید")
    await update.message.reply_text("👑 پنل مدیریت", reply_markup=admin_menu())

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID: return

    data = query.data

    # ======== برگشت به پنل ادمین ========
    if data == "back_to_admin":
        await query.message.edit_text("👑 پنل مدیریت", reply_markup=admin_menu())
        return

    # ======== داشبورد ========
    if data == "dash":
        t = await total_users()
        d = await today_users()
        await query.message.edit_text(box("داشبورد", f"👥 کل کاربران: {t}\n📅 امروز: {d}"), reply_markup=admin_menu())

    # ======== کاربران ========
    elif data == "users":
        async with db.execute("SELECT user_id, first_name, last_seen FROM users ORDER BY last_seen DESC LIMIT 15") as c:
            rows = await c.fetchall()
        text = "👤 کاربران اخیر:\n\n" + "\n".join([f"• {r[1]} | {r[0]}" for r in rows])
        await query.message.edit_text(text, reply_markup=back_button())

    # ======== لاگ‌ها ========
    elif data == "logs":
        async with db.execute("SELECT user_id, action, created_at FROM logs ORDER BY id DESC LIMIT 15") as c:
            rows = await c.fetchall()
        text = "📈 لاگ‌ها:\n\n" + "\n".join([f"• {r[1]} | {r[0]}" for r in rows])
        await query.message.edit_text(text, reply_markup=back_button())

    # ======== مدیریت محتوا ========
    elif data == "edit":
        await query.message.edit_text("✏️ مدیریت محتوا", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 شبکه‌ها", callback_data="e_1")],
            [InlineKeyboardButton("🌐 سایت", callback_data="e_2")],
            [InlineKeyboardButton("💰 اقساط", callback_data="e_3")],
            [InlineKeyboardButton("📞 پشتیبانی", callback_data="e_4")],
            [InlineKeyboardButton("📍 آدرس", callback_data="e_5")],
            [InlineKeyboardButton("✉️ تنظیم پیام خوش‌آمدگویی", callback_data="set_welcome")],
            [InlineKeyboardButton("🔙 برگشت", callback_data="back_to_admin")]
        ]))

    elif data.startswith("e_"):
        key = data.split("_")[1]
        context.user_data["edit_key"] = key
        context.user_data["mode"] = "edit"
        current = responses.get(key, "تنظیم نشده")
        await query.message.reply_text(f"📝 متن فعلی:\n\n{current}\n\nمتن جدید را ارسال کنید:", reply_markup=admin_cancel_menu())

    elif data == "set_welcome":
        context.user_data["mode"] = "set_welcome"
        current = responses.get("welcome", "پیام پیش‌فرض")
        await query.message.reply_text(
            f"📝 پیام خوش‌آمدگویی فعلی:\n\n{current}\n\nمتن جدید را ارسال کنید:",
            reply_markup=admin_cancel_menu()
        )

    # ======== پخش همگانی ========
    elif data == "broadcast":
        context.user_data["mode"] = "broadcast"
        await query.message.reply_text("📢 متن پیام پخش همگانی را ارسال کنید:", reply_markup=admin_cancel_menu())

    # ======================================
    # مدیریت بنر
    # ======================================
    elif data == "banner_menu":
        file_id = banner.get("file_id")
        caption = banner.get("caption", "")
        active = banner.get("active", False)
        show_on = banner.get("show_on", [])

        location_names = {
            "welcome": "خوش‌آمدگویی", "1": "شبکه‌ها", "2": "سایت",
            "3": "اقساط", "4": "پشتیبانی", "5": "آدرس"
        }
        show_labels = ", ".join([location_names.get(k, k) for k in show_on]) or "هیچ‌کدام"

        info = (
            f"🖼 مدیریت بنر\n"
            f"──────────────\n"
            f"وضعیت: {'✅ فعال' if active else '❌ غیرفعال'}\n"
            f"عکس: {'✅ آپلود شده' if file_id else '❌ ندارد'}\n"
            f"کپشن: {caption if caption else '—'}\n"
            f"نمایش در: {show_labels}\n"
            f"──────────────"
        )
        await query.message.edit_text(info, reply_markup=banner_menu_keyboard())

    elif data == "banner_status_info":
        await query.answer("این دکمه فقط وضعیت فعلی بنر را نشان می‌دهد.", show_alert=True)

    elif data == "banner_toggle":
        banner["active"] = not banner.get("active", False)
        await save_banner()
        status = "✅ فعال شد" if banner["active"] else "❌ غیرفعال شد"
        await query.answer(f"بنر {status}", show_alert=True)
        # بروزرسانی منو
        await callbacks_banner_menu_refresh(query)

    elif data == "banner_delete":
        banner["file_id"] = None
        banner["caption"] = ""
        banner["active"] = False
        await save_banner()
        await query.answer("🗑 بنر حذف شد.", show_alert=True)
        await callbacks_banner_menu_refresh(query)

    elif data == "banner_upload":
        context.user_data["mode"] = "banner_upload"
        await query.message.reply_text(
            "🖼 لطفاً عکس بنر را ارسال کنید:\n\n"
            "• عکس باید مستقیم ارسال شود (نه فایل)\n"
            "• این عکس در بالای پیام‌های انتخابی نمایش داده می‌شود",
            reply_markup=admin_cancel_menu()
        )

    elif data == "banner_locations":
        await query.message.edit_text(
            "📍 انتخاب کنید بنر در کدام بخش‌ها نمایش داده شود:\n(روی هر گزینه کلیک کنید تا تغییر کند)",
            reply_markup=banner_locations_keyboard()
        )

    elif data.startswith("banner_loc_"):
        key = data.replace("banner_loc_", "")
        show_on = banner.get("show_on", [])
        if key in show_on:
            show_on.remove(key)
        else:
            show_on.append(key)
        banner["show_on"] = show_on
        await save_banner()
        await query.message.edit_reply_markup(reply_markup=banner_locations_keyboard())


async def callbacks_banner_menu_refresh(query):
    """بروزرسانی نمایش منوی بنر"""
    file_id = banner.get("file_id")
    caption = banner.get("caption", "")
    active = banner.get("active", False)
    show_on = banner.get("show_on", [])

    location_names = {
        "welcome": "خوش‌آمدگویی", "1": "شبکه‌ها", "2": "سایت",
        "3": "اقساط", "4": "پشتیبانی", "5": "آدرس"
    }
    show_labels = ", ".join([location_names.get(k, k) for k in show_on]) or "هیچ‌کدام"

    info = (
        f"🖼 مدیریت بنر\n"
        f"──────────────\n"
        f"وضعیت: {'✅ فعال' if active else '❌ غیرفعال'}\n"
        f"عکس: {'✅ آپلود شده' if file_id else '❌ ندارد'}\n"
        f"کپشن: {caption if caption else '—'}\n"
        f"نمایش در: {show_labels}\n"
        f"──────────────"
    )
    try:
        await query.message.edit_text(info, reply_markup=banner_menu_keyboard())
    except:
        pass

# ======================================
# TEXT HANDLER
# ======================================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global responses
    user = update.effective_user
    text = update.message.text.strip()

    await save_user(user)
    await log_event(user.id, "message")

    if not await anti_spam(user.id):
        return await update.message.reply_text("🐢 لطفاً آرام‌تر پیام دهید.")

    if text == "❌ لغو عملیات":
        context.user_data.clear()
        return await update.message.reply_text("❌ عملیات لغو شد.", reply_markup=main_menu())

    mode = context.user_data.get("mode")

    # تنظیم پیام خوش‌آمدگویی
    if user.id == ADMIN_ID and mode == "set_welcome":
        context.user_data.pop("mode", None)
        responses["welcome"] = text
        await save_data()
        await update.message.reply_text("✅ پیام خوش‌آمدگویی با موفقیت ذخیره شد.", reply_markup=main_menu())
        return

    # Broadcast
    if user.id == ADMIN_ID and mode == "broadcast":
        context.user_data.pop("mode", None)
        await update.message.reply_text("📤 در حال ارسال...")
        await send_broadcast(context, text)
        return

    # Edit Content
    if user.id == ADMIN_ID and mode == "edit":
        key = context.user_data.pop("edit_key")
        context.user_data.pop("mode", None)
        responses[key] = text
        await save_data()
        await update.message.reply_text("✅ محتوا ذخیره شد.", reply_markup=main_menu())
        return

    # User Menu
    for k, v in MENU_ITEMS.items():
        if text == v:
            return await send_with_banner(update.message, box(v, responses.get(k, "تنظیم نشده")), k)

    await update.message.reply_text("⚠️ گزینه نامعتبر است.", reply_markup=main_menu())

# ======================================
# PHOTO HANDLER (برای آپلود بنر)
# ======================================
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return

    mode = context.user_data.get("mode")
    if mode != "banner_upload":
        return

    context.user_data.pop("mode", None)

    # بزرگ‌ترین سایز عکس را ذخیره می‌کنیم
    photo = update.message.photo[-1]
    banner["file_id"] = photo.file_id
    if not banner.get("active"):
        banner["active"] = True  # به صورت خودکار فعال می‌شود

    await save_banner()
    await update.message.reply_text(
        "✅ بنر با موفقیت آپلود و فعال شد!\n\n"
        "برای تنظیم بیشتر به پنل مدیریت → مدیریت بنر مراجعه کنید.",
        reply_markup=main_menu()
    )

# ======================================
# MAIN
# ======================================
async def post_init(app):
    await init_db()
    await load_data()
    await load_banner()
    logger.info("✅ ربات با موفقیت راه‌اندازی شد")

def main():
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("🚀 ربات در حال اجراست...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
