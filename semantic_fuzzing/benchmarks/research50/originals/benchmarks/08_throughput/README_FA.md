# ACSU-08 — Fixed Fan-out Throughput Kernel

فرستادن پیام به چند اکتور ثابت

## فایل کد

کد واقعی منبع در `source/ThroughputAkkaActorBenchmark.scala` قرار دارد. این فایل عیناً از commit زیر گرفته شده و تغییر نکرده است:

- Repository: `shamsimam/savina`
- Commit: `52e546959a57670cdba7a88f0a030b53cfdb16d6`
- Git blob: `39f568d32176de0cf664430483b245af1c25e302`
- [Source](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/fjthrput/ThroughputAkkaActorBenchmark.scala)
- کلاس‌ها یا بخش انتخاب‌شده: `ThroughputActor`
- خانواده: `fixed_fanout`
- مسیر فایل‌های کمکی از ریشه بسته: `upstream/shamsimam__savina/`
- مجوز از ریشه بسته: `LICENSES/S_shamsimam__savina_LICENSE.txt`

## پیش از استفاده

این پوشه یک برنامه مستقل آماده اجرای `sbt run` نیست. در فایل‌های چندمثالی، فقط بخش نام‌برده‌شده بالا موضوع انتخاب است. کل فایل ممکن است شامل تست، timer، ask، ساخت اکتور یا مثال‌های دیگری باشد که در محدوده پژوهش نیستند.

برای مثال‌های دارای منبع مشترک، فایل اصلی ممکن است با پوشه دیگری یکسان باشد؛ کلاس یا ترکیب انتخابی متفاوت است. این به معنی ۵۰ برنامه مستقل منتشرشده نیست.

**آماده‌سازی و خطرها:** Use a fixed named worker set and compare message counts, not elapsed throughput. Remove benchmark timing harness and audit actor exit.

**سناریوی کوتاه پیشنهادی:** 2 precreated workers; 2 messages each

**هدف مقایسه:** fan-out and per-worker counts

وضعیت: فقط کد منبع جمع‌آوری و صحت بایت‌های آن بررسی شده است. سازگارسازی، کامپایل با نسخه ابزار شما و اجرای differential campaign انجام نشده‌اند. فایل `case.json` جزئیات کامل را دارد.
