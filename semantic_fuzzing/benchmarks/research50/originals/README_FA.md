# کدهای منبع فهرست ۵۰تایی Akka Classic

این بسته کدهای واقعی همان ۵۰ مورد فهرست پژوهشی قبلی را دارد؛ فقط لینک یا شرح نیست.

## از کجا شروع کنم؟

۱. پوشه `benchmarks` را باز کن.
۲. هر یک از ۵۰ مورد پوشه شماره‌دار جدا دارد.
۳. داخل هر پوشه، فایل Scala واقعی در `source` و راهنمای انتخاب در `README_FA.md` است.
۴. فایل `case.json` منبع، نسخه، کلاس انتخابی و محدودیت‌ها را ثبت می‌کند.
۵. کدهای کمکی مرتبط، تنظیمات موجود و فایل‌های اصل منبع در `upstream` هستند.

## وضعیت دقیق بسته

این بسته آرشیو منبع است، نه ۵۰ پروژه مستقلِ سازگارشده و تست‌شده. فهرست قبلی شامل بعضی کلاس‌ها، قطعه‌کدهای مستندات، الگوهای کتابخانه‌ای و ترکیب‌های پیشنهادی بود. بنابراین چند پوشه از فایل اصلی مشترک استفاده می‌کنند. هر فایل اصلی بدون تغییر نگه داشته شده تا منبع تحریف نشود.

**۵۰ مورد فهرست به ۳۷ فایل اصلی یکتا ارجاع دارند و در ۳۴ خانواده موضوعی قرار می‌گیرند.** کد واقعی هر ۵۰ مورد در پوشه خودش کپی شده است. فایل‌های کمکی هم جدا آمده‌اند. این تعداد به معنی ۵۰ الگوریتم مستقل نیست.

کل فایل اصلی لزوماً فاقد زمان یا ایجاد اکتور نیست؛ برای فایل‌های چندمثالی باید فقط کلاس‌ها و هسته‌های نام‌برده‌شده را انتخاب کنیم. نسخه نهایی پذیرفته‌شده باید فقط Akka Classic، دارای همه اکتورهای ثابت پیش از شروع، بی‌زمان و بدون state قابل‌تغییر مشترک باشد. این شروط هنوز برای یک نسخه اجرایی نرمال‌شده از همه موارد تأیید نشده‌اند.

برای مثال FibonacciActor انتخاب‌شده یک اکتور ثابت است، اما App کنار آن ask زمان‌دار دارد و انتخاب نشده است. Inventory انتخاب‌شده untimed است، ولی InventoryWithTimer در همان فایل کنار گذاشته شده است.

ساختار `upstream` یک clone کاملِ شش مخزن نیست؛ فایل‌های اصلی و فایل‌های کمکی مرتبط دریافت‌شده را نگه می‌دارد. به‌خصوص کدهای رسمی Akka داخل پروژه تست اصلی خود وابستگی دارند. وجود build metadata، تضمین build مستقل این زیرمجموعه نیست. برای build اصلی می‌توان به commit و README مخزن مراجعه کرد.

در این درخواست کدها بازنویسی، compile یا اجرا نشده‌اند. بنابراین از این بسته نباید ادعای «۵۰ بنچمارک آماده اجرا و بدون dynamic creation/time» برداشت کرد.

## صحت فایل‌ها

- تمام ۱۱۵ فایل دریافت‌شده با Git blob SHA-1 نسخه منبع مطابقت داده شده‌اند.
- `SOURCE_INDEX.json` برای هر فایل URL، commit، Git blob و SHA-256 را دارد.
- `SHA256SUMS` برای محتوای بسته است.
- برای بررسی پس از extract: `python3 verify_bundle.py`
- این بررسی صحت محتوا و وجود ۵۰ پوشه را کنترل می‌کند؛ تست compile یا صحت معنایی نیست.

## مجوز و انتساب

مجوز هر شش مخزن در `LICENSES` و در مسیر اصلی `upstream` حفظ شده است. کدها متعلق به نویسندگان اصلی‌اند. شرح و فراداده انتخاب پژوهشی جداگانه مشخص شده‌اند. برای بازتوزیع کدهای مشتق‌شده، مجوز منبع مربوط را حفظ کنید.

## فهرست

