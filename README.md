# Market Intelligence Lab

مختبر محلي باللغة العربية لأبحاث السوق التاريخية، والتحليل الكمي القابل للتكرار، والتقارير متعددة الوكلاء، والاختبار التاريخي، والمحفظة الافتراضية. الواجهة مبنية على Streamlit وتعمل على Windows. **لا ينفذ التطبيق صفقات حقيقية ولا يتصل بواجهات الحسابات الخاصة.**

> السيناريو الصاعد/الهابط تصنيف وصفي مبني على قواعد معلنة، وليس توصية استثمارية أو احتمالًا معايرًا أو ضمانًا لنتيجة مربحة. الاختبارات التاريخية والمحفظة افتراضية ولا تتنبأ بالمستقبل.

## ما الذي يتضمنه المشروع؟

- أربع وحدات تحليل مستقلة: البنية الفنية، الأخبار والأحداث، بنية الموجات/فيبوناتشي، والمراجعة الكمية للمخاطر.
- منسّق يتحقق من البيانات، يستدعي الوكلاء، يحفظ تقاريرهم، ويختار واحدًا من: `BULLISH SCENARIO` أو `BEARISH SCENARIO` أو `NEUTRAL / RANGE-BOUND` أو `INCONCLUSIVE`.
- مؤشرات RSI وMACD وSMA وEMA وATR وBollinger Bands والحجم النسبي؛ القيم الرقمية تحسب في Python ولا تعتمد على نموذج لغوي.
- وضع `DEMO DATA` يعمل بلا إنترنت أو مفاتيح API. الشموع في هذا الوضع **اصطناعية بالكامل** ومولّدة محليًا لغرض الاختبار والعرض، وليست أسعارًا حقيقية.
- مصدر اختياري لبيانات OHLCV العامة عبر CCXT، مع مهلة اتصال، محدد معدل الطلبات، إعادة محاولة محدودة، وتخزين مؤقت قصير. قد لا يدعم كل مصدر جميع الأصول والأطر الزمنية.
- موائم أخبار عام مبني على GDELT DOC API. لا يجلب نص المقالات ولا يتجاوز الحواجز المدفوعة. التمييز الإيجابي/السلبي مطابقة كلمات وصفية وليس تحليلًا سببيًا مؤكدًا.
- اختبار تاريخي لاستراتيجية تقاطع متوسطات بسيطة. تُزاح الإشارة شمعة واحدة، وتطبق رسوم وانزلاق قابلان للضبط؛ تظهر فترة تقييم زمنية منفصلة عن فترة التهيئة.
- محفظة افتراضية مستقلة مخزنة محليًا عبر SQLite؛ كل عملية موسومة بأنها افتراضية.
- اختبارات آلية حتمية لا تحتاج إلى API حقيقي.

## المتطلبات

- Windows 10 أو 11.
- Python 3.11–3.14. تم فحص بيئة التطوير المستخدمة لبناء هذا الإصدار على Python 3.13.5. لا يقوم المثبّت بتغيير Python العام؛ ينشئ `.venv` محليًا.
- اتصال إنترنت فقط إذا أردت تثبيت المكتبات أو استخدام مصادر الأخبار/السوق العامة. لا توجد مفاتيح مدفوعة مطلوبة للوضع التجريبي.

## التثبيت على Windows

1. فك ضغط مجلد `market_intelligence_lab` في موقع تملكه.
2. افتح المجلد.
3. شغّل `setup.bat` بالنقر المزدوج. يفحص Python، ينشئ `.venv`، ثم يثبت المكتبات من `requirements.txt`.
4. شغّل `run_app.bat`.
5. ستظهر في نافذة الأوامر وصلة محلية، غالبًا `http://localhost:8501`. افتحها في المتصفح على نفس الجهاز.

### التثبيت والتشغيل يدويًا

من موجه الأوامر داخل مجلد المشروع:

