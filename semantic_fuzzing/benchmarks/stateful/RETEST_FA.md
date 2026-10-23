# بررسی مجدد ترجمه‌های ثابت با ورودی‌های متنوع

این مسیر هیچ LLM یا کلید API لازم ندارد. final_code موفق را از آرشیو قبلی می‌خواند و همان کد را بدون اصلاح بررسی می‌کند. تلاش اصلاحی یا ترجمهٔ مجدد انجام نمی‌شود. فایل‌های اجرای قبلی دست‌نخورده می‌مانند.

## دریافت

هر دو مخزن باید روی برنچ feature/semantic-fuzzing-integration به‌روز باشند؛ موتور نیز انتخاب سناریو بر اساس seed را اضافه کرده است. از پوشهٔ master-thesis:

```bash
git -C semantic-differential-fuzzing pull --ff-only origin feature/semantic-fuzzing-integration
git -C akka2rebecatranslation pull --ff-only origin feature/semantic-fuzzing-integration
cd akka2rebecatranslation
source "../.semantic-fuzzing-tools/venv/bin/activate"
export JAVA_HOME="/usr/lib/jvm/java-17-openjdk-amd64"
export PATH="$JAVA_HOME/bin:$PATH"
hash -r
java -version
```

مسیر Java بالا برای نصب قبلی شماست؛ در نصب متفاوت مسیر درست JDK 17 یا بالاتر را قرار بده. runtime.json همان تنظیمات ابزار اجرای موفق قبلی است.

## اجرای ۵۰ ورودی برای هر چهار ترجمه

```bash
python -m semantic_fuzzing.retest_stateful \
  --translations-root ../runs/stateful-live-02-01 \
  --config semantic_fuzzing/runtime.json \
  --cases 50 --start-seed 20000 --messages 16 \
  --output ../runs/stateful-retest50-01
```

این دستور ۵۰ ورودی برنامه‌ریزی‌شده برای هر مثال، در مجموع ۲۰۰ case، را به‌صورت ترتیبی اجرا می‌کند. بسته به زمان کامپایل، RMC و ظرفیت ماشین زمان‌بر است. سناریوهای دقیق و تعداد ورودی‌های متمایز ثبت می‌شوند؛ تعداد seed به‌تنهایی معادل تعداد رفتارهای متمایز نیست.

برای شروع سبک، --cases را 3 بگذار و نام خروجی دیگری انتخاب کن. برای یک مثال از `--case FSM-01` استفاده کن؛ این گزینه قابل تکرار است. پوشهٔ خروجی باید جدید باشد. آرشیو باید شامل پوشه‌های شناسه/translation، نتیجهٔ ترجمه و semantic_checks باشد؛ فایل final.rebeca به‌تنهایی برای کنترل منشأ کافی نیست.

برای دیدن برنامهٔ کامل بدون اجرای ابزارها و بدون API:

```bash
python -m semantic_fuzzing.retest_stateful \
  --translations-root ../runs/stateful-live-02-01 \
  --config semantic_fuzzing/runtime.json \
  --cases 50 --start-seed 20000 --messages 16 \
  --plan-only --output ../runs/stateful-plan50-01
```

## سناریوها چه فرقی کرده‌اند؟

- هر نمونه ابتدا یک پیشوند مشخص برای فعال‌کردن مسیرهای مهم دارد، سپس پیام‌های بعدی با RNG مبتنی بر شناسهٔ مثال و seed انتخاب می‌شوند.
- Swapper: Swap و Noop، با تعداد و محل متفاوت Swapها. این مدل فقط دو رفتار دارد؛ تنوع ورودی به معنی ۵۰ وضعیت متفاوت نیست.
- HotSwap: Foo/Bar و رفت‌وبرگشت بین حالت‌ها، از client معتبر برای حفظ دامنهٔ پروتکل پاسخ.
- SwitchRouter: روشن/خاموش کردن مسیر و Data با مقادیر صحیح بین منفی ۷ و مثبت ۷.
- FSM: Open/Add/Close/Reset، مقدار منفی/صفر/مثبت، ورود دوباره به همان وضعیت، callbackها و مسیرهای fallback.

هر ورودی به طور پیش‌فرض ۱۶ پیام اولیه دارد. پیام‌های ناشی از اجرای actorها جداگانه اجرا می‌شوند؛ trace_bound حداقل دو برابر پیام‌های اولیه به‌اضافهٔ ۸ است. sender پیام‌های اولیه client است؛ تمام ترکیب‌های sender، تمام interleavingها یا همهٔ مقادیر Int بررسی نمی‌شوند. الگوریتم planner نسخهٔ stateful-random-v1 دارد و برای ورودی یکسان برنامهٔ یکسان تولید می‌کند؛ زمان‌بندی واقعی actorها ممکن است متفاوت باشد.

## خروجی‌ها و تفسیر

```bash
cat ../runs/stateful-retest50-01/summary.md
```

برای هر شناسه:

- candidate.rebeca: نسخهٔ ثابت همان ترجمهٔ قبلی.
- generation_spec.json: پیام‌های دقیق برای تک‌تک seedها.
- validation/campaign/cases/seed_*/scenario.json: سناریوی واقعاً تولیدشده.
- validation/campaign/cases/seed_*/akka_trace_execution.json: trace واقعی Akka.
- validation/result.json: نتیجه و مسیر جزئیات مقایسه و counterexample.

summary.json هش آرشیو، Scala، candidate، برنامهٔ هر seed و سناریوی تولیدشده را ثبت می‌کند. پیش از اجرا هش source/candidate با گزارش موفق قبلی تطبیق داده می‌شود؛ اگر کد تغییر کرده یا آرشیو ناقص باشد اجرا متوقف می‌شود. پس از اجرا نیز برنامهٔ مورد انتظار با scenario.json واقعی تطبیق داده می‌شود. گزارش ناقص یا تولید سناریویی غیر از برنامه نمی‌تواند موفق اعلام شود.

BOUNDED_MATCH یعنی توافق در همین آزمون‌ها، نه اثبات هم‌ارزی. MISMATCH می‌تواند خطای ترجمه‌ای را آشکار کند که قالب‌های قبلی پوشش نمی‌دادند. ظرفیت صف انتخاب‌شده توسط LLM نیز ممکن است برای ۱۶ پیام کافی نباشد؛ آن را جداگانه از اختلاف منطق بررسی کن. ابزار ظرفیت یا کد را خودکار تغییر نمی‌دهد. ERROR/INCONCLUSIVE اثبات نادرستی ترجمه نیستند؛ لاگ‌های همان case باید بررسی شوند. Completed به معنی تعداد caseهای تکمیل‌شده است، نه لزوماً تعداد matchها.

## اعتبارسنجی توسعه

آزمون‌های خودکار تولید ۵۰ برنامه برای هر چهار نمونه، بازتولیدپذیری، تنوع، تطبیق هش آرشیو و جلوگیری از پذیرش سناریوی اشتباه را بررسی می‌کنند. اجرای واقعی کنترل‌شده روی ترجمهٔ ذخیره‌شدهٔ ScalarFsm با سه seed جدید انجام شد؛ هر سه ورودی متمایز بودند و BOUNDED_MATCH شدند. ترجمه‌های محلی شما در این محیط در دسترس نیستند؛ نتیجهٔ ۲۰۰ case روی آن‌ها را باید با دستور بالا به دست آورد.
