# 🚀 Reporter Bot

ربات حرفه‌ای Telegram Reporter با پنل مدیریت، مدیریت ادمین‌ها، سشن‌ها، گزارش‌گیری و سیستم تنظیمات.

## ✨ امکانات

- پنل مالک و ادمین
- سیستم مدیریت دسترسی
- مدیریت Session های تلگرام
- سیستم گزارش‌گیری و لاگ
- پشتیبانی فارسی و انگلیسی
- ذخیره اطلاعات JSON
- اجرای دائمی روی سرور لینوکسی

## 📦 نصب روی Ubuntu 26.04 (صفر تا صد)

### 1) آپدیت سرور
```bash
sudo apt update && sudo apt upgrade -y
```

### 2) نصب پیش‌نیازها
```bash
sudo apt install python3 python3-pip python3-venv git -y
```

### 3) دریافت پروژه
```bash
git clone https://github.com/kiarash707/reporter.git
cd reporter
```

### 4) ساخت محیط مجازی پایتون
```bash
python3 -m venv venv
source venv/bin/activate
```

### 5) نصب کتابخانه‌ها
```bash
pip install -r requirements.txt
```

### 6) تنظیم اطلاعات ربات

اطلاعات حساس مانند API ID، API HASH و BOT TOKEN را داخل فایل تنظیمات قرار دهید.
هرگز اطلاعات محرمانه را داخل GitHub عمومی قرار ندهید.

### 7) اجرای تستی
```bash
python3 main.py
```

## ⚙️ اجرای دائمی با Systemd

فایل سرویس را در مسیر زیر قرار دهید:

```
/etc/systemd/system/reporter.service
```

سپس:

```bash
sudo systemctl daemon-reload
sudo systemctl enable reporter
sudo systemctl start reporter
```

بررسی وضعیت:

```bash
systemctl status reporter
```

نمایش لاگ‌ها:

```bash
journalctl -u reporter -f
```

## 🔄 مدیریت ربات

ری‌استارت:
```bash
sudo systemctl restart reporter
```

توقف:
```bash
sudo systemctl stop reporter
```

## 🛡️ نکات امنیتی

- توکن ربات را عمومی نکنید.
- Session های تلگرام را محافظت کنید.
- دسترسی فایل‌ها را محدود کنید.
- قبل از تغییرات بکاپ بگیرید.

## 📁 فایل‌های دیتا

فایل‌های ساخته شده توسط ربات شامل اطلاعات کاربران، تنظیمات و Session ها هستند.
قبل از حذف پروژه از آن‌ها بکاپ تهیه کنید.

---

ساخته شده برای اجرای پایدار روی سرورهای Linux Ubuntu 26.04.
