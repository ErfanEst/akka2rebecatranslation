# راهنمای دریافت، نصب و اجرای پایپ‌لاین Akka به Rebeca

## این نسخه چه کاری می‌کند؟

یک فایل Scala/Akka از کاربر می‌گیرد، آن را با مدل زبانی و پرامپت کامل Handbook به Rebeca تبدیل می‌کند، سینتکس و نوع‌ها را با RMC بررسی می‌کند و فقط پس از پذیرش مدل، پروژهٔ `semantic-differential-fuzzing` را اجرا می‌کند. در پایان، کد، گزارش، سناریوها، خطاها و نتیجهٔ مقایسه ذخیره می‌شوند.

در صورت خطای سینتکس یا عدم تطابق سمنتیک، اطلاعات خطا به مدل زبانی برمی‌گردد و تلاش بعدی انجام می‌شود. موفقیت تنها زمانی ثبت می‌شود که تمام سناریوهای درخواست‌شده، trace معتبر و غیرخالیِ مطابق داشته باشند.

کدهای قدیمی تغییر نکرده‌اند. ورودی جدید `python -m semantic_fuzzing` است؛ اجرای اسکریپت‌های آزمایش قدیمی همچنان مسیر قدیمی را اجرا می‌کند. برنچ کار `feature/semantic-fuzzing-integration` روی GitHub منتشر شده است.

## ۱. دریافت پروژه

### همین محیط ابری

دو پروژه در این مسیرها موجودند:

```text
/workspace/akka2rebecatranslation
/workspace/semantic-differential-fuzzing
```

برای استفاده از وابستگی‌های از قبل نصب‌شده:

```bash
source /workspace/cloud-setup/activate.sh
cd /workspace/akka2rebecatranslation
```

در دستورهای این راهنما، در همین محیط می‌توانید به جای `runtime.session.json` از `cloud.example.json` استفاده کنید.

### دریافت بستهٔ آماده روی دستگاه دیگر

بستهٔ `semantic-fuzzing-project.tar.gz` در `/workspace/deliverables` شامل فایل‌های نسخهٔ فعلی هر دو پروژه است. این بسته به انتشار برنچ در GitHub وابسته نیست. فایل کلید، محیط مجازی، کش، JAR و تاریخچهٔ Git داخل آن نیست. از یک پوشهٔ خالی استفاده کنید:

```bash
tar -xzf semantic-fuzzing-project.tar.gz
cd semantic-fuzzing-project/akka2rebecatranslation
```

فایل `SOURCE_VERSION.json` در ریشهٔ بسته، نسخهٔ پایهٔ هر مخزن و SHA-256 فایل‌های سورس را ثبت می‌کند. بسته یک snapshot از فایل‌هاست، نه clone دارای تاریخچهٔ Git.

### دریافت مستقیم از GitHub

```bash
git clone --branch feature/semantic-fuzzing-integration https://github.com/ErfanEst/akka2rebecatranslation.git
git clone https://github.com/ErfanEst/semantic-differential-fuzzing.git
git -C semantic-differential-fuzzing checkout 3086cba00497848d2a999ed6f219a6e6fca2fa13
cd akka2rebecatranslation
```

کلون کردن صرفِ `main` مترجم این نسخه را دریافت نمی‌کند؛ برنچ بالا را مشخص کنید.

## ۲. پیش‌نیازها و نصب

محیط بررسی‌شده Linux با Python 3.12، Java 21 و g++ است. برای Windows از WSL2/Ubuntu استفاده کنید. برای اجرای اولیه اینترنت، چند گیگابایت فضای آزاد و حداقل حدود ۴ گیگابایت RAM در نظر بگیرید؛ کامپایل Scala در اولین اجرا زمان بیشتری می‌برد.

