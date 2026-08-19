#!/usr/bin/env bash
# تشخیص سریع مشکل ربات — روی وی‌پی‌اس اجرا کنید:
#   bash deploy/doctor.sh
cd "$(dirname "$0")/.." || exit 1
echo "════════ ۱) وضعیت سرویس ════════"
systemctl is-active telegram-bot 2>/dev/null || echo "(سرویس فعال نیست)"
systemctl show telegram-bot -p ExecStart --value 2>/dev/null | sed 's/^/ExecStart: /'
systemctl show telegram-bot -p EnvironmentFiles --value 2>/dev/null | sed 's/^/EnvFile:   /'
systemctl show telegram-bot -p WorkingDirectory --value 2>/dev/null | sed 's/^/WorkDir:   /'

echo
echo "════════ ۲) فایل‌های لازم ════════"
for f in bot.py app.py requirements.txt .env; do
  [ -e "$f" ] && echo "✅ $f" || echo "❌ $f پیدا نشد"
done

echo
echo "════════ ۳) متغیرهای محیطی ════════"
if [ -f .env ]; then
  grep -q '^BOT_TOKEN=.\+' .env && echo "✅ BOT_TOKEN ست شده" || echo "❌ BOT_TOKEN خالی است"
  grep -q '^ADMIN_ID=.\+'  .env && echo "✅ ADMIN_ID ست شده"  || echo "❌ ADMIN_ID خالی است"
  grep -q '^export ' .env && echo "⚠️  خط export در .env هست — systemd آن را قبول نمی‌کند، export را بردارید"
fi

echo
echo "════════ ۴) چند نسخه در حال اجراست؟ ════════"
n=$(pgrep -af "python.*(bot|app)\.py" | wc -l)
pgrep -af "python.*(bot|app)\.py" || echo "(هیچ پروسه‌ای در حال اجرا نیست)"
[ "$n" -gt 1 ] && echo "⛔ بیش از یک نسخه اجراست — باعث Conflict و بی‌پاسخی ربات می‌شود!"

echo
echo "════════ ۵) پکیج‌ها ════════"
PY=venv/bin/python; [ -x "$PY" ] || PY=python3
$PY -c "import telegram,aiosqlite,aiofiles,jdatetime,pytz;print('✅ همه پکیج‌ها نصب‌اند — PTB',telegram.__version__)" \
  2>&1 | tail -2

echo
echo "════════ ۶) آخرین خطاهای لاگ ════════"
journalctl -u telegram-bot -n 25 --no-pager 2>/dev/null | tail -25 || echo "(لاگ در دسترس نیست)"
