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

async def load_data():
    global responses
    try:
        async with aiofiles.open(DATA_FILE, "r", encoding="utf-8") as f:
            responses = json.loads(await f.read())
    except:
        responses = MENU_ITEMS.copy()
        responses["welcome"] = "✨ خوش آمدید به ربات استوک لند"  # پیام پیش‌فرض

async def save_data():
    try:
        async with aiofiles.open(DATA_FILE, "w", encoding="utf-8") as f:
            await f.write(json.dumps(responses, ensure_ascii=False, indent=4))
    except Exception as e:
        logger.error(f"Save error: {e}")

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
    await update.message.reply_text(welcome_text, reply_markup=main_menu())

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ دسترسی ندارید")
    await update.message.reply_text("👑 پنل مدیریت", reply_markup=admin_menu())

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID: return

    if query.data == "back_to_admin":
        await query.message.edit_text("👑 پنل مدیریت", reply_markup=admin_menu())
        return

    if query.data == "dash":
        t = await total_users()
        d = await today_users()
        await query.message.edit_text(box("داشبورد", f"👥 کل کاربران: {t}\n📅 امروز: {d}"), reply_markup=admin_menu())

    elif query.data == "users":
        async with db.execute("SELECT user_id, first_name, last_seen FROM users ORDER BY last_seen DESC LIMIT 15") as c:
            rows = await c.fetchall()
        text = "👤 کاربران اخیر:\n\n" + "\n".join([f"• {r[1]} | {r[0]}" for r in rows])
        await query.message.edit_text(text, reply_markup=back_button())

    elif query.data == "logs":
        async with db.execute("SELECT user_id, action, created_at FROM logs ORDER BY id DESC LIMIT 15") as c:
            rows = await c.fetchall()
        text = "📈 لاگ‌ها:\n\n" + "\n".join([f"• {r[1]} | {r[0]}" for r in rows])
        await query.message.edit_text(text, reply_markup=back_button())

    elif query.data == "edit":
        await query.message.edit_text("✏️ مدیریت محتوا", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 شبکه‌ها", callback_data="e_1")],
            [InlineKeyboardButton("🌐 سایت", callback_data="e_2")],
            [InlineKeyboardButton("💰 اقساط", callback_data="e_3")],
            [InlineKeyboardButton("📞 پشتیبانی", callback_data="e_4")],
            [InlineKeyboardButton("📍 آدرس", callback_data="e_5")],
            [InlineKeyboardButton("✉️ تنظیم پیام خوش‌آمدگویی", callback_data="set_welcome")],
            [InlineKeyboardButton("🔙 برگشت", callback_data="back_to_admin")]
        ]))

    elif query.data.startswith("e_"):
        key = query.data.split("_")[1]
        context.user_data["edit_key"] = key
        context.user_data["mode"] = "edit"
        current = responses.get(key, "تنظیم نشده")
        await query.message.reply_text(f"📝 متن فعلی:\n\n{current}\n\nمتن جدید را ارسال کنید:", reply_markup=admin_cancel_menu())

    elif query.data == "set_welcome":
        context.user_data["mode"] = "set_welcome"
        current = responses.get("welcome", "پیام پیش‌فرض")
        await query.message.reply_text(
            f"📝 پیام خوش‌آمدگویی فعلی:\n\n{current}\n\n"
            f"متن جدید را ارسال کنید:", 
            reply_markup=admin_cancel_menu()
        )

    elif query.data == "broadcast":
        context.user_data["mode"] = "broadcast"
        await query.message.reply_text("📢 متن پیام پخش همگانی را ارسال کنید:", reply_markup=admin_cancel_menu())

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
            return await update.message.reply_text(box(v, responses.get(k, "تنظیم نشده")))

    await update.message.reply_text("⚠️ گزینه نامعتبر است.", reply_markup=main_menu())

# ======================================
# MAIN
# ======================================
async def post_init(app):
    await init_db()
    await load_data()
    logger.info("✅ ربات با موفقیت راه‌اندازی شد")

def main():
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("🚀 ربات در حال اجراست...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
