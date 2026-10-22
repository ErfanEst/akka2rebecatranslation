# ACSU-22 — Hierarchical Publish/Subscribe

اشتراک در شاخه موضوع‌ها

## فایل کد

کد واقعی منبع در `source/EventBusDocSpec.scala` قرار دارد. این فایل عیناً از commit زیر گرفته شده و تغییر نکرده است:

- Repository: `akka/akka-core`
- Commit: `044bb2dc0a3804d7fe33a1d3e988830256c108fa`
- Git blob: `2b684798cf0cb7200d849e367a7523640cb6c7ff`
- [Source](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/event/EventBusDocSpec.scala)
- کلاس‌ها یا بخش انتخاب‌شده: `SubchannelBusImpl + StartsWithSubclassification`
- خانواده: `pubsub`
- مسیر فایل‌های کمکی از ریشه بسته: `upstream/akka__akka-core/`
- مجوز از ریشه بسته: `LICENSES/A_akka__akka-core_LICENSE.txt`

## پیش از استفاده

این پوشه یک برنامه مستقل آماده اجرای `sbt run` نیست. در فایل‌های چندمثالی، فقط بخش نام‌برده‌شده بالا موضوع انتخاب است. کل فایل ممکن است شامل تست، timer، ask، ساخت اکتور یا مثال‌های دیگری باشد که در محدوده پژوهش نیستند.

برای مثال‌های دارای منبع مشترک، فایل اصلی ممکن است با پوشه دیگری یکسان باشد؛ کلاس یا ترکیب انتخابی متفاوت است. این به معنی ۵۰ برنامه مستقل منتشرشده نیست.

**آماده‌سازی و خطرها:** RESERVE. Same EventBus boundary issue as lookup; finite topic hierarchy and exact subscription matching. Do not silently turn synchronous library behavior into asynchronous broker semantics.

**سناریوی کوتاه پیشنهادی:** subscribe a and ab; publish abc

**هدف مقایسه:** prefix/subclass delivery and overlapping subscriptions

وضعیت: فقط کد منبع جمع‌آوری و صحت بایت‌های آن بررسی شده است. سازگارسازی، کامپایل با نسخه ابزار شما و اجرای differential campaign انجام نشده‌اند. فایل `case.json` جزئیات کامل را دارد.
