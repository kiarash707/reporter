# 🚀 Reporter Bot

ربات Telegram Reporter با ساختار آماده برای اجرای پایدار روی سرور لینوکسی.

## ✨ امکانات پروژه

- اجرای دائمی روی Ubuntu Server
- مدیریت تنظیمات و فایل‌های پروژه
- نصب استاندارد Python Virtual Environment
- مدیریت سرویس با Systemd
- لاگ‌گیری و عیب‌یابی آسان
- آماده‌سازی برای محیط Production

---

# 🖥️ نصب روی Ubuntu 26.04 (راهنمای کامل 0 تا 100)

## 1. اتصال به سرور

با SSH وارد سرور شوید:

```bash
ssh username@SERVER_IP
```

## 2. آپدیت سیستم

```bash
apt update && apt upgrade -y
```

## 3. نصب ابزارهای مورد نیاز

```bash
apt install git python3 python3-pip python3-venv curl -y
```

## 4. دریافت پروژه

```bash
git clone https://github.com/kiarash707/reporter.git
cd reporter
```

## 5. ساخت محیط مجازی Python

```bash
python3 -m venv venv
source venv/bin/activate
```

## 6. نصب کتابخانه‌ها

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 7. تنظیمات پروژه

اطلاعات حساس مانند Token ها، API Key ها و تنظیمات شخصی را در فایل‌های تنظیمات امن قرار دهید.

هرگز اطلاعات محرمانه را در GitHub عمومی قرار ندهید.

---

# ▶️ اجرای تستی

```bash
python3 main.py
```

اگر بدون خطا اجرا شد، آماده اجرای دائمی است.

---

# ⚙️ اجرای دائمی با Systemd

یک سرویس بسازید:

```bash
nano /etc/systemd/system/reporter.service
```

نمونه:

```ini
[Unit]
Description=Reporter Bot
After=network.target

[Service]
WorkingDirectory=/opt/reporter
ExecStart=/opt/reporter/venv/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

فعال‌سازی:

```bash
systemctl daemon-reload
systemctl enable reporter
systemctl start reporter
```

بررسی وضعیت:

```bash
systemctl status reporter
```

مشاهده لاگ زنده:

```bash
journalctl -u reporter -f
```

---

# 🔄 دستورات مدیریت

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

---

# 🛡️ امنیت سرور

- اطلاعات حساس را داخل GitHub قرار ندهید.
- از Session و فایل‌های دیتا بکاپ بگیرید.
- دسترسی فایل‌ها را محدود کنید.
- سیستم‌عامل را همیشه به‌روز نگه دارید.

---

# 📂 ساختار پیشنهادی Production

```
reporter/
├── main.py
├── requirements.txt
├── venv/
├── data/
├── logs/
├── config/
└── README.md
```

---

# 🧰 عیب‌یابی

مشاهده لاگ:

```bash
journalctl -u reporter --no-pager -n 100
```

بررسی Python:

```bash
python3 --version
```

بررسی نصب پکیج‌ها:

```bash
pip list
```

---

ساخته شده برای استقرار پایدار روی Linux Ubuntu 26.04.
