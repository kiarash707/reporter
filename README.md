# Reporter Dashboard

پنل عملیات زنده برای مدیریت و پایش سرویس Reporter.

## امکانات

- مرکز عملیات زنده با وضعیت Telegram، Processing، Handlerها و Storage
- نمایش uptime، کاربران، مدیران، sessionها، کانال‌های اجباری و deployment
- API latency و تشخیص داده‌های قدیمی/قطع ارتباط
- بروزرسانی خودکار با توقف خودکار هنگام مخفی بودن تب برای کاهش مصرف منابع
- مدیریت کاربران: جستجو، بلاک/آنبلاک و ارسال پیام
- مدیریت مدیران با اعتبارسنجی تعداد روز
- مدیریت کانال‌های اجباری با اعتبارسنجی username
- کنسول لاگ زنده با فیلتر متن و سطح
- کنترل پاسخ‌گویی و Restart
- Diagnostics و وضعیت Volume / data.json / admin sessions
- طراحی RTL واکنش‌گرا، Glass UI، انیمیشن و حالت کم‌مصرف با prefers-reduced-motion
- بدون CDN یا وابستگی بیرونی در رابط

## Environment variables

```text
BOT_INTERNAL_URL=http://reporter.railway.internal:8080
MONITOR_TOKEN=<same token configured on reporter>
DASHBOARD_USER=admin
DASHBOARD_PASSWORD=<strong password>
PORT=8080
REQUEST_TIMEOUT=8
```

## Stability / security

- سرویس Dashboard مستقل از Bot اجرا می‌شود.
- endpoint عمومی `/health` برای Railway بدون احراز هویت است؛ سایر APIها نیازمند Basic Auth هستند.
- داده‌های API با `Cache-Control: no-store` ارسال می‌شوند.
- هدرهای امنیتی و محدودیت اندازه درخواست POST فعال است.
- رابط در برابر timeout، قطعی موقت و خطاهای API حالت خطای کنترل‌شده دارد.
