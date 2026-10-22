# ACSU-24 — Content-Based Speed Router

انتخاب مسیر براساس مقدار پیام

## فایل کد

کد واقعی منبع در `source/Routing.scala` قرار دارد. این فایل عیناً از commit زیر گرفته شده و تغییر نکرده است:

- Repository: `RayRoestenburg/akka-in-action`
- Commit: `32b301d3042c832a016ca3220576960c43317630`
- Git blob: `30064cc1d075e87b85f0c3274046235fc58a9423`
- [Source](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-routing/src/main/scala/aia/routing/Routing.scala)
- کلاس‌ها یا بخش انتخاب‌شده: `SpeedRouterLogic`
- خانواده: `fixed_routing`
- مسیر فایل‌های کمکی از ریشه بسته: `upstream/RayRoestenburg__akka-in-action/`
- مجوز از ریشه بسته: `LICENSES/I_RayRoestenburg__akka-in-action_LICENSE.txt`

## پیش از استفاده

این پوشه یک برنامه مستقل آماده اجرای `sbt run` نیست. در فایل‌های چندمثالی، فقط بخش نام‌برده‌شده بالا موضوع انتخاب است. کل فایل ممکن است شامل تست، timer، ask، ساخت اکتور یا مثال‌های دیگری باشد که در محدوده پژوهش نیستند.

برای مثال‌های دارای منبع مشترک، فایل اصلی ممکن است با پوشه دیگری یکسان باشد؛ کلاس یا ترکیب انتخابی متفاوت است. این به معنی ۵۰ برنامه مستقل منتشرشده نیست.

**آماده‌سازی و خطرها:** Extract routing predicate with fixed endpoints; source Pool and GetLicense are not admitted. Embedding library RoutingLogic in an explicit Actor is a derived benchmark, not unchanged source.

**سناریوی کوتاه پیشنهادی:** speed equal/below/above minSpeed

**هدف مقایسه:** threshold branch and destination

وضعیت: فقط کد منبع جمع‌آوری و صحت بایت‌های آن بررسی شده است. سازگارسازی، کامپایل با نسخه ابزار شما و اجرای differential campaign انجام نشده‌اند. فایل `case.json` جزئیات کامل را دارد.
