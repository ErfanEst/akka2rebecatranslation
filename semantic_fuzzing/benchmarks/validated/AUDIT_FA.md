# گزارش بررسی تمام ۵۰ ورودی اصلی

این بررسی روی فایل‌های اصلیِ ارسال‌شده توسط `research_batch` و ابزار واقعی پروژه انجام شده است. ۵۰ شناسه به ۳۷ فایل یکتا اشاره دارند؛ فایل یکسان فقط یک بار بررسی شده و نتیجه به شناسه‌های متناظر اختصاص یافته است.

- ۳۶ مورد: نبود نوع actor یا نمونهٔ ثابت قابل استخراج.
- ۳ مورد: actor استخراج می‌شود، اما message type نام‌دار در فایل ورودی استخراج نمی‌شود.
- ۱۱ مورد: استخراج اولیه انجام می‌شود، اما کامپایل با Scala 2.13 و وابستگی‌های runner فعلی شکست می‌خورد.
- صفر مورد از فایل‌های اصلی در شکل فعلی از این دروازه‌های اولیه عبور کرده است.

برای موارد متوقف‌شده در استخراج، مرحلهٔ بعد اجرا نشده است. این ارزیابی دربارهٔ فایل منفرد و تنظیمات فعلی ماست، نه امکان اجرای پروژهٔ upstream با تمام وابستگی‌های خودش. LLM در این بررسی فراخوانی نشده است.

نسخه‌های مستقل و مشتق‌شده در `akka/` قرار دارند؛ نتیجهٔ آنها با نتیجهٔ کد اصلی یکی محسوب نمی‌شود. جزئیات ماشینی و hash هر منبع در `audit_originals.json` است.

