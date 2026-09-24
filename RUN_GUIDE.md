# 🚀 Reporter Bot - Full Run Guide (Web Terminal / Ubuntu 26.04)

این راهنما مخصوص اجرای شخصی پروژه روی سرور است. تمام مراحل از نصب تا رفع خطا نوشته شده است.

## 1) ورود به وب ترمینال سرور

ابتدا وارد Web Terminal شوید و این دستورات را پشت سر هم اجرا کنید.

## 2) آماده سازی سرور

```bash
apt update && apt upgrade -y
apt install -y git python3 python3-pip python3-venv curl nano
```

بررسی Python:

```bash
python3 --version
```

## 3) دریافت پروژه

اگر پروژه وجود ندارد:

```bash
cd /opt
git clone https://github.com/kiarash707/reporter.git
```

ورود:

```bash
cd /opt/reporter
```

اگر قبلا نصب شده:

```bash
cd /opt/reporter
git pull
```

## 4) ساخت محیط Python

```bash
python3 -m venv venv
source venv/bin/activate
```

اگر خطای venv گرفتید:

```bash
apt install python3-venv -y
```

## 5) نصب کتابخانه ها

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

اگر خطای Permission گرفتید:

```bash
chmod -R 755 /opt/reporter
```

## 6) تست اولیه اجرا

```bash
python3 main.py
```

اگر اجرا شد، با CTRL+C متوقف کنید و به مرحله سرویس بروید.

## 7) اجرای دائمی 24/7

ساخت سرویس:

```bash
nano /etc/systemd/system/reporter.service
```

محتوا:

```ini
[Unit]
Description=Reporter Bot
After=network.target

[Service]
WorkingDirectory=/opt/reporter
ExecStart=/opt/reporter/venv/bin/python3 /opt/reporter/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

فعال سازی:

```bash
systemctl daemon-reload
systemctl enable reporter
systemctl start reporter
```

## 8) بررسی وضعیت

```bash
systemctl status reporter
```

لاگ زنده:

```bash
journalctl -u reporter -f
```

آخرین خطاها:

```bash
journalctl -u reporter -n 100 --no-pager
```

## 9) دستورات روزانه

ری استارت:

```bash
systemctl restart reporter
```

توقف:

```bash
systemctl stop reporter
```

شروع:

```bash
systemctl start reporter
```

## خطاهای رایج

### Python پیدا نشد
```bash
apt install python3 python3-pip -y
```

### پکیج نصب نیست
```bash
pip install -r requirements.txt
```

### Permission denied
```bash
chmod -R 755 /opt/reporter
```

### پروژه بعد از ریبوت اجرا نمی شود

```bash
systemctl enable reporter
systemctl restart reporter
```

### بررسی مصرف سرور

```bash
top
```

یا:

```bash
free -h
```

## آپدیت نسخه جدید

```bash
cd /opt/reporter
systemctl stop reporter
git pull
source venv/bin/activate
pip install -r requirements.txt
systemctl start reporter
```

این فایل برای نصب و مدیریت ساده پروژه در محیط Web Terminal ساخته شده است.
