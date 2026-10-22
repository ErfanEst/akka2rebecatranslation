# ACSU-33 — Dining Philosophers / Arbitrator

گرفتن دو منبع بدون تداخل

## فایل کد

کد واقعی منبع در `source/PhilosopherAkkaActorBenchmark.scala` قرار دارد. این فایل عیناً از commit زیر گرفته شده و تغییر نکرده است:

- Repository: `shamsimam/savina`
- Commit: `52e546959a57670cdba7a88f0a030b53cfdb16d6`
- Git blob: `8b317a13ba4cd8d78d12665e435aef99c64712e3`
- [Source](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/philosopher/PhilosopherAkkaActorBenchmark.scala)
- کلاس‌ها یا بخش انتخاب‌شده: `ArbitratorActor, PhilosopherActor`
- خانواده: `resource_arbitration`
- مسیر فایل‌های کمکی از ریشه بسته: `upstream/shamsimam__savina/`
- مجوز از ریشه بسته: `LICENSES/S_shamsimam__savina_LICENSE.txt`

## پیش از استفاده

این پوشه یک برنامه مستقل آماده اجرای `sbt run` نیست. در فایل‌های چندمثالی، فقط بخش نام‌برده‌شده بالا موضوع انتخاب است. کل فایل ممکن است شامل تست، timer، ask، ساخت اکتور یا مثال‌های دیگری باشد که در محدوده پژوهش نیستند.

برای مثال‌های دارای منبع مشترک، فایل اصلی ممکن است با پوشه دیگری یکسان باشد؛ کلاس یا ترکیب انتخابی متفاوت است. این به معنی ۵۰ برنامه مستقل منتشرشده نیست.

**آماده‌سازی و خطرها:** Choose Savina's untimed arbitrator variant, not Dining Hakkers timers. Remove only shared AtomicLong performance instrumentation or replace it with an actor observer; fork ownership is private arbitrator state. Prove any reduction preserves protocol behavior.

**سناریوی کوتاه پیشنهادی:** 3 philosophers; 1 eating round each

**هدف مقایسه:** mutual exclusion, release and retry

وضعیت: فقط کد منبع جمع‌آوری و صحت بایت‌های آن بررسی شده است. سازگارسازی، کامپایل با نسخه ابزار شما و اجرای differential campaign انجام نشده‌اند. فایل `case.json` جزئیات کامل را دارد.
