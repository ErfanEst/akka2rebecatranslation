# ACSU-28 — Ticket Seller

فروش از موجودی محدود بلیت

## فایل کد

کد واقعی منبع در `source/TicketSeller.scala` قرار دارد. این فایل عیناً از commit زیر گرفته شده و تغییر نکرده است:

- Repository: `RayRoestenburg/akka-in-action`
- Commit: `32b301d3042c832a016ca3220576960c43317630`
- Git blob: `eea0d7ca32d6333632b2bb21afb16649b6c5eb00`
- [Source](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-up-and-running/src/main/scala/com/goticks/TicketSeller.scala)
- کلاس‌ها یا بخش انتخاب‌شده: `TicketSeller`
- خانواده: `inventory`
- مسیر فایل‌های کمکی از ریشه بسته: `upstream/RayRoestenburg__akka-in-action/`
- مجوز از ریشه بسته: `LICENSES/I_RayRoestenburg__akka-in-action_LICENSE.txt`

## پیش از استفاده

این پوشه یک برنامه مستقل آماده اجرای `sbt run` نیست. در فایل‌های چندمثالی، فقط بخش نام‌برده‌شده بالا موضوع انتخاب است. کل فایل ممکن است شامل تست، timer، ask، ساخت اکتور یا مثال‌های دیگری باشد که در محدوده پژوهش نیستند.

برای مثال‌های دارای منبع مشترک، فایل اصلی ممکن است با پوشه دیگری یکسان باشد؛ کلاس یا ترکیب انتخابی متفاوت است. این به معنی ۵۰ برنامه مستقل منتشرشده نیست.

**آماده‌سازی و خطرها:** Use one precreated seller, not BoxOffice (creates event sellers). Vector/Option/nested messages and event metadata need mapping. Exclude Cancel initially or specify PoisonPill/dead-letter semantics explicitly.

**سناریوی کوتاه پیشنهادی:** Add 2 tickets; Buy 2; Buy 1

**هدف مقایسه:** stock depletion and exact-amount boundary

وضعیت: فقط کد منبع جمع‌آوری و صحت بایت‌های آن بررسی شده است. سازگارسازی، کامپایل با نسخه ابزار شما و اجرای differential campaign انجام نشده‌اند. فایل `case.json` جزئیات کامل را دارد.