روی Ubuntu، در صورت نبود پیش‌نیازها:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv openjdk-21-jdk g++ make curl git
bash semantic_fuzzing/setup.sh
source ../.semantic-fuzzing-tools/activate.sh
```

اسکریپت نصب، محیط مجازی و بسته‌های Python، sbt نسخهٔ `1.12.13` و RMC نسخهٔ `2.14` را آماده می‌کند. دانلود JARها با SHA-256 مشخص بررسی می‌شود؛ این hashها از دریافت HTTPS بررسی‌شدهٔ قبلی ثبت شده‌اند، نه امضای منتشرشدهٔ سازنده. اجرای دوباره، فایل تنظیمات موجود را بازنویسی نمی‌کند. کامپایل Scala در اولین اجرای `check` یا `translate` انجام می‌شود.

مسیرهای متفاوت نیز قابل تنظیم‌اند:

```bash
bash semantic_fuzzing/setup.sh /absolute/path/to/semantic-differential-fuzzing /absolute/path/to/tools
source /absolute/path/to/tools/activate.sh
```

بعد از جابه‌جایی پوشه‌ها، مسیرهای `runtime*.json` را اصلاح کنید. نصب مجدد عمداً تنظیمات موجود کاربر را حفظ می‌کند.

از `pip install -r requirements.txt` ریشهٔ پروژه استفاده نکنید؛ فایل قدیمی قالب معتبر requirements ندارد. فایل صحیحِ مسیر جدید `semantic_fuzzing/requirements.txt` است. نسخه‌های مستقیم بسته‌ها ثابت‌اند؛ وابستگی‌های غیرمستقیم توسط pip حل می‌شوند.

JAR رسمی `compiler-2.25.jar` دارای مشکل entry point است و جایگزین قابل‌اعتماد فایل سفارشی قدیمی نیست. مسیر جدید به آن نیاز ندارد: frontend داخل RMC هم سینتکس و نوع‌ها را بررسی می‌کند و هم کد C++ لازم را می‌سازد.

## ۳. API key را کجا بگذارم؟

فقط مرحلهٔ `translate` به کلید OpenAI نیاز دارد. `check`، `batch` و آزمون‌های محلی بدون کلید کار می‌کنند.

در محیط ابری، بخش Secrets تنظیمات محیط را باز کنید و مقدار `TRANSLATION_API_KEY` را وارد و اعمال کنید. دامنهٔ موردنیاز `api.openai.com` است. نام این secret از قبل در تنظیمات پیشنهادی ثبت شده، ولی ثبت نام به معنی وجود مقدار نیست. کلید را در چت نفرستید.

روی دستگاه خودتان، فایل `.env` را در **ریشهٔ پروژهٔ مترجم** ایجاد کنید؛ نه در پوشهٔ `semantic_fuzzing`:

```bash
cp semantic_fuzzing/.env.example .env
chmod 600 .env
```

آن را با ویرایشگر باز کنید و مقدار واقعی را فقط همان‌جا وارد کنید:

```dotenv
TRANSLATION_API_KEY=YOUR_REAL_KEY_HERE
```

`YOUR_REAL_KEY_HERE` نمونه است و کار نمی‌کند. فایل `.env` در Git نادیده گرفته می‌شود؛ کلید را در JSON تنظیمات، گزارش، commit یا اسکرین‌شات نگذارید. CLI فایل `.env` را بارگذاری و این متغیر را برای کتابخانهٔ OpenAI تنظیم می‌کند. `OPENAI_API_KEY` نیز پشتیبانی می‌شود و اگر هر دو موجود باشند اولویت دارد.

اعتبار مالی حساب و دسترسی به مدل نیز لازم است. ترجمه هزینه دارد؛ پرامپت شامل متن کامل ۶۰ صفحهٔ دو سند است و در هر تلاش دوباره ارسال می‌شود. کد Akka و اطلاعات اصلاح خطا به سرویس مدل فرستاده می‌شوند؛ برای کد محرمانه باید مجوز ارسال داشته باشید. لاگ پرامپت نیز متن کامل کد را نگه می‌دارد.

## ۴. اول اجرای بدون هزینه را بررسی کنید

از ریشهٔ مترجم، پس از فعال‌سازی محیط:

```bash
python -m semantic_fuzzing --config semantic_fuzzing/runtime.session.json check \
  --akka-source ../semantic-differential-fuzzing/examples/akka/SessionWorkflow.scala \
  --candidate ../semantic-differential-fuzzing/examples/session_workflow.rebeca \
  --mutant ../semantic-differential-fuzzing/examples/session_workflow_mutant_wrong_submit_id.rebeca \
  --output ../runs/session-check-01
