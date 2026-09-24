# Troubleshooting

## ModuleNotFoundError

محیط مجازی را فعال کنید:

```bash
source /opt/reporter/venv/bin/activate
pip install -r /opt/reporter/requirements.txt
```

## خطای Telethon

نسخه نصب‌شده را بررسی کنید:

```bash
python3 -c "import telethon; print(telethon.__version__)"
```

## ربات با systemd اجرا نمی‌شود

وضعیت:

```bash
systemctl status reporter --no-pager
```

لاگ:

```bash
journalctl -u reporter -n 100 --no-pager
```

## تست بدون systemd

```bash
cd /opt/reporter
source venv/bin/activate
python3 main.py
```

اجرای مستقیم معمولاً خطای واقعی Python را واضح‌تر نشان می‌دهد.

## بررسی فایل‌ها

```bash
cd /opt/reporter
ls -lah
```

## بررسی Python

```bash
which python3
python3 --version
```

## بررسی نصب وابستگی‌ها

```bash
pip list
```
