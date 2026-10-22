# مثال‌های مستقل آمادهٔ آزمایش

بررسی همهٔ ۵۰ فایل اصلی در `AUDIT_FA.md` و `audit_originals.json` ثبت شده است. هیچ فایل اصلی در شکل ارسال‌شده از دروازه‌های اولیهٔ اجرای فعلی عبور نکرد: ۳۶ مورد مانع استخراج، ۳ مورد نبود پیام نام‌دار و ۱۱ مورد خطای کامپایل داشتند. این نتیجه مربوط به pipeline تک‌فایلی ماست، نه اجرای پروژهٔ اصلی با build و تمام وابستگی‌های upstream.

این پوشه پنج **نسخهٔ مشتق‌شده و مستقل** دارد. آنها را با ۵ ورودی اصلیِ بدون تغییر اشتباه نگیرید. کدهای اصلی، مجوزها و اطلاعات منبع در `../research50/originals/` باقی مانده‌اند. برای هر نمونه یک Client ثابت اضافه شده که درخواست را می‌فرستد و در نمونه‌های پاسخ‌دار، آخرین پاسخ را در `lastValue` ثبت می‌کند. actorها فقط در bootstrap ساخته می‌شوند. هیچ fixture آماده‌ای جای پاسخ واقعی LLM در حالت ترجمه قرار نمی‌گیرد.

| شناسهٔ اصلی | فایل ورودی جدید | تغییرات نسبت به هستهٔ اصلی |
|---|---|---|
| ACSU-01 | `akka/Echo.scala` | Echo از فایل تست Router جدا شده؛ ورودی Any به Int محدود و پیام‌ها EchoValue/Reply نام‌گذاری شده‌اند. |
| ACSU-03 | `akka/Adder.scala` | DemoActor تودرتو به AdderActor مستقل تبدیل شده؛ مقدار constructor برابر ۴ و ورودی/پاسخ عددی نام‌دار است. |
| ACSU-04 | `akka/Calculator.scala` | Sum و Multiply حفظ شده؛ پاسخ Int در Reply قرار گرفته و Client ثابت اضافه شده است. |
| ACSU-05 | `akka/Accumulator.scala` | فقط هستهٔ SummingActor انتخاب شده؛ Int در Add قرار گرفته؛ برنامهٔ sleep، نسخهٔ دیگر actor و logging/catch-all خارج از دامنهٔ ورودی حذف شده‌اند. |
| ACSU-42 | `akka/Fibonacci.scala` | تابع بازگشتی fib حفظ شده؛ App دارای ask/Await/Timeout با Client ثابت و پیام‌های نام‌دار جایگزین شده است. |

این آماده‌سازی ادعای هم‌ارزی کل فایل اصلی با نسخهٔ جدید نیست. خروجی کنسول و رفتار خارج از پروتکل تعریف‌شده در آزمایش این نسخه‌ها مقایسه نمی‌شوند. برای Echo فقط زیرمجموعهٔ پیام‌های عددی بررسی می‌شود؛ برای Fibonacci مقادیر آزمون ۰ تا ۸ هستند و رفتار تابع برای سایر مقادیر بازنویسی نشده است.

## دریافت و اجرا

در محیط مجازی فعال و ریشهٔ پروژه:

```bash
git pull --ff-only origin feature/semantic-fuzzing-integration
python -m semantic_fuzzing.validated_batch \
  --group 1 \
  --cases 50 \
  --start-seed 10000 \
  --output ../runs/validated/group-01
```

این دستور پنج فایل جدید را به‌ترتیب ترجمه می‌کند، سپس برای هر کاندیدِ پذیرفته‌شده از نظر سینتکس، کمپین ۵۰ سناریویی را اجرا می‌کند. مدل پیش‌فرض `gpt-5.6-sol` با reasoning متوسط و prompt نوع compact است. کلید همان `TRANSLATION_API_KEY` یا `OPENAI_API_KEY` در محیط یا `.env` پروژه است.

مسیر ابزارها از `semantic_fuzzing/runtime.json` خوانده می‌شود؛ فایل باید مربوط به سیستم خودتان باشد. با `--config` فایل دیگری برای ابزارها و با `--translation-config` تنظیمات مدل دیگری انتخاب کنید.

