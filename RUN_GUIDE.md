# 🚀 Reporter Bot — نصب مستقیم روی سرور

این روش برای Web Terminal و Ubuntu با دسترسی root است. نیازی به `sudo su` نیست.

## 1) دریافت پروژه

اگر پروژه قبلاً نصب شده:

```bash
cd /opt/reporter
git pull
```

اگر پروژه هنوز نصب نشده و ریپو Private است، پس از تنظیم دسترسی GitHub روی سرور:

```bash
cd /opt
git clone git@github.com:kiarash707/reporter.git
cd reporter
```

## 2) نصب کامل

```bash
bash scripts/install.sh
```

اسکریپت Python، venv، کتابخانه‌ها و Systemd را تنظیم می‌کند و سرویس را برای اجرای خودکار بعد از reboot فعال می‌کند.

## 3) اجرا

```bash
systemctl start reporter
systemctl status reporter --no-pager
```

لاگ:

```bash
journalctl -u reporter -n 100 --no-pager
```

## 4) تست مستقیم

اگر سرویس بالا نیامد:

```bash
cd /opt/reporter
./venv/bin/python3 main.py
```

## 5) آپدیت

```bash
cd /opt/reporter
systemctl stop reporter
git pull
./venv/bin/python -m pip install -r requirements.txt
systemctl daemon-reload
systemctl start reporter
systemctl status reporter --no-pager
```
