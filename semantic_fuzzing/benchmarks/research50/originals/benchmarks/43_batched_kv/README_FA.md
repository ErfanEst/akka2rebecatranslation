# ACSU-43 — Batched Key-Value Requests

اجرای چند درخواست در یک پیام دسته‌ای

## فایل کد

کد واقعی منبع در `source/AkkademyDb.scala` قرار دارد. این فایل عیناً از commit زیر گرفته شده و تغییر نکرده است:

- Repository: `jasongoodwin/learning-akka`
- Commit: `e96dd964b26ea4f98cb6b0531e02018ee3d4c109`
- Git blob: `1a3d82a35d0715f77920bc70054db33d3522cbcc`
- [Source](https://github.com/jasongoodwin/learning-akka/blob/e96dd964b26ea4f98cb6b0531e02018ee3d4c109/ch4/akkademy-db-scala/src/main/scala/com/akkademy/AkkademyDb.scala)
- کلاس‌ها یا بخش انتخاب‌شده: `AkkademyDb (chapter 4)`
- خانواده: `key_value`
- مسیر فایل‌های کمکی از ریشه بسته: `upstream/jasongoodwin__learning-akka/`
- مجوز از ریشه بسته: `LICENSES/L_jasongoodwin__learning-akka_LICENSE.txt`

## پیش از استفاده

این پوشه یک برنامه مستقل آماده اجرای `sbt run` نیست. در فایل‌های چندمثالی، فقط بخش نام‌برده‌شده بالا موضوع انتخاب است. کل فایل ممکن است شامل تست، timer، ask، ساخت اکتور یا مثال‌های دیگری باشد که در محدوده پژوهش نیستند.

برای مثال‌های دارای منبع مشترک، فایل اصلی ممکن است با پوشه دیگری یکسان باشد؛ کلاس یا ترکیب انتخابی متفاوت است. این به معنی ۵۰ برنامه مستقل منتشرشده نیست.

**آماده‌سازی و خطرها:** Use local precreated db/clients, no remoting/client FSM. Preserve that List requests run inside ONE handler; splitting a batch into separate mailbox messages changes semantics. Object/List/String/Status/ActorRef reply fields need complete finite encoding.

**سناریوی کوتاه پیشنهادی:** batch [Set(k,1),Get(k)] then another-client write

**هدف مقایسه:** batch atomicity, per-item reply and missing key

وضعیت: فقط کد منبع جمع‌آوری و صحت بایت‌های آن بررسی شده است. سازگارسازی، کامپایل با نسخه ابزار شما و اجرای differential campaign انجام نشده‌اند. فایل `case.json` جزئیات کامل را دارد.
