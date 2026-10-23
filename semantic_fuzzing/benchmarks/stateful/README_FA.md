# نمونه‌های become و FSM بدون زمان

این پوشه جدا از فایل‌های اصلی پژوهش است. فایل‌های اصلی تغییر نکرده‌اند.
مقایسهٔ معنایی بین Scala آماده‌شده در همین پوشه و ترجمهٔ Rebeca آن انجام می‌شود؛
این نتیجه اثبات هم‌ارزی نسخهٔ اقتباس‌شده با کل فایل upstream نیست.

## نمونه‌ها و منشأ

| شناسه | نمونه | تغییرات و محدوده |
|---|---|---|
| ACSU-09 | Swapper | هستهٔ Swapper از ActorDocSpec؛ رفتار anonymous به متد نام‌دار تبدیل شد. لاگ Hi/Ho با متغیر مشاهده‌ای greeting=1/2 نمایش داده می‌شود؛ logger اصلی آزمایش نمی‌شود. |
| ACSU-10 | HotSwap | هستهٔ HotSwapActor از ActorDocSpec؛ foo/bar و دو پاسخ رشته‌ای به Foo/Bar و AlreadyAngry/AlreadyHappy نگاشت شدند. client ثابت پاسخ‌ها را می‌شمارد. |
| ACSU-25 | SwitchRouter | هستهٔ SwitchRouter، نه SwitchRouter2؛ دامنهٔ AnyRef به Data(Int) محدود شده، logging حذف شده و receive اولیه صریحاً همان مسیر off را اجرا می‌کند. دو مقصد ثابت‌اند. این actor معمولی است، نه Router کتابخانه‌ای Akka. |
| FSM-01 | ScalarFsm | نمونهٔ جدید رگرسیون ابزار، نه اقتباس Inventory و نه یکی از ۵۰ مثال اصلی. دارای FSM[Phase, Int]، دو وضعیت و callbackهای واقعی Akka است. |

منشأ سه مثال اقتباس‌شده، commit و permalink دقیق در فایل‌های زیر موجودند:

- `../research50/originals/benchmarks/09_swapper/case.json`
- `../research50/originals/benchmarks/10_hot_swap/case.json`
- `../research50/originals/benchmarks/25_switch_router/case.json`

## چه چیزی هنوز قابل اجرا نیست؟

- ACSU-47، Inventory اصلی: دادهٔ FSM آن StateData شامل Seq[BookRequest]، ActorRef و پاسخ Either است. پشتیبانی Int به معنی پشتیبانی این داده‌ها نیست. نسخهٔ InventoryWithTimer نیز خارج از محدوده است.
- ACSU-49 و ACSU-50: به صف خصوصی Stash نیاز دارند؛ فقط پشتیبانی become کافی نیست.
- ACSU-37 و ACSU-38: مسائل صف خصوصی/داده‌های پیچیده و محاسبات عددی همچنان باقی‌اند.
- این تغییر فایل‌های کامل تست upstream، ساخت actor پویا، زمان یا Router/EventBus کتابخانه‌ای را سازگار نمی‌کند.

## قرارداد FSM جدید

`FSM[Phase, Int]` با وضعیت‌های نام‌دار در `when(State)`، یک `startWith(State, data)` بدون زمان، `goto` با مقصد نام‌دار، `stay`، `using`، `whenUnhandled` و `onTransition` پشتیبانی می‌شود.
فیلدهای mutable خود actor نیز باید صریحاً `Int` یا `Boolean` باشند. mixinهای اضافی، زمان، restart، stop، subscription و Stash خارج از زیرمجموعه‌اند و تعدادی از این موارد در extractor صریحاً رد می‌شوند. این اعتبارسنجی، بررسی ایستای جامع تمام برنامه‌های Scala نیست؛ alias یا کد کتابخانه‌ای دلخواه مجوز عبور از محدودیت‌ها نیست.

instrumenter خود FSM را بازنویسی نمی‌کند: پس از بازگشت `super.aroundReceive` وضعیت واقعی را می‌خواند. بنابراین تغییر stateData، اجرای onTransition و ارسال پیام‌های callback قبل از ثبت post-state اتفاق افتاده‌اند.

- `fuzzFsmState`: شناسهٔ وضعیت، طبق مرتب‌سازی لغوی نام‌های when از صفر.
- `fuzzFsmData`: مقدار واقعی Int دادهٔ FSM.
- سایر متغیرهای scalar و mailboxها نیز مقایسه می‌شوند.

