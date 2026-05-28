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

os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("ALL_PROXY", None)
os.environ["NO_PROXY"] = "*"

TOKEN = os.getenv("BOT_TOKEN", "8792062012:AAGXforSa1IY45AuC-yOHs2PsdzudvtdD44")
ADMIN_ID = int(os.getenv("ADMIN_ID", "638469407"))

DATA_FILE = "data.json"
DB_FILE = "users.db"
BANNER_FILE = "banner.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

IRAN_TZ = pytz.timezone("Asia/Tehran")

def shamsi_now():
    now = datetime.now(IRAN_TZ)
    j_now = jdatetime.datetime.fromgregorian(datetime=now)
    return j_now.strftime("%Y/%m/%d - %H:%M")

def gregorian_now():
    return datetime.now(IRAN_TZ).strftime("%Y-%m-%d %H:%M:%S")

MENU_ITEMS = {
    "1": "🌐 شبکه‌های اجتماعی",
    "2": "🌐 سایت استوک لند",
    "3": "💰 شرایط اقساط",
    "4": "📞 پشتیبانی",
    "5": "📍 آدرس فروشگاه"
}

SECTION_NAMES = {
    "welcome": "🏠 خوش‌آمدگویی",
    "1": "🌐 شبکه‌های اجتماعی",
    "2": "🌐 سایت استوک لند",
    "3": "💰 شرایط اقساط",
    "4": "📞 پشتیبانی",
    "5": "📍 آدرس فروشگاه"
}

responses = None

