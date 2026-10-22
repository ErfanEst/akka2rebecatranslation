# ACSU-23 — Predicate Publish/Subscribe

انتخاب مشترک براساس شرط

## فایل کد

کد واقعی منبع در `source/EventBusDocSpec.scala` قرار دارد. این فایل عیناً از commit زیر گرفته شده و تغییر نکرده است:

- Repository: `akka/akka-core`
- Commit: `044bb2dc0a3804d7fe33a1d3e988830256c108fa`
- Git blob: `2b684798cf0cb7200d849e367a7523640cb6c7ff`
- [Source](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/event/EventBusDocSpec.scala)
- کلاس‌ها یا بخش انتخاب‌شده: `ScanningBusImpl`
- خانواده: `pubsub`
- مسیر فایل‌های کمکی از ریشه بسته: `upstream/akka__akka-core/`
- مجوز از ریشه بسته: `LICENSES/A_akka__akka-core_LICENSE.txt`

## پیش از استفاده

این پوشه یک برنامه مستقل آماده اجرای `sbt run` نیست. در فایل‌های چندمثالی، فقط بخش نام‌برده‌شده بالا موضوع انتخاب است. کل فایل ممکن است شامل تست، timer، ask، ساخت اکتور یا مثال‌های دیگری باشد که در محدوده پژوهش نیستند.

برای مثال‌های دارای منبع مشترک، فایل اصلی ممکن است با پوشه دیگری یکسان باشد؛ کلاس یا ترکیب انتخابی متفاوت است. این به معنی ۵۰ برنامه مستقل منتشرشده نیست.

**آماده‌سازی و خطرها:** RESERVE. Source predicate is String.length <= classifier. Preserve length operation and sender behavior; requires external-library adapter or separately labeled actor-based derivative.

**سناریوی کوتاه پیشنهادی:** length thresholds 2 and 3; publish lengths 1,3,4

**هدف مقایسه:** overlapping predicates and boundary values

وضعیت: فقط کد منبع جمع‌آوری و صحت بایت‌های آن بررسی شده است. سازگارسازی، کامپایل با نسخه ابزار شما و اجرای differential campaign انجام نشده‌اند. فایل `case.json` جزئیات کامل را دارد.
