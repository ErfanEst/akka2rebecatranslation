# ACSU-19 — Fixed Broadcast Routing

ارسال هر پیام به همه گیرنده‌ها

## فایل کد

کد واقعی منبع در `source/RouterDocSpec.scala` قرار دارد. این فایل عیناً از commit زیر گرفته شده و تغییر نکرده است:

- Repository: `akka/akka-core`
- Commit: `044bb2dc0a3804d7fe33a1d3e988830256c108fa`
- Git blob: `b9d19d6fb75ab920d212eadb7f6056a1474f8de5`
- [Source](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/routing/RouterDocSpec.scala)
- کلاس‌ها یا بخش انتخاب‌شده: `Broadcast routing configuration`
- خانواده: `fixed_routing`
- مسیر فایل‌های کمکی از ریشه بسته: `upstream/akka__akka-core/`
- مجوز از ریشه بسته: `LICENSES/A_akka__akka-core_LICENSE.txt`

## پیش از استفاده

این پوشه یک برنامه مستقل آماده اجرای `sbt run` نیست. در فایل‌های چندمثالی، فقط بخش نام‌برده‌شده بالا موضوع انتخاب است. کل فایل ممکن است شامل تست، timer، ask، ساخت اکتور یا مثال‌های دیگری باشد که در محدوده پژوهش نیستند.

برای مثال‌های دارای منبع مشترک، فایل اصلی ممکن است با پوشه دیگری یکسان باشد؛ کلاس یا ترکیب انتخابی متفاوت است. این به معنی ۵۰ برنامه مستقل منتشرشده نیست.

**آماده‌سازی و خطرها:** Use a static routee set and no pool resizer/replacement. Built-in Router internals are not automatically supported by the existing extractor; explicit actor implementation is a derived benchmark.

**سناریوی کوتاه پیشنهادی:** one request -> each of 3 workers once

**هدف مقایسه:** duplicate omission and fan-out cardinality

وضعیت: فقط کد منبع جمع‌آوری و صحت بایت‌های آن بررسی شده است. سازگارسازی، کامپایل با نسخه ابزار شما و اجرای differential campaign انجام نشده‌اند. فایل `case.json` جزئیات کامل را دارد.