```

در این دستور، Rebeca از قبل موجود است؛ ترجمهٔ زنده انجام نمی‌شود. نتیجهٔ مورد انتظار برای candidate، `BOUNDED_MATCH` و برای mutant، کشف `STATE_MISMATCH` است. نام پوشهٔ خروجی هر اجرا باید جدید باشد.

## ۵. اجرای کامل از فایل Akka تا نتیجه

ابتدا برای نمونهٔ موجود، با کلید معتبر:

```bash
python -m semantic_fuzzing --config semantic_fuzzing/runtime.session.json translate \
  --akka-source ../semantic-differential-fuzzing/examples/akka/SessionWorkflow.scala \
  --translation-config semantic_fuzzing/translation.handbook.example.json \
  --output ../runs/session-live-01
```

این دستور به ترتیب ترجمه، بررسی سینتکس، فازتستینگ، اصلاح احتمالی و ثبت نتیجه را اجرا می‌کند. موفقیتِ مدل زبانی تضمین‌شده نیست؛ نتیجه را از JSON نهایی بخوانید، نه صرفاً پیام «COMPILATION SUCCESS» در چاپ‌های حلقهٔ قدیمی.

برای کد خودتان:

```bash
python -m semantic_fuzzing --config semantic_fuzzing/runtime.json translate \
  --akka-source /absolute/path/MyActors.scala \
  --translation-config semantic_fuzzing/translation.handbook.example.json \
  --output ../runs/my-actors-01
```

فایل `runtime.json` تنظیمات اختصاصی SessionWorkflow ندارد. پیش از یک آزمایش پژوهشی، دامنهٔ پارامترها و توالی‌های معنادار برنامهٔ خود را در `generation_spec` تعریف کنید؛ مثال ساختار آن در مخزن fuzzing با نام `semantic_generation_session_workflow.example.json` موجود است. صرف تغییر مسیر ورودی، سناریوی SessionWorkflow را برای برنامهٔ دیگر معتبر نمی‌کند.

ورودی `translate` در این نسخه یک فایل است. `check` با تکرار `--akka-source` چند فایل را می‌پذیرد. دامنهٔ پشتیبانی موتور، Akka Classic با Scala 2.13، actorهای ایستا و state/پارامترهای scalar پشتیبانی‌شده است؛ پشتیبانی از هر برنامهٔ دلخواه Akka، Akka Typed یا ایجاد پویای actor ادعا نمی‌شود.

## ۶. تنظیمات مهم

فایل `translation.handbook.example.json` شامل مدل پیش‌فرض `gpt-4o`، دمای `0.1` و حداکثر `3` تلاش است. `max_retries` در این حلقه تعداد کل تلاش‌هاست، نه تعداد تلاش‌های اضافه. برای مدل دیگر باید ظرفیت context کافی و سازگاری با پارامترهای ChatOpenAI موجود را بررسی کنید. متن handbook کوتاه یا حذف نمی‌شود.

در فایل تنظیمات fuzzing:

| گزینه | کاربرد |
| --- | --- |
| `case_count` | تعداد سناریوهای تولیدی |
| `message_count` | تعداد پیام‌های ورودی هر سناریو |
| `start_seed` | seed اولیه برای ثبت و بازتولید سناریوها |
| `trace_bound` | سقف طول trace مقایسه‌شده |
| `run_millis` | زمان اجرای Akka در هر سناریو |
| `generation_spec` | دامنهٔ پارامترها و الگوهای توالی برنامه |
| `coverage_mode` | `message`، `sender-message` یا `random` |
| `value_coverage` | `boundary` یا `random` |
| `stage_timeout_seconds` | مهلت کامپایل/استخراج؛ پیش‌فرض ۶۰۰ ثانیه |
| `model_timeout_seconds` | مهلت هر مدل؛ پیش‌فرض ۱۲۰ ثانیه |
| `campaign_timeout_seconds` | مهلت کل کمپین؛ پیش‌فرض ۳۶۰۰ ثانیه |

دو سناریوی تنظیمات نمونه فقط smoke test هستند. برای آزمایش وسیع‌تر، تعداد سناریو، seedها، زمان و دامنه‌ها را متناسب با برنامه افزایش دهید و پوشش واقعی را بررسی کنید. افزایش این اعداد به تنهایی اثبات هم‌ارزی نیست.

## ۷. خروجی‌ها کجا هستند؟

در پوشهٔ مشخص‌شده با `--output` برای ترجمه:

```text
report.md                         گزارش کوتاه نهایی
MyActors_result.json              همهٔ تلاش‌ها و وضعیت نهایی
MyActors_final.rebeca             فقط در صورت موفقیت نهایی
prompt_logs/                     پرامپت کامل و پاسخ هر تلاش
semantic_checks/<attempt>/
  candidate.rebeca                پاسخ همان تلاش
  fuzzing/result.json             سینتکس، سمنتیک، hash و تنظیمات
  fuzzing/report.md               گزارش کوتاه بررسی
  fuzzing/logs/                   فرمان‌ها و خطاهای ابزارها
  fuzzing/sources/                نسخهٔ ورودی Akka
  fuzzing/campaign/               سناریوها، traceها، پوشش و counterexampleها
