# ACSU-50 — Pausable Worker

یک کار در لحظه و ادامه با پیام Ready

## فایل کد

کد واقعی منبع در `source/PausableActor.scala` قرار دارد. این فایل عیناً از commit زیر گرفته شده و تغییر نکرده است:

- Repository: `PacktPublishing/Akka-Cookbook`
- Commit: `ac64624036d75df5da76390d30e19d94333e6fa2`
- Git blob: `011427a8983b7d8132f73c3343c69f4260308271`
- [Source](https://github.com/PacktPublishing/Akka-Cookbook/blob/ac64624036d75df5da76390d30e19d94333e6fa2/Chapter10/src/main/scala/com/packt/chapter10/PausableActor.scala)
- کلاس‌ها یا بخش انتخاب‌شده: `PausableActor with untimed completion worker`
- خانواده: `stash_protocol`
- مسیر فایل‌های کمکی از ریشه بسته: `upstream/PacktPublishing__Akka-Cookbook/`
- مجوز از ریشه بسته: `LICENSES/C_PacktPublishing__Akka-Cookbook_LICENSE.txt`

## پیش از استفاده

این پوشه یک برنامه مستقل آماده اجرای `sbt run` نیست. در فایل‌های چندمثالی، فقط بخش نام‌برده‌شده بالا موضوع انتخاب است. کل فایل ممکن است شامل تست، timer، ask، ساخت اکتور یا مثال‌های دیگری باشد که در محدوده پژوهش نیستند.

برای مثال‌های دارای منبع مشترک، فایل اصلی ممکن است با پوشه دیگری یکسان باشد؛ کلاس یا ترکیب انتخابی متفاوت است. این به معنی ۵۰ برنامه مستقل منتشرشده نیست.

**آماده‌سازی و خطرها:** RESERVE. Preserve stash and behavior stack; use an explicit untimed worker, not original HardWorker's artificial delay. Selecting a replacement worker yields a documented benchmark composition, not the complete original app.

**سناریوی کوتاه پیشنهادی:** Work(1), Work(2), bogus Ready, worker Ready

**هدف مقایسه:** backpressure, sender authentication and FIFO unstash

وضعیت: فقط کد منبع جمع‌آوری و صحت بایت‌های آن بررسی شده است. سازگارسازی، کامپایل با نسخه ابزار شما و اجرای differential campaign انجام نشده‌اند. فایل `case.json` جزئیات کامل را دارد.
