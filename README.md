# Reporter Dashboard

Independent read-only monitoring dashboard for the Reporter Telegram bot.

## Features

- مرکز عملیات زنده با وضعیت Telegram، پردازش پیام و زمان فعالیت
- تشخیص Event Handler و شمارش /start، Callback و پیام خصوصی
- Diagnostics داخلی برای Telegram، Handlers، Processing و Volume/Storage
- مدیریت کاربران: مشاهده، جستجو، بلاک/آنبلاک و ارسال پیام
- مدیریت مدیران و تاریخ انقضا
- مدیریت کانال‌های اجباری
- کنسول لاگ زنده با فیلتر سطح و ترجمه رخدادهای رایج
- کنترل عملیاتی: فعال‌سازی، توقف پاسخ‌گویی و Restart
- رابط RTL واکنش‌گرا با Glass UI، پس‌زمینه ذرات، انیمیشن، Pulse و Scan
- بدون وابستگی به CDN یا سرویس خارجی در رابط کاربری
- بروزرسانی خودکار وضعیت و لاگ‌ها

## Environment variables

```text
BOT_INTERNAL_URL=http://reporter.railway.internal:8080
MONITOR_TOKEN=<same token configured on reporter>
DASHBOARD_USER=admin
DASHBOARD_PASSWORD=<strong password>
PORT=8080
```

The dashboard is intentionally a separate Railway service. If the dashboard service crashes or is redeployed, the Telegram bot remains independent.
