# راهنمای نصب (فارسی)

راهنمای کامل انگلیسی: [installation.md](installation.md)

## پیش‌نیازها

* پایتون **۳.۱۰ یا بالاتر**
* `git`
* سه مقدار از تلگرام:
  * `API_ID` و `API_HASH` از <https://my.telegram.org>
  * `BOT_TOKEN` از [@BotFather](https://t.me/BotFather)
  * آیدی عددی خودتان از [@userinfobot](https://t.me/userinfobot)

> این مقادیر مثل رمز عبور هستند: فقط داخل فایل `.env` نگهشان دارید؛ هیچ‌وقت در کد یا مخزن گیت قرار ندهید.

## نصب سریع (یک دستور)

```bash
git clone <repository-url> reporter
cd reporter
bash scripts/install.sh
```

نصب‌کننده این کارها را انجام می‌دهد:

1. بررسی نسخه پایتون
2. نصب بسته‌های سیستمی موردنیاز (با `--skip-system-deps` رد می‌شود)
3. ساخت محیط مجازی `.venv` و نصب وابستگی‌ها
4. ساخت فایل `.env` از روی `.env.example` با دسترسی `600`
5. اجرای بررسی تنظیمات (`python -m bot check`)

## تنظیم و اجرا

```bash
nano .env            # پر کردن API_ID و API_HASH و BOT_TOKEN و OWNER_IDS
.venv/bin/python -m bot check    # بررسی صحت تنظیمات
.venv/bin/python -m bot run      # اجرای بات
```

## اجرای دائمی با systemd

```bash
sudo bash scripts/install.sh --service
sudo systemctl status reporter
journalctl -u reporter -f        # مشاهده زنده لاگ‌ها
```

## اجرا با داکر

```bash
docker build -f deploy/docker/Dockerfile -t telegram-community-bot .
docker run -d --name telegram-bot --restart unless-stopped \
  --env-file .env \
  -v "$PWD/data:/app/data" -v "$PWD/sessions:/app/sessions" -v "$PWD/logs:/app/logs" \
  telegram-community-bot
docker logs -f telegram-bot
```

یا با Compose:

```bash
docker compose -f deploy/docker/docker-compose.yml up -d
```

## به‌روزرسانی و پشتیبان‌گیری

```bash
bash scripts/backup.sh      # پشتیبان از داده‌ها
bash scripts/update.sh      # پشتیبان + دریافت نسخه جدید + مهاجرت + ری‌استارت
bash scripts/doctor.sh      # گزارش کامل وضعیت برای عیب‌یابی
```

## حذف نصب

```bash
sudo bash scripts/uninstall.sh           # حذف سرویس، نگه‌داشتن داده‌ها
sudo bash scripts/uninstall.sh --purge   # حذف کامل داده‌ها و محیط مجازی
```

اگر بات بالا نیامد، ابتدا `bash scripts/doctor.sh` را اجرا کنید و خروجی را بررسی کنید؛
مشکلات رایج در [troubleshooting.md](troubleshooting.md) فهرست شده‌اند.
