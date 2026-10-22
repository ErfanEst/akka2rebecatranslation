# ACSU-42 — Single-Actor Fibonacci

محاسبه فیبوناچی داخل یک اکتور ثابت

## فایل کد

کد واقعی منبع در `source/FibonacciActor.scala` قرار دارد. این فایل عیناً از commit زیر گرفته شده و تغییر نکرده است:

- Repository: `PacktPublishing/Akka-Cookbook`
- Commit: `ac64624036d75df5da76390d30e19d94333e6fa2`
- Git blob: `1f85076ca3cca6f79cb4e31f2a6d4d99808c6f24`
- [Source](https://github.com/PacktPublishing/Akka-Cookbook/blob/ac64624036d75df5da76390d30e19d94333e6fa2/Hello-Akka/src/main/scala/com/packt/chapter1/FibonacciActor.scala)
- کلاس‌ها یا بخش انتخاب‌شده: `FibonacciActor only (NOT FibonacciActorApp)`
- خانواده: `local_recursion`
- مسیر فایل‌های کمکی از ریشه بسته: `upstream/PacktPublishing__Akka-Cookbook/`
- مجوز از ریشه بسته: `LICENSES/C_PacktPublishing__Akka-Cookbook_LICENSE.txt`

## پیش از استفاده

این پوشه یک برنامه مستقل آماده اجرای `sbt run` نیست. در فایل‌های چندمثالی، فقط بخش نام‌برده‌شده بالا موضوع انتخاب است. کل فایل ممکن است شامل تست، timer، ask، ساخت اکتور یا مثال‌های دیگری باشد که در محدوده پژوهش نیستند.

برای مثال‌های دارای منبع مشترک، فایل اصلی ممکن است با پوشه دیگری یکسان باشد؛ کلاس یا ترکیب انتخابی متفاوت است. این به معنی ۵۰ برنامه مستقل منتشرشده نیست.

**آماده‌سازی و خطرها:** This is NOT Savina recursive actor Fibonacci. The selected class recursively calls an ordinary Scala method and creates no actors. Exclude App's ask/Await/Timeout; use a fixed requester and tell replies. Preserve recursion or validate bounded translation; restrict n to 0..8.

**سناریوی کوتاه پیشنهادی:** Fib(0), Fib(1), Fib(5) -> 0,1,5

**هدف مقایسه:** recursive handler computation without actor creation

وضعیت: فقط کد منبع جمع‌آوری و صحت بایت‌های آن بررسی شده است. سازگارسازی، کامپایل با نسخه ابزار شما و اجرای differential campaign انجام نشده‌اند. فایل `case.json` جزئیات کامل را دارد.
