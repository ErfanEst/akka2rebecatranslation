# ACSU-47 — Untimed Inventory FSM

درخواست کالا، تأمین و اتمام موجودی

## فایل کد

کد واقعی منبع در `source/Inventory.scala` قرار دارد. این فایل عیناً از commit زیر گرفته شده و تغییر نکرده است:

- Repository: `RayRoestenburg/akka-in-action`
- Commit: `32b301d3042c832a016ca3220576960c43317630`
- Git blob: `89325f43e430010f74a9403979eee2ff11ff059e`
- [Source](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-state/src/main/scala/aia/state/Inventory.scala)
- کلاس‌ها یا بخش انتخاب‌شده: `Inventory + Publisher (NOT InventoryWithTimer)`
- خانواده: `inventory`
- مسیر فایل‌های کمکی از ریشه بسته: `upstream/RayRoestenburg__akka-in-action/`
- مجوز از ریشه بسته: `LICENSES/I_RayRoestenburg__akka-in-action_LICENSE.txt`

## پیش از استفاده

این پوشه یک برنامه مستقل آماده اجرای `sbt run` نیست. در فایل‌های چندمثالی، فقط بخش نام‌برده‌شده بالا موضوع انتخاب است. کل فایل ممکن است شامل تست، timer، ask، ساخت اکتور یا مثال‌های دیگری باشد که در محدوده پژوهش نیستند.

برای مثال‌های دارای منبع مشترک، فایل اصلی ممکن است با پوشه دیگری یکسان باشد؛ کلاس یا ترکیب انتخابی متفاوت است. این به معنی ۵۰ برنامه مستقل منتشرشده نیست.

**آماده‌سازی و خطرها:** Select only the first untimed Inventory class and Publisher. Same file also contains InventoryWithTimer; exclude it entirely. FSM state and pending requests need full observation and supported transformation.

**سناریوی کوتاه پیشنهادی:** finite stock; concurrent BookRequest; Publisher replies

**هدف مقایسه:** pending queue, replenishment and sold-out branch

وضعیت: فقط کد منبع جمع‌آوری و صحت بایت‌های آن بررسی شده است. سازگارسازی، کامپایل با نسخه ابزار شما و اجرای differential campaign انجام نشده‌اند. فایل `case.json` جزئیات کامل را دارد.
