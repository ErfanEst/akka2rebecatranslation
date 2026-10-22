# ACSU-26 — Envelope Enrichment

افزودن اطلاعات ثابت به پیام

## فایل کد

کد واقعی منبع در `source/EnvelopingActor.scala` قرار دارد. این فایل عیناً از commit زیر گرفته شده و تغییر نکرده است:

- Repository: `PacktPublishing/Akka-Cookbook`
- Commit: `ac64624036d75df5da76390d30e19d94333e6fa2`
- Git blob: `5c88481cca1e4bd38b2b8762b03bbdb7d1c93f9a`
- [Source](https://github.com/PacktPublishing/Akka-Cookbook/blob/ac64624036d75df5da76390d30e19d94333e6fa2/Chapter10/src/main/scala/com/packt/chapter10/EnvelopingActor.scala)
- کلاس‌ها یا بخش انتخاب‌شده: `EnvelopingActor with constant header function`
- خانواده: `envelope`
- مسیر فایل‌های کمکی از ریشه بسته: `upstream/PacktPublishing__Akka-Cookbook/`
- مجوز از ریشه بسته: `LICENSES/C_PacktPublishing__Akka-Cookbook_LICENSE.txt`

## پیش از استفاده

این پوشه یک برنامه مستقل آماده اجرای `sbt run` نیست. در فایل‌های چندمثالی، فقط بخش نام‌برده‌شده بالا موضوع انتخاب است. کل فایل ممکن است شامل تست، timer، ask، ساخت اکتور یا مثال‌های دیگری باشد که در محدوده پژوهش نیستند.

برای مثال‌های دارای منبع مشترک، فایل اصلی ممکن است با پوشه دیگری یکسان باشد؛ کلاس یا ترکیب انتخابی متفاوت است. این به معنی ۵۰ برنامه مستقل منتشرشده نیست.

**آماده‌سازی و خطرها:** Select a constant pure addHeaders function. Do NOT use EnvelopingActorApp, whose header includes currentTimeMillis. Generic nested payloads/maps need finite serialization and projection.

**سناریوی کوتاه پیشنهادی:** Send(5) -> Envelope(5, fixed-header)

**هدف مقایسه:** payload preservation and metadata

وضعیت: فقط کد منبع جمع‌آوری و صحت بایت‌های آن بررسی شده است. سازگارسازی، کامپایل با نسخه ابزار شما و اجرای differential campaign انجام نشده‌اند. فایل `case.json` جزئیات کامل را دارد.
