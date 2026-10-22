# بنچمارک نامزد ACSU-50 برای Akka Classic → Core Rebeca

تاریخ بررسی: ۲۰۲۶-۱۰-۲۲

## نتیجه در یک نگاه

- ۵۰ workload دارای منبع مشخص، در ۳۴ خانواده موضوعی، از ۶ مخزن.
- ۴۰ نامزد اصلی برای آماده‌سازی، و ۱۰ مورد ذخیره با مانع قابلیت مشخص.
- ۱۹ مورد از Savina، ۱۳ مورد از نمونه‌های رسمی Akka، ۱۰ مورد از Akka in Action، ۵ مورد از Akka Cookbook، ۲ مورد از Bita و ۱ مورد از Learning Akka.
- «۵۰ مثال آماده و اجراشده» پیدا نشده است. این خروجی یک فهرست پژوهشی و برنامه سازگارسازی است، نه بسته ۵۰ برنامه قابل اجرا.
- برخی موردها یک کلاس یا قطعه کد هستند، برخی یک workload پژوهشی کامل‌تر، و برخی ترکیب یا گونه‌ای از یک خانواده‌اند. تعداد ۵۰ نباید به عنوان ۵۰ الگوریتم مستقل گزارش شود.
- تمام وضعیت‌های پیاده‌سازی، کامپایل، تولید Rebeca و اجرای campaign در manifest برابر PENDING است. بررسی منبع با اثبات سازگاری ابزار فرق دارد.

## محدودیت دقیق موردنظر

۱. فقط Akka Classic: نمونه Typed یا Akka.NET را نمونه Classic محسوب نمی‌کنیم.
۲. تمام اکتورهای برنامه باید پیش از شروع پردازش آزمایش ساخته و نام‌گذاری شوند. ساخت فرزند، worker جدید، بازیابی اکتور با ایجاد مجدد، router resizer و ساخت اکتور در تابعی که handler فراخوانی می‌کند ممنوع است.
۳. در منطق برنامه ساعت، sleep، timer، schedule، timeout، deadline یا ask زمان‌دار نداریم.
۴. مهلت بیرونی برای توقف اجرای تست، مانند model-timeout-seconds، «زمان در مدل برنامه» نیست.
۵. مدل مقایسه از صف FIFO استفاده می‌کند. PriorityMailbox را نمی‌توان بدون تغییر معنی حذف کرد.
۶. mutable state مشترک بین اکتورها پذیرفته نیست. آرایه‌ای که چند worker مستقیم تغییرش می‌دهند با state خصوصی اکتور فرق دارد.
۷. تعداد اکتورهای ثابت کافی نیست: ابزار فعلی باید بتواند تعریف آنها، پیام‌ها، پارامترها و state را هم بشناسد.
۸. همه ActorRefهای مجاز از مجموعه ثابت آغاز برنامه‌اند. شناسه‌های نمادین باید نگاشت صریح، ثابت و بدون برخورد داشته باشند.

### اشتباه رایج درباره ساخت ثابت

ساختن N اکتور در یک حلقه با N ثابت، از نظر طرح شبکه می‌تواند پیش‌ساخته باشد؛ اما استخراج‌کننده فعلی لزوماً حلقه را به نام‌های مستقل تبدیل نمی‌کند. برای نسخه مورد آزمایش باید همان شبکه را به تعریف‌های صریح آغاز برنامه تبدیل و برابری آن را جداگانه بررسی کنیم.

ساخت در constructor یا preStart هم مجوز خودکار نیست. به‌ویژه Savina یک پیام داخلی StartAkkaActorMessage دارد و onPostStart را هنگام پردازش آن اجرا می‌کند. ساخت اکتور در آن مسیر باید پیش از آزادشدن پردازش به bootstrap منتقل شود، یا مثال رد شود. صرفِ ثابت‌بودن تعداد کافی نیست.

### اشتباه رایج درباره صف

ترتیب تضمین‌شده Akka برای ارسال مستقیم، به جفت فرستنده–گیرنده مربوط است؛ از فرستنده‌های مختلف یک ترتیب کلی ارسال نداریم. FIFO پردازش هم به نوع mailbox بستگی دارد. صف خصوصی stash با mailbox معمولی یکی نیست؛ ثبت کامل mailbox به‌تنهایی stash را ثبت نمی‌کند.

## منابع و میزان اطمینان

در Savina، ۳۸ فایل پیاده‌سازی Akka در ۳۰ پوشه خانواده در commit ثبت‌شده بازیابی شد. گونه‌های Await، ManualStash و Priority را نمونه‌های مستقل یک مسئله محسوب نکردیم. مقاله اولیه ۲۰۱۴ جدول ۲۸تایی دارد و مقالات بعدی از ۳۰ مورد صحبت می‌کنند؛ این اختلاف نسخه‌ها نباید به اشتباه گزارش شود.

جست‌وجو شامل منابع دانشگاهی، مستندات رسمی و مخزن نویسنده/ناشر کتاب‌ها بوده است. ادعای مرور نظام‌مند همه مقالات جهان یا اثبات نبودن منابع دیگر نداریم. منبع اولیه برای هر قطعه کد، commit و Git blob ثابت در JSON ثبت شده است.

### مقاله‌ها و اسناد خوانده‌شده

