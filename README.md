# SHIKH REPORTER

ربات Telegram مبتنی بر Python و Telethon.

## فایل‌های پروژه

- `Reporter.py` — کد اصلی ربات
- `requirements.txt` — وابستگی‌های Python
- `Dockerfile` — build قابل تکرار برای Railway
- `railway.toml` — تنظیمات build و start در Railway
- `.env.example` — فهرست متغیرهای لازم
- `.gitignore` — جلوگیری از commit شدن فایل‌های محلی و اطلاعات runtime

## متغیرهای محیطی لازم

این پروژه اطلاعات حساس را از Environment Variables می‌خواند:

```text
API_ID=...
API_HASH=...
BOT_TOKEN=...
OWNER_IDS=...
DATA_DIR=/app/data
```

برای چند مالک/آیدی از کاما استفاده کنید:

```text
OWNER_IDS=123456789,987654321
```

## اجرای روی Railway

این پروژه برای یک **Persistent Service** طراحی شده و با `Dockerfile` اجرا می‌شود.

### 1. ساخت Service از GitHub

در Railway:

```text
New Project → Deploy from GitHub Repo → kiarash707/reporter
```

سپس Repository و Branch موردنظر را انتخاب کنید.

### 2. افزودن Variables

در Service → Variables این موارد را بسازید:

```text
API_ID
API_HASH
BOT_TOKEN
OWNER_IDS
DATA_DIR
```

مقدار `DATA_DIR`:

```text
/app/data
```

### 3. ساخت Volume

در همان Service یک Volume بسازید و Mount Path را دقیقاً این قرار دهید:

```text
/app/data
```

چون برنامه داده‌های runtime را داخل `DATA_DIR` ذخیره می‌کند، موارد زیر روی Volume باقی می‌مانند:

```text
/app/data/data.json
/app/data/bot.log
/app/data/admin_sessions/
/app/data/bot_session.session
```

### 4. Deploy

بعد از تکمیل Variables و Volume، Deployment را اجرا کنید.

Railway باید در build از `Dockerfile` استفاده کند و برنامه با این دستور اجرا شود:

```text
python Reporter.py
```

### 5. بررسی Logs

در Service → Deployments → Logs موارد زیر را بررسی کنید:

```text
Bot started
SHIKH REPORTER is running...
```

در صورت نبودن یکی از متغیرهای اصلی، برنامه عمداً با خطای زیر متوقف می‌شود:

```text
Missing required environment variables: API_ID, API_HASH, BOT_TOKEN
```

### 6. تست ربات

در Telegram به ربات پیام `/start` بدهید.

مالک باید منوی اصلی را ببیند. کاربران دیگر تا وقتی به‌عنوان Admin مجاز نشده باشند، دسترسی مدیریتی ندارند.

## نکات مهم Railway

- این برنامه وب‌سایت نیست؛ به Public Domain و Port نیاز ندارد.
- Service باید به‌صورت Persistent Service اجرا شود.
- Volume برای نگهداری Sessionها و `data.json` مهم است.
- تغییر Variables در Railway نیاز به Deploy دارد.
- فایل `.env.example` فقط نمونه است و هیچ Secret واقعی داخل آن قرار ندارد.

## اجرای محلی

نمونه متغیرها را از روی `.env.example` بسازید و سپس:

```bash
pip install -r requirements.txt
python Reporter.py
```

## امنیت

Secret واقعی را داخل GitHub commit نکنید. در Railway از Variables استفاده کنید.

در صورت تعویض Bot Token یا Telegram API credentials، فقط Variables را در Railway تغییر دهید؛ نیازی به تغییر کد نیست.


## مانیتورینگ و داشبورد

برای نمایش وضعیت و لاگ‌های زنده، یک سرویس مستقل `reporter-dashboard` وجود دارد. سرویس داشبورد از طریق Private Networking به API داخلی ربات متصل می‌شود؛ خاموش یا خراب شدن داشبورد نباید سرویس Telegram را متوقف کند.

متغیرهای مانیتورینگ ربات:

```text
MONITOR_TOKEN=...
MONITOR_PORT=8080
```

دامنه فعلی داشبورد:

```text
https://reporter-dashboard-production.up.railway.app
```

این داشبورد با Basic Auth محافظت شده است.
