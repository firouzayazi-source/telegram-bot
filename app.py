"""
راه‌انداز یکپارچه: بات تلگرام + پنل وب
بات در یک ترد جدا، Flask در ترد اصلی اجرا می‌شود.
هر دو به یک دیتابیس و فایل‌های JSON دسترسی دارند.
"""
import os, sys, asyncio, threading, logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "webpanel"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("app")

# ── آپلودر عکس به تلگرام ─────────────────────────
import requests

def make_tg_uploader(token, admin_id):
    """یک تابع برمی‌گرداند که فایل را به تلگرام آپلود و file_id برمی‌گرداند."""
    def upload(filepath):
        try:
            with open(filepath, "rb") as f:
                r = requests.post(
                    f"https://api.telegram.org/bot{token}/sendPhoto",
                    data={"chat_id": admin_id, "disable_notification": "true"},
                    files={"photo": f}, timeout=30)
            j = r.json()
            if j.get("ok"):
                photos = j["result"].get("photo", [])
                if photos:
                    return photos[-1]["file_id"]
        except Exception as e:
            logger.error(f"tg upload error: {e}")
        return None
    return upload

# ── اجرای بات در ترد جدا ─────────────────────────
def run_bot():
    """بات را در event loop مخصوص این ترد اجرا می‌کند."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    import bot
    app = bot.ApplicationBuilder().token(bot.TOKEN).post_init(bot.post_init).build()
    app.add_handler(bot.CommandHandler("start", bot.cmd_start))
    app.add_handler(bot.CommandHandler("admin", bot.cmd_admin))
    app.add_handler(bot.CallbackQueryHandler(bot.callbacks))
    app.add_handler(bot.MessageHandler(bot.filters.PHOTO & ~bot.filters.COMMAND, bot.photo_handler))
    app.add_handler(bot.MessageHandler(bot.filters.Document.ZIP & ~bot.filters.COMMAND, bot.document_handler))
    app.add_handler(bot.MessageHandler(bot.filters.TEXT & ~bot.filters.COMMAND, bot.text_handler))
    logger.info("🤖 بات شروع شد")
    app.run_polling(drop_pending_updates=True, close_loop=False, stop_signals=())  # ← تغییر اینجاست

# ── Main ─────────────────────────────────────────
def main():
    token = os.environ["BOT_TOKEN"].strip()
    admin_id = int(os.environ["ADMIN_ID"].strip())

    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    import web
    web.set_tg_uploader(make_tg_uploader(token, admin_id))

    logger.info("🌐 پنل وب در حال اجرا...")
    web.run_web()

if __name__ == "__main__":
    main()