```

برای `check`، فایل `result.json` مستقیماً در پوشهٔ خروجی است. اگر `--output` را در `translate` ندهید، پوشه‌ای یکتا زیر `experiments/results/semantic_fuzzing/<experiment_name>/run-*` ساخته می‌شود. پوشهٔ موجود بازنویسی نمی‌شود. خطاهای پیش‌نیاز، مانند کلید غایب، قبل از ایجاد اجرای ترجمه در stderr گزارش می‌شوند.

| نتیجه | کد خروج | معنی |
| --- | --- | --- |
| `BOUNDED_MATCH` | ۰ | تمام traceهای درخواست‌شده معتبر، غیرخالی و در حدود آزمون مطابق‌اند |
| `MISMATCH` | ۱ | اختلاف معتبر یا overflow مشاهده شده است |
| `INCONCLUSIVE` | ۲ | اطلاعات کافی یا قابل‌اعتماد نیست |
| `ERROR` | ۳ | خطای ابزار، timeout، تنظیمات یا اجرای زیرساخت |
| `SYNTAX_ERROR` | ۴ | RMC مدل را نپذیرفته؛ سمنتیک اجرا نشده است |

`semantic_status=NOT_RUN` یعنی سمنتیک هنوز اجرا نشده، نه اینکه موفق بوده است. `semantic_equivalence=NOT_ESTABLISHED` حتی در اجرای موفق باقی می‌ماند؛ این سیستم تست محدود انجام می‌دهد و اثبات ریاضی هم‌ارزی همهٔ اجراها نیست. رد frontend بدون artifact با `SYNTAX_ERROR` ثبت می‌شود؛ برای علت دقیق باید لاگ RMC را دید. خطای خود پردازش Java جداگانه `ERROR` است.

## ۸. آزمون‌ها و عیب‌یابی

```bash
python -m unittest -v semantic_fuzzing.test_pipeline semantic_fuzzing.test_handbook_prompt semantic_fuzzing.test_workflow
python -m semantic_fuzzing.integration_test \
  --config semantic_fuzzing/runtime.session.json \
  --output ../runs/scripted-retry-01
```

دستور دوم آزمون یکپارچهٔ واقعی ابزارهاست، اما پاسخ‌های LLM عمداً از سه fixture مشخص می‌آیند: کد با سینتکس خراب، مدل دارای خطای سمنتیک، مدل سالم. این حالت جایگزین پنهانی برای `translate` نیست و در نتیجه با `SCRIPTED_TEST_RESPONSES` و `live_api_executed=false` مشخص می‌شود.

خطای کلید: مقدار secret یا `.env` و اعمال آن به محیط فعلی را بررسی کنید. خطای 401 با کد `token_invalidated`: سرویس اعتبارنامه را باطل‌شده اعلام کرده است؛ کلید جدید را در همان Secret جایگزین و تنظیمات را ذخیره و Publish کنید، سپس با پوشهٔ خروجی تازه اجرا کنید. صرف وجود متغیر محیطی به معنی معتبر بودن کلید نیست. خطای 429: اعتبار مالی و محدودیت نرخ را بررسی کنید. خطای context: مدل با ظرفیت کافی انتخاب کنید. خطای دانلود: دسترسی به GitHub Releases، Maven Central و PyPI لازم است؛ بررسی TLS یا hash را غیرفعال نکنید. خطای Scala/actor extraction: سازگاری ورودی با محدودیت‌های موتور را بررسی کنید. خطای سمنتیک: به counterexample و state/mailbox اختلاف‌دار مراجعه کنید، نه به موفقیت صرفِ کامپایل.

برای اطمینان از سالم ماندن موتور اصلی نیز می‌توانید در مخزن fuzzing اجرا کنید:

```bash
python -m unittest -v tests/test_semantic_differential_orchestrators.py
```
