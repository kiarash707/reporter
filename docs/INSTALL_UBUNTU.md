# نصب و اجرای ربات روی Ubuntu Server

## 1. ورود به سرور

از Web Terminal یا SSH وارد سرور شوید.

## 2. آپدیت Ubuntu

```bash
apt update && apt upgrade -y
```

## 3. نصب Python

```bash
apt install -y python3 python3-pip python3-venv git
```

بررسی:

```bash
python3 --version
pip3 --version
```

## 4. دریافت Repository

```cd /opt
git clone https://github.com/kiarash707/reporter.git
cd reporter
```

اگر Repository خصوصی است، GitHub باید با روش احراز هویت مناسب در سرور در دسترس باشد.

## 5. ساخت Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

## 6. نصب وابستگی‌ها

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 7. بررسی سریع

```bash
python3 -c "import telethon, pytz; print('Dependencies OK')"
```

## 8. اجرای مستقیم

نام فایل اصلی سورس را بررسی کنید:

```bash
ls -la
```

سپس:

```bash
python3 main.py
```

اگر نام فایل سورس چیز دیگری است، همان نام واقعی را جایگزین `main.py` کنید.

## 9. اجرای دائمی با systemd

```bash
nano /etc/systemd/system/reporter.service
```

محتوا:

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

## 10. بررسی

```systemctl status reporter
```

لاگ زنده:

```bash
journalctl -u reporter -f
```

## 11. توقف و راه‌اندازی مجدد

```bash
systemctl stop reporter
systemctl restart reporter
```

## 12. اجرای مجدد بعد از آپدیت

```bash
cd /opt/reporter
git pull
source venv/bin/activate
pip install -r requirements.txt
systemctl restart reporter
```
