# 🚀 Reporter Bot

ربات شخصی Telegram Reporter با ساختار آماده برای اجرای پایدار 24/7 روی سرور Linux Ubuntu 26.04.

> این پروژه برای استفاده شخصی طراحی شده و نیازی به تنظیمات عمومی یا سرویس‌دهی به کاربران دیگر ندارد.

---

# 🖥️ نصب کامل روی Ubuntu 26.04 (وب ترمینال سرور)

## 1. آپدیت سرور

در وب ترمینال سرور اجرا کنید:

```bash
apt update && apt upgrade -y
```

## 2. نصب ابزارهای لازم

```bash
apt install git python3 python3-pip python3-venv curl -y
```

## 3. دانلود پروژه

```bash
cd /opt
git clone https://github.com/kiarash707/reporter.git
cd reporter
```

اگر پوشه قبلاً وجود داشت:

```bash
cd /opt/reporter
git pull
```

## 4. ساخت محیط مجازی

```bash
python3 -m venv venv
source venv/bin/activate
```

## 5. نصب کتابخانه‌ها

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

# ⚙️ تنظیمات شخصی

اطلاعات حساس را داخل فایل‌های عمومی GitHub قرار ندهید.

قبل از اجرا تنظیمات مورد نیاز پروژه را وارد کنید.

---

# ▶️ تست اولیه اجرا

```bash
source venv/bin/activate
python3 main.py
```

اگر بدون خطا اجرا شد، با `CTRL+C` متوقف کنید و مرحله سرویس دائمی را انجام دهید.

---

# 🔥 اجرای دائمی 24/7 با Systemd

ساخت سرویس:

```bash
nano /etc/systemd/system/reporter.service
```

محتوا:

```ini
[Unit]
Description=Personal Reporter Bot
After=network.target

[Service]
WorkingDirectory=/opt/reporter
ExecStart=/opt/reporter/venv/bin/python3 /opt/reporter/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

فعال‌سازی:

```bash
systemctl daemon-reload
systemctl enable reporter
systemctl start reporter
```

---

# 📌 دستورات مدیریت ربات

وضعیت:

```bash
systemctl status reporter
```

شروع:

```bash
systemctl start reporter
```

توقف:

```bash
systemctl stop reporter
```

ری‌استارت:

```bash
systemctl restart reporter
```

لاگ زنده:

```bash
journalctl -u reporter -f
```

آخرین خطاها:

```bash
journalctl -u reporter -n 100 --no-pager
```

---

# 🔄 آپدیت نسخه جدید

```bash
cd /opt/reporter
systemctl stop reporter
git pull
source venv/bin/activate
pip install -r requirements.txt
systemctl start reporter
```

---

# 🛡️ نکات مهم سرور

- فایل‌های حساس را در GitHub قرار ندهید.
- از session و data بکاپ بگیرید.
- دسترسی فایل‌ها را محدود کنید.
- قبل از تغییرات بزرگ بکاپ بگیرید.

---

# 🧰 رفع مشکلات رایج

بررسی Python:

```bash
python3 --version
```

بررسی پکیج‌ها:

```bash
pip list
```

بررسی سرویس:

```bash
systemctl status reporter
```

---

# ✅ نصب سریع بعد از آماده بودن سرور

```bash
cd /opt
git clone https://github.com/kiarash707/reporter.git
cd reporter
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

پس از تست موفق، Systemd را فعال کنید.

---

ساخته شده برای اجرای پایدار شخصی روی Ubuntu 26.04.