| شماره | مثال | پوشه | کلید منبع |
|---|---|---|---|
| 01 | Echo | `benchmarks/01_echo` | A |
| 02 | Key-Value Cache | `benchmarks/02_cache` | A |
| 03 | Parameterized Adder | `benchmarks/03_adder` | A |
| 04 | Integer Calculator | `benchmarks/04_calculator` | C |
| 05 | Summing Accumulator | `benchmarks/05_accumulator` | C |
| 06 | Finite Ping-Pong | `benchmarks/06_ping_pong` | S |
| 07 | Counting | `benchmarks/07_counting` | S |
| 08 | Fixed Fan-out Throughput Kernel | `benchmarks/08_throughput` | S |
| 09 | Swapper | `benchmarks/09_swapper` | A |
| 10 | Hot-Swap Actor | `benchmarks/10_hot_swap` | A |
| 11 | Redirect Relay | `benchmarks/11_relay` | I |
| 12 | Speed Threshold Filter | `benchmarks/12_speed_filter` | I |
| 13 | License Validity Filter | `benchmarks/13_license_filter` | I |
| 14 | Two-Stage Filter Pipeline | `benchmarks/14_filter_pipeline` | I |
| 15 | Producer/Consumer Roles | `benchmarks/15_producer_consumer_roles` | A |
| 16 | Thread Ring | `benchmarks/16_thread_ring` | S |
| 17 | Big All-to-All | `benchmarks/17_big` | S |
| 18 | Fixed Round-Robin Routing | `benchmarks/18_round_robin` | A |
| 19 | Fixed Broadcast Routing | `benchmarks/19_broadcast` | A |
| 20 | Consistent-Hash Cache Routing | `benchmarks/20_consistent_hash` | A |
| 21 | Lookup Publish/Subscribe | `benchmarks/21_pubsub_lookup` | A |
| 22 | Hierarchical Publish/Subscribe | `benchmarks/22_pubsub_hierarchical` | A |
| 23 | Predicate Publish/Subscribe | `benchmarks/23_pubsub_predicate` | A |
| 24 | Content-Based Speed Router | `benchmarks/24_content_router` | I |
| 25 | Switchable Router | `benchmarks/25_switch_router` | I |
| 26 | Envelope Enrichment | `benchmarks/26_envelope` | C |
| 27 | Correlation Join | `benchmarks/27_correlation_gather` | I |
| 28 | Ticket Seller | `benchmarks/28_ticket_seller` | I |
| 29 | Bounded Producer-Consumer | `benchmarks/29_bounded_buffer` | S |
| 30 | Concurrent Dictionary | `benchmarks/30_concurrent_dictionary` | S |
| 31 | Concurrent Sorted List | `benchmarks/31_sorted_list` | S |
| 32 | Chameneos | `benchmarks/32_chameneos` | S |
| 33 | Dining Philosophers / Arbitrator | `benchmarks/33_dining_philosophers` | S |
| 34 | Cigarette Smokers | `benchmarks/34_cigarette_smokers` | S |
| 35 | Distributed Single-Source Shortest Path | `benchmarks/35_shortest_path` | B |
| 36 | Capture-Based Leader Election | `benchmarks/36_leader_election` | B |
| 37 | Asynchronous Bank Transactions | `benchmarks/37_bank_transactions` | S |
| 38 | Logistic Map Series | `benchmarks/38_logistic_map` | S |
| 39 | Radix Sort Pipeline | `benchmarks/39_radix_sort` | S |
| 40 | Bitonic Sorting Network | `benchmarks/40_bitonic_sort` | S |
| 41 | All-Pairs Shortest Path | `benchmarks/41_apsp` | S |
| 42 | Single-Actor Fibonacci | `benchmarks/42_local_fibonacci` | C |
| 43 | Batched Key-Value Requests | `benchmarks/43_batched_kv` | L |
| 44 | N-Queens / FIFO Variant | `benchmarks/44_nqueens` | S |
| 45 | Trapezoidal Integration | `benchmarks/45_trapezoidal` | S |
| 46 | Precise Pi Computation | `benchmarks/46_precise_pi` | S |
| 47 | Untimed Inventory FSM | `benchmarks/47_inventory_fsm` | I |
| 48 | Routing Slip / Car Assembly | `benchmarks/48_routing_slip` | I |
| 49 | Open-Write-Close Stash Protocol | `benchmarks/49_open_write_close` | A |
| 50 | Pausable Worker | `benchmarks/50_pausable_worker` | C |
