# ACSU-05 — Summing Accumulator

جمع‌کردن پیام‌های متوالی در state

## فایل کد

کد واقعی منبع در `source/BehaviourAndState.scala` قرار دارد. این فایل عیناً از commit زیر گرفته شده و تغییر نکرده است:

- Repository: `PacktPublishing/Akka-Cookbook`
- Commit: `ac64624036d75df5da76390d30e19d94333e6fa2`
- Git blob: `4d946f6639070eb988d56d2f53beccf34a25679a`
- [Source](https://github.com/PacktPublishing/Akka-Cookbook/blob/ac64624036d75df5da76390d30e19d94333e6fa2/Hello-Akka/src/main/scala/com/packt/chapter1/BehaviourAndState.scala)
- کلاس‌ها یا بخش انتخاب‌شده: `SummingActor`
- خانواده: `counter`
- مسیر فایل‌های کمکی از ریشه بسته: `upstream/PacktPublishing__Akka-Cookbook/`
- مجوز از ریشه بسته: `LICENSES/C_PacktPublishing__Akka-Cookbook_LICENSE.txt`

## پیش از استفاده

این پوشه یک برنامه مستقل آماده اجرای `sbt run` نیست. در فایل‌های چندمثالی، فقط بخش نام‌برده‌شده بالا موضوع انتخاب است. کل فایل ممکن است شامل تست، timer، ask، ساخت اکتور یا مثال‌های دیگری باشد که در محدوده پژوهش نیستند.

برای مثال‌های دارای منبع مشترک، فایل اصلی ممکن است با پوشه دیگری یکسان باشد؛ کلاس یا ترکیب انتخابی متفاوت است. این به معنی ۵۰ برنامه مستقل منتشرشده نیست.

**آماده‌سازی و خطرها:** Extract SummingActor only. Exclude BehaviourAndState App's infinite Thread.sleep loop and the different SummingActorWithConstructor variant.

**سناریوی کوتاه پیشنهادی:** Add(2), Add(3) -> sum=5

**هدف مقایسه:** persistent scalar state and message order

وضعیت: فقط کد منبع جمع‌آوری و صحت بایت‌های آن بررسی شده است. سازگارسازی، کامپایل با نسخه ابزار شما و اجرای differential campaign انجام نشده‌اند. فایل `case.json` جزئیات کامل را دارد.
