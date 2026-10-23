# پشتیبانی محدود از become و unbecome

این نسخه یک توسعهٔ مشخص است، نه پشتیبانی کامل از تمام Akka:

- actor مستقیماً از `Actor` ارث می‌برد و تعداد actorها ثابت است.
- رفتارها به صورت `def receive: Receive` و `def active: Receive` تعریف می‌شوند؛ بدنه باید یک partial function مستقیم باشد.
- `context.become(active)`، `context.become(active, discardOld = false)` و `context.unbecome()` پشتیبانی می‌شوند. مقدار `discardOld` باید ثابت باشد.
- حداکثر چهار رفتار روی رفتار اولیه قرار می‌گیرند. push پنجم خطای اجراست، نه تطابق معنایی و نه حذف خودکار رفتار قدیمی.
- رفتارهای anonymous، پارامتردار، ترکیبی، alias، restart و supervision در این زیرمجموعه نیستند.
- `Stash`، FSM کتابخانه‌ای، Router/EventBus، زمان و مدل‌سازی دقیق `Double`/`BigDecimal` در این تغییر پیاده‌سازی نشده‌اند. این نسخه باعث قابل اجرا شدن خودکار همهٔ ۵۰ مثال پژوهشی نمی‌شود.

## چه چیزی تغییر کرده است؟

extractor رفتارهای نام‌دار و شناسه‌هایشان را استخراج می‌کند. instrumenter علاوه بر `receive`، پایان handlerهای رفتارهای دیگر را هم ثبت می‌کند. خود عملیات Akka همچنان اجرا می‌شود؛ شش فیلد مشاهده‌ای وضعیت و پشتهٔ رفتار را ثبت می‌کنند. مدل Rebeca باید همین فیلدها را مطابق قرارداد تولید کند. مقایسه، مقدار متغیرهای اصلی، فیلدهای رفتار و mailboxها را بررسی می‌کند.

قواعد افزوده در `semantic_fuzzing/prompts/named_behaviors.md` هستند. فقط با `named_behavior_support: true` به پرامپت افزوده می‌شوند؛ پرامپت پیش‌فرض قبلی تغییر نکرده است. شناسهٔ افزونه و hash پرامپت نهایی در نتیجه ذخیره می‌شوند.

## دریافت و تنظیم

هر دو مخزن باید روی برنچ `feature/semantic-fuzzing-integration` به‌روز شوند. از پوشهٔ `master-thesis`:

```bash
git -C semantic-differential-fuzzing pull --ff-only
git -C akka2rebecatranslation pull --ff-only
cd akka2rebecatranslation
```

محیط Python نصب‌شدهٔ خودت را فعال کن. `python -m pip check`، `java -version` و `javac -version` را بررسی کن؛ Java باید حداقل ۱۷ باشد. پیش‌نیازها همان راهنمای `semantic_fuzzing/README.md` هستند.

در فایل `semantic_fuzzing/examples/configs/behavior_stack.json` مسیرهای `fuzzing_repo`، `rmc_jar` و `sbt` را با سیستم خودت تطبیق بده. مسیرهای نسبی نسبت به خود فایل JSON محاسبه می‌شوند، نه ترمینال. تنظیم‌های آماده به ابزارهای `.semantic-fuzzing-tools` کنار دو مخزن اشاره دارند؛ در نصب متفاوت از مسیر مطلق استفاده کن.

کلید را در `.env` ریشهٔ مخزن ترجمه با نام `TRANSLATION_API_KEY` قرار بده؛ فایل را کامیت نکن و کلید را در چت نفرست. مدل و `reasoning_effort` در `semantic_fuzzing/translation.behavior-medium.json` قابل تغییرند.

## اجرای کامل با LLM

ورودی آماده: `semantic_fuzzing/examples/akka/BehaviorStack.scala`.

```bash
python -m semantic_fuzzing \
  --config semantic_fuzzing/examples/configs/behavior_stack.json translate \
  --akka-source semantic_fuzzing/examples/akka/BehaviorStack.scala \
  --translation-config semantic_fuzzing/translation.behavior-medium.json \
  --output ../runs/behavior-stack-live-01
```

پوشهٔ خروجی باید جدید باشد. مسیر اجرا: Akka و پرامپت → LLM → کنترل سینتکس RMC → استخراج و ابزارگذاری Akka → تولید سناریو → اجرای واقعی Akka و مدل Rebeca → مقایسه و ثبت نتیجه. در صورت رد شدن، تلاش بعدی ترجمه تا سقف `max_retries` انجام می‌شود.

خروجی‌ها: `BehaviorStack_final.rebeca`، `BehaviorStack_result.json`، `report.md`، `prompt_logs/` و `semantic_checks/`. گزارش جزئی فازتستینگ در `semantic_checks/*/fuzzing/result.json` و لاگ‌ها و traceها زیر همان پوشه هستند.

برای کد خودت، `--akka-source` را تغییر بده و generation spec را با پیام‌ها و نام actorهای خودت هماهنگ کن. صرف تعویض فایل Scala کافی نیست.

## آزمون بدون API

```bash
python -m semantic_fuzzing \
  --config semantic_fuzzing/examples/configs/behavior_stack.json check \
  --akka-source semantic_fuzzing/examples/akka/BehaviorStack.scala \
  --candidate semantic_fuzzing/examples/behavior_stack.rebeca \
  --mutant semantic_fuzzing/examples/behavior_stack_mutant.rebeca \
  --output ../runs/behavior-stack-fixture-01
```

انتظار: candidate برابر `BOUNDED_MATCH` و mutant در `campaign/campaign_summary.json` برابر `KILLED`. mutant هنگام pop رفتار قبلی را اشتباه بازیابی می‌کند.

برای تست مرزی، config را به `behavior_stack_boundary.json` تغییر بده: چهار push، replace در سقف، popهای متوالی و pop روی پشتهٔ خالی. برای تست خروج از حد، از `behavior_stack_overflow.json` استفاده کن: نتیجهٔ مورد انتظار `ERROR` با `BEHAVIOR_STACK_BOUND_EXCEEDED` در لاگ Akka است. این خطا به معنی اثبات نادرستی ترجمه نیست؛ اجرای مورد آزمایش خارج از حد تعریف‌شده است.

## دامنهٔ نتیجه

سناریوی اصلی ترتیب مشخصی برای آزمودن پشته دارد؛ seedهای بیشتر الزاماً ترتیب‌های جدید ایجاد نمی‌کنند. `case_count: 50` پنجاه اجرای همان قالب تولید می‌کند، نه پنجاه پروتکل متفاوت. برای تنوع ترتیب باید generation spec مناسب طراحی شود. پوشش کامل، رفتار dead-letter و همهٔ interleavingها ادعا نمی‌شوند. `BOUNDED_MATCH` اثبات هم‌ارزی عمومی نیست.

آزمون‌های ثبت‌شده در `named_behavior_verification.json` خلاصه شده‌اند. اجرای واقعی LLM در تلاش اول پذیرفته شد؛ mutant در هر دو seed رد شد و overflow موفق گزارش نشد.