banners = {
    "welcome": {"file_id": None, "active": False},
    "1":       {"file_id": None, "active": False},
    "2":       {"file_id": None, "active": False},
    "3":       {"file_id": None, "active": False},
    "4":       {"file_id": None, "active": False},
    "5":       {"file_id": None, "active": False},
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

async def load_banners():
    global banners
    try:
        async with aiofiles.open(BANNER_FILE, "r", encoding="utf-8") as f:
            data = json.loads(await f.read())
            if "welcome" in data:
                banners = data
    except:
        pass

async def save_banners():
    try:
        async with aiofiles.open(BANNER_FILE, "w", encoding="utf-8") as f:
            await f.write(json.dumps(banners, ensure_ascii=False, indent=4))
    except Exception as e:
        logger.error(f"Banner save error: {e}")

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

async def total_users():
    async with db.execute("SELECT COUNT(*) FROM users") as c:
        return (await c.fetchone())[0]

async def today_users():
    async with db.execute(
    "SELECT COUNT(*) FROM users WHERE DATE(last_seen)=DATE('now', 'localtime')"
) as c:    
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
        [InlineKeyboardButton("🖼 مدیریت بنرها", callback_data="banner_list")],
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

def banner_list_keyboard():
    buttons = []
    for key, name in SECTION_NAMES.items():
        b = banners.get(key, {})
        has_banner = "🖼" if b.get("file_id") else "➕"
        is_active = "✅" if b.get("active") else "❌"
        buttons.append([InlineKeyboardButton(
            f"{has_banner} {is_active} {name}",
            callback_data=f"bmng_{key}"
        )])
    buttons.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_to_admin")])
    return InlineKeyboardMarkup(buttons)

def banner_section_keyboard(key: str):
    b = banners.get(key, {})
    has_banner = b.get("file_id")
    is_active = b.get("active", False)
    toggle_label = "🔴 غیرفعال کردن" if is_active else "🟢 فعال کردن"
    buttons = [
        [InlineKeyboardButton("🖼 آپلود / تغییر عکس", callback_data=f"bup_{key}")],
        [InlineKeyboardButton(toggle_label, callback_data=f"btg_{key}")],
    ]
    if has_banner:
        buttons.append([InlineKeyboardButton("🗑 حذف بنر", callback_data=f"bdl_{key}")])
    buttons.append([InlineKeyboardButton("🔙 برگشت به لیست", callback_data="banner_list")])
    return InlineKeyboardMarkup(buttons)

async def send_with_banner(msg, text: str, section_key: str, reply_markup=None):
    b = banners.get(section_key, {})
    should_show = b.get("active") and b.get("file_id")
    if should_show:
        try:
            await msg.reply_photo(photo=b["file_id"], caption=text, reply_markup=reply_markup)
            return
        except Exception as e:
            logger.error(f"Banner send error [{section_key}]: {e}")
    if reply_markup:
        await msg.reply_text(text, reply_markup=reply_markup)
    else:
        await msg.reply_text(text)

async def send_broadcast(context: ContextTypes.DEFAULT_TYPE, text: str):
    users = await get_all_users()
    total = len(users)

    success = 0
    failed = 0

    status = await context.bot.send_message(
        ADMIN_ID,
        f"📢 شروع پخش به {total} کاربر..."
    )

    for i, uid in enumerate(users, 1):
        try:
            await context.bot.send_message(uid, text)
            success += 1

        except TelegramError:
            failed += 1

        if i % 10 == 0 or i == total:
            await status.edit_text(
                f"""📢 در حال پخش...

✅ موفق: {success}
❌ شکست: {failed}

{i}/{total}"""
            )

        await asyncio.sleep(0.2)

    await status.edit_text(
        f"""✅ پخش تمام شد!

موفق: {success}
شکست: {failed}"""
    )

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

    if data == "back_to_admin":
        await query.message.edit_text("👑 پنل مدیریت", reply_markup=admin_menu())
        return

    if data == "dash":
        t = await total_users()
        d = await today_users()
        await query.message.edit_text(
    box(
        "داشبورد",
        f"""👥 کل کاربران: {t}
📅 امروز: {d}"""
    ),
    reply_markup=admin_menu()
)
    
    elif data == "users":
        async with db.execute("SELECT user_id, first_name, last_seen FROM users ORDER BY last_seen DESC LIMIT 15") as c:
            rows = await c.fetchall()
        text = "👤 کاربران اخیر:

" + "
".join([f"• {r[1]} | {r[0]}" for r in rows])
        await query.message.edit_text(text, reply_markup=back_button())

    elif data == "logs":
        async with db.execute("SELECT user_id, action, created_at FROM logs ORDER BY id DESC LIMIT 15") as c:
            rows = await c.fetchall()
        text = "📈 لاگ‌ها:

" + "
".join([f"• {r[1]} | {r[0]}" for r in rows])
        await query.message.edit_text(text, reply_markup=back_button())

    elif data == "edit":
        await query.message.edit_text("✏️ مدیریت محتوا", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 شبکه‌ها", callback_data="e_1")],
            [InlineKeyboardButton("🌐 سایت", callback_data="e_2")],
            [InlineKeyboardButton("💰 اقساط", callback_data="e_3")],
            [InlineKeyboardButton("📞 پشتیبانی", callback_data="e_4")],
            [InlineKeyboardButton("📍 آدرس", callback_data="e_5")],
            [InlineKeyboardButton("✉️ پیام خوش‌آمدگویی", callback_data="set_welcome")],
            [InlineKeyboardButton("🔙 برگشت", callback_data="back_to_admin")]
        ]))

    elif data.startswith("e_"):
        key = data.split("_")[1]
        context.user_data["edit_key"] = key
        context.user_data["mode"] = "edit"
        current = responses.get(key, "تنظیم نشده")
        await query.message.reply_text(f"📝 متن فعلی:

{current}

متن جدید را ارسال کنید:", reply_markup=admin_cancel_menu())

    elif data == "set_welcome":
        context.user_data["mode"] = "set_welcome"
        current = responses.get("welcome", "پیام پیش‌فرض")
        await query.message.reply_text(f"📝 پیام خوش‌آمدگویی فعلی:

{current}

متن جدید را ارسال کنید:", reply_markup=admin_cancel_menu())

    elif data == "broadcast":
        context.user_data["mode"] = "broadcast"
        await query.message.reply_text("📢 متن پیام پخش همگانی را ارسال کنید:", reply_markup=admin_cancel_menu())

    elif data == "banner_list":
        await query.message.edit_text(
            "🖼 مدیریت بنرها
──────────────
روی هر بخش بزنید تا بنر آن را تنظیم کنید:

🖼 = دارد بنر  |  ➕ = ندارد
✅ = فعال  |  ❌ = غیرفعال",
            reply_markup=banner_list_keyboard()
        )

    elif data.startswith("bmng_"):
        key = data.replace("bmng_", "")
        b = banners.get(key, {})
        name = SECTION_NAMES.get(key, key)
        status = "✅ فعال" if b.get("active") else "❌ غیرفعال"
        has = "✅ آپلود شده" if b.get("file_id") else "❌ ندارد"
        await query.message.edit_text(
            f"🖼 بنر بخش: {name}
──────────────
عکس: {has}
وضعیت: {status}
──────────────",
            reply_markup=banner_section_keyboard(key)
        )

    elif data.startswith("bup_"):
        key = data.replace("bup_", "")
        context.user_data["mode"] = "banner_upload"
        context.user_data["banner_key"] = key
        name = SECTION_NAMES.get(key, key)
        await query.message.reply_text(
            f"🖼 عکس بنر بخش «{name}» را ارسال کنید:

• عکس را مستقیم بفرستید (نه فایل)",
            reply_markup=admin_cancel_menu()
        )

    elif data.startswith("btg_"):
        key = data.replace("btg_", "")
        if not banners[key].get("file_id"):
            await query.answer("ابتدا عکس آپلود کنید!", show_alert=True)
            return
        banners[key]["active"] = not banners[key].get("active", False)
        await save_banners()
        st_txt = "✅ فعال شد" if banners[key]["active"] else "❌ غیرفعال شد"
        await query.answer(st_txt, show_alert=True)
        b = banners[key]
        name = SECTION_NAMES.get(key, key)
        has = "✅ آپلود شده" if b.get("file_id") else "❌ ندارد"
        st = "✅ فعال" if b.get("active") else "❌ غیرفعال"
        await query.message.edit_text(
            f"🖼 بنر بخش: {name}
──────────────
عکس: {has}
وضعیت: {st}
──────────────",
            reply_markup=banner_section_keyboard(key)
        )

    elif data.startswith("bdl_"):
        key = data.replace("bdl_", "")
        banners[key] = {"file_id": None, "active": False}
        await save_banners()
        await query.answer("🗑 بنر حذف شد.", show_alert=True)
        name = SECTION_NAMES.get(key, key)
        await query.message.edit_text(
            f"🖼 بنر بخش: {name}
──────────────
عکس: ❌ ندارد
وضعیت: ❌ غیرفعال
──────────────",
            reply_markup=banner_section_keyboard(key)
        )

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
    if user.id == ADMIN_ID and mode == "set_welcome":
        context.user_data.pop("mode", None)
        responses["welcome"] = text
        await save_data()
        await update.message.reply_text("✅ پیام خوش‌آمدگویی ذخیره شد.", reply_markup=main_menu())
        return
    if user.id == ADMIN_ID and mode == "broadcast":
        context.user_data.pop("mode", None)
        await update.message.reply_text("📤 در حال ارسال...")
        await send_broadcast(context, text)
        return
    if user.id == ADMIN_ID and mode == "edit":
        key = context.user_data.pop("edit_key")
        context.user_data.pop("mode", None)
        responses[key] = text
        await save_data()
        await update.message.reply_text("✅ محتوا ذخیره شد.", reply_markup=main_menu())
        return
    for k, v in MENU_ITEMS.items():
        if text == v:
            return await send_with_banner(update.message, box(v, responses.get(k, "تنظیم نشده")), k)
    await update.message.reply_text("⚠️ گزینه نامعتبر است.", reply_markup=main_menu())

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID: return
    mode = context.user_data.get("mode")
    if mode != "banner_upload": return
    key = context.user_data.pop("banner_key", None)
    context.user_data.pop("mode", None)
    if not key or key not in banners:
        await update.message.reply_text("❌ خطا — دوباره از پنل ادمین امتحان کنید.", reply_markup=main_menu())
        return
    photo = update.message.photo[-1]
    banners[key]["file_id"] = photo.file_id
    banners[key]["active"] = True
    await save_banners()
    name = SECTION_NAMES.get(key, key)
    await update.message.reply_text(f"✅ بنر بخش «{name}» آپلود و فعال شد!", reply_markup=main_menu())

async def post_init(app):
    await init_db()
    await load_data()
    await load_banners()
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