| شناسه | مثال | نوع actor | نمونهٔ actor | پیام نام‌دار | نتیجه |
|---|---|---:|---:|---:|---|
| ACSU-01 | Echo | 5 | 25 | 1 | BLOCKED_AT_COMPILATION |
| ACSU-02 | Key-Value Cache | 1 | 1 | 3 | BLOCKED_AT_COMPILATION |
| ACSU-03 | Parameterized Adder | 23 | 8 | 14 | BLOCKED_AT_COMPILATION |
| ACSU-04 | Integer Calculator | 1 | 0 | 2 | BLOCKED_AT_EXTRACTION |
| ACSU-05 | Summing Accumulator | 2 | 1 | 0 | BLOCKED_NO_MESSAGES |
| ACSU-06 | Finite Ping-Pong | 0 | 0 | 0 | BLOCKED_AT_EXTRACTION |
| ACSU-07 | Counting | 0 | 0 | 3 | BLOCKED_AT_EXTRACTION |
| ACSU-08 | Fixed Fan-out Throughput Kernel | 0 | 0 | 0 | BLOCKED_AT_EXTRACTION |
| ACSU-09 | Swapper | 23 | 8 | 14 | BLOCKED_AT_COMPILATION |
| ACSU-10 | Hot-Swap Actor | 23 | 8 | 14 | BLOCKED_AT_COMPILATION |
| ACSU-11 | Redirect Relay | 4 | 0 | 5 | BLOCKED_AT_EXTRACTION |
| ACSU-12 | Speed Threshold Filter | 2 | 0 | 1 | BLOCKED_AT_EXTRACTION |
| ACSU-13 | License Validity Filter | 2 | 0 | 1 | BLOCKED_AT_EXTRACTION |
| ACSU-14 | Two-Stage Filter Pipeline | 2 | 0 | 1 | BLOCKED_AT_EXTRACTION |
| ACSU-15 | Producer/Consumer Roles | 23 | 8 | 14 | BLOCKED_AT_COMPILATION |
| ACSU-16 | Thread Ring | 0 | 0 | 0 | BLOCKED_AT_EXTRACTION |
| ACSU-17 | Big All-to-All | 0 | 0 | 1 | BLOCKED_AT_EXTRACTION |
| ACSU-18 | Fixed Round-Robin Routing | 5 | 25 | 1 | BLOCKED_AT_COMPILATION |
| ACSU-19 | Fixed Broadcast Routing | 5 | 25 | 1 | BLOCKED_AT_COMPILATION |
| ACSU-20 | Consistent-Hash Cache Routing | 1 | 1 | 3 | BLOCKED_AT_COMPILATION |
| ACSU-21 | Lookup Publish/Subscribe | 0 | 0 | 2 | BLOCKED_AT_EXTRACTION |
| ACSU-22 | Hierarchical Publish/Subscribe | 0 | 0 | 2 | BLOCKED_AT_EXTRACTION |
| ACSU-23 | Predicate Publish/Subscribe | 0 | 0 | 2 | BLOCKED_AT_EXTRACTION |
| ACSU-24 | Content-Based Speed Router | 4 | 0 | 5 | BLOCKED_AT_EXTRACTION |
| ACSU-25 | Switchable Router | 4 | 0 | 5 | BLOCKED_AT_EXTRACTION |
| ACSU-26 | Envelope Enrichment | 1 | 0 | 1 | BLOCKED_AT_EXTRACTION |
| ACSU-27 | Correlation Join | 1 | 0 | 2 | BLOCKED_AT_EXTRACTION |
| ACSU-28 | Ticket Seller | 1 | 0 | 6 | BLOCKED_AT_EXTRACTION |
| ACSU-29 | Bounded Producer-Consumer | 0 | 0 | 0 | BLOCKED_AT_EXTRACTION |
| ACSU-30 | Concurrent Dictionary | 0 | 0 | 0 | BLOCKED_AT_EXTRACTION |
| ACSU-31 | Concurrent Sorted List | 0 | 0 | 0 | BLOCKED_AT_EXTRACTION |
| ACSU-32 | Chameneos | 0 | 0 | 0 | BLOCKED_AT_EXTRACTION |
| ACSU-33 | Dining Philosophers / Arbitrator | 0 | 0 | 6 | BLOCKED_AT_EXTRACTION |
| ACSU-34 | Cigarette Smokers | 0 | 0 | 0 | BLOCKED_AT_EXTRACTION |
| ACSU-35 | Distributed Single-Source Shortest Path | 1 | 0 | 2 | BLOCKED_AT_EXTRACTION |
| ACSU-36 | Capture-Based Leader Election | 2 | 0 | 7 | BLOCKED_AT_EXTRACTION |
| ACSU-37 | Asynchronous Bank Transactions | 0 | 0 | 0 | BLOCKED_AT_EXTRACTION |
| ACSU-38 | Logistic Map Series | 0 | 0 | 0 | BLOCKED_AT_EXTRACTION |
| ACSU-39 | Radix Sort Pipeline | 0 | 0 | 2 | BLOCKED_AT_EXTRACTION |
| ACSU-40 | Bitonic Sorting Network | 0 | 0 | 4 | BLOCKED_AT_EXTRACTION |
| ACSU-41 | All-Pairs Shortest Path | 0 | 0 | 3 | BLOCKED_AT_EXTRACTION |
| ACSU-42 | Single-Actor Fibonacci | 1 | 1 | 0 | BLOCKED_NO_MESSAGES |
| ACSU-43 | Batched Key-Value Requests | 1 | 1 | 0 | BLOCKED_NO_MESSAGES |
| ACSU-44 | N-Queens / FIFO Variant | 0 | 0 | 0 | BLOCKED_AT_EXTRACTION |
| ACSU-45 | Trapezoidal Integration | 0 | 0 | 0 | BLOCKED_AT_EXTRACTION |
| ACSU-46 | Precise Pi Computation | 0 | 0 | 0 | BLOCKED_AT_EXTRACTION |
| ACSU-47 | Untimed Inventory FSM | 3 | 0 | 13 | BLOCKED_AT_EXTRACTION |
| ACSU-48 | Routing Slip / Car Assembly | 4 | 4 | 3 | BLOCKED_AT_COMPILATION |
| ACSU-49 | Open-Write-Close Stash Protocol | 23 | 8 | 14 | BLOCKED_AT_COMPILATION |
| ACSU-50 | Pausable Worker | 1 | 0 | 2 | BLOCKED_AT_EXTRACTION |