پوشش شاخه‌های داخل DSL مربوط به FSM در این نسخه ابزارگذاری نشده و در interface با `NOT_INSTRUMENTED` و warning اعلام می‌شود. درصد پوشش شاخهٔ عمومی را به معنی پوشش کامل FSM تفسیر نکن.

پرامپت افزوده: `semantic_fuzzing/prompts/scalar_fsm.md`.
فعال‌سازی: `scalar_fsm_support: true`. تنظیم آمادهٔ `translation.stateful-medium.json` هم افزونهٔ رفتارهای نام‌دار و هم افزونهٔ FSM را فعال می‌کند. ورودی FSM فیلدهای پشتهٔ become نمی‌گیرد.

## دریافت و اجرای گروهی

هر دو مخزن را روی `feature/semantic-fuzzing-integration` به‌روز کن. دستورهای دریافت و پیش‌نیازها در `../../NAMED_BEHAVIORS_FA.md` هستند. از ریشهٔ مخزن ترجمه و در محیط Python فعال:

```bash
python -m semantic_fuzzing.validated_batch \
  --suite stateful \
  --config semantic_fuzzing/runtime.json \
  --cases 2 \
  --check-fixtures \
  --output ../runs/stateful-fixtures-01
```

این دستور API مصرف نمی‌کند؛ چهار fixture دست‌نویس را با اجرای واقعی Akka و RMC بررسی می‌کند. مسیرهای ابزار در runtime.json را با سیستم خودت تطبیق بده. پوشهٔ خروجی باید جدید باشد.

ترجمه با LLM و سپس بررسی کامل:

```bash
python -m semantic_fuzzing.validated_batch \
  --suite stateful \
  --config semantic_fuzzing/runtime.json \
  --translation-config semantic_fuzzing/translation.stateful-medium.json \
  --cases 50 --start-seed 10000 \
  --output ../runs/stateful-live-50-01
```

کلید `TRANSLATION_API_KEY` را در `.env` ریشهٔ مخزن ترجمه تنظیم کن و آن را کامیت نکن. مدل و reasoning_effort در فایل translation قابل تغییرند. هر مثال جداگانه ترجمه می‌شود و نتیجهٔ سمنتیک ناموفق می‌تواند تا max_retries باعث درخواست ترجمهٔ مجدد شود.

**نکتهٔ مهم:** این چهار spec آزمون رگرسیون با ترتیب پیام مشخص‌اند. `--cases 50` پنجاه seed اجرا می‌کند اما ترتیب و مقادیر templateها ثابت‌اند؛ آن را پنجاه سناریوی تصادفی متمایز معرفی نکن. برای تنوع واقعی ورودی/ترتیب باید generation spec متناسب با پروتکل طراحی شود. ترتیب پردازش بین actorهای مستقل می‌تواند در اجرا متفاوت باشد.

خلاصه‌ها در `summary.md` و `summary.json` هستند. هر شناسه پوشهٔ جداگانه با logs و translation یا validation دارد. ورودی‌ها در `akka/`، سناریوها در `specs/` و مدل‌های کنترل در `fixtures/` قرار دارند.

## اجرای تکی FSM و کنترل منفی

```bash
python -m semantic_fuzzing \
  --config semantic_fuzzing/examples/configs/scalar_fsm.json translate \
  --akka-source semantic_fuzzing/benchmarks/stateful/akka/ScalarFsm.scala \
  --translation-config semantic_fuzzing/translation.stateful-medium.json \
  --output ../runs/scalar-fsm-live-01
```

برای کنترل منفی، به جای translate از check و این ورودی‌ها استفاده کن:

```bash
python -m semantic_fuzzing \
  --config semantic_fuzzing/examples/configs/scalar_fsm.json check \
  --akka-source semantic_fuzzing/benchmarks/stateful/akka/ScalarFsm.scala \
  --candidate semantic_fuzzing/benchmarks/stateful/fixtures/ScalarFsm.rebeca \
  --mutant semantic_fuzzing/benchmarks/stateful/fixtures/ScalarFsm_mutant.rebeca \
  --output ../runs/scalar-fsm-mutation-01
```

mutant عمداً در Add یک واحد اضافه می‌کند. انتظار: candidate برابر BOUNDED_MATCH و mutant برابر KILLED. نمونهٔ FSM انتقال به همان وضعیت، تفاوت stay با goto، دادهٔ قدیم/جدید در callback و مسیر whenUnhandled را تمرین می‌کند.

نتایج اجرای واقعی در `verification.json` ثبت می‌شوند. `BOUNDED_MATCH` فقط توافق در حدود و سناریوهای اجراشده است، نه اثبات هم‌ارزی عمومی.
