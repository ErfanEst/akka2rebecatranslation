# ACSU-16 — Thread Ring

گردش توکن بین گره‌های ثابت

## فایل کد

کد واقعی منبع در `source/ThreadRingAkkaActorBenchmark.scala` قرار دارد. این فایل عیناً از commit زیر گرفته شده و تغییر نکرده است:

- Repository: `shamsimam/savina`
- Commit: `52e546959a57670cdba7a88f0a030b53cfdb16d6`
- Git blob: `9dc9d0b6eb6157774aa3bf53dccffdb8198ce37f`
- [Source](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/threadring/ThreadRingAkkaActorBenchmark.scala)
- کلاس‌ها یا بخش انتخاب‌شده: `ThreadRingActor`
- خانواده: `token_ring`
- مسیر فایل‌های کمکی از ریشه بسته: `upstream/shamsimam__savina/`
- مجوز از ریشه بسته: `LICENSES/S_shamsimam__savina_LICENSE.txt`

## پیش از استفاده

این پوشه یک برنامه مستقل آماده اجرای `sbt run` نیست. در فایل‌های چندمثالی، فقط بخش نام‌برده‌شده بالا موضوع انتخاب است. کل فایل ممکن است شامل تست، timer، ask، ساخت اکتور یا مثال‌های دیگری باشد که در محدوده پژوهش نیستند.

برای مثال‌های دارای منبع مشترک، فایل اصلی ممکن است با پوشه دیگری یکسان باشد؛ کلاس یا ترکیب انتخابی متفاوت است. این به معنی ۵۰ برنامه مستقل منتشرشده نیست.

**آماده‌سازی و خطرها:** Unroll actor array into three named bootstrap declarations; configure neighbors before Start and keep topology frozen. Neighbor setup ActorRef payloads need adapter.

**سناریوی کوتاه پیشنهادی:** 3 nodes; token with 5 hops

**هدف مقایسه:** routing, hop decrement and destination

وضعیت: فقط کد منبع جمع‌آوری و صحت بایت‌های آن بررسی شده است. سازگارسازی، کامپایل با نسخه ابزار شما و اجرای differential campaign انجام نشده‌اند. فایل `case.json` جزئیات کامل را دارد.
