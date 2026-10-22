# ACSU-35 — Distributed Single-Source Shortest Path

بهبود فاصله با پیام همسایه‌ها

## فایل کد

کد واقعی منبع در `source/SPActor.scala` قرار دارد. این فایل عیناً از commit زیر گرفته شده و تغییر نکرده است:

- Repository: `samira-t/Bita`
- Commit: `a3241fdea138799c0d6956571bcb7f4f8c8e0ddd`
- Git blob: `8d97e852bb8bcca422617a1d19ae88505cae3bfc`
- [Source](https://github.com/samira-t/Bita/blob/a3241fdea138799c0d6956571bcb7f4f8c8e0ddd/src/test/scala/sample/SPActor.scala)
- کلاس‌ها یا بخش انتخاب‌شده: `SPActor`
- خانواده: `graph_shortest_path`
- مسیر فایل‌های کمکی از ریشه بسته: `upstream/samira-t__Bita/`
- مجوز از ریشه بسته: `LICENSES/B_samira-t__Bita_LICENSE.txt`

## پیش از استفاده

این پوشه یک برنامه مستقل آماده اجرای `sbt run` نیست. در فایل‌های چندمثالی، فقط بخش نام‌برده‌شده بالا موضوع انتخاب است. کل فایل ممکن است شامل تست، timer، ask، ساخت اکتور یا مثال‌های دیگری باشد که در محدوده پژوهش نیستند.

برای مثال‌های دارای منبع مشترک، فایل اصلی ممکن است با پوشه دیگری یکسان باشد؛ کلاس یا ترکیب انتخابی متفاوت است. این به معنی ۵۰ برنامه مستقل منتشرشده نیست.

**آماده‌سازی و خطرها:** Create vertices at bootstrap; AddNeighbor only during setup and then freeze graph. ActorRef keys/parent need fixed IDs and full map projection. Node allocation is not dynamic actor creation here.

**سناریوی کوتاه پیشنهادی:** 4 vertices; nonnegative edge weights 0..3

**هدف مقایسه:** relaxation, alternate paths, parent identity

وضعیت: فقط کد منبع جمع‌آوری و صحت بایت‌های آن بررسی شده است. سازگارسازی، کامپایل با نسخه ابزار شما و اجرای differential campaign انجام نشده‌اند. فایل `case.json` جزئیات کامل را دارد.
