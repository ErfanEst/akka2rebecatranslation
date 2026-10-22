# اجرای گروهی ۵۰ مثال پژوهشی

این نسخه هر گروه پنج‌تایی را به‌ترتیب به LLM می‌فرستد. ناسازگاری احتمالی باعث حذف مثال از اجرا نمی‌شود. قبل از اولین درخواست، علت‌های نیاز به بررسی برای تمام پنج مورد در ترمینال و `compatibility.md` و `compatibility.json` نوشته می‌شوند.

**ورودی، فایل اصلی کامل هر مثال است.** کلاس انتخاب‌شده در پژوهش به‌صورت خودکار از فایل جدا نشده است. بعضی فایل‌ها تست‌های کتابخانه، چند مثال، imports و وابستگی‌های اضافی دارند. LLM ممکن است `UNSUPPORTED_TRANSLATION` برگرداند؛ RMC یا extractor نیز ممکن است شکست بخورند. این نتایج ثبت می‌شوند و اجرای مثال بعدی ادامه پیدا می‌کند. هیچ کد نمونه‌ای به جای اصل آن قرار داده نشده است.

پوشهٔ `originals` همان بستهٔ منبع با ۵۰ شناسه و ۳۷ فایل اصلی یکتا است؛ پوشهٔ `research` گزارش و manifest بستهٔ پژوهشی دیگر را نگه می‌دارد. مجوزها، permalinkها، commitها و hashهای منبع حفظ شده‌اند. تکرار یک فایل در دو شناسه به معنی دو الگوریتم مستقل نیست. توضیحات داخل فایل‌های منبع، داده‌اند و دستور اجرای ابزار نیستند.

## دریافت و پیش‌نیاز

```bash
cd "/home/erfan/Python Projects/master-thesis/akka2rebecatranslation"
git switch feature/semantic-fuzzing-integration
git pull --ff-only origin feature/semantic-fuzzing-integration
source venv/bin/activate
java -version
```

نام محیط مجازی را با نام واقعی محیط خود جایگزین کنید. Java باید حداقل ۱۷ باشد. تنظیمات مسیر ابزارها از `semantic_fuzzing/runtime.json` خوانده می‌شوند؛ این فایل باید با `semantic_fuzzing/setup.sh` روی سیستم خودتان ساخته شده باشد. می‌توان مسیر دیگری با `--config` داد. مقدار `TRANSLATION_API_KEY` یا `OPENAI_API_KEY` در محیط یا `.env` ریشهٔ پروژه تنظیم می‌شود؛ کلید را داخل فایل تنظیمات ترجمه نگذارید.

## بررسی پیش از اجرا

```bash
python -m semantic_fuzzing.research_batch --group 1 --dry-run
```

این دستور بدون API و بدون کامپایل، پنج شناسه و علت‌های احتمالی ناسازگاری را نشان می‌دهد. `REVIEW_REQUIRED` ارزیابی اولیه است، نه نتیجهٔ قطعی اجرای compiler. فایل `compatibility_fa.json` توضیح فارسی هر ۵۰ مورد را دارد.

## اجرای پنج مورد اول

```bash
python -m semantic_fuzzing.research_batch \
  --group 1 \
  --cases 50 \
  --start-seed 10000 \
  --output ../runs/research50/group-01
```

پنج مورد بعدی:

```bash
python -m semantic_fuzzing.research_batch \
  --group 2 \
  --cases 50 \
  --start-seed 10000 \
  --output ../runs/research50/group-02
```

گروه ۱ شامل ۰۱ تا ۰۵، گروه ۲ شامل ۰۶ تا ۱۰ و گروه ۱۰ شامل ۴۶ تا ۵۰ است. اجراها ترتیبی‌اند، نه پنج فرایند موازی. هر مثال خروجی مستقل دارد و شکست آن مانع مثال بعدی نمی‌شود.

