# Telegram Reporter Bot

ربات مدیریت و اجرای عملیات گزارش در تلگرام با رابط مدیریتی فارسی/انگلیسی.

این پروژه یک ربات Python/Telethon است که بخش‌های مدیریتی، مدیریت حساب‌ها و Sessionها، SMTP، عملیات گزارش و گزارش وضعیت عملیات را در یک پنل تلگرامی جمع می‌کند.

> **نکته:** فایل سورس اصلی این نسخه باید دقیقاً همان فایل دریافت‌شده از پروژه باشد و نباید برای اجرای پروژه به‌صورت دستی بازنویسی شود.

## قابلیت‌ها

### SMTP / Email
- افزودن چند SMTP جیمیل با App Password
- تست اتصال SMTP
- فعال/غیرفعال کردن فرستنده‌ها
- ارسال تکی و گروهی

### Telegram Reporter
- ریپورت کانال/گروه
- ریپورت پست
- ریپورت پروفایل
- ریپورت ربات
- ریپورت اکانت
- ریپورت دستی
- انتخاب نوع دلیل گزارش
- تنظیم تأخیر بین عملیات
- امکان مدیریت Join اجباری قبل از عملیات

### مدیریت Session
- ذخیره Session برای هر ادمین در پوشه اختصاصی
- نمایش حساب‌ها و شماره‌ها
- اشتراک Session بین مالک و ادمین‌ها
- مدیریت Sessionهای مشترک
- پشتیبانی از چند حساب

### مدیریت کاربران و ادمین‌ها
- افزودن ادمین
- تمدید اشتراک ادمین
- حذف ادمین
- افزودن مالک جدید
- مشاهده وضعیت انقضای ادمین‌ها
- مدیریت کانال اجباری
- تیکت پشتیبانی و مدیریت کاربران

### گزارش عملیات
- نمایش وضعیت عملیات
- درصد پیشرفت
- زمان سپری‌شده و زمان تخمینی
- نمایش موفق/ناموفق
- مشاهده حساب‌های موفق و ناموفق
- گزارش پایان عملیات برای مالک
- آمار کلی ربات
- ریست آمار/گزارش‌ها

## تکنولوژی

- Python 3.10+
- Telethon
- asyncio
- SMTP
- pytz
- JSON-based local data

## ساختار پیشنهادی

```text
reporter/
├── main.py                 # سورس اصلی ربات
├── requirements.txt        # وابستگی‌های Python
├── README.md
├── CHANGELOG.md
├── .gitignore
└── docs/
    ├── INSTALL_UBUNTU.md
    ├── CONFIGURATION.md
    └── TROUBLESHOOTING.md
```

نام فایل سورس را می‌توانید مطابق نام فایل اصلی پروژه نگه دارید؛ در آموزش‌های این مخزن از `main.py` به‌عنوان نام نمونه استفاده شده است.

## پیش‌نیاز

برای اجرای روی Ubuntu Server:

- Ubuntu 22.04 / 24.04 / 26.04
- Python 3
- pip
- دسترسی به Web Terminal یا SSH
- اینترنت فعال روی سرور
- اطلاعات Telegram API
- Bot Token
- مقادیر مالکین و تنظیمات موردنیاز خود سورس

## نصب سریع روی Ubuntu

### 1. آپدیت سیستم

```bash
apt update && apt upgrade -y
```

### 2. نصب Python و ابزارهای لازم

```bash
apt install -y python3 python3-pip python3-venv git
```

بررسی:

```bash
python3 --version
pip3 --version
git --version
```

### 3. دریافت پروژه

```bash
git clone https://github.com/kiarash707/reporter.git
cd reporter
```

اگر Repository خصوصی است، روش احراز هویت Git خودتان را استفاده کنید.

### 4. ساخت محیط مجازی

```bash
python3 -m venv venv
source venv/bin/activate
```

### 5. نصب وابستگی‌ها

```pip
pip install --upgrade pip
pip install -r requirements.txt
```

### 6. اجرای ربات

اگر فایل اصلی `main.py` است:

```bash
python3 main.py
```

اگر نام فایل اصلی متفاوت است، همان نام واقعی فایل را در دستور بالا قرار دهید.

## اجرای دائمی

برای اینکه بعد از بستن Web Terminal ربات متوقف نشود، از systemd استفاده کنید.

فایل سرویس:

```bash
nano /etc/systemd/system/reporter.service
```

نمونه:

```ini
[Unit]
Description=Telegram Reporter Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/reporter
ExecStart=/opt/reporter/venv/bin/python /opt/reporter/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

سپس:

```bash
systemctl daemon-reload
systemctl enable reporter
systemctl start reporter
```

بررسی وضعیت:

```bash
systemctl status reporter
```

مشاهده لاگ:

```bash
journalctl -u reporter -f
```

توقف:

```bash
systemctl stop reporter
```

شروع مجدد:

```bash
systemctl restart reporter
```

## اطلاعات Telegram

مقادیر مربوط به Telegram در سورس فعلی پروژه تعریف شده‌اند. قبل از اجرای نسخه شخصی خودتان، مقادیر موردنیاز فایل اصلی را بررسی و مقداردهی کنید.

برای Telegram API معمولاً به:

- API ID
- API Hash
- Bot Token
- Owner ID

نیاز است.

Bot Token از BotFather و API ID/API Hash از Telegram API Development Tools دریافت می‌شود.

## SMTP

بخش SMTP پروژه از Gmail SMTP استفاده می‌کند.

تنظیمات موردنیاز در خود پنل ربات قرار دارد. برای Gmail از App Password استفاده کنید و رمز اصلی حساب Gmail را جایگزین App Password نکنید.

## Sessionها

Sessionهای Telethon توسط برنامه مدیریت می‌شوند و برای حساب‌های مختلف در مسیرهای مخصوص ذخیره می‌شوند.

پس از اولین ورود هر حساب، فایل Session مربوط به آن حساب توسط برنامه ایجاد/مدیریت خواهد شد.

## عیب‌یابی سریع

### ModuleNotFoundError

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### بررسی نصب Telethon

```bash
python3 -c "import telethon; print(telethon.__version__)"
```

### ربات اجرا می‌شود ولی پاسخ نمی‌دهد

لاگ را ببینید:

```bash
journalctl -u reporter -n 100 --no-pager
```

### بررسی اجرای مستقیم

قبل از systemd، برنامه را مستقیم اجرا کنید:

```bash
cd /opt/reporter
source venv/bin/activate
python3 main.py
```

هر خطای Python یا Telethon در همین مرحله واضح‌تر نمایش داده می‌شود.

## آپدیت پروژه

```bash
cd /opt/reporter
git pull
source venv/bin/activate
pip install -r requirements.txt
systemctl restart reporter
```

## وضعیت پروژه

نسخه حاضر برای اجرای ربات روی Linux Server مستند شده است. منطق اصلی برنامه باید در فایل سورس پروژه نگهداری شود و تغییرات کد مستقل از مستندات انجام شوند.

## License

برای این پروژه هنوز License مشخصی اعلام نشده است.