```bat
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

إن لم يكن لديك Python 3.13، استخدم `py -3` لإصدار مدعوم مثبت لديك، أو حدّث أول سطر لرقم الإصدار الموجود. لا تحتاج لتفعيل البيئة افتراضيًا؛ استخدام ` .venv\Scripts\python.exe` يجعل المفسّر المستخدم واضحًا.

## تشغيل الاختبارات

```bat
.venv\Scripts\python.exe -m pytest -q
```

يجب أن تنجح الاختبارات دون طلب بيانات خارجية. تستخدم الشبكة في اختبارات المزوّدات محاكاة داخلية، ولا يتصل الاختبار بمنصة تداول.

## استعمال لوحة التحكم

- عند أول تشغيل تظهر بيانات اصطناعية محلية موسومة `DEMO DATA`؛ وهذا مقصود حتى تعمل الواجهة من دون اتصال خارجي.
- اختر الأصل والإطار وعدد الشموع من الشريط الجانبي، ثم اضغط **تشغيل / تحديث التحليل** لتطبيق الخيارات الجديدة.
- لاختيار البيانات العامة، اختر مصدرًا عامًا عبر CCXT. يتطلب ذلك اتصالًا وتوفر الأصل/الإطار لدى المصدر. نجاح استدعاء عام لا يعني ضمان حداثة كل حقل؛ يتحقق التطبيق من الطوابع الزمنية ويظهر التحذيرات.
- لتشغيل الأخبار، فعّل خيار البحث عند التحليل أو افتح تبويب **الأخبار والأحداث** واضغط تحديث GDELT. إن تعذر المصدر، تُعرض الحالة كغير متاحة ولا يتم تركيب عناوين بديلة.
- في تبويب الوكلاء افتح كل لوحة لمراجعة النتائج والأدلة المتعارضة والمستويات والقيود.
- في الاختبار التاريخي، فترة البيانات الأخيرة تُعامل كفترة تقييم بعد فصل زمني. لا يوجد ضبط تلقائي للمعلمات، ولا تُرسل أوامر.
- في المحفظة الافتراضية أدخل عمليات BUY/SELL محاكية فقط؛ تُحفظ في SQLite ويمكن إعادة ضبط السجل بعد التأكيد.

## الوثائق الرسمية المستخدمة

- Streamlit installation and virtual environments: https://docs.streamlit.io/get-started/installation/command-line
- CCXT public OHLCV and rate limiting: https://github.com/ccxt/ccxt/wiki/Manual
- GDELT DOC API: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
- Plotly charts in Streamlit: https://docs.streamlit.io/develop/api-reference/charts/st.plotly_chart

## مصادر البيانات وحدودها

- السوق: موائم CCXT يستخدم `fetch_ohlcv` العام و`enableRateLimit=True`. ليست كل منصة أو زوج أو إطار مدعومًا. قد تعيد المنصة شمعة غير مكتملة؛ يوضح التطبيق ذلك ولا يتعامل مع الاستدعاء كضمان لخلو البيانات من التأخير.
- الأخبار: GDELT DOC API العام؛ التغطية واللغة والتوقيت والأرشفة ليست شاملة. توقيت ظهور المقال في مصدر تجميعي قد لا يساوي لحظة وقوع الحدث. الأخبار المعادة تُعرض بروابطها الأصلية.
- العملات: هذا الإصدار يطبّع شموع العملات الرقمية الفورية فقط. لا تخلط أطر بيانات Forex أو الأسهم مع هذه المخططات؛ عند إضافة سوق جديد أنشئ موائمًا ومخطط بيانات مميزًا.
- لا توجد بيانات سوق مدمجة حقيقية. كل بيانات العرض دون مزوّد خارجي هي بيانات اصطناعية بوسم واضح.

## الملفات المهمة

```text
agents/                 الوكلاء الأربعة
analysis/               المؤشرات وبنية السوق والموجات
backtesting/            محرك الاختبار ومقاييسه والمحفظة الافتراضية
data/                   موائمات السوق والأخبار والتحقق والتخزين المؤقت والبيانات التجريبية
orchestration/          مخططات المخرجات والتحقق والمنسّق
storage/                قاعدة SQLite ومستودعاتها
ui/                     مكوّنات لوحة التحكم والرسوم والتقارير
tests/                  اختبارات pytest
app.py                  نقطة دخول Streamlit
setup.bat               تثبيت Windows
run_app.bat             تشغيل Windows
requirements.txt        الاعتمادات
.env.example            أسماء متغيرات اختيارية فقط — بلا أسرار
```

## التخزين والخصوصية

القاعدة المحلية الافتراضية هي `market_intelligence_lab.sqlite3` داخل مجلد المشروع. يمكن تعيين `MIL_DATABASE_PATH` إلى مسار آخر. لا يسجل التطبيق مفاتيح API أو كلمات مرور؛ ويفضل عدم وضع أسرار حساسة في ملفات البيئة. `LLM_PROVIDER` و`LLM_API_BASE_URL` و`LLM_API_KEY` و`LLM_MODEL` موضوعة كأسماء/عناصر نائبة فقط. **لا يوجد تكامل نموذج لغوي نشط في هذا الإصدار** ولا يتم طلب نموذج عند التشغيل.

## ما الذي لم يُنفذ بعد؟

- لا توجد استنتاجات مالية مدعومة بنموذج لغة؛ التحليل الكمي وقواعد التفسير محلية ومحددة.
- موائم GDELT مصدر واحد اختياري، ولا توجد خدمة مدفوعة أو مصادر اقتصادية كلية موثقة متعددة.
- تحليل الموجات تخميني/قائم على نقاط انعطاف محلية وليس عدًّا Elliott رسميًا ولا يمكنه تحديد موجة صحيحة وحيدة.
- لا توجد معايرة احتمالية، أو تنفيذ حي، أو مراكز بيع على المكشوف، أو رافعة مالية، أو تداول عقود آجلة، أو اتصال بحساب خاص.
- اختبارات تاريخية سليمة وظيفيًا لا تعني وجود ميزة ربحية؛ نموذج الإعدام بسيط، وتكاليف السوق والسيولة والتنفيذ الواقعي ليست ممثلة بالكامل.

---

## Native Windows desktop application (new)

The project now includes a native desktop interface in `desktop_app.py`, built with PySide6. It reuses the existing analysis agents, orchestrator, backtesting engine, paper portfolio, and SQLite storage. The desktop shell is separate from the original Streamlit app, so the existing `app.py` has not been overwritten.

### Install and launch

1. Extract the project ZIP to a normal writable folder.
2. Install Python 3.11, 3.12, or 3.13 if it is not already installed. The setup script does not replace system Python.
3. Double-click `setup_desktop.bat`. It creates `.venv`, installs the desktop dependencies, and runs the test suite.
4. Double-click `run_desktop.bat`.

### Build a Windows executable

After `setup_desktop.bat` completes, run `build_exe.bat`. PyInstaller will create a folder at `dist\MarketIntelligenceLab\` containing `MarketIntelligenceLab.exe` and its bundled runtime files. Keep that folder intact. The executable build must be performed and verified on Windows; a successful build is not claimed until this command has completed successfully on a Windows machine.

### Desktop interface contents

- Arabic-first, right-to-left desktop interface with a dark dashboard.
- Overview and consolidated report.
- Separate reports for each of the four agents.
- A lightweight Qt-drawn candlestick chart and recent-candle table.
- Historical SMA-crossover backtest with configurable fees and slippage.
- SQLite-backed paper portfolio, simulated trades, and reset confirmation.
- Settings and explicit data-source / demo-data warnings.

### Important verification note

The desktop source file passes Python syntax compilation, and the existing automated suite passes. PySide6 is not installed in the development execution environment used to prepare this package, so a live GUI/browser smoke test and Windows executable build have **not** been performed here. Run `setup_desktop.bat` and verify the app on Windows before relying on it. Demo candles are synthetic, never live prices; no real orders are sent.