## علت‌های اختصاصی

- **ACSU-01:** Echo داخل فایل بزرگ تست Router است؛ پیام Any و نبود harness مستقل نیاز به توجه دارد.
- **ACSU-02:** Map[String,String]، پاسخ Option و router/pool با مشاهدهٔ scalar فعلی سازگار نیستند.
- **ACSU-03:** DemoActor کلاس تودرتو است؛ پیام عددی خام و wrapper اطراف آن برای extractor مسئله‌سازند.
- **ACSU-04:** پاسخ عددی خام و نبود topology مستقل؛ محدودهٔ Int و overflow باید بررسی شوند.
- **ACSU-05:** فایل شامل حلقهٔ بی‌نهایت Thread.sleep و دو نوع actor است؛ فقط SummingActor در پژوهش انتخاب شده.
- **ACSU-06:** وابستگی به wrapper اختصاصی Savina، پیام‌های ActorRef و رفتار exit باید بررسی شوند.
- **ACSU-07:** receive از wrapper به ارث می‌رسد؛ شمارنده و producer بدون harness Savina مستقل نیستند.
- **ACSU-08:** ساخت workerها، اندازه‌گیری زمان و خروج actor در harness وجود دارد؛ هدف پژوهش فقط هستهٔ ارسال پیام است.
- **ACSU-09:** become و پشتهٔ رفتار به‌علاوه خروجی صرفاً log؛ مشاهدهٔ scalar فعلی رفتار کامل را پوشش نمی‌دهد.
- **ACSU-10:** become، کلاس محلی و فرمان‌های رشته‌ای؛ همهٔ Receiveهای فعال باید مشاهده شوند.
- **ACSU-11:** فایل چندمثالی شامل pool و کد کارایی است؛ sender در ارسال معمولی با forward متفاوت است.
- **ACSU-12:** payload مجوز و harness source/filter/sink باید آماده شوند؛ عدم ارسال با timeout قابل جایگزینی نیست.
- **ACSU-13:** شرط‌های String و payload مجوز؛ نگاشت دلخواه رشته به عدد معنای برنامه را عوض می‌کند.
- **ACSU-14:** ترکیب پیشنهادی دو فیلتر است و برنامهٔ مستقل منتشرشده نیست؛ topology و payload نیاز به آماده‌سازی دارند.
- **ACSU-15:** receive-orElse، پیام ActorRef/Any و مشاهده از طریق log خارج از مسیر سادهٔ فعلی‌اند.
- **ACSU-16:** آرایهٔ actorها و تنظیم همسایه با پیام ActorRef؛ استخراج topology ثابت خودکار تضمین نشده.
- **ACSU-17:** انتخاب تصادفی مقصد و مجموعهٔ ActorRef؛ seed یکسان به‌تنهایی تصادفی‌سازی دو زبان را معادل نمی‌کند.
- **ACSU-18:** Router کتابخانه‌ای و handler جایگزینی actor پس از Terminated؛ بخش‌های خارج از topology ثابت وجود دارند.
- **ACSU-19:** broadcast کتابخانه‌ای و pool؛ وضعیت داخلی Router توسط extractor عادی مشاهده نمی‌شود.
- **ACSU-20:** hash ring، Map و routing داخلی؛ جایگزینی با modulo routing هم‌ارز نیست.
- **ACSU-21:** EventBus یک Actor نیست؛ publish/subscribe همگام و sender خارجی نیاز به adapter دارند.
- **ACSU-22:** EventBus و تطبیق سلسله‌مراتبی topic؛ تبدیل آن به broker ناهمگام می‌تواند معنا را عوض کند.
- **ACSU-23:** EventBus و شرط طول String؛ هم مشاهدهٔ کتابخانه و هم نوع داده نیاز به پشتیبانی دارند.
- **ACSU-24:** RoutingLogic، Pool و endpointهای اطراف؛ نسخهٔ actor مستقل یک مشتق جدید خواهد بود.
- **ACSU-25:** تغییر Receive بین on/off؛ وضعیت رفتار باید علاوه بر مقصدهای ثابت مشاهده شود.
- **ACSU-26:** App از currentTimeMillis استفاده می‌کند؛ payload تو‌در‌تو و Map نیز خارج از scalar هستند.
- **ACSU-27:** Map، Seq، correlation-id و درخواست‌های در انتظار؛ فقط scalarها حالت کامل را نشان نمی‌دهند.
- **ACSU-28:** BoxOffice actor جدید می‌سازد؛ Vector/Option و Cancel/PoisonPill نیاز به پشتیبانی دارند.
- **ACSU-29:** فرزندان داخل constructor ساخته می‌شوند و محتوای صف خصوصی اهمیت دارد؛ اندازهٔ صف کافی نیست.
- **ACSU-30:** Map خصوصی و تولید workload تصادفی؛ مدل باید محتوای کامل دیکشنری را حفظ کند.
- **ACSU-31:** لیست پیوندی و تخصیص node معمولی؛ ترتیب و تکرار عناصر با scalarها پوشش داده نمی‌شوند.
- **ACSU-32:** ساخت شرکت‌کننده‌ها در constructor، رنگ enum و پیام ActorRef؛ نگاشت صریح لازم است.
- **ACSU-33:** وضعیت مالکیت چنگال‌ها و AtomicLong مشترکِ اندازه‌گیری؛ حذف instrumentation باید جدا بررسی شود.
- **ACSU-34:** انتخاب تصادفی smoker و busyWait؛ busyWait محاسبه است، اما تصادفی‌سازی باید قابل تطبیق باشد.
- **ACSU-35:** Map با کلید ActorRef، والد و AddNeighbor؛ topology و مشاهدهٔ کامل داده‌ها نیاز به آماده‌سازی دارند.
- **ACSU-36:** منبع صریحاً BUGGY است؛ خطای الگوریتم باید در ترجمه حفظ شود. Simulator شامل failure/reinitialization است.
- **ACSU-37:** Double، صف pending و ActorRef؛ generator منبع حداقل ۱۰ حساب لازم دارد.
- **ACSU-38:** Double، آرایهٔ mutable و صف خصوصی pending؛ نسخه‌های Await نیز باید از هسته تفکیک شوند.
- **ACSU-39:** ساخت pipeline در setup، PRNG و تفاوت Long/Int؛ ترتیب خروجی باید حفظ شود.
- **ACSU-40:** ساخت بازگشتی topology در constructor و آرایه‌ها؛ extractor ثابت آن را مستقیماً پشتیبانی نمی‌کند.
- **ACSU-41:** ماتریس، پیام آرایه‌ای و ساخت actor در حلقه؛ aliasing و مشاهدهٔ کامل داده‌ها مهم است.
- **ACSU-42:** خود Fibonacci بازگشت تابعی دارد، اما App شامل ask/Await/Timeout است؛ harness ثابت لازم است.
- **ACSU-43:** List/Object/String/Status و ActorRef؛ پردازش کل batch در یک handler باید اتمیک بماند.
- **ACSU-44:** payload صفحهٔ شطرنج و نسخه‌های priority؛ aliasing، توقف و محدودیت taskها باید بررسی شوند.
- **ACSU-45:** Double و محاسبات عددی؛ جایگزینی با عدد صحیح ترجمهٔ بدون تغییر معنا نیست.
- **ACSU-46:** BigDecimal در scalarهای فعلی پشتیبانی نمی‌شود؛ نمایش و محاسبات اعشاری نیازمند توسعه‌اند.
- **ACSU-47:** FSM و pending requests؛ همان فایل InventoryWithTimer هم دارد که خارج از مدل بی‌زمان است.
- **ACSU-48:** Seq[ActorRef] و payload تو‌در‌تو؛ مسیرها و مجموعهٔ actorها باید محدود و قابل مشاهده باشند.
- **ACSU-49:** Stash صف خصوصی دوم است و با mailbox یکی نیست؛ مشاهدهٔ mailbox به‌تنهایی کافی نیست.
- **ACSU-50:** Stash، پشتهٔ رفتار و تأخیر HardWorker؛ برنامهٔ اصلی بدون adapter بی‌زمان نیست.
