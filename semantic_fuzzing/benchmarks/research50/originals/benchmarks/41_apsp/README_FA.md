# ACSU-41 — All-Pairs Shortest Path

فاصله کوتاه‌ترین مسیر همه جفت‌ها

## فایل کد

کد واقعی منبع در `source/ApspAkkaActorBenchmark.scala` قرار دارد. این فایل عیناً از commit زیر گرفته شده و تغییر نکرده است:

- Repository: `shamsimam/savina`
- Commit: `52e546959a57670cdba7a88f0a030b53cfdb16d6`
- Git blob: `072ace683c6fcbe8f466f5a40532dfca77e9212f`
- [Source](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/apsp/ApspAkkaActorBenchmark.scala)
- کلاس‌ها یا بخش انتخاب‌شده: `ApspFloydWarshallActor`
- خانواده: `graph_apsp`
- مسیر فایل‌های کمکی از ریشه بسته: `upstream/shamsimam__savina/`
- مجوز از ریشه بسته: `LICENSES/S_shamsimam__savina_LICENSE.txt`

## پیش از استفاده

این پوشه یک برنامه مستقل آماده اجرای `sbt run` نیست. در فایل‌های چندمثالی، فقط بخش نام‌برده‌شده بالا موضوع انتخاب است. کل فایل ممکن است شامل تست، timer، ask، ساخت اکتور یا مثال‌های دیگری باشد که در محدوده پژوهش نیستند.

برای مثال‌های دارای منبع مشترک، فایل اصلی ممکن است با پوشه دیگری یکسان باشد؛ کلاس یا ترکیب انتخابی متفاوت است. این به معنی ۵۰ برنامه مستقل منتشرشده نیست.

**آماده‌سازی و خطرها:** Fixed block graph; flatten startup loops into named actors. Matrix/array messages require deep-copy/immutability audit and complete bounded state projection.

**سناریوی کوتاه پیشنهادی:** 2x2 or 3x3 graph; tiny nonnegative weights

**هدف مقایسه:** phase barriers and distributed matrix updates

وضعیت: فقط کد منبع جمع‌آوری و صحت بایت‌های آن بررسی شده است. سازگارسازی، کامپایل با نسخه ابزار شما و اجرای differential campaign انجام نشده‌اند. فایل `case.json` جزئیات کامل را دارد.
