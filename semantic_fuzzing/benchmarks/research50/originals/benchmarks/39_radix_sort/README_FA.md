# ACSU-39 — Radix Sort Pipeline

مرتب‌سازی مرحله‌ای براساس بیت‌ها

## فایل کد

کد واقعی منبع در `source/RadixSortAkkaActorBenchmark.scala` قرار دارد. این فایل عیناً از commit زیر گرفته شده و تغییر نکرده است:

- Repository: `shamsimam/savina`
- Commit: `52e546959a57670cdba7a88f0a030b53cfdb16d6`
- Git blob: `c0083cb0a2559331552f087739b7c179ca72ef33`
- [Source](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/radixsort/RadixSortAkkaActorBenchmark.scala)
- کلاس‌ها یا بخش انتخاب‌شده: `IntSourceActor, SortActor, ValidationActor`
- خانواده: `sorting_pipeline`
- مسیر فایل‌های کمکی از ریشه بسته: `upstream/shamsimam__savina/`
- مجوز از ریشه بسته: `LICENSES/S_shamsimam__savina_LICENSE.txt`

## پیش از استفاده

این پوشه یک برنامه مستقل آماده اجرای `sbt run` نیست. در فایل‌های چندمثالی، فقط بخش نام‌برده‌شده بالا موضوع انتخاب است. کل فایل ممکن است شامل تست، timer، ask، ساخت اکتور یا مثال‌های دیگری باشد که در محدوده پژوهش نیستند.

برای مثال‌های دارای منبع مشترک، فایل اصلی ممکن است با پوشه دیگری یکسان باشد؛ کلاس یا ترکیب انتخابی متفاوت است. این به معنی ۵۰ برنامه مستقل منتشرشده نیست.

**آماده‌سازی و خطرها:** Unroll setup-created pipeline; feed explicit value inputs instead of language-specific PRNG. Preserve Long/Int widths and emitted value order; compare output values, not just success prints.

**سناریوی کوتاه پیشنهادی:** 3 values in 0..7; 3 fixed bit stages

**هدف مقایسه:** bit partitioning and FIFO batches

وضعیت: فقط کد منبع جمع‌آوری و صحت بایت‌های آن بررسی شده است. سازگارسازی، کامپایل با نسخه ابزار شما و اجرای differential campaign انجام نشده‌اند. فایل `case.json` جزئیات کامل را دارد.