- [Savina — An Actor Benchmark Suite](https://soft.vub.ac.be/AGERE14/papers/ageresplash2014_submission_19.pdf) — 2014. Workload families. Early paper lists 28; later repository/literature has 30. Inspected snapshot contains 38 Akka implementation files across 30 families.
- [Targeted Test Generation for Actor Systems](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ECOOP.2018.8) — 2018. Actor test generation using Savina; does not certify our fragment.
- [Run, Actor, Run: Towards Cross-Actor Language Benchmarking](https://www.doc.ic.ac.uk/~scb12/publications/splashws19ageremain-p6-p-ce8b582-42427-submitted.pdf) — 2019. Isolation and benchmark rules: edits that change rules create another benchmark.
- [High-Performance Deterministic Concurrency using Lingua Franca](https://arxiv.org/html/2301.02444v2) — 2023. Reuses selected Savina workloads and discusses cross-model differences; LF code is not Akka.
- [Classic Actors](https://doc.akka.io/libraries/akka-core/current/actors.html). API reference only; catalog code pinned to 2.6.20.
- [Classic Routing](https://doc.akka.io/libraries/akka-core/current/routing.html). Distinguish fixed/static routees, replacement/resizing, and timed strategies.
- [Classic Event Bus](https://doc.akka.io/libraries/akka-core/current/event-bus.html). EventBus is not a message-handler actor and does not preserve original sender.
- [Message Delivery Reliability](https://doc.akka.io/libraries/akka-core/current/general/message-delivery-reliability.html). Ordering per sender/receiver; FIFO processing depends on mailbox.
- [Core Rebeca](https://rebeca-lang.org/allprojects/CoreRebeca). No shared variables, atomic handlers; Rebeca-only code is not an Akka benchmark.

### مخزن‌های ثابت‌شده

| کلید | منبع | commit | کاربرد |
|---|---|---|---|
| S | [Savina](https://github.com/shamsimam/savina/tree/52e546959a57670cdba7a88f0a030b53cfdb16d6) | `52e546959a57670cdba7a88f0a030b53cfdb16d6` | Peer-reviewed actor performance suite; selected kernels repurposed for semantic testing. |
| A | [Akka Classic official examples](https://github.com/akka/akka-core/tree/044bb2dc0a3804d7fe33a1d3e988830256c108fa) | `044bb2dc0a3804d7fe33a1d3e988830256c108fa` | Official 2.6.20 code snippets; not standalone application benchmarks. |
| I | [Akka in Action](https://github.com/RayRoestenburg/akka-in-action/tree/32b301d3042c832a016ca3220576960c43317630) | `32b301d3042c832a016ca3220576960c43317630` | Book author's repository; selected untimed actor classes only. |
| C | [Akka Cookbook](https://github.com/PacktPublishing/Akka-Cookbook/tree/ac64624036d75df5da76390d30e19d94333e6fa2) | `ac64624036d75df5da76390d30e19d94333e6fa2` | Publisher repository; selected actor kernels, not entire applications. |
| B | [Bita](https://github.com/samira-t/Bita/tree/a3241fdea138799c0d6956571bcb7f4f8c8e0ddd) | `a3241fdea138799c0d6956571bcb7f4f8c8e0ddd` | Researcher's test subjects; includes intentionally buggy leader election. |
| L | [Learning Akka](https://github.com/jasongoodwin/learning-akka/tree/e96dd964b26ea4f98cb6b0531e02018ee3d4c109) | `e96dd964b26ea4f98cb6b0531e02018ee3d4c109` | Book author's repository; chapter-4 local database actor only. |

## روش خواندن فهرست

- **P1**: هسته کوچک؛ نیاز اصلی wrapper و راه‌اندازی ثابت است. این هم به معنای اجرای آماده نیست.
- **P2**: نیازمند adapter، مشاهده‌پذیری بیشتر یا نمایش کران‌دار داده‌ها؛ پیش از اجرای معنایی باید پذیرش شود.
- **P3**: ذخیره؛ یک قابلیت مهم مانند stash، EventBus، hash یا محاسبات اعشاری حل نشده است.
- تخمین تعداد اکتورها، اندازه پیشنهادی نسخه آزمایشی است؛ آمار واقعی نسخه منبع نیست.
- درجه آماده‌سازی با دشواری الگوریتم یکسان نیست: یک cache ساده از نظر Map و String ممکن است برای ابزار سخت‌تر از Ping-Pong باشد.
- در فایل‌های چندمثالی فقط کلاس‌های ستون selected_symbols انتخاب می‌شوند. اجرای کل فایل ممکن است timed/dynamic باشد.
- ترکیب جدید، بازنویسی router، کدگذاری داده یا تغییر رفتار باید با عنوان DERIVED ثبت شود؛ آن را نسخه دست‌نخورده منبع یا ترجمه اصلی LLM گزارش نمی‌کنیم.

## چهل نامزد اصلی

| شناسه | مثال | به زبان ساده | سطح | منبع |
|---|---|---|---|---|
| ACSU-01 | [Echo](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/routing/RouterDocSpec.scala) | پاسخ‌دادن با همان پیام | P1 | A |
| ACSU-02 | [Key-Value Cache](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/routing/ConsistentHashingRouterDocSpec.scala) | ذخیره، خواندن و حذف مقدار | P2 | A |
| ACSU-03 | [Parameterized Adder](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/actor/ActorDocSpec.scala) | افزودن عدد ثابت به ورودی | P1 | A |
| ACSU-04 | [Integer Calculator](https://github.com/PacktPublishing/Akka-Cookbook/blob/ac64624036d75df5da76390d30e19d94333e6fa2/Chapter11/akka-impl/src/main/scala/com/packt/chapter11/akka/impl/CalculatorActor.scala) | جمع و ضرب دو عدد | P1 | C |
| ACSU-05 | [Summing Accumulator](https://github.com/PacktPublishing/Akka-Cookbook/blob/ac64624036d75df5da76390d30e19d94333e6fa2/Hello-Akka/src/main/scala/com/packt/chapter1/BehaviourAndState.scala) | جمع‌کردن پیام‌های متوالی در state | P1 | C |
| ACSU-06 | [Finite Ping-Pong](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/pingpong/PingPongAkkaActorBenchmark.scala) | رفت‌وبرگشت محدود پیام | P1 | S |
| ACSU-07 | [Counting](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/count/CountingAkkaActorBenchmark.scala) | شمردن تعداد پیام‌های رسیده | P1 | S |
| ACSU-08 | [Fixed Fan-out Throughput Kernel](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/fjthrput/ThroughputAkkaActorBenchmark.scala) | فرستادن پیام به چند اکتور ثابت | P1 | S |
| ACSU-09 | [Swapper](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/actor/ActorDocSpec.scala) | عوض‌شدن نوبتی رفتار | P2 | A |
| ACSU-10 | [Hot-Swap Actor](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/actor/ActorDocSpec.scala) | پاسخ متفاوت بسته به حالت | P2 | A |
| ACSU-11 | [Redirect Relay](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-routing/src/main/scala/aia/routing/Routing.scala) | عبور پیام از واسطه | P1 | I |
| ACSU-12 | [Speed Threshold Filter](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-structure/src/main/scala/aia/structure/Filters.scala) | عبور پیام فقط بالاتر از حد | P1 | I |
| ACSU-13 | [License Validity Filter](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-structure/src/main/scala/aia/structure/Filters.scala) | ردکردن شناسه خالی | P2 | I |
| ACSU-14 | [Two-Stage Filter Pipeline](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-structure/src/main/scala/aia/structure/Filters.scala) | عبور از دو شرط پشت سر هم | P2 | I |
| ACSU-15 | [Producer/Consumer Roles](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/actor/ActorDocSpec.scala) | درخواست کالا و دریافت پاسخ | P2 | A |
| ACSU-16 | [Thread Ring](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/threadring/ThreadRingAkkaActorBenchmark.scala) | گردش توکن بین گره‌های ثابت | P1 | S |
| ACSU-17 | [Big All-to-All](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/big/BigAkkaActorBenchmark.scala) | ارتباط چند گره با یکدیگر | P2 | S |
| ACSU-18 | [Fixed Round-Robin Routing](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/routing/RouterDocSpec.scala) | تقسیم نوبتی کار بین workerها | P2 | A |
| ACSU-19 | [Fixed Broadcast Routing](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/routing/RouterDocSpec.scala) | ارسال هر پیام به همه گیرنده‌ها | P2 | A |
| ACSU-24 | [Content-Based Speed Router](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-routing/src/main/scala/aia/routing/Routing.scala) | انتخاب مسیر براساس مقدار پیام | P2 | I |
| ACSU-25 | [Switchable Router](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-routing/src/main/scala/aia/routing/Routing.scala) | تغییر مسیر با پیام روشن/خاموش | P2 | I |
| ACSU-26 | [Envelope Enrichment](https://github.com/PacktPublishing/Akka-Cookbook/blob/ac64624036d75df5da76390d30e19d94333e6fa2/Chapter10/src/main/scala/com/packt/chapter10/EnvelopingActor.scala) | افزودن اطلاعات ثابت به پیام | P2 | C |
| ACSU-27 | [Correlation Join](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-routing/src/main/scala/aia/routing/HashRouting.scala) | جمع‌کردن دو پاسخ دارای شناسه یکسان | P2 | I |
| ACSU-28 | [Ticket Seller](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-up-and-running/src/main/scala/com/goticks/TicketSeller.scala) | فروش از موجودی محدود بلیت | P2 | I |
| ACSU-29 | [Bounded Producer-Consumer](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/bndbuffer/ProdConsAkkaActorBenchmark.scala) | تولید و مصرف با بافر محدود | P2 | S |
| ACSU-30 | [Concurrent Dictionary](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/concdict/DictionaryAkkaActorBenchmark.scala) | خواندن و نوشتن چند client روی دیکشنری | P2 | S |
| ACSU-31 | [Concurrent Sorted List](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/concsll/SortedListAkkaActorBenchmark.scala) | درج و جست‌وجوی هم‌زمان در فهرست مرتب | P2 | S |
| ACSU-32 | [Chameneos](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/chameneos/ChameneosAkkaActorBenchmark.scala) | هماهنگی ملاقات و تغییر رنگ | P2 | S |
| ACSU-33 | [Dining Philosophers / Arbitrator](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/philosopher/PhilosopherAkkaActorBenchmark.scala) | گرفتن دو منبع بدون تداخل | P2 | S |
| ACSU-34 | [Cigarette Smokers](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/cigsmok/CigaretteSmokerAkkaActorBenchmark.scala) | تخصیص نوبتی منابع توسط داور | P2 | S |
| ACSU-35 | [Distributed Single-Source Shortest Path](https://github.com/samira-t/Bita/blob/a3241fdea138799c0d6956571bcb7f4f8c8e0ddd/src/test/scala/sample/SPActor.scala) | بهبود فاصله با پیام همسایه‌ها | P2 | B |
| ACSU-36 | [Capture-Based Leader Election](https://github.com/samira-t/Bita/blob/a3241fdea138799c0d6956571bcb7f4f8c8e0ddd/src/test/scala/sample/LeaderElection.scala) | انتخاب رهبر با پیام‌های رقابتی | P2 | B |
| ACSU-39 | [Radix Sort Pipeline](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/radixsort/RadixSortAkkaActorBenchmark.scala) | مرتب‌سازی مرحله‌ای براساس بیت‌ها | P2 | S |
| ACSU-40 | [Bitonic Sorting Network](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/bitonicsort/BitonicSortAkkaActorBenchmark.scala) | شبکه ثابت مقایسه و جابه‌جایی | P2 | S |
| ACSU-41 | [All-Pairs Shortest Path](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/apsp/ApspAkkaActorBenchmark.scala) | فاصله کوتاه‌ترین مسیر همه جفت‌ها | P2 | S |
| ACSU-42 | [Single-Actor Fibonacci](https://github.com/PacktPublishing/Akka-Cookbook/blob/ac64624036d75df5da76390d30e19d94333e6fa2/Hello-Akka/src/main/scala/com/packt/chapter1/FibonacciActor.scala) | محاسبه فیبوناچی داخل یک اکتور ثابت | P2 | C |
| ACSU-43 | [Batched Key-Value Requests](https://github.com/jasongoodwin/learning-akka/blob/e96dd964b26ea4f98cb6b0531e02018ee3d4c109/ch4/akkademy-db-scala/src/main/scala/com/akkademy/AkkademyDb.scala) | اجرای چند درخواست در یک پیام دسته‌ای | P2 | L |
| ACSU-44 | [N-Queens / FIFO Variant](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/nqueenk/NQueensAkkaActorBenchmark.scala) | جست‌وجوی حالت‌های صفحه کوچک | P2 | S |
| ACSU-47 | [Untimed Inventory FSM](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-state/src/main/scala/aia/state/Inventory.scala) | درخواست کالا، تأمین و اتمام موجودی | P2 | I |
| ACSU-48 | [Routing Slip / Car Assembly](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-routing/src/main/scala/aia/routing/SlipRouter.scala) | عبور سفارش از مراحل انتخابی | P2 | I |

## ده مورد ذخیره

| شناسه | مثال | دلیل نگه‌داشتن در ذخیره | منبع |
|---|---|---|---|
| ACSU-20 | [Consistent-Hash Cache Routing](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/routing/ConsistentHashingRouterDocSpec.scala) | hash و router داخلی باید دقیق مدل شود | A |
| ACSU-21 | [Lookup Publish/Subscribe](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/event/EventBusDocSpec.scala) | EventBus اکتور نیست؛ adapter لازم است | A |
| ACSU-22 | [Hierarchical Publish/Subscribe](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/event/EventBusDocSpec.scala) | اشتراک سلسله‌مراتبی و EventBus | A |
| ACSU-23 | [Predicate Publish/Subscribe](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/event/EventBusDocSpec.scala) | اشتراک شرطی و EventBus | A |
| ACSU-37 | [Asynchronous Bank Transactions](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/banking/BankingAkkaManualStashActorBenchmark.scala) | Double، صف خصوصی، ActorRef در پیام | S |
| ACSU-38 | [Logistic Map Series](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/logmap/LogisticMapAkkaManualStashActorBenchmark.scala) | Double و صف خصوصی پیام‌های معوق | S |
| ACSU-45 | [Trapezoidal Integration](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/trapezoid/TrapezoidalAkkaActorBenchmark.scala) | محاسبات اعشاری و قرارداد عددی | S |
| ACSU-46 | [Precise Pi Computation](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/piprecision/PiPrecisionAkkaActorBenchmark.scala) | BigDecimal خارج از scalarهای فعلی | S |
| ACSU-49 | [Open-Write-Close Stash Protocol](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/actor/ActorDocSpec.scala) | stash و پشته رفتار خارج از mailbox معمولی | A |
| ACSU-50 | [Pausable Worker](https://github.com/PacktPublishing/Akka-Cookbook/blob/ac64624036d75df5da76390d30e19d94333e6fa2/Chapter10/src/main/scala/com/packt/chapter10/PausableActor.scala) | stash، حالت توقف و worker بی‌زمان | C |

## توضیح فنی تک‌تک موارد

شرح‌های فنی زیر به انگلیسی نگه داشته شده‌اند تا بعداً مستقیم به مشخصات پیاده‌سازی، issue یا prompt اضافه شوند. هیچ‌کدام ادعای اجرا نیست.

### ACSU-01 — Echo

پاسخ‌دادن با همان پیام

- خانواده: `echo`
- انتخاب از منبع: `RouterDocSpec.Echo`
- کد ثابت: [akka-docs/src/test/scala/docs/routing/RouterDocSpec.scala](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/routing/RouterDocSpec.scala)
- درجه آماده‌سازی: `P1_SMALL_KERNEL_AND_HARNESS`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 2
- هدف معنایی: integer echo, sender identity, reply recipient
- آزمایش کوتاه پیشنهادی: Echo(7) -> Reply(7)
- تغییرات و خطرها: Wrap raw primitive messages in named scalar messages; instantiate a fixed requester and echo actor. Do not copy the surrounding router test suite.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-02 — Key-Value Cache

ذخیره، خواندن و حذف مقدار

- خانواده: `key_value`
- انتخاب از منبع: `ConsistentHashingRouterDocSpec.Cache`
- کد ثابت: [akka-docs/src/test/scala/docs/routing/ConsistentHashingRouterDocSpec.scala](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/routing/ConsistentHashingRouterDocSpec.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 2
- هدف معنایی: update, miss, eviction
- آزمایش کوتاه پیشنهادی: Entry(k,v), Get(k), Evict(k), Get(k)
- تغییرات و خطرها: Extract Cache without its pool/router. Keep a finite string/key domain and expose full bounded map; Option replies and strings need explicit representation.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-03 — Parameterized Adder

افزودن عدد ثابت به ورودی

- خانواده: `arithmetic`
- انتخاب از منبع: `DemoActorWrapper.DemoActor`
- کد ثابت: [akka-docs/src/test/scala/docs/actor/ActorDocSpec.scala](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/actor/ActorDocSpec.scala)
- درجه آماده‌سازی: `P1_SMALL_KERNEL_AND_HARNESS`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 2
- هدف معنایی: constructor parameter and integer arithmetic
- آزمایش کوتاه پیشنهادی: Add(3) with constant 4 -> 7
- تغییرات و خطرها: Lift nested DemoActor into a top-level Actor, keep the constructor constant, and wrap Int input/output. Do not instantiate DemoActorWrapper/SomeOtherActor.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-04 — Integer Calculator

جمع و ضرب دو عدد

- خانواده: `arithmetic`
- انتخاب از منبع: `CalculatorActor`
- کد ثابت: [Chapter11/akka-impl/src/main/scala/com/packt/chapter11/akka/impl/CalculatorActor.scala](https://github.com/PacktPublishing/Akka-Cookbook/blob/ac64624036d75df5da76390d30e19d94333e6fa2/Chapter11/akka-impl/src/main/scala/com/packt/chapter11/akka/impl/CalculatorActor.scala)
- درجه آماده‌سازی: `P1_SMALL_KERNEL_AND_HARNESS`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 2
- هدف معنایی: two argument values and operation dispatch
- آزمایش کوتاه پیشنهادی: Sum(2,3), Multiply(2,3)
- تغییرات و خطرها: Use CalculatorActor alone, no Lagom service. Restrict inputs to avoid overflow initially; later test signed Int boundaries with matching semantics.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-05 — Summing Accumulator

جمع‌کردن پیام‌های متوالی در state

- خانواده: `counter`
- انتخاب از منبع: `SummingActor`
- کد ثابت: [Hello-Akka/src/main/scala/com/packt/chapter1/BehaviourAndState.scala](https://github.com/PacktPublishing/Akka-Cookbook/blob/ac64624036d75df5da76390d30e19d94333e6fa2/Hello-Akka/src/main/scala/com/packt/chapter1/BehaviourAndState.scala)
- درجه آماده‌سازی: `P1_SMALL_KERNEL_AND_HARNESS`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 2
- هدف معنایی: persistent scalar state and message order
- آزمایش کوتاه پیشنهادی: Add(2), Add(3) -> sum=5
- تغییرات و خطرها: Extract SummingActor only. Exclude BehaviourAndState App's infinite Thread.sleep loop and the different SummingActorWithConstructor variant.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-06 — Finite Ping-Pong

رفت‌وبرگشت محدود پیام

- خانواده: `ping_pong`
- انتخاب از منبع: `PingActor, PongActor`
- کد ثابت: [src/main/scala/edu/rice/habanero/benchmarks/pingpong/PingPongAkkaActorBenchmark.scala](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/pingpong/PingPongAkkaActorBenchmark.scala)
- درجه آماده‌سازی: `P1_SMALL_KERNEL_AND_HARNESS`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 2
- هدف معنایی: reply chain, sender, termination boundary
- آزمایش کوتاه پیشنهادی: Start; run 2 ping-pong rounds
- تغییرات و خطرها: Replace Savina base wrapper with explicit Classic receive without changing message causality. Declare named actors in one bootstrap; map ActorRef-valued fields or gate them; audit exit behavior.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-07 — Counting

شمردن تعداد پیام‌های رسیده

- خانواده: `counter`
- انتخاب از منبع: `ProducerActor, CountingActor`
- کد ثابت: [src/main/scala/edu/rice/habanero/benchmarks/count/CountingAkkaActorBenchmark.scala](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/count/CountingAkkaActorBenchmark.scala)
- درجه آماده‌سازی: `P1_SMALL_KERNEL_AND_HARNESS`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 2
- هدف معنایی: many-to-one FIFO and count
- آزمایش کوتاه پیشنهادی: send 3 increment messages then read count
- تغییرات و خطرها: Lift inherited process into explicit receive; fixed producer/counter refs and tiny N. Preserve source-specific ordering and completion protocol.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-08 — Fixed Fan-out Throughput Kernel

فرستادن پیام به چند اکتور ثابت

- خانواده: `fixed_fanout`
- انتخاب از منبع: `ThroughputActor`
- کد ثابت: [src/main/scala/edu/rice/habanero/benchmarks/fjthrput/ThroughputAkkaActorBenchmark.scala](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/fjthrput/ThroughputAkkaActorBenchmark.scala)
- درجه آماده‌سازی: `P1_SMALL_KERNEL_AND_HARNESS`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 3
- هدف معنایی: fan-out and per-worker counts
- آزمایش کوتاه پیشنهادی: 2 precreated workers; 2 messages each
- تغییرات و خطرها: Use a fixed named worker set and compare message counts, not elapsed throughput. Remove benchmark timing harness and audit actor exit.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-09 — Swapper

عوض‌شدن نوبتی رفتار

- خانواده: `behavior_switch`
- انتخاب از منبع: `Swapper`
- کد ثابت: [akka-docs/src/test/scala/docs/actor/ActorDocSpec.scala](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/actor/ActorDocSpec.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 2
- هدف معنایی: become/unbecome stack behavior
- آزمایش کوتاه پیشنهادی: Swap, Swap, Swap
- تغییرات و خطرها: Source effects are logs and hidden behavior stack. Add an explicit observable protocol/state or log oracle; cannot claim meaningful state validation from the current scalar extractor alone.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-10 — Hot-Swap Actor

پاسخ متفاوت بسته به حالت

- خانواده: `behavior_switch`
- انتخاب از منبع: `HotSwapActor`
- کد ثابت: [akka-docs/src/test/scala/docs/actor/ActorDocSpec.scala](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/actor/ActorDocSpec.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 2
- هدف معنایی: state-dependent dispatch and replies
- آزمایش کوتاه پیشنهادی: foo, foo, bar, bar
- تغییرات و خطرها: Extract local class; wrap string commands as a finite protocol. Preserve behavior transitions; instrument all active Receive methods or use a validated explicit mode representation.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-11 — Redirect Relay

عبور پیام از واسطه

- خانواده: `relay`
- انتخاب از منبع: `RedirectActor`
- کد ثابت: [chapter-routing/src/main/scala/aia/routing/Routing.scala](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-routing/src/main/scala/aia/routing/Routing.scala)
- درجه آماده‌سازی: `P1_SMALL_KERNEL_AND_HARNESS`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 3
- هدف معنایی: receiver/sender effects across a proxy
- آزمایش کوتاه پیشنهادی: Requester -> Redirect -> Sink
- تغییرات و خطرها: Extract RedirectActor only. Its ! send changes sender to relay; do not replace with forward. Exclude GetLicense, routing pools, and performance code from the same file.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-12 — Speed Threshold Filter

عبور پیام فقط بالاتر از حد

- خانواده: `photo_filter`
- انتخاب از منبع: `SpeedFilter`
- کد ثابت: [chapter-structure/src/main/scala/aia/structure/Filters.scala](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-structure/src/main/scala/aia/structure/Filters.scala)
- درجه آماده‌سازی: `P1_SMALL_KERNEL_AND_HARNESS`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 3
- هدف معنایی: strict comparison and no-send branch
- آزمایش کوتاه پیشنهادی: speed below/equal/above threshold
- تغییرات و خطرها: Fixed source/filter/sink; use tiny licence domain. Extract SpeedFilter without unrelated routing/performance code; compare absent sends through post-mailboxes, not a wall-clock timeout.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-13 — License Validity Filter

ردکردن شناسه خالی

- خانواده: `photo_filter`
- انتخاب از منبع: `LicenseFilter`
- کد ثابت: [chapter-structure/src/main/scala/aia/structure/Filters.scala](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-structure/src/main/scala/aia/structure/Filters.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 3
- هدف معنایی: empty/nonempty data branch
- آزمایش کوتاه پیشنهادی: Photo(empty, v), Photo(valid, v)
- تغییرات و خطرها: Finite String support or documented bijective symbol encoding is required. Do not silently change string predicates to arbitrary integers.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-14 — Two-Stage Filter Pipeline

عبور از دو شرط پشت سر هم

- خانواده: `photo_filter`
- انتخاب از منبع: `SpeedFilter + LicenseFilter composition`
- کد ثابت: [chapter-structure/src/main/scala/aia/structure/Filters.scala](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-structure/src/main/scala/aia/structure/Filters.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 4
- هدف معنایی: composition, stage order, dropped messages
- آزمایش کوتاه پیشنهادی: below threshold; high/empty; high/nonempty
- تغییرات و خطرها: New benchmark composition of two existing source classes, not a separately published standalone program. Explicit source provenance and finite payload domain.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-15 — Producer/Consumer Roles

درخواست کالا و دریافت پاسخ

- خانواده: `producer_consumer`
- انتخاب از منبع: `ProducerBehavior, ConsumerBehavior, ProducerConsumer`
- کد ثابت: [akka-docs/src/test/scala/docs/actor/ActorDocSpec.scala](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/actor/ActorDocSpec.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 3
- هدف معنایی: receive.orElse composition and response role
- آزمایش کوتاه پیشنهادی: consumer requests GiveMeThings; producer sends Give
- تغییرات و خطرها: Extract untimed receive-orElse snippet only. ActorRef messages/Any payloads need fixed role mapping. Consumer logs must be replaced by a declared observation or captured separately.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-16 — Thread Ring

گردش توکن بین گره‌های ثابت

- خانواده: `token_ring`
- انتخاب از منبع: `ThreadRingActor`
- کد ثابت: [src/main/scala/edu/rice/habanero/benchmarks/threadring/ThreadRingAkkaActorBenchmark.scala](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/threadring/ThreadRingAkkaActorBenchmark.scala)
- درجه آماده‌سازی: `P1_SMALL_KERNEL_AND_HARNESS`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 3
- هدف معنایی: routing, hop decrement and destination
- آزمایش کوتاه پیشنهادی: 3 nodes; token with 5 hops
- تغییرات و خطرها: Unroll actor array into three named bootstrap declarations; configure neighbors before Start and keep topology frozen. Neighbor setup ActorRef payloads need adapter.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-17 — Big All-to-All

ارتباط چند گره با یکدیگر

- خانواده: `all_to_all`
- انتخاب از منبع: `BigActor, SinkActor`
- کد ثابت: [src/main/scala/edu/rice/habanero/benchmarks/big/BigAkkaActorBenchmark.scala](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/big/BigAkkaActorBenchmark.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 4
- هدف معنایی: multiple senders, response correlation
- آزمایش کوتاه پیشنهادی: 3 nodes; 2 exchanges per node
- تغییرات و خطرها: Freeze all actor refs at bootstrap. Move random routing decisions into reproducible inputs or preserve a specified PRNG exactly; seed alone across different languages is insufficient.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-18 — Fixed Round-Robin Routing

تقسیم نوبتی کار بین workerها

- خانواده: `fixed_routing`
- انتخاب از منبع: `RoundRobin routing configuration`
- کد ثابت: [akka-docs/src/test/scala/docs/routing/RouterDocSpec.scala](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/routing/RouterDocSpec.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 4
- هدف معنایی: route index and one-recipient delivery
- آزمایش کوتاه پیشنهادی: tasks 0,1,2,3 -> workers 0,1,2,0
- تغییرات و خطرها: Use fixed ActorRef routees; no resizer, deathwatch replacement, or pool creation after release. The documented Master Terminated handler spawns replacements and is excluded. Built-in routing internals need a verified adapter, or label an explicit router rewrite DERIVED.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-19 — Fixed Broadcast Routing

ارسال هر پیام به همه گیرنده‌ها

- خانواده: `fixed_routing`
- انتخاب از منبع: `Broadcast routing configuration`
- کد ثابت: [akka-docs/src/test/scala/docs/routing/RouterDocSpec.scala](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/routing/RouterDocSpec.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 4
- هدف معنایی: duplicate omission and fan-out cardinality
- آزمایش کوتاه پیشنهادی: one request -> each of 3 workers once
- تغییرات و خطرها: Use a static routee set and no pool resizer/replacement. Built-in Router internals are not automatically supported by the existing extractor; explicit actor implementation is a derived benchmark.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-20 — Consistent-Hash Cache Routing

رسیدن کلید یکسان به cache یکسان

- خانواده: `key_value`
- انتخاب از منبع: `Cache + ConsistentHashingPool`
- کد ثابت: [akka-docs/src/test/scala/docs/routing/ConsistentHashingRouterDocSpec.scala](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/routing/ConsistentHashingRouterDocSpec.scala)
- درجه آماده‌سازی: `P3_UNRESOLVED_FEATURE_GATE`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 4
- هدف معنایی: key affinity, routing hash and cache state
- آزمایش کوتاه پیشنهادی: put/get same key across 3 fixed caches
- تغییرات و خطرها: RESERVE. Replace pool bootstrap with fixed refs only after proving routing consistency. Hash ring, key encoding and hidden library state must be modeled exactly; modulo routing is not an equivalent substitute.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-21 — Lookup Publish/Subscribe

ارسال رویداد به مشترکان موضوع

- خانواده: `pubsub`
- انتخاب از منبع: `LookupBusImpl`
- کد ثابت: [akka-docs/src/test/scala/docs/event/EventBusDocSpec.scala](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/event/EventBusDocSpec.scala)
- درجه آماده‌سازی: `P3_UNRESOLVED_FEATURE_GATE`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 4
- هدف معنایی: exact topic match, missing subscriber
- آزمایش کوتاه پیشنهادی: fixed subscriptions; publish one matching and one other topic
- تغییرات و خطرها: RESERVE. EventBus is not an Actor. Existing tool cannot treat its synchronous publish/subscribe calls as actor handlers; need an adapter preserving sender=noSender and observation cuts. An explicit broker rewrite is DERIVED.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-22 — Hierarchical Publish/Subscribe

اشتراک در شاخه موضوع‌ها

- خانواده: `pubsub`
- انتخاب از منبع: `SubchannelBusImpl + StartsWithSubclassification`
- کد ثابت: [akka-docs/src/test/scala/docs/event/EventBusDocSpec.scala](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/event/EventBusDocSpec.scala)
- درجه آماده‌سازی: `P3_UNRESOLVED_FEATURE_GATE`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 4
- هدف معنایی: prefix/subclass delivery and overlapping subscriptions
- آزمایش کوتاه پیشنهادی: subscribe a and ab; publish abc
- تغییرات و خطرها: RESERVE. Same EventBus boundary issue as lookup; finite topic hierarchy and exact subscription matching. Do not silently turn synchronous library behavior into asynchronous broker semantics.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-23 — Predicate Publish/Subscribe

انتخاب مشترک براساس شرط

- خانواده: `pubsub`
- انتخاب از منبع: `ScanningBusImpl`
- کد ثابت: [akka-docs/src/test/scala/docs/event/EventBusDocSpec.scala](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/event/EventBusDocSpec.scala)
- درجه آماده‌سازی: `P3_UNRESOLVED_FEATURE_GATE`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 4
- هدف معنایی: overlapping predicates and boundary values
- آزمایش کوتاه پیشنهادی: length thresholds 2 and 3; publish lengths 1,3,4
- تغییرات و خطرها: RESERVE. Source predicate is String.length <= classifier. Preserve length operation and sender behavior; requires external-library adapter or separately labeled actor-based derivative.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-24 — Content-Based Speed Router

انتخاب مسیر براساس مقدار پیام

- خانواده: `fixed_routing`
- انتخاب از منبع: `SpeedRouterLogic`
- کد ثابت: [chapter-routing/src/main/scala/aia/routing/Routing.scala](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-routing/src/main/scala/aia/routing/Routing.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 4
- هدف معنایی: threshold branch and destination
- آزمایش کوتاه پیشنهادی: speed equal/below/above minSpeed
- تغییرات و خطرها: Extract routing predicate with fixed endpoints; source Pool and GetLicense are not admitted. Embedding library RoutingLogic in an explicit Actor is a derived benchmark, not unchanged source.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-25 — Switchable Router

تغییر مسیر با پیام روشن/خاموش

- خانواده: `fixed_routing`
- انتخاب از منبع: `SwitchRouter (not SwitchRouter2)`
- کد ثابت: [chapter-routing/src/main/scala/aia/routing/Routing.scala](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-routing/src/main/scala/aia/routing/Routing.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 4
- هدف معنایی: mode transitions and branch-specific mailbox
- آزمایش کوتاه پیشنهادی: On, Data, Off, Data
- تغییرات و خطرها: Use fixed normal/cleanup sinks. Instrument on/off Receive methods or validate explicit scalar mode rewrite; no creation is needed when switching existing destinations.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-26 — Envelope Enrichment

افزودن اطلاعات ثابت به پیام

- خانواده: `envelope`
- انتخاب از منبع: `EnvelopingActor with constant header function`
- کد ثابت: [Chapter10/src/main/scala/com/packt/chapter10/EnvelopingActor.scala](https://github.com/PacktPublishing/Akka-Cookbook/blob/ac64624036d75df5da76390d30e19d94333e6fa2/Chapter10/src/main/scala/com/packt/chapter10/EnvelopingActor.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 3
- هدف معنایی: payload preservation and metadata
- آزمایش کوتاه پیشنهادی: Send(5) -> Envelope(5, fixed-header)
- تغییرات و خطرها: Select a constant pure addHeaders function. Do NOT use EnvelopingActorApp, whose header includes currentTimeMillis. Generic nested payloads/maps need finite serialization and projection.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-27 — Correlation Join

جمع‌کردن دو پاسخ دارای شناسه یکسان

- خانواده: `correlation_join`
- انتخاب از منبع: `SimpleGather`
- کد ثابت: [chapter-routing/src/main/scala/aia/routing/HashRouting.scala](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-routing/src/main/scala/aia/routing/HashRouting.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 4
- هدف معنایی: interleaved ids and first/second reply state
- آزمایش کوتاه پیشنهادی: A1, B1, A2, B2 -> joins A and B
- تغییرات و خطرها: Fixed workers and gather actor; finite correlation-id/value domain. Map, Seq, and pending values must be fully observed or encoded with justified bounds; do not model a timeout.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-28 — Ticket Seller

فروش از موجودی محدود بلیت

- خانواده: `inventory`
- انتخاب از منبع: `TicketSeller`
- کد ثابت: [chapter-up-and-running/src/main/scala/com/goticks/TicketSeller.scala](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-up-and-running/src/main/scala/com/goticks/TicketSeller.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 2
- هدف معنایی: stock depletion and exact-amount boundary
- آزمایش کوتاه پیشنهادی: Add 2 tickets; Buy 2; Buy 1
- تغییرات و خطرها: Use one precreated seller, not BoxOffice (creates event sellers). Vector/Option/nested messages and event metadata need mapping. Exclude Cancel initially or specify PoisonPill/dead-letter semantics explicitly.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-29 — Bounded Producer-Consumer

تولید و مصرف با بافر محدود

- خانواده: `producer_consumer`
- انتخاب از منبع: `ManagerActor, ProducerActor, ConsumerActor`
- کد ثابت: [src/main/scala/edu/rice/habanero/benchmarks/bndbuffer/ProdConsAkkaActorBenchmark.scala](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/bndbuffer/ProdConsAkkaActorBenchmark.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 5
- هدف معنایی: capacity, backpressure, pending requests
- آزمایش کوتاه پیشنهادی: 2 producers,2 consumers; capacity 2
- تغییرات و خطرها: Move all constructor-created children to named bootstrap declarations. Queue contents matter, not just scalar size. Select Savina asynchronous version, not Bita ask/Await examples.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-30 — Concurrent Dictionary

خواندن و نوشتن چند client روی دیکشنری

- خانواده: `key_value`
- انتخاب از منبع: `Master, Dictionary, Worker`
- کد ثابت: [src/main/scala/edu/rice/habanero/benchmarks/concdict/DictionaryAkkaActorBenchmark.scala](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/concdict/DictionaryAkkaActorBenchmark.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 4
- هدف معنایی: read/write interleavings and overwritten values
- آزمایش کوتاه پیشنهادی: 2 clients; 2 keys; interleaved writes/reads
- تغییرات و خطرها: Fixed dictionary/workers; externalize workload PRNG; preserve finite key/value map exactly. It is a single server's private map, not shared mutable state between actors.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-31 — Concurrent Sorted List

درج و جست‌وجوی هم‌زمان در فهرست مرتب

- خانواده: `sorted_collection`
- انتخاب از منبع: `Master, SortedList, Worker`
- کد ثابت: [src/main/scala/edu/rice/habanero/benchmarks/concsll/SortedListAkkaActorBenchmark.scala](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/concsll/SortedListAkkaActorBenchmark.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 4
- هدف معنایی: ordered insertion, contains, size
- آزمایش کوتاه پیشنهادی: Insert(2), Insert(1), Contains(1), Size
- تغییرات و خطرها: Fixed actors; the data structure allocates ordinary list nodes, not actors. Bound list length and preserve multiplicity/order; full projection or equivalent finite representation required.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-32 — Chameneos

هماهنگی ملاقات و تغییر رنگ

- خانواده: `rendezvous`
- انتخاب از منبع: `ChameneosMallActor, ChameneosChameneoActor`
- کد ثابت: [src/main/scala/edu/rice/habanero/benchmarks/chameneos/ChameneosAkkaActorBenchmark.scala](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/chameneos/ChameneosAkkaActorBenchmark.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 4
- هدف معنایی: pairing, enumeration transition, completion
- آزمایش کوتاه پیشنهادی: 3 chameneos; 2 meetings
- تغییرات و خطرها: Flatten constructor-created participants into fixed named actors. Enum colors may use a bijective int representation. Explicitly model ActorRef payloads and small round bound.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-33 — Dining Philosophers / Arbitrator

گرفتن دو منبع بدون تداخل

- خانواده: `resource_arbitration`
- انتخاب از منبع: `ArbitratorActor, PhilosopherActor`
- کد ثابت: [src/main/scala/edu/rice/habanero/benchmarks/philosopher/PhilosopherAkkaActorBenchmark.scala](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/philosopher/PhilosopherAkkaActorBenchmark.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 4
- هدف معنایی: mutual exclusion, release and retry
- آزمایش کوتاه پیشنهادی: 3 philosophers; 1 eating round each
- تغییرات و خطرها: Choose Savina's untimed arbitrator variant, not Dining Hakkers timers. Remove only shared AtomicLong performance instrumentation or replace it with an actor observer; fork ownership is private arbitrator state. Prove any reduction preserves protocol behavior.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-34 — Cigarette Smokers

تخصیص نوبتی منابع توسط داور

- خانواده: `resource_arbiter`
- انتخاب از منبع: `ArbiterActor, SmokerActor`
- کد ثابت: [src/main/scala/edu/rice/habanero/benchmarks/cigsmok/CigaretteSmokerAkkaActorBenchmark.scala](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/cigsmok/CigaretteSmokerAkkaActorBenchmark.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 4
- هدف معنایی: arbiter acknowledgement and repeated allocation
- آزمایش کوتاه پیشنهادی: 3 smokers; fixed selected-smoker inputs; 2 rounds
- تغییرات و خطرها: Inspect helper: busyWait is a bounded computation loop, not a clock/deadline. It calls Math.random with discarded result; externalize random smoker choices. If retaining standard smoke-resource semantics is required, note this source is an instantaneous-acquisition variant.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-35 — Distributed Single-Source Shortest Path

بهبود فاصله با پیام همسایه‌ها

- خانواده: `graph_shortest_path`
- انتخاب از منبع: `SPActor`
- کد ثابت: [src/test/scala/sample/SPActor.scala](https://github.com/samira-t/Bita/blob/a3241fdea138799c0d6956571bcb7f4f8c8e0ddd/src/test/scala/sample/SPActor.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 4
- هدف معنایی: relaxation, alternate paths, parent identity
- آزمایش کوتاه پیشنهادی: 4 vertices; nonnegative edge weights 0..3
- تغییرات و خطرها: Create vertices at bootstrap; AddNeighbor only during setup and then freeze graph. ActorRef keys/parent need fixed IDs and full map projection. Node allocation is not dynamic actor creation here.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-36 — Capture-Based Leader Election

انتخاب رهبر با پیام‌های رقابتی

- خانواده: `leader_election`
- انتخاب از منبع: `NodeActor (Simulator excluded)`
- کد ثابت: [src/test/scala/sample/LeaderElection.scala](https://github.com/samira-t/Bita/blob/a3241fdea138799c0d6956571bcb7f4f8c8e0ddd/src/test/scala/sample/LeaderElection.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 3
- هدف معنایی: capture/accept/elect state transitions
- آزمایش کوتاه پیشنهادی: 3 fixed nodes; explicit Init and Start; no physical failures
- تغییرات و خطرها: The source explicitly says BUGGY. Use as a known-bug/translation subject, never an automatically correct reference. Exclude Simulator's failure/reinitialization scenario and unused timeout imports; preserve source bug for translation comparison.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-37 — Asynchronous Bank Transactions

انتقال مبلغ و انتظار پاسخ حساب

- خانواده: `bank_transactions`
- انتخاب از منبع: `Teller, Account`
- کد ثابت: [src/main/scala/edu/rice/habanero/benchmarks/banking/BankingAkkaManualStashActorBenchmark.scala](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/banking/BankingAkkaManualStashActorBenchmark.scala)
- درجه آماده‌سازی: `P3_UNRESOLVED_FEATURE_GATE`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 11
- هدف معنایی: debit/credit conservation and pending reply
- آزمایش کوتاه پیشنهادی: 10 fixed accounts; 2 transfers
- تغییرات و خطرها: RESERVE. ManualStash variant avoids timed ask/Await, but Double balances, pending-message lists and ActorRef fields need support. Source generator requires at least 10 accounts because of integer division; do not blindly reduce to 2.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-38 — Logistic Map Series

محاسبه مرحله‌ای با درخواست و پاسخ

- خانواده: `iterative_numeric`
- انتخاب از منبع: `Master, SeriesWorker, RateComputer`
- کد ثابت: [src/main/scala/edu/rice/habanero/benchmarks/logmap/LogisticMapAkkaManualStashActorBenchmark.scala](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/logmap/LogisticMapAkkaManualStashActorBenchmark.scala)
- درجه آماده‌سازی: `P3_UNRESOLVED_FEATURE_GATE`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 5
- هدف معنایی: per-worker sequencing and pending requests
- آزمایش کوتاه پیشنهادی: 2 series; 2 terms
- تغییرات و خطرها: RESERVE. Fixed bootstrap; use manual asynchronous version, not Await version. Double arithmetic equality, mutable one-element arrays and private pending queue require defined observation/numeric semantics.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-39 — Radix Sort Pipeline

مرتب‌سازی مرحله‌ای براساس بیت‌ها

- خانواده: `sorting_pipeline`
- انتخاب از منبع: `IntSourceActor, SortActor, ValidationActor`
- کد ثابت: [src/main/scala/edu/rice/habanero/benchmarks/radixsort/RadixSortAkkaActorBenchmark.scala](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/radixsort/RadixSortAkkaActorBenchmark.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 5
- هدف معنایی: bit partitioning and FIFO batches
- آزمایش کوتاه پیشنهادی: 3 values in 0..7; 3 fixed bit stages
- تغییرات و خطرها: Unroll setup-created pipeline; feed explicit value inputs instead of language-specific PRNG. Preserve Long/Int widths and emitted value order; compare output values, not just success prints.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-40 — Bitonic Sorting Network

شبکه ثابت مقایسه و جابه‌جایی

- خانواده: `sorting_network`
- انتخاب از منبع: `CompareExchangeActor and fixed network construction`
- کد ثابت: [src/main/scala/edu/rice/habanero/benchmarks/bitonicsort/BitonicSortAkkaActorBenchmark.scala](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/bitonicsort/BitonicSortAkkaActorBenchmark.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 10
- هدف معنایی: routing network and compare-exchange
- آزمایش کوتاه پیشنهادی: 4 values with duplicates; fixed network
- تغییرات و خطرها: Source creates topology recursively in constructors. Prove fixed finite network, then declare every node before release; not admitted unchanged by static extractor. Keep array bounds, comparator direction and stage order.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-41 — All-Pairs Shortest Path

فاصله کوتاه‌ترین مسیر همه جفت‌ها

- خانواده: `graph_apsp`
- انتخاب از منبع: `ApspFloydWarshallActor`
- کد ثابت: [src/main/scala/edu/rice/habanero/benchmarks/apsp/ApspAkkaActorBenchmark.scala](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/apsp/ApspAkkaActorBenchmark.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 4
- هدف معنایی: phase barriers and distributed matrix updates
- آزمایش کوتاه پیشنهادی: 2x2 or 3x3 graph; tiny nonnegative weights
- تغییرات و خطرها: Fixed block graph; flatten startup loops into named actors. Matrix/array messages require deep-copy/immutability audit and complete bounded state projection.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-42 — Single-Actor Fibonacci

محاسبه فیبوناچی داخل یک اکتور ثابت

- خانواده: `local_recursion`
- انتخاب از منبع: `FibonacciActor only (NOT FibonacciActorApp)`
- کد ثابت: [Hello-Akka/src/main/scala/com/packt/chapter1/FibonacciActor.scala](https://github.com/PacktPublishing/Akka-Cookbook/blob/ac64624036d75df5da76390d30e19d94333e6fa2/Hello-Akka/src/main/scala/com/packt/chapter1/FibonacciActor.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 2
- هدف معنایی: recursive handler computation without actor creation
- آزمایش کوتاه پیشنهادی: Fib(0), Fib(1), Fib(5) -> 0,1,5
- تغییرات و خطرها: This is NOT Savina recursive actor Fibonacci. The selected class recursively calls an ordinary Scala method and creates no actors. Exclude App's ask/Await/Timeout; use a fixed requester and tell replies. Preserve recursion or validate bounded translation; restrict n to 0..8.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-43 — Batched Key-Value Requests

اجرای چند درخواست در یک پیام دسته‌ای

- خانواده: `key_value`
- انتخاب از منبع: `AkkademyDb (chapter 4)`
- کد ثابت: [ch4/akkademy-db-scala/src/main/scala/com/akkademy/AkkademyDb.scala](https://github.com/jasongoodwin/learning-akka/blob/e96dd964b26ea4f98cb6b0531e02018ee3d4c109/ch4/akkademy-db-scala/src/main/scala/com/akkademy/AkkademyDb.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 3
- هدف معنایی: batch atomicity, per-item reply and missing key
- آزمایش کوتاه پیشنهادی: batch [Set(k,1),Get(k)] then another-client write
- تغییرات و خطرها: Use local precreated db/clients, no remoting/client FSM. Preserve that List requests run inside ONE handler; splitting a batch into separate mailbox messages changes semantics. Object/List/String/Status/ActorRef reply fields need complete finite encoding.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-44 — N-Queens / FIFO Variant

جست‌وجوی حالت‌های صفحه کوچک

- خانواده: `constraint_search`
- انتخاب از منبع: `Master, Worker`
- کد ثابت: [src/main/scala/edu/rice/habanero/benchmarks/nqueenk/NQueensAkkaActorBenchmark.scala](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/nqueenk/NQueensAkkaActorBenchmark.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 3
- هدف معنایی: partial solution propagation and result count
- آزمایش کوتاه پیشنهادی: 4 queens; 2 precreated workers
- تغییرات و خطرها: Use non-priority implementation; search recursion is task recursion, not necessarily actor creation. Preserve board payload and stop criterion; choose tiny task bound and audit aliasing.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-45 — Trapezoidal Integration

تقسیم محاسبه عددی و جمع جواب‌ها

- خانواده: `numeric_reduction`
- انتخاب از منبع: `Master, Worker`
- کد ثابت: [src/main/scala/edu/rice/habanero/benchmarks/trapezoid/TrapezoidalAkkaActorBenchmark.scala](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/trapezoid/TrapezoidalAkkaActorBenchmark.scala)
- درجه آماده‌سازی: `P3_UNRESOLVED_FEATURE_GATE`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 3
- هدف معنایی: work partition and numeric reduction
- آزمایش کوتاه پیشنهادی: 2 workers; few trapezoids
- تغییرات و خطرها: RESERVE. No protocol time; Double/transcendental math is the blocker. Do not replace with integer arithmetic and call it unchanged. Require a common numerical contract and supported argument generation.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-46 — Precise Pi Computation

تقسیم محاسبه دقیق عدد پی

- خانواده: `big_decimal_reduction`
- انتخاب از منبع: `Master, Worker`
- کد ثابت: [src/main/scala/edu/rice/habanero/benchmarks/piprecision/PiPrecisionAkkaActorBenchmark.scala](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/piprecision/PiPrecisionAkkaActorBenchmark.scala)
- درجه آماده‌سازی: `P3_UNRESOLVED_FEATURE_GATE`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 3
- هدف معنایی: work assignment, completion and precision
- آزمایش کوتاه پیشنهادی: 2 fixed workers; low precision after source validation
- تغییرات و خطرها: RESERVE. BigDecimal is not a supported scalar of the current fuzzer/observations. Needs explicit decimal representation and arithmetic verification; no claim it runs in v1.11.1.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-47 — Untimed Inventory FSM

درخواست کالا، تأمین و اتمام موجودی

- خانواده: `inventory`
- انتخاب از منبع: `Inventory + Publisher (NOT InventoryWithTimer)`
- کد ثابت: [chapter-state/src/main/scala/aia/state/Inventory.scala](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-state/src/main/scala/aia/state/Inventory.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 4
- هدف معنایی: pending queue, replenishment and sold-out branch
- آزمایش کوتاه پیشنهادی: finite stock; concurrent BookRequest; Publisher replies
- تغییرات و خطرها: Select only the first untimed Inventory class and Publisher. Same file also contains InventoryWithTimer; exclude it entirely. FSM state and pending requests need full observation and supported transformation.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-48 — Routing Slip / Car Assembly

عبور سفارش از مراحل انتخابی

- خانواده: `routing_slip`
- انتخاب از منبع: `SlipRouter, PaintCar, AddNavigation, AddParkingSensors`
- کد ثابت: [chapter-routing/src/main/scala/aia/routing/SlipRouter.scala](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-routing/src/main/scala/aia/routing/SlipRouter.scala)
- درجه آماده‌سازی: `P2_ADAPTER_OR_BOUNDED_REPRESENTATION`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 6
- هدف معنایی: variable route over fixed actors and payload enrichment
- آزمایش کوتاه پیشنهادی: fixed color/navigation/sensor actors; orders with 2 option sets
- تغییرات و خطرها: Precreate fixed component actors and inject refs. Choosing a path through existing actors is not creating actors; if dynamic topology is also forbidden, fix the finite allowed route set explicitly. Seq[ActorRef]/nested messages need bounded representation.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-49 — Open-Write-Close Stash Protocol

نگه‌داشتن پیام تا بازشدن منبع

- خانواده: `stash_protocol`
- انتخاب از منبع: `ActorWithProtocol`
- کد ثابت: [akka-docs/src/test/scala/docs/actor/ActorDocSpec.scala](https://github.com/akka/akka-core/blob/044bb2dc0a3804d7fe33a1d3e988830256c108fa/akka-docs/src/test/scala/docs/actor/ActorDocSpec.scala)
- درجه آماده‌سازی: `P3_UNRESOLVED_FEATURE_GATE`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 2
- هدف معنایی: stash release order and behavior stack
- آزمایش کوتاه پیشنهادی: write before open; open; write; close
- تغییرات و خطرها: RESERVE. Stash is a second private queue, not the ordinary mailbox. Existing complete-post-mailbox comparison does not establish stash equivalence; source is only a protocol snippet, not a real file service.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

### ACSU-50 — Pausable Worker

یک کار در لحظه و ادامه با پیام Ready

- خانواده: `stash_protocol`
- انتخاب از منبع: `PausableActor with untimed completion worker`
- کد ثابت: [Chapter10/src/main/scala/com/packt/chapter10/PausableActor.scala](https://github.com/PacktPublishing/Akka-Cookbook/blob/ac64624036d75df5da76390d30e19d94333e6fa2/Chapter10/src/main/scala/com/packt/chapter10/PausableActor.scala)
- درجه آماده‌سازی: `P3_UNRESOLVED_FEATURE_GATE`
- تعداد تقریبی اکتور در نسخه کوچک پیشنهادی: 3
- هدف معنایی: backpressure, sender authentication and FIFO unstash
- آزمایش کوتاه پیشنهادی: Work(1), Work(2), bogus Ready, worker Ready
- تغییرات و خطرها: RESERVE. Preserve stash and behavior stack; use an explicit untimed worker, not original HardWorker's artificial delay. Selecting a replacement worker yields a documented benchmark composition, not the complete original app.
- وضعیت واقعی: هنوز نسخه نرمال‌شده ساخته، کامپایل یا اجرا نشده است.

## موارد مشهور که عمداً حذف شدند

| منبع/مثال | علت |
|---|---|
| [Savina actor-recursive Fibonacci](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/fib/FibonacciAkkaActorBenchmark.scala) | creates two child actors while handling Request. ACSU-42 deliberately uses another, single-actor Fibonacci implementation. |
| [Savina Quicksort](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/quicksort/QuickSortAkkaActorBenchmark.scala) | creates left/right actors during Sort handling. |
| [Savina Sieve](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/sieve/SieveAkkaActorBenchmark.scala) | creates next filter when a new prime arrives. |
| [Savina Facility Location](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/facloc/FacilityLocationAkkaActorBenchmark.scala) | creates quadrant children as data arrives. |
| [Savina UCT](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/uct/UctAkkaActorBenchmark.scala) | grows actor topology during processing; Renaissance akka-uct is not automatically an eligible replacement. |
| [Savina Sleeping Barber](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/barber/SleepingBarberAkkaActorBenchmark.scala) | customer factory creates customer actors at runtime. |
| [Savina SOR](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/sor/SucOverRelaxAkkaActorBenchmark.scala) | SorBootMessage invokes boot that creates grid actors; not admitted as-is. |
| [Savina FilterBank](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/filterbank/FilterBankAkkaActorBenchmark.scala) | main explicitly warns its Akka implementation deadlocks and needs debugging; not a known-good baseline. |
| [Savina timed Await banking](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/banking/BankingAkkaAwaitActorBenchmark.scala) | timed ask and Await inside application handler; ManualStash version alone is reserved. |
| [Savina priority search](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/astar/GuidedSearchAkkaPriorityActorBenchmark.scala) | priority mailbox does not match the stipulated Core Rebeca FIFO contract. |
| [Savina matrix multiplication](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/recmatmul/MatMulAkkaActorBenchmark.scala) | workers mutate shared MatMulConfig.C; violates no-shared-state assumptions. Local-array rewrite would be a DIFFERENT derived benchmark. |
| [Savina guided search](https://github.com/shamsimam/savina/blob/52e546959a57670cdba7a88f0a030b53cfdb16d6/src/main/scala/edu/rice/habanero/benchmarks/astar/GuidedSearchAkkaActorBenchmark.scala) | workers mutate shared graph parent state via setParent; excluded from pure-actor roster. |
| [Bita LoadBalancer](https://github.com/samira-t/Bita/blob/a3241fdea138799c0d6956571bcb7f4f8c8e0ddd/src/test/scala/sample/LoadBalancer.scala) | on-demand worker creation and Thread.sleep. |
| [Bita ProcessRegistry](https://github.com/samira-t/Bita/blob/a3241fdea138799c0d6956571bcb7f4f8c8e0ddd/src/test/scala/sample/ProcessRegistry.scala) | monitor creation during requests and timed ask/Await. |
| [Bita Messenger](https://github.com/samira-t/Bita/blob/a3241fdea138799c0d6956571bcb7f4f8c8e0ddd/src/test/scala/sample/Messenger.scala) | timed ask/Await in client handlers; not admitted unchanged. |
| [Bita SantaClaus](https://github.com/samira-t/Bita/blob/a3241fdea138799c0d6956571bcb7f4f8c8e0ddd/src/test/scala/sample/SantaClaus.scala) | timed ask/Await in secretary coordination. |
| [Akka in Action timed Inventory](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-state/src/main/scala/aia/state/Inventory.scala) | InventoryWithTimer has a state timeout; only Inventory + Publisher selected. |
| [Akka in Action GetLicense / performance router](https://github.com/RayRoestenburg/akka-in-action/blob/32b301d3042c832a016ca3220576960c43317630/chapter-routing/src/main/scala/aia/routing/Routing.scala) | Thread.sleep/serviceTime logic; only named untimed classes selected. |
| [Cookbook envelope app](https://github.com/PacktPublishing/Akka-Cookbook/blob/ac64624036d75df5da76390d30e19d94333e6fa2/Chapter10/src/main/scala/com/packt/chapter10/EnvelopingActorApp.scala) | application adds currentTimeMillis header; only constant-header EnvelopingActor kernel selected. |
| [Learning Akka Chatroom](https://github.com/jasongoodwin/learning-akka/blob/e96dd964b26ea4f98cb6b0531e02018ee3d4c109/ch8/scala-akka-chat/src/main/scala/com/akkachat/Chatroom.scala) | receive only handles joins; posting is unimplemented, so not a complete chat benchmark. |
| [Rock the JVM current akka-essentials](https://github.com/rockthejvm/akka-essentials/tree/9de45ace5fc4d9bea54d4b460d8512f8bfc7e5b4) | Inspected current files use akka.actor.typed; not Classic. |
| [Dining Hakkers official sample](https://github.com/akka/akka-samples/tree/767522ac64db040715dcc6da5d1c16c5fcf8406c/akka-sample-fsm-scala) | Timers/schedules for eating and thinking; untimed Savina arbitrator is a separate implementation. |
| [Scatter-gather-first-completed and tail-chopping](https://doc.akka.io/libraries/akka-core/current/routing.html) | Timing via within/interval is semantic; removing it creates another benchmark. |
| [Timed Ticket Service](https://rebeca-lang.org/allprojects/TAROExamples/TicketService) | Timed Rebeca reference is not an untimed Akka Classic example. |

## شش یافته مهم که انتخاب را تغییر دادند

۱. **Fibonacci دو شکل متفاوت دارد.** نسخه Savina در handler اکتور جدید می‌سازد و حذف شد. نسخه Akka Cookbook یک اکتور ثابت دارد و داخل یک متد عادی بازگشت می‌کند؛ فقط کلاس آن انتخاب شد و App زمان‌دارش کنار گذاشته شد. بازگشت تابع، dynamic actor creation نیست.

۲. **Sleeping Barber مشهور لزوماً مناسب نیست.** کارخانه مشتری در Savina هنگام کار اکتور جدید می‌سازد؛ صرف مشهوربودن یک مسئله آن را مناسب نمی‌کند.

۳. **Matrix Multiplication و Guided Search فقط مشکل اندازه ندارند.** کد بررسی‌شده از state قابل‌تغییر مشترک استفاده می‌کند. کوچک‌کردن ورودی این مشکل را از بین نمی‌برد. آنها را با دو مورد مناسب‌تر جایگزین کردیم.

۴. **FilterBank منبع سالم فرض نشد.** فایل اصلی خودش هشدار deadlock دارد. از آن به عنوان baseline صحیح استفاده نکردیم.

۵. **Bita LeaderElection عمداً buggy است.** موضوع مناسبی برای مقایسه ترجمه می‌تواند باشد: ترجمه باید رفتار همان منبع را حفظ کند، حتی اگر منبع bug داشته باشد. این با اثبات درستی الگوریتم انتخاب رهبر فرق دارد.

۶. **کلاس untimed در فایل timed ممکن است وجود داشته باشد.** مثلاً Inventory و InventoryWithTimer یا FibonacciActor و App آن. واحد انتخاب دقیقاً کلاس/هسته مشخص‌شده است، نه همه فایل یا همه پروژه.

## از فهرست به بنچمارک قابل اجرا: شروط پذیرش

برای هر مثال، این کارها جداگانه باید انجام شوند:

1. Snapshot منبع، commit، مجوز و hash فایل ثبت شود.
2. کلاس‌های انتخابی و مرز semantic model روشن شود؛ چه چیزی هسته برنامه و چه چیزی test harness است؟
3. تمام مسیرهای قابل‌دسترسی از receive، constructor، preStart و helperها برای actor creation و زمان بررسی شوند؛ جست‌وجوی regex به‌تنهایی کافی نیست.
4. به صورت پویا نیز بعد از پایان bootstrap ثابت‌بودن مجموعه اکتورهای برنامه کنترل شود. اکتورهای داخلی runtime از اکتورهای موضوع آزمایش جدا هستند.
5. پیام‌های scalar/case-class، state خصوصی، ActorRefها، مجموعه‌ها و حالت رفتار نگاشت شوند. داده نامشخص را نباید حذف یا به یک placeholder یکسان تبدیل کرد.
6. تعداد اکتورها و دامنه ورودی پیش از تولید ترجمه تثبیت شود. برای شروع ۲ تا ۵ اکتور، ۱ تا ۳ دور و ۳ تا ۸ پیام پیشنهاد می‌شود، نه یک قاعده معتبر برای همه منابع. بانک Savina نمونه نقض مهم است: منبع تولید تصادفی‌اش حداقل ده حساب لازم دارد.
7. تغییرات رفتارمحور مانند حذف stash، تعویض hash با modulo، شکستن batch به چند پیام، جایگزینی double با int یا تغییر stop به active=false تغییر خنثی نیستند.
8. wrapper استاندارد و instrumented Akka با نسخه اصلی در دامنه محدود مقایسه شوند؛ ابزار مشاهده نباید معنای برنامه را عوض کند.
9. compile Akka و syntax/codegen RMC موفق شوند.
10. baseline صحیح، حداقل یک mutant مستقل و نمونه‌های مرزی اجرا شوند. منبع intentionally buggy baseline صحیح الگوریتم محسوب نمی‌شود.
11. FIFO ابتدایی، sender/receiver/args، state و تمام صف‌های لازم در نقاط متناظر بررسی شوند. برای state رفتار، stash و کتابخانه‌ها قرارداد اضافی لازم است.
12. هر تست باید معلوم کند handler موردنظر واقعاً اجرا شده؛ صرف تولید ورودی یا ۱۰۰٪ message coverage کافی نیست.
13. تکمیل state space و نبود overflow بررسی شود. overflow یک مدل با صف محدود، به‌تنهایی counterexample برابری با Akka بدون کران صف نیست؛ جدا گزارش شود و در صورت نیاز ظرفیت هر دو سمت همسان شود.
14. پس از عبور از مراحل بالا admission از PENDING به ADMITTED تغییر کند. در این بررسی هیچ موردی به ADMITTED تغییر نکرده است.

## پیشنهاد اجرای پژوهش

### موج اول: ۸ مثال کوچک

ACSU-01 Echo، ACSU-03 Adder، ACSU-04 Calculator، ACSU-05 Accumulator، ACSU-06 Ping-Pong، ACSU-07 Counting، ACSU-11 Relay، ACSU-16 ThreadRing.

این موج عمدتاً دامنه کوچک و رفتار واضح دارد. Ping-Pong کنترل موجود پروژه است، نه شاهد جدید مستقل. از translated outputs واقعی LLM استفاده شود و محدودیت‌های ابزار ثبت شوند.

### موج دوم: تنوع state و شبکه

SpeedFilter، TicketSeller، BoundedBuffer، Dictionary، Chameneos، ShortestPath و Local Fibonacci، سپس Inventory و RoutingSlip. موردهای مربوط به Map/String/ActorRef و مجموعه‌ها فقط پس از عبور از gate مربوط اجرا شوند.

### موج سوم: پیشرفته یا ذخیره

ابتدا sorting و APSP در ابعاد کوچک؛ سپس فقط در صورت نیاز پژوهش، stash/EventBus/hash/decimal. برای رسیدن به عدد ۵۰، توسعه بی‌پایان ابزار یا تغییر معنی منابع توجیه ندارد.

### قرارداد مقایسه برای ترجمه‌های LLM

- input Akka اصلی/نرمال‌شده پیش از فراخوانی LLM ثابت شود و هش آن ثبت گردد.
- خروجی خام LLM بدون اصلاح دستی نگه‌داری شود.
- نگاشت نام actor/message/state جداگانه تعریف و کنترل شود. نام‌های متفاوت الزاماً خطای معنایی نیستند.
- نسخه خام، نسخه حاصل از feedback و نسخه adapter هرکدام شناسه مستقل داشته باشند.
- budget پیام، seedهای ورودی و تعداد اجراهای مختلف زمان‌بندی ثابت گزارش شوند. seed ورودی لزوماً seed scheduler Akka نیست.
- شباهت scalar state به تنهایی مشاهده کامل نیست؛ state حذف‌شده، رفتار become یا stash می‌تواند موجب پذیرش بی‌معنا شود.
- MATCH یعنی این اجرای محدود Akka در مدل Rebeca مسیر متناظر داشت؛ نه اینکه تمام رفتارهای دو طرف برابرند.
- هنگام عدم تطبیق، اول نگاشت، صف اولیه، قرارداد مشاهده، زمان‌بندی و کامل‌بودن فضای حالت را کنترل کنیم؛ سپس اختلاف را به ترجمه نسبت دهیم.
- ۵۰ workload در ۳۴ خانواده‌اند. نتایج هم به تفکیک workload و هم خانواده گزارش شود تا چند گونه از یک موضوع آمار را باد نکنند.
- پوشش‌های پیام/پارامتر/شاخه شاخص کفایت تست‌اند؛ به تنهایی اثبات هم‌ارزی نیستند.
- مجموعه‌های استفاده‌شده در RAG/few-shot باید از test split جدا شوند؛ مثال‌های توسعه قبلی پروژه کنترل‌اند، نه holdout پاک.
- برای کاربرد پایان‌نامه هدف تشخیص خطای ترجمه است؛ اعداد performance گزارش‌شده در Savina مستقیماً نتیجه کار ما نیستند.

## خروجی این بسته و کار باقی‌مانده

این بسته شامل همین گزارش و manifest ماشین‌خوان است. منبع‌های کامل یا PDFهای دارای حق نشر بازتوزیع نشده‌اند؛ فقط نشانی ثابت و فراداده آمده است. فایل LICENSE هر مخزن نیز در manifest لینک شده است.

کار انجام‌شده: جست‌وجو، بازیابی کدهای منتخب، غربال‌گری محدودیت‌ها، انتخاب ۵۰ workload، ثبت خطرها و مرزهای سازگارسازی، تثبیت نسخه منبع.

کار انجام‌نشده: نوشتن ۵۰ فایل استاندارد Scala، ساخت همه مدل‌های Rebeca، اجرای ۵۰ campaign، اثبات حفظ رفتار adapterها و پذیرش نهایی تمام مثال‌ها.

**نتیجه دقیق: یک نقشه اجرایی ۵۰تایی داریم؛ نه ادعای غیرواقعی ۵۰ بنچمارک آماده.**