```bash
cat ../runs/validated/group-01/summary.md
```

برای هر شناسه پوشهٔ جدا، فایل تنظیمات مؤثر، log و گزارش ترجمه ذخیره می‌شود. خطای یک نمونه مانع ادامهٔ بقیه نیست. خروجی باید پوشهٔ جدید باشد؛ برای اجرای دوباره از `../runs/validated/group-01-run2` استفاده کنید. این runner گزینهٔ resume ندارد. گروه فعلی یک گروه پنج‌تایی است؛ شماره‌های اصلی در گزارش حفظ می‌شوند.

## سناریوها

هر دو حالت coverage و value برابر random هستند. هر سناریو ۴ پیام ورودی دارد؛ نخستین پیام همیشه یک Request با مقدار تصادفی برای فعال‌کردن هسته است و سه پیام باقی‌مانده توسط generator از پیام‌های interface انتخاب می‌شوند. بنابراین تصادفی‌سازی دارای یک پیشوند هدایت‌شده است، نه انتخاب کاملاً آزاد همهٔ پیام‌ها. اثر sender از ارسال‌های واقعی Client استخراج می‌شود.

دامنهٔ پارامترهای حسابی ۱۰۰- تا ۱۰۰ است؛ برای Fibonacci ورودی‌ها ۰ تا ۸ هستند. فایل‌های `specs/` تمام دامنه‌ها و پیشوند را مشخص می‌کنند. seed اولیهٔ پیش‌فرض ۱۰۰۰۰، trace bound برابر ۲۴ و ظرفیت mailbox در fixtureها برابر ۱۲ است. نسخهٔ تولیدشده توسط LLM ظرفیت خود را طبق قرارداد انتخاب می‌کند. ۵۰ سناریو یعنی ۵۰ درخواست LLM نیست؛ retry ترجمه می‌تواند درخواست اضافه ایجاد کند.

## اعتبارسنجی بدون API

فایل‌های `fixtures/` مدل‌های Rebeca نوشته‌شده برای بررسی ابزارها هستند و خروجی LLM محسوب نمی‌شوند. برای تکرار بررسی آنها:

```bash
python -m semantic_fuzzing.validated_batch \
  --check-fixtures \
  --cases 2 \
  --start-seed 10000 \
  --output ../runs/validated/fixture-smoke
```

در این حالت هیچ LLM فراخوانی نمی‌شود، ولی Akka، RMC و موتور semantic differential fuzzing واقعی اجرا می‌شوند. نتیجهٔ اجرای توسعه در `verification.json` ثبت می‌شود. این بررسی صحت ابزارها و قابلیت اجرای نسخه‌های جدید را می‌سنجد؛ موفقیت ترجمهٔ آیندهٔ مدل یا پوشش همهٔ ورودی‌ها را تضمین نمی‌کند.

## بازتولید بررسی ۵۰ منبع اصلی

```bash
python -m semantic_fuzzing.research_audit \
  --config semantic_fuzzing/runtime.json \
  --output ../runs/research50/audit-all
```

این دستور بدون API، هر فایل یکتا را با extractor واقعی بررسی می‌کند و موارد دارای actor، instance و پیام نام‌دار را با وابستگی‌های واقعی akka-runner کامپایل می‌کند. sourceهای اصلی دستکاری نمی‌شوند. گزارش و logها در پوشهٔ خروجی باقی می‌مانند. compilation_excerpts.txt نمونهٔ خطاهای اجرای ثبت‌شده را دارد.

## منابع و مجوزها

برای URL دقیق، commit و hash هر منبع، فایل `case.json` این پوشه‌ها را ببینید:

- `../research50/originals/benchmarks/01_echo/`
- `../research50/originals/benchmarks/03_adder/`
- `../research50/originals/benchmarks/04_calculator/`
- `../research50/originals/benchmarks/05_accumulator/`
- `../research50/originals/benchmarks/42_local_fibonacci/`

Echo و Adder از akka/akka-core با مجوز Apache 2.0 هستند. Calculator، Accumulator و Fibonacci از PacktPublishing/Akka-Cookbook با مجوز MIT هستند. متن مجوزها در `../research50/originals/LICENSES/` حفظ شده است.
