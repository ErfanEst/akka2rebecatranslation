# ACSU-36 — Capture-Based Leader Election

انتخاب رهبر با پیام‌های رقابتی

## فایل کد

کد واقعی منبع در `source/LeaderElection.scala` قرار دارد. این فایل عیناً از commit زیر گرفته شده و تغییر نکرده است:

- Repository: `samira-t/Bita`
- Commit: `a3241fdea138799c0d6956571bcb7f4f8c8e0ddd`
- Git blob: `4c5dc21b0d7c8e43e49963887ea2c1931a715699`
- [Source](https://github.com/samira-t/Bita/blob/a3241fdea138799c0d6956571bcb7f4f8c8e0ddd/src/test/scala/sample/LeaderElection.scala)
- کلاس‌ها یا بخش انتخاب‌شده: `NodeActor (Simulator excluded)`
- خانواده: `leader_election`
- مسیر فایل‌های کمکی از ریشه بسته: `upstream/samira-t__Bita/`
- مجوز از ریشه بسته: `LICENSES/B_samira-t__Bita_LICENSE.txt`

## پیش از استفاده

این پوشه یک برنامه مستقل آماده اجرای `sbt run` نیست. در فایل‌های چندمثالی، فقط بخش نام‌برده‌شده بالا موضوع انتخاب است. کل فایل ممکن است شامل تست، timer، ask، ساخت اکتور یا مثال‌های دیگری باشد که در محدوده پژوهش نیستند.

برای مثال‌های دارای منبع مشترک، فایل اصلی ممکن است با پوشه دیگری یکسان باشد؛ کلاس یا ترکیب انتخابی متفاوت است. این به معنی ۵۰ برنامه مستقل منتشرشده نیست.

**آماده‌سازی و خطرها:** The source explicitly says BUGGY. Use as a known-bug/translation subject, never an automatically correct reference. Exclude Simulator's failure/reinitialization scenario and unused timeout imports; preserve source bug for translation comparison.

**سناریوی کوتاه پیشنهادی:** 3 fixed nodes; explicit Init and Start; no physical failures

**هدف مقایسه:** capture/accept/elect state transitions

وضعیت: فقط کد منبع جمع‌آوری و صحت بایت‌های آن بررسی شده است. سازگارسازی، کامپایل با نسخه ابزار شما و اجرای differential campaign انجام نشده‌اند. فایل `case.json` جزئیات کامل را دارد.
