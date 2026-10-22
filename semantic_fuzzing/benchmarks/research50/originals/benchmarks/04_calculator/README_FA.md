# ACSU-04 — Integer Calculator

جمع و ضرب دو عدد

## فایل کد

کد واقعی منبع در `source/CalculatorActor.scala` قرار دارد. این فایل عیناً از commit زیر گرفته شده و تغییر نکرده است:

- Repository: `PacktPublishing/Akka-Cookbook`
- Commit: `ac64624036d75df5da76390d30e19d94333e6fa2`
- Git blob: `bb830feadb7dd4f743af971cbc897d6e09d50a2d`
- [Source](https://github.com/PacktPublishing/Akka-Cookbook/blob/ac64624036d75df5da76390d30e19d94333e6fa2/Chapter11/akka-impl/src/main/scala/com/packt/chapter11/akka/impl/CalculatorActor.scala)
- کلاس‌ها یا بخش انتخاب‌شده: `CalculatorActor`
- خانواده: `arithmetic`
- مسیر فایل‌های کمکی از ریشه بسته: `upstream/PacktPublishing__Akka-Cookbook/`
- مجوز از ریشه بسته: `LICENSES/C_PacktPublishing__Akka-Cookbook_LICENSE.txt`

## پیش از استفاده

این پوشه یک برنامه مستقل آماده اجرای `sbt run` نیست. در فایل‌های چندمثالی، فقط بخش نام‌برده‌شده بالا موضوع انتخاب است. کل فایل ممکن است شامل تست، timer، ask، ساخت اکتور یا مثال‌های دیگری باشد که در محدوده پژوهش نیستند.

برای مثال‌های دارای منبع مشترک، فایل اصلی ممکن است با پوشه دیگری یکسان باشد؛ کلاس یا ترکیب انتخابی متفاوت است. این به معنی ۵۰ برنامه مستقل منتشرشده نیست.

**آماده‌سازی و خطرها:** Use CalculatorActor alone, no Lagom service. Restrict inputs to avoid overflow initially; later test signed Int boundaries with matching semantics.

**سناریوی کوتاه پیشنهادی:** Sum(2,3), Multiply(2,3)

**هدف مقایسه:** two argument values and operation dispatch

وضعیت: فقط کد منبع جمع‌آوری و صحت بایت‌های آن بررسی شده است. سازگارسازی، کامپایل با نسخه ابزار شما و اجرای differential campaign انجام نشده‌اند. فایل `case.json` جزئیات کامل را دارد.
