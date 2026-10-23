"""Market Intelligence Lab — Arabic-first research and paper-simulation dashboard."""
from __future__ import annotations
import logging
import os
from pathlib import Path
import streamlit as st
import pandas as pd

from data.demo_data import demo_result
from data.crypto_provider import CryptoMarketProvider
from data.news_provider import GdeltNewsProvider
from agents.news_agent import NewsEventAgent
from orchestration.orchestrator import AnalysisOrchestrator
from storage.database import Database
from storage.repositories import Repository
from backtesting.paper_portfolio import PaperPortfolio
from ui.charts import make_market_chart, make_indicator_chart
from ui.agents_view import render_agents
from ui.reports_view import render_report, LABELS
from ui.news_view import render_news
from ui.backtesting_view import render_backtesting
from ui.portfolio_view import render_portfolio
from ui.settings_view import render_settings
from orchestration.schemas import MarketClassification

APP_DIR = Path(__file__).resolve().parent
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[logging.StreamHandler()])
logger = logging.getLogger("market_intelligence_lab")

st.set_page_config(page_title="مختبر استخبارات السوق", page_icon="📊", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
html, body, [class*="css"] { direction: rtl; }
[data-testid="stAppViewContainer"] { direction: rtl; }
[data-testid="stSidebar"] { direction: rtl; }
[data-testid="stMarkdownContainer"] { text-align: right; }
[data-testid="stMetricLabel"] { text-align: right; }
div[data-testid="stAlert"] { direction: rtl; }
.block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
small { direction: rtl; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_database() -> Database:
    db_path = os.environ.get("MIL_DATABASE_PATH")
    return Database(db_path) if db_path else Database(APP_DIR / "market_intelligence_lab.sqlite3")

@st.cache_resource
def get_repository() -> Repository:
    return Repository(get_database())

@st.cache_resource
def get_portfolio() -> PaperPortfolio:
    return PaperPortfolio(get_repository())

repo = get_repository()
portfolio = get_portfolio()

st.title("📊 مختبر استخبارات السوق متعددة الوكلاء")
st.caption("Market Intelligence Lab · بحث تاريخي وتحليل كمي ومحفظة افتراضية — لا توجد أوامر تداول حقيقية.")
st.info("**تنبيه ثابت:** التصنيفات سيناريوهات تعليمية وليست توصيات شخصية أو ضمانًا للربح. راجع مصدر البيانات وحداثتها قبل تفسير النتائج.")

source_options = ["DEMO DATA — بيانات اصطناعية", "بيانات عامة من منصة عبر CCXT"]
exchange_options = ["binance", "kraken", "coinbase"]
asset_options = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT", "XRP/USDT"]
timeframe_options = ["15m", "1h", "4h", "1d", "1w"]
saved_source = repo.get_preference("market_source_mode", source_options[0])
saved_asset = repo.get_preference("default_asset", "BTC/USDT")
saved_timeframe = repo.get_preference("default_timeframe", "1h")
saved_exchange = repo.get_preference("market_exchange", "binance")
saved_limit = int(repo.get_preference("candle_limit", 500))
saved_cache_ttl = int(repo.get_preference("cache_ttl_seconds", 60))
saved_news_enabled = bool(repo.get_preference("news_enabled", False))
with st.sidebar:
    st.header("إعداد التحليل")
    source_mode = st.selectbox("مصدر بيانات السوق", source_options, index=source_options.index(saved_source) if saved_source in source_options else 0)
    exchange_id = st.selectbox("مصدر السوق العام", exchange_options, index=exchange_options.index(saved_exchange) if saved_exchange in exchange_options else 0, disabled=source_mode.startswith("DEMO"))
    asset = st.selectbox("الأصل", asset_options, index=asset_options.index(saved_asset) if saved_asset in asset_options else 0)
    timeframe = st.selectbox("الإطار الزمني", timeframe_options, index=timeframe_options.index(saved_timeframe) if saved_timeframe in timeframe_options else 1)
    candle_limit = st.slider("عدد الشموع المطلوبة", min_value=100, max_value=1000, value=max(100, min(saved_limit, 1000)), step=100)
    cache_ttl = st.slider("مدة التخزين المؤقت (ثانية)", min_value=0, max_value=300, value=max(0, min(saved_cache_ttl, 300)), step=30, disabled=source_mode.startswith("DEMO"))
    fetch_news = st.checkbox("البحث في الأخبار العامة عند التحليل", value=saved_news_enabled, help="يستخدم GDELT DOC API العام؛ قد لا يعيد نتائج أو قد يتعذر الوصول إليه.")
    run_clicked = st.button("تشغيل / تحديث التحليل", type="primary", width="stretch")
    st.divider()
    st.caption("الوضع الأولي تجريبي محلي، ولا يحتاج مفتاح API أو اتصالًا خارجيًا.")

if "market_result" not in st.session_state:
    # Even when the user's last selected source was public, startup data remain explicitly demo-labelled
    # until a fresh public request is triggered; a previous preference is not evidence of a live feed.
    startup_asset = saved_asset if saved_asset in asset_options else "BTC/USDT"
    startup_timeframe = saved_timeframe if saved_timeframe in timeframe_options else "1h"
    initial_result = demo_result(startup_asset, startup_timeframe, max(100, min(saved_limit, 1000)))
    initial_orchestrator = AnalysisOrchestrator(news_provider=None, repository=repo)
    initial_marks = {initial_result.asset: float(initial_result.candles["close"].iloc[-1])}
    normalized_result, initial_report = initial_orchestrator.analyze(initial_result.asset, initial_result.timeframe,
        market_result=initial_result, portfolio_summary=portfolio.state(initial_marks))
    st.session_state["market_result"] = normalized_result
    st.session_state["consolidated_report"] = initial_report
    st.session_state["selected_asset"] = initial_result.asset
    st.session_state["selected_timeframe"] = initial_result.timeframe
    st.session_state["news_override"] = None
    st.session_state["run_metadata"] = {"source_mode": "DEMO DATA — بيانات اصطناعية", "exchange": None,
        "news_enabled": False, "cache_ttl_seconds": saved_cache_ttl}

if run_clicked:
    with st.spinner("جارٍ الحصول على البيانات والتحقق منها وتشغيل الوكلاء الأربعة..."):
        market_provider = None
        market_result = None
        news_provider = GdeltNewsProvider() if fetch_news else None
        if source_mode.startswith("DEMO"):
            market_result = demo_result(asset, timeframe, candle_limit)
            orchestrator = AnalysisOrchestrator(news_provider=news_provider, repository=repo)
            current_marks = {asset: float(market_result.candles["close"].iloc[-1])} if not market_result.candles.empty else {}
            updated_result, final_report = orchestrator.analyze(asset, timeframe, market_result=market_result,
                portfolio_summary=portfolio.state(current_marks))
        else:
            try:
                market_provider = CryptoMarketProvider(exchange_id=exchange_id, cache_ttl=cache_ttl)
                orchestrator = AnalysisOrchestrator(market_provider=market_provider, news_provider=news_provider, repository=repo)
                updated_result, final_report = orchestrator.analyze(asset, timeframe, limit=candle_limit,
                    portfolio_summary=portfolio.state())
            except Exception as exc:
                logger.exception("User-triggered analysis failed")
                st.error(f"تعذر تشغيل مصدر السوق: {type(exc).__name__}: {exc}")
                class FailedMarketProvider:
                    def fetch_ohlcv(self, requested_asset, requested_timeframe, limit=500):
                        raise RuntimeError(f"Public provider setup failed ({type(exc).__name__}).")
                failed_orchestrator = AnalysisOrchestrator(market_provider=FailedMarketProvider(), news_provider=news_provider, repository=repo)
                updated_result, final_report = failed_orchestrator.analyze(asset, timeframe, limit=candle_limit,
                    portfolio_summary=portfolio.state())
        st.session_state["market_result"] = updated_result
        st.session_state["consolidated_report"] = final_report
        st.session_state["selected_asset"] = asset
        st.session_state["selected_timeframe"] = timeframe
        st.session_state["news_override"] = None
        st.session_state["run_metadata"] = {"source_mode": source_mode, "exchange": exchange_id if not source_mode.startswith("DEMO") else None,
            "news_enabled": bool(fetch_news), "cache_ttl_seconds": int(cache_ttl)}
        repo.set_preference("default_asset", asset)
        repo.set_preference("default_timeframe", timeframe)
        repo.set_preference("market_source_mode", source_mode)
        repo.set_preference("market_exchange", exchange_id)
        repo.set_preference("candle_limit", int(candle_limit))
        repo.set_preference("news_enabled", bool(fetch_news))
        repo.set_preference("cache_ttl_seconds", int(cache_ttl))
        st.session_state.pop("backtest_result", None)

current_result = st.session_state.get("market_result")
consolidated = st.session_state.get("consolidated_report")
run_metadata = st.session_state.get("run_metadata", {})
asset_or_timeframe_stale = consolidated is not None and (consolidated.asset != asset or consolidated.timeframe != timeframe)
source_config_stale = bool(run_metadata) and (
    run_metadata.get("source_mode") != source_mode
    or (not source_mode.startswith("DEMO") and run_metadata.get("exchange") != exchange_id)
)
selected_is_stale = asset_or_timeframe_stale or source_config_stale
if asset_or_timeframe_stale:
    st.warning(f"المعروض حاليًا لتحليل {consolidated.asset} / {consolidated.timeframe}. اختر «تشغيل / تحديث التحليل» لتطبيق {asset} / {timeframe}؛ لم يتم تبديل النتائج تلقائيًا.")
elif source_config_stale:
    st.warning("تغيّر مصدر البيانات المختار، لكن البيانات المعروضة ما زالت من المصدر السابق. اضغط «تشغيل / تحديث التحليل» قبل تفسيرها على أنها من المصدر الجديد.")

if current_result is None:
    st.error("لا توجد شموع صالحة معروضة حاليًا. استخدم الوضع التجريبي أو أعد محاولة مصدر السوق العام.")
    frame = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    current_close = None
else:
    frame = current_result.candles.copy()
    current_close = float(frame["close"].iloc[-1]) if len(frame) else None
    status_labels = {"demo": "DEMO DATA — بيانات اصطناعية", "live": "بيانات عامة حديثة (الحداثة مستنتجة من الطابع الزمني)",
        "delayed": "بيانات عامة متأخرة/قديمة", "cached": "بيانات من الذاكرة المؤقتة", "historical": "بيانات تاريخية", "unavailable": "غير متاح"}
    status_label = status_labels.get(current_result.status, current_result.status)
    if current_result.status == "demo": st.warning("⚠️ **DEMO DATA:** الأسعار والشموع المعروضة اصطناعية ومولّدة محليًا، وليست أسعارًا حقيقية.")
    elif current_result.status in {"delayed", "cached"}: st.warning(f"حالة البيانات: {status_label}. تحقق من وقت آخر شمعة.")
    st.caption(f"المصدر: {current_result.source} · الحالة: {status_label} · الأصل: {current_result.asset} · الإطار: {current_result.timeframe} · وقت الاسترجاع: {current_result.fetched_at.isoformat() if current_result.fetched_at else 'غير متاح'}")
    st.caption(current_result.message)

# Top-level dashboard metrics.
if consolidated:
    recent_classification = LABELS[consolidated.classification]
    top1, top2, top3, top4 = st.columns(4)
    top1.metric("الأصل محل التحليل", consolidated.asset)
    top2.metric("الإطار الزمني", consolidated.timeframe)
    top3.metric("السيناريو التجميعي", recent_classification)
    top4.metric("قوة الأدلة الإرشادية", f"{consolidated.evidence_strength_score}/100")

pages = st.tabs(["نظرة عامة", "الوكلاء الأربعة", "الرسوم والمؤشرات", "الأخبار والأحداث", "التقرير النهائي", "الاختبار التاريخي", "المحفظة الافتراضية", "السجل والإعدادات"])

with pages[0]:
    st.subheader("نظرة عامة")
    if consolidated:
        render_report(consolidated)
    if current_result is not None and not frame.empty:
        import plotly.graph_objects as go
        overview = go.Figure(data=[go.Candlestick(x=frame["timestamp"], open=frame["open"], high=frame["high"], low=frame["low"], close=frame["close"], name="OHLCV")])
        overview.update_layout(title=f"{current_result.asset} · {current_result.timeframe}", height=420, xaxis_rangeslider_visible=False)
        st.plotly_chart(overview, width="stretch")
        st.dataframe(frame.tail(10).iloc[::-1], width="stretch")
    st.markdown("#### حالات يجب الانتباه إليها")
    if consolidated:
        for warning in consolidated.data_quality.warnings: st.warning(warning)
        if not consolidated.data_quality.warnings: st.success("لم تُكتشف تحذيرات من قواعد الجودة الأساسية؛ هذا لا يعني أن البيانات كاملة من كل الجوانب.")

with pages[1]:
    st.subheader("تقارير مستقلة قابلة للفحص")
    if consolidated: render_agents(consolidated.agent_reports)
    else: st.info("لا توجد تقارير متاحة.")

with pages[2]:
    st.subheader("الرسم التفاعلي والمؤشرات")
    if current_result is None or frame.empty:
        st.info("لا توجد شموع صالحة للرسم.")
    else:
        overlays = st.multiselect("المؤشرات على الرسم السعري", ["SMA 20", "SMA 50", "EMA 12", "Bollinger Bands"], default=["SMA 20", "EMA 12"])
        auxiliary = st.multiselect("مؤشرات إضافية", ["RSI(14)", "MACD", "ATR(14)", "Relative volume"], default=["RSI(14)", "MACD"])
        show_swings = st.checkbox("إظهار القمم والقيعان المؤكدة", value=False)
        technical_report = consolidated.agent_reports.get("technical_market_structure") if consolidated else None
        levels = technical_report.levels if technical_report else {}
        st.plotly_chart(make_market_chart(frame, current_result.asset, current_result.timeframe, overlays, show_swings, levels), width="stretch")
        fig2 = make_indicator_chart(frame, auxiliary)
        if fig2 is not None: st.plotly_chart(fig2, width="stretch")

with pages[3]:
    st.subheader("الأخبار والأحداث")
    news_report = None
    if consolidated: news_report = consolidated.agent_reports.get("news_event_macro")
    override = st.session_state.get("news_override")
    if override is not None: news_report = override
    if selected_is_stale:
        st.warning("قم بتشغيل التحليل أولًا حتى تتطابق الأخبار مع الأصل والإطار الزمني المحمّلين.")
    if st.button("تحديث الأخبار العامة من GDELT", key="fetch_news_now", disabled=selected_is_stale or current_result is None):
        news_asset = current_result.asset if current_result is not None else asset
        news_timeframe = current_result.timeframe if current_result is not None else timeframe
        with st.spinner("جارٍ طلب عناوين الأخبار من المصدر العام..."):
            news_report = NewsEventAgent(GdeltNewsProvider()).analyze(news_asset, news_timeframe)
            st.session_state["news_override"] = news_report
            if current_result is not None:
                # Re-run all agents using exactly the currently visible market data and new news report.
                fresh_orchestrator = AnalysisOrchestrator(news_provider=GdeltNewsProvider(), repository=repo)
                mark_for_risk = {current_result.asset: float(current_result.candles["close"].iloc[-1])} if not current_result.candles.empty else {}
                updated_result, updated_report = fresh_orchestrator.analyze(current_result.asset, current_result.timeframe,
                    market_result=current_result, portfolio_summary=portfolio.state(mark_for_risk))
                st.session_state["market_result"] = updated_result
                st.session_state["consolidated_report"] = updated_report
                consolidated = updated_report
                st.session_state["news_override"] = updated_report.agent_reports.get("news_event_macro")
                news_report = st.session_state["news_override"]
        st.rerun()
    render_news(news_report)

with pages[4]:
    st.subheader("التقرير التجميعي القابل للمراجعة")
    if consolidated:
        render_report(consolidated)
        st.download_button("تنزيل التقرير بصيغة JSON", data=consolidated.model_dump_json(indent=2), file_name=f"market_report_{consolidated.asset.replace('/', '-')}_{consolidated.timeframe}.json", mime="application/json")
    else: st.info("لا يوجد تقرير بعد.")

with pages[5]:
    if current_result is not None and not frame.empty:
        render_backtesting(frame, f"{current_result.source} / {current_result.status}")
    else: st.info("الاختبار التاريخي غير متاح حتى تتوفر بيانات صحيحة.")

with pages[6]:
    mark_price = current_close if current_result is not None and not frame.empty else None
    render_portfolio(portfolio, asset, mark_price)

with pages[7]:
    st.subheader("سجل التحليلات المحلية")
    history = repo.analysis_history(limit=100)
    if history: st.dataframe(pd.DataFrame(history), width="stretch")
    else: st.info("لا توجد تحليلات محفوظة بعد.")
    meta = st.session_state.get("run_metadata", {})
    settings = {"نسخة التطبيق": "1.0.0", "مسار قاعدة البيانات": str(get_database().path),
        "مصدر السوق المختار آخر مرة": meta.get("source_mode"), "معرّف المصدر العام": meta.get("exchange"),
        "بحث الأخبار عند التحليل": meta.get("news_enabled", False), "مدة التخزين المؤقت (ثانية)": meta.get("cache_ttl_seconds", 60), "تكامل نموذج لغوي": "غير مفعّل في هذه النسخة",
        "تنفيذ أوامر حقيقية": False, "واجهة الحسابات الخاصة": False}
    render_settings(settings)

st.divider()
st.caption("Market Intelligence Lab · إصدار محلي تعليمي · كل النتائج احتمالية ومحدودة بجودة البيانات وقواعد التحليل المستخدمة.")