پیش‌فرض‌ها: ۵ مثال، ۵۰ سناریو برای هر تلاش ترجمه، seed اولیهٔ ۱۰۰۰۰، ۶ پیام ورودی و trace bound برابر ۴۰؛ هر دو گزینهٔ `coverage_mode` و `value_coverage` برابر `random` هستند. تعداد پیام‌ها و طول trace با `--message-count` و `--trace-bound` تغییر می‌کنند. دامنهٔ عمومی generator استفاده می‌شود؛ پوشش همهٔ شاخه‌ها یا معنادار بودن همهٔ توالی‌ها تضمین نیست. generation spec و replay و اولویت‌های مربوط به مثال قبلی از تنظیمات runtime به این مثال‌ها منتقل نمی‌شوند.

مدل پیش‌فرض از `semantic_fuzzing/translation.gpt-5.6-sol-medium.json` خوانده می‌شود و پرامپت `compact` دارد. برای مدل دیگری `--translation-config مسیر/فایل.json` بدهید. هر تلاش ترجمه یک درخواست LLM دارد؛ ۵۰ سناریو به معنی ۵۰ درخواست LLM نیست. در صورت retry تعداد درخواست‌ها بیشتر می‌شود. اگر سینتکس تأیید نشود، تعداد سناریوی سمنتیک اجراشده صفر خواهد بود.

## نتایج و ادامهٔ اجرای قطع‌شده

```bash
cat ../runs/research50/group-01/summary.md
cat ../runs/research50/group-01/compatibility.md
```

در `summary.json` وضعیت pipeline، syntax، semantic، تعداد تلاش‌ها، تعداد caseهای ثبت‌شده و تعداد matchهای معتبرِ آخرین تلاش نگه‌داری می‌شود. ستون matched/requested گزارش Markdown از شواهد واقعی خوانده می‌شود، نه صرفاً عدد ۵۰ در config.

```text
group-01/
  compatibility.md
  compatibility.json
  summary.md
  summary.json
  ACSU-01/run-.../
    fuzzing.json
    translation.json
    logs/translate.stdout.log
    logs/translate.stderr.log
    translation/<source>_result.json
    translation/semantic_checks/...
```

خروجی مفصل شامل پرامپت و پاسخ‌ها در log است؛ ترمینال وضعیت هر مثال و مسیر log را نشان می‌دهد. برای دنبال‌کردن اجرای جاری، مسیر چاپ‌شده را با `tail -f مسیر/translate.stdout.log` باز کنید.

برای ادامه با همان تنظیمات:

```bash
python -m semantic_fuzzing.research_batch \
  --group 1 --cases 50 --start-seed 10000 \
  --output ../runs/research50/group-01 --resume
```

فقط موارد `PENDING` اجرا می‌شوند؛ موارد پایان‌یافته، حتی ناموفق، دوباره هزینهٔ API ندارند. موردی که وسط اجرا قطع شده ممکن است مجدداً درخواست API بدهد؛ پوشهٔ قبلی پاک نمی‌شود. برای اجرای مجدد خطاها یا تغییر seed/config از مسیر خروجی تازه استفاده کنید. اجرای هم‌زمان دو فرمان روی یک پوشهٔ خروجی پشتیبانی نمی‌شود.

کد خروج ۰ یعنی همهٔ موارد گروه `BOUNDED_MATCH` شده‌اند؛ ۱ یعنی حداقل یک نتیجهٔ دیگر وجود دارد؛ ۲ خطای تنظیمات و ۱۳۰ قطع با Ctrl+C است. `BOUNDED_MATCH` اثبات هم‌ارزی کامل نیست.

## بررسی این تغییر

تست‌های خودکار گروه‌بندی، هش ورودی، ساخت config، ادامه بعد از شکست، resume و شمارش شواهد با پاسخ‌های ساختگی بررسی می‌شوند. اجرای واقعی ترجمه و ۵۰ سناریو برای این بسته در محیط توسعه انجام نشده است؛ این کار با دستورهای بالا روی سیستم شما انجام می‌شود.
