# ACSU-48 — Routing Slip / Car Assembly

عبور سفارش از مراحل انتخابی

## فایل کد

کد واقعی منبع در `source/SlipRouter.scala` قرار دارد. این فایل عیناً از commit زیر گرفته شده و تغییر نکرده است:

- Repository: `RayRoestenburg/akka-in-action`
- Commit: `32b301d3042c832a016ca3220576960c43317630`
- Git blob: `ad2163f0b7aa79e3300079e2acc205db450a938e`
- [Source](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-routing/src/main/scala/aia/routing/SlipRouter.scala)
- کلاس‌ها یا بخش انتخاب‌شده: `SlipRouter, PaintCar, AddNavigation, AddParkingSensors`
- خانواده: `routing_slip`
- مسیر فایل‌های کمکی از ریشه بسته: `upstream/RayRoestenburg__akka-in-action/`
- مجوز از ریشه بسته: `LICENSES/I_RayRoestenburg__akka-in-action_LICENSE.txt`

## پیش از استفاده

این پوشه یک برنامه مستقل آماده اجرای `sbt run` نیست. در فایل‌های چندمثالی، فقط بخش نام‌برده‌شده بالا موضوع انتخاب است. کل فایل ممکن است شامل تست، timer، ask، ساخت اکتور یا مثال‌های دیگری باشد که در محدوده پژوهش نیستند.

برای مثال‌های دارای منبع مشترک، فایل اصلی ممکن است با پوشه دیگری یکسان باشد؛ کلاس یا ترکیب انتخابی متفاوت است. این به معنی ۵۰ برنامه مستقل منتشرشده نیست.

**آماده‌سازی و خطرها:** Precreate fixed component actors and inject refs. Choosing a path through existing actors is not creating actors; if dynamic topology is also forbidden, fix the finite allowed route set explicitly. Seq[ActorRef]/nested messages need bounded representation.

**سناریوی کوتاه پیشنهادی:** fixed color/navigation/sensor actors; orders with 2 option sets

**هدف مقایسه:** variable route over fixed actors and payload enrichment

وضعیت: فقط کد منبع جمع‌آوری و صحت بایت‌های آن بررسی شده است. سازگارسازی، کامپایل با نسخه ابزار شما و اجرای differential campaign انجام نشده‌اند. فایل `case.json` جزئیات کامل را دارد.
