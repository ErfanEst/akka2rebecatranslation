# شش مثال سازگار برای ترجمه و فازتستینگ

این مثال‌ها برای محدودهٔ فعلی موتور ساخته شده‌اند: Scala 2.13، Akka Classic،
ساخت ایستای actorها در شیء `App`، پیام‌های `case class`/`case object`، stateهای
`Int` و `Boolean`، و شاخه‌های مستقیم `if/else`. هیچ مثال از ساخت پویای actor،
Akka Typed، scheduler/زمان، Future/callback، loop، exception، collection یا
پیام زمان‌دار استفاده نمی‌کند.

| سطح | مثال | موضوع اصلی |
| --- | --- | --- |
| ساده | `SimpleCounter` | state عددی، پیام پارامتردار و Reset |
| ساده | `SimpleThreshold` | یک شرط مرزی مستقیم روی پارامتر |
| متوسط | `MediumWallet` | رفتار وابسته به تاریخچه و توالی Credit/Debit |
| متوسط | `MediumInventoryAudit` | شاخهٔ stateful و ارسال داخلی به actor دوم |
| سخت | `HardOrderWorkflow` | توالی سه‌مرحله‌ای و زنجیرهٔ Order→Warehouse→Audit |
| سخت | `HardTransferWorkflow` | چهار actor ایستا، شاخهٔ موفق/ناموفق و چند hop |

از ریشهٔ `akka2rebecatranslation` و بعد از فعال‌سازی محیط اجرا کنید. مثال اول:

```bash
python -m semantic_fuzzing \
  --config semantic_fuzzing/examples/configs/simple_counter.json \
  translate \
  --akka-source semantic_fuzzing/examples/akka/SimpleCounter.scala \
  --translation-config semantic_fuzzing/translation.handbook.example.json \
  --output ../runs/simple-counter-01
```

برای پنج مثال دیگر، نام فایل و config را مطابق جدول زیر عوض کنید:

| Akka source | config |
| --- | --- |
| `SimpleThreshold.scala` | `simple_threshold.json` |
| `MediumWallet.scala` | `medium_wallet.json` |
| `MediumInventoryAudit.scala` | `medium_inventory_audit.json` |
| `HardOrderWorkflow.scala` | `hard_order_workflow.json` |
| `HardTransferWorkflow.scala` | `hard_transfer_workflow.json` |

هر بار یک مسیر `--output` تازه بدهید. فایل‌های config فرض می‌کنند دو repository
کنار هم و `.semantic-fuzzing-tools` در پوشهٔ والد آن‌هاست؛ این همان ساختاری است
که `semantic_fuzzing/setup.sh` می‌سازد. تعداد caseها برای هزینه و زمان مناسبِ
اجرای اولیه کوچک است؛ برای آزمایش پایان‌نامه آن را با آگاهی از هزینه افزایش دهید.

`generation_specs` تست را تعریف می‌کنند، نه رفتار برنامه را. `bind` یک مقدار
تولید می‌کند و `use` همان مقدار را در مرحلهٔ بعد به‌کار می‌برد. این کار برای
رسیدن قطعی به رفتارهای وابسته به تاریخچه لازم است. `BOUNDED_MATCH` فقط نتیجهٔ
همین bounds و سناریوهاست و اثبات هم‌ارزی کامل نیست.
