# ACSU-12 — Speed Threshold Filter

عبور پیام فقط بالاتر از حد

## فایل کد

کد واقعی منبع در `source/Filters.scala` قرار دارد. این فایل عیناً از commit زیر گرفته شده و تغییر نکرده است:

- Repository: `RayRoestenburg/akka-in-action`
- Commit: `32b301d3042c832a016ca3220576960c43317630`
- Git blob: `674cdaf805db38111c476721a763df457bd749cc`
- [Source](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-structure/src/main/scala/aia/structure/Filters.scala)
- کلاس‌ها یا بخش انتخاب‌شده: `SpeedFilter`
- خانواده: `photo_filter`
- مسیر فایل‌های کمکی از ریشه بسته: `upstream/RayRoestenburg__akka-in-action/`
- مجوز از ریشه بسته: `LICENSES/I_RayRoestenburg__akka-in-action_LICENSE.txt`

## پیش از استفاده

این پوشه یک برنامه مستقل آماده اجرای `sbt run` نیست. در فایل‌های چندمثالی، فقط بخش نام‌برده‌شده بالا موضوع انتخاب است. کل فایل ممکن است شامل تست، timer، ask، ساخت اکتور یا مثال‌های دیگری باشد که در محدوده پژوهش نیستند.

برای مثال‌های دارای منبع مشترک، فایل اصلی ممکن است با پوشه دیگری یکسان باشد؛ کلاس یا ترکیب انتخابی متفاوت است. این به معنی ۵۰ برنامه مستقل منتشرشده نیست.

**آماده‌سازی و خطرها:** Fixed source/filter/sink; use tiny licence domain. Extract SpeedFilter without unrelated routing/performance code; compare absent sends through post-mailboxes, not a wall-clock timeout.

**سناریوی کوتاه پیشنهادی:** speed below/equal/above threshold

**هدف مقایسه:** strict comparison and no-send branch

وضعیت: فقط کد منبع جمع‌آوری و صحت بایت‌های آن بررسی شده است. سازگارسازی، کامپایل با نسخه ابزار شما و اجرای differential campaign انجام نشده‌اند. فایل `case.json` جزئیات کامل را دارد.
