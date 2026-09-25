# 🚀 Reporter Bot

ربات شخصی Telegram Reporter با ساختار آماده برای اجرای پایدار 24/7 روی سرور Linux Ubuntu 26.04.

> این پروژه برای استفاده شخصی طراحی شده و برای سرویس‌دهی عمومی نیست.

---

# 🖥️ نصب مستقیم روی سرور Ubuntu

> این روش برای Web Terminal و سرورهایی است که دسترسی root دارند. در این پروژه نیازی به `sudo su` نیست.

## 1) دریافت پروژه

اگر پروژه از قبل روی سرور است:

```bash
cd /opt/reporter
git pull
```

اگر هنوز روی سرور نیست و ریپو Private است، ابتدا دسترسی GitHub را روی سرور تنظیم کنید و سپس پروژه را دریافت کنید. برای مثال با SSH:

```bash
cd /opt
git clone git@github.com:kiarash707/reporter.git
cd reporter
```

## 2) نصب مستقیم

داخل پوشه پروژه فقط این را اجرا کنید:

```bash
bash scripts/install.sh
```

اسکریپت به‌صورت خودکار:
- Python و `venv` و وابستگی‌ها را نصب می‌کند.
- محیط مجازی `venv` را می‌سازد.
- `requirements.txt` را نصب می‌کند.
- سرویس Systemd را در مسیر درست قرار می‌دهد.
- سرویس را برای اجرای خودکار بعد از reboot فعال می‌کند.

## 3) اجرای ربات

برای شروع:

```bash
systemctl start reporter
```

بررسی:

```bash
systemctl status reporter --no-pager
```

لاگ:

```bash
journalctl -u reporter -n 100 --no-pager
```

اگر ربات خطا داشت، اجرای مستقیم برای دیدن خطای واقعی:

```bash
cd /opt/reporter
./venv/bin/python3 main.py
```

---

# 📥 دریافت پروژه

```bash
cd /opt
git clone https://github.com/kiarash707/reporter.git
cd reporter
```

اگر پروژه قبلاً نصب شده:

```bash
cd /opt/reporter
git pull
```

---

# 🐍 ساخت محیط Python

```bash
python3 -m venv venv
source venv/bin/activate
```

اگر خطای venv گرفتید:

```bash
apt install python3-venv -y
python3 -m venv venv
```

---

# 📦 نصب وابستگی‌ها

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

اگر خطای نصب پکیج داشتید:

```bash
pip install --upgrade setuptools wheel
pip install -r requirements.txt
```

---

# ⚙️ تنظیمات پروژه

اطلاعات حساس مثل Token، API Key و Session را داخل GitHub عمومی قرار ندهید.

قبل از اجرا تنظیمات مورد نیاز پروژه را وارد کنید.

---

# ▶️ تست اولیه

```bash
source venv/bin/activate
python3 main.py
```

اگر بدون خطا اجرا شد:

```bash
CTRL+C
```

و به مرحله سرویس بروید.

---

# 🔥 اجرای دائمی 24/7 با Systemd

ساخت سرویس:

```bash
nano /etc/systemd/system/reporter.service
```

قرار دهید:

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

ذخیره و فعال‌سازی:

```bash
systemctl daemon-reload
systemctl enable reporter
systemctl start reporter
```

---

# 📌 مدیریت ربات

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
journalctl -u reporter -n 200 --no-pager
```

---

# 🔄 آپدیت پروژه

```bash
cd /opt/reporter
systemctl stop reporter
git pull
source venv/bin/activate
pip install -r requirements.txt
systemctl start reporter
```

---

# 🧰 رفع مشکلات رایج

## سرویس اجرا نمی‌شود

```bash
systemctl status reporter
journalctl -u reporter -n 100 --no-pager
```

## Permission denied

```bash
chmod +x main.py
chmod -R 755 /opt/reporter
```

## پایتون یا پکیج‌ها پیدا نمی‌شوند

```bash
which python3
source /opt/reporter/venv/bin/activate
pip list
```

## اجرای دستی برای تست خطا

```bash
cd /opt/reporter
source venv/bin/activate
python3 main.py
```

## ریبوت و بررسی اجرا

```bash
reboot
```

بعد از ورود:

```bash
systemctl status reporter
```

---

# 💾 بکاپ پیشنهادی

از فایل‌های مهم پروژه بکاپ بگیرید:

```bash
tar -czf reporter-backup.tar.gz /opt/reporter
```

---

# ⚡ نصب سریع

```bash
cd /opt
git clone https://github.com/kiarash707/reporter.git
cd reporter
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python3 main.py
```

بعد از تست موفق Systemd را فعال کنید.

---

ساخته شده برای اجرای پایدار شخصی روی Ubuntu 26.04.
