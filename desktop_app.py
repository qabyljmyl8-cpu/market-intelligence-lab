"""Market Intelligence Lab — native Windows desktop interface.

The desktop shell reuses the project's existing analytical modules. It never
places real orders. Public market data uses only the configured CCXT spot OHLCV
adapter; demo candles are clearly labelled synthetic data.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from PySide6.QtCore import Qt, QThread, Signal, QRectF, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QTabWidget,
    QTextBrowser, QTableWidget, QTableWidgetItem, QMessageBox, QGroupBox,
    QFormLayout, QHeaderView, QSplitter, QFrame, QLineEdit, QCheckBox,
)

from agents.technical_agent import TechnicalMarketStructureAgent
from analysis.indicators import add_indicators
from backtesting.engine import run_backtest
from backtesting.paper_portfolio import PaperPortfolio
from data.crypto_provider import CryptoMarketProvider
from data.demo_data import demo_result
from orchestration.orchestrator import AnalysisOrchestrator
from storage.database import Database
from storage.repositories import Repository

APP_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MIL_DATABASE_PATH", str(APP_DIR / "market_intelligence_lab.sqlite3"))
logging.basicConfig(filename=str(APP_DIR / "market_intelligence_lab.log"), level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

DARK_STYLE = """
QWidget { background: #10151f; color: #e8edf5; font-family: 'Segoe UI'; font-size: 10pt; }
QMainWindow { background: #10151f; }
QLabel#Title { font-size: 22pt; font-weight: 700; color: #f5f7fb; }
QLabel#SubTitle { color: #9caec4; font-size: 10pt; }
QFrame#MetricCard, QGroupBox { background: #182231; border: 1px solid #29384b; border-radius: 10px; }
QGroupBox { margin-top: 12px; padding: 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: #8fbaff; }
QLabel#MetricValue { font-size: 18pt; font-weight: 700; color: #8fbaff; }
QLabel#MetricLabel { color: #9caec4; }
QPushButton { background: #2864dc; border: none; border-radius: 7px; padding: 9px 14px; font-weight: 600; }
QPushButton:hover { background: #3977f3; }
QPushButton:disabled { background: #374355; color: #9caec4; }
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit { background: #111a27; border: 1px solid #35465d; border-radius: 6px; padding: 6px; min-height: 22px; }
QTabWidget::pane { border: 1px solid #29384b; border-radius: 8px; top: -1px; }
QTabBar::tab { background: #182231; color: #b9c6d8; padding: 11px 18px; margin-right: 3px; border-top-left-radius: 7px; border-top-right-radius: 7px; }
QTabBar::tab:selected { background: #2864dc; color: white; }
QTextBrowser { background: #121b28; border: 1px solid #29384b; border-radius: 8px; padding: 10px; }
QTableWidget { background: #121b28; alternate-background-color: #182231; gridline-color: #29384b; border: 1px solid #29384b; border-radius: 7px; }
QHeaderView::section { background: #202d40; color: #dfe8f4; padding: 8px; border: none; }
"""


def html_escape(value: Any) -> str:
    import html
    return html.escape(str(value))


def report_html(report: Any) -> str:
    """Render validated agent reports as safe HTML; external text is escaped."""
    rows = [f"<h2>{html_escape(report.agent_name)}</h2>",
            f"<p><b>الحالة:</b> {html_escape(report.status.value)} &nbsp; <b>الاتجاه:</b> {html_escape(report.direction.value)}</p>",
            f"<p>{html_escape(report.summary)}</p>"]
    if report.findings:
        rows.append("<h3>النتائج</h3><ul>")
        for finding in report.findings:
            rows.append(f"<li><b>{html_escape(finding.title)}:</b> {html_escape(finding.detail)}")
            if finding.evidence:
                rows.append("<br><span style='color:#9caec4'>" + html_escape(" • ".join(finding.evidence)) + "</span>")
            rows.append("</li>")
        rows.append("</ul>")
    for title, items in [("الأدلة المؤيدة", report.supporting_evidence),
                         ("الأدلة المتعارضة", report.conflicting_evidence),
                         ("شروط إبطال التفسير", report.invalidation_conditions),
                         ("القيود", report.limitations)]:
        if items:
            rows.append(f"<h3>{html_escape(title)}</h3><ul>" + "".join(f"<li>{html_escape(item)}</li>" for item in items) + "</ul>")
    if report.levels:
        rows.append("<h3>المستويات المحسوبة</h3><ul>" + "".join(
            f"<li>{html_escape(k)}: {float(v):,.6g}</li>" for k, v in report.levels.items()) + "</ul>")
    if report.sources:
        rows.append("<h3>مصادر الأخبار</h3><ul>")
        for source in report.sources[:15]:
            headline = html_escape(source.get("headline", "عنوان غير متاح"))
            url = str(source.get("url", ""))
            safe_href = html_escape(url) if url.startswith("https://") else ""
            link = f'<a href="{safe_href}">{headline}</a>' if safe_href else headline
            rows.append(f"<li>{link} — {html_escape(source.get('publisher', ''))} — {html_escape(source.get('published_at') or source.get('provider_seen_at') or 'وقت النشر غير متاح')}</li>")
        rows.append("</ul>")
    return "<html><body dir='rtl' style='font-family:Segoe UI;color:#e8edf5'>" + "".join(rows) + "</body></html>"


class CandleChart(QWidget):
    """Small dependency-light OHLC candle chart drawn with Qt."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.frame = pd.DataFrame()
        self.setMinimumHeight(330)

    def set_frame(self, frame: pd.DataFrame):
        self.frame = frame.tail(100).copy() if frame is not None else pd.DataFrame()
        self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt API name
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#121b28"))
        painter.setPen(QPen(QColor("#29384b"), 1))
        if self.frame.empty or not {"open", "high", "low", "close"}.issubset(self.frame.columns):
            painter.setPen(QColor("#9caec4")); painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "لا توجد بيانات شموع للعرض")
            return
        data = self.frame.reset_index(drop=True)
        low = float(data["low"].min()); high = float(data["high"].max())
        if not (high > low): high = low + 1.0
        margin_l, margin_r, margin_t, margin_b = 62, 18, 18, 30
        plot = QRectF(margin_l, margin_t, max(1, self.width()-margin_l-margin_r), max(1, self.height()-margin_t-margin_b))
        for i in range(5):
            y = plot.top() + plot.height() * i / 4
            painter.setPen(QPen(QColor("#29384b"), 1, Qt.PenStyle.DotLine)); painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            price = high - (high-low)*i/4
            painter.setPen(QColor("#9caec4")); painter.drawText(QRectF(2, y-9, margin_l-7, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{price:,.4g}")
        step = plot.width()/max(1, len(data)); body_w = max(2.0, step*0.58)
        for i, row in data.iterrows():
            x = plot.left() + (i+0.5)*step
            y = lambda value: plot.bottom() - (float(value)-low)/(high-low)*plot.height()
            up = float(row["close"]) >= float(row["open"])
            color = QColor("#21c995" if up else "#ff6577")
            painter.setPen(QPen(color, 1.2)); painter.drawLine(QPointF(x, y(row["high"])), QPointF(x, y(row["low"])))
            top = min(y(row["open"]), y(row["close"])); bottom = max(y(row["open"]), y(row["close"]))
            painter.fillRect(QRectF(x-body_w/2, top, body_w, max(1.5, bottom-top)), QBrush(color))
        painter.setPen(QColor("#9caec4")); painter.drawText(QRectF(plot.left(), plot.bottom()+5, plot.width(), 20), Qt.AlignmentFlag.AlignLeft, "أقدم شمعة")
        painter.drawText(QRectF(plot.left(), plot.bottom()+5, plot.width(), 20), Qt.AlignmentFlag.AlignRight, "أحدث شمعة")


class AnalysisWorker(QThread):
    completed = Signal(object, object, object, str)
    failed = Signal(str)

    def __init__(self, asset: str, timeframe: str, source: str, limit: int):
        super().__init__(); self.asset, self.timeframe, self.source, self.limit = asset, timeframe, source, limit

    def run(self):
        try:
            result = demo_result(self.asset, self.timeframe, self.limit) if self.source == "تجريبية" else CryptoMarketProvider().fetch_ohlcv(self.asset, self.timeframe, self.limit)
            repo = Repository(Database(os.environ.get("MIL_DATABASE_PATH")))
            provider = None if self.source == "تجريبية" else CryptoMarketProvider()
            orchestrator = AnalysisOrchestrator(market_provider=provider, repository=repo)
            # Explicitly pass the already-fetched data to avoid a second network request.
            normalized_result, report = orchestrator.analyze(self.asset, self.timeframe, self.limit, market_result=result)
            self.completed.emit(normalized_result, report, result.candles, result.status)
        except Exception as exc:
            logging.exception("Desktop analysis failed")
            self.failed.emit(f"تعذر إكمال التحليل: {type(exc).__name__}: {exc}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Market Intelligence Lab | مختبر ذكاء السوق")
        self.resize(1440, 920); self.setMinimumSize(1100, 700)
        self.repo = Repository(Database(os.environ.get("MIL_DATABASE_PATH")))
        self.portfolio = PaperPortfolio(self.repo)
        self.current_frame = pd.DataFrame(); self.current_report = None; self.worker = None
        root = QWidget(); self.setCentralWidget(root); layout = QVBoxLayout(root); layout.setContentsMargins(22,18,22,14); layout.setSpacing(14)
        header = QHBoxLayout(); title_col = QVBoxLayout()
        title = QLabel("مختبر ذكاء السوق"); title.setObjectName("Title")
        subtitle = QLabel("تحليل متعدد الوكلاء • بيانات واضحة المصدر • تداول افتراضي فقط"); subtitle.setObjectName("SubTitle")
        title_col.addWidget(title); title_col.addWidget(subtitle); header.addLayout(title_col); header.addStretch()
        self.status_label = QLabel("جاهز — ابدأ بالبيانات التجريبية أو اختر مصدر السوق العام")
        self.status_label.setStyleSheet("color:#8fbaff; padding:8px; background:#182231; border-radius:7px;")
        header.addWidget(self.status_label); layout.addLayout(header)
        controls = QGroupBox("إعداد التحليل"); form = QHBoxLayout(controls)
        self.asset = QComboBox(); self.asset.setEditable(True); self.asset.addItems(["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]); self.asset.setMinimumWidth(130)
        self.timeframe = QComboBox(); self.timeframe.addItems(["15m","30m","1h","4h","1d","1w"]); self.timeframe.setCurrentText("1h")
        self.source = QComboBox(); self.source.addItems(["تجريبية", "بيانات عامة — Binance Spot"])
        self.limit = QSpinBox(); self.limit.setRange(100, 1500); self.limit.setSingleStep(100); self.limit.setValue(500)
        self.analyze_btn = QPushButton("تشغيل الوكلاء الأربعة")
        for label, widget in [("الأصل",self.asset),("الإطار الزمني",self.timeframe),("المصدر",self.source),("عدد الشموع",self.limit)]:
            form.addWidget(QLabel(label)); form.addWidget(widget)
        form.addWidget(self.analyze_btn); layout.addWidget(controls)
        self.tabs = QTabWidget(); layout.addWidget(self.tabs, 1)
        self._build_overview(); self._build_agents(); self._build_charts(); self._build_backtest(); self._build_portfolio(); self._build_settings()
        self.analyze_btn.clicked.connect(self.start_analysis)
        self.load_history_summary()
        self.start_analysis()

    def _metric_card(self, label: str, value: str = "—"):
        frame = QFrame(); frame.setObjectName("MetricCard"); box = QVBoxLayout(frame); box.setContentsMargins(15,12,15,12)
        v = QLabel(value); v.setObjectName("MetricValue"); l = QLabel(label); l.setObjectName("MetricLabel")
        box.addWidget(v); box.addWidget(l); return frame, v

    def _build_overview(self):
        page = QWidget(); v = QVBoxLayout(page)
        cards = QGridLayout(); self.metric_values = {}
        for i, (key, label) in enumerate([("asset","الأصل"),("price","آخر إغلاق"),("classification","السيناريو"),("quality","جودة البيانات"),("score","قوة الأدلة / 100"),("source","مصدر البيانات")]):
            card, value = self._metric_card(label); self.metric_values[key] = value; cards.addWidget(card, i//3, i%3)
        v.addLayout(cards)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.summary_box = QTextBrowser(); self.summary_box.setOpenExternalLinks(True)
        self.warnings_box = QTextBrowser()
        summary_group = QGroupBox("التقرير الموحّد"); gl = QVBoxLayout(summary_group); gl.addWidget(self.summary_box)
        warn_group = QGroupBox("جودة البيانات والتنبيهات"); wl = QVBoxLayout(warn_group); wl.addWidget(self.warnings_box)
        split.addWidget(summary_group); split.addWidget(warn_group); split.setSizes([700,500]); v.addWidget(split)
        self.tabs.addTab(page, "نظرة عامة")

    def _build_agents(self):
        page = QWidget(); layout = QVBoxLayout(page); self.agent_tabs = QTabWidget(); self.agent_views = {}
        names = [("technical_market_structure","المحلل الفني"),("news_event_macro","الأخبار والأحداث"),("wave_fibonacci_structure","إليوت وفيبوناتشي"),("quantitative_validation_risk_review","مراجع المخاطر")]
        for key, label in names:
            view = QTextBrowser(); view.setOpenExternalLinks(True); view.setHtml("<div dir='rtl'>شغّل التحليل لعرض التقرير.</div>")
            self.agent_views[key] = view; self.agent_tabs.addTab(view, label)
        layout.addWidget(self.agent_tabs); self.tabs.addTab(page, "الوكلاء الأربعة")

    def _build_charts(self):
        page = QWidget(); layout = QVBoxLayout(page)
        self.chart_status = QLabel("الشموع التجريبية ستظهر بوضوح على أنها بيانات تجريبية."); layout.addWidget(self.chart_status)
        self.chart = CandleChart(); layout.addWidget(self.chart, 1)
        self.candle_table = QTableWidget(0, 6); self.candle_table.setHorizontalHeaderLabels(["الوقت (UTC)","Open","High","Low","Close","Volume"])
        self.candle_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.candle_table.setMaximumHeight(220); layout.addWidget(self.candle_table)
        self.tabs.addTab(page, "الرسم البياني")

    def _build_backtest(self):
        page = QWidget(); layout = QVBoxLayout(page)
        form = QHBoxLayout(); self.fast = QSpinBox(); self.fast.setRange(2,50); self.fast.setValue(10); self.slow = QSpinBox(); self.slow.setRange(5,150); self.slow.setValue(30)
        self.cash = QDoubleSpinBox(); self.cash.setRange(100,100000000); self.cash.setValue(10000); self.cash.setPrefix("$")
        self.fee = QDoubleSpinBox(); self.fee.setDecimals(3); self.fee.setRange(0,5); self.fee.setValue(0.1); self.fee.setSuffix(" %")
        self.slippage = QDoubleSpinBox(); self.slippage.setDecimals(3); self.slippage.setRange(0,5); self.slippage.setValue(0.05); self.slippage.setSuffix(" %")
        for label, widget in [("المتوسط السريع",self.fast),("المتوسط البطيء",self.slow),("الرصيد الافتراضي",self.cash),("الرسوم",self.fee),("الانزلاق السعري",self.slippage)]: form.addWidget(QLabel(label)); form.addWidget(widget)
        self.backtest_btn = QPushButton("تشغيل الاختبار التاريخي"); form.addWidget(self.backtest_btn); layout.addLayout(form)
        self.backtest_output = QTextBrowser(); layout.addWidget(self.backtest_output)
        self.backtest_btn.clicked.connect(self.run_backtest_ui)
        self.tabs.addTab(page, "الاختبار التاريخي")

    def _build_portfolio(self):
        page = QWidget(); layout = QVBoxLayout(page)
        disclaimer = QLabel("محفظة افتراضية فقط — لا توجد أوامر حقيقية ولا اتصال بحساب تداول.")
        disclaimer.setStyleSheet("color:#ffc66d; padding:8px; background:#302719; border-radius:7px;"); layout.addWidget(disclaimer)
        form = QHBoxLayout(); self.paper_side = QComboBox(); self.paper_side.addItems(["شراء افتراضي", "بيع افتراضي"])
        self.paper_qty = QDoubleSpinBox(); self.paper_qty.setDecimals(8); self.paper_qty.setRange(0.00000001, 100000000); self.paper_qty.setValue(0.01)
        self.paper_price = QDoubleSpinBox(); self.paper_price.setDecimals(8); self.paper_price.setRange(0.00000001, 1000000000); self.paper_price.setValue(1)
        self.paper_fee = QDoubleSpinBox(); self.paper_fee.setDecimals(3); self.paper_fee.setRange(0,5); self.paper_fee.setValue(0.1); self.paper_fee.setSuffix(" %")
        self.paper_trade_btn = QPushButton("تسجيل صفقة افتراضية"); self.paper_refresh_btn = QPushButton("تحديث المحفظة"); self.paper_reset_btn = QPushButton("إعادة ضبط المحفظة")
        for label, widget in [("العملية",self.paper_side),("الكمية",self.paper_qty),("السعر",self.paper_price),("الرسوم",self.paper_fee)]: form.addWidget(QLabel(label)); form.addWidget(widget)
        form.addWidget(self.paper_trade_btn); layout.addLayout(form)
        self.paper_summary = QTextBrowser(); self.paper_summary.setMaximumHeight(150); layout.addWidget(self.paper_summary)
        self.paper_table = QTableWidget(0, 6); self.paper_table.setHorizontalHeaderLabels(["الأصل","الكمية","متوسط التكلفة","السعر التقديري","القيمة","ربح/خسارة غير محققة"]); self.paper_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); layout.addWidget(self.paper_table,1)
        row = QHBoxLayout(); row.addWidget(self.paper_refresh_btn); row.addWidget(self.paper_reset_btn); row.addStretch(); layout.addLayout(row)
        self.paper_trade_btn.clicked.connect(self.paper_trade); self.paper_refresh_btn.clicked.connect(self.refresh_portfolio); self.paper_reset_btn.clicked.connect(self.reset_portfolio)
        self.refresh_portfolio(); self.tabs.addTab(page, "المحفظة الافتراضية")

    def _build_settings(self):
        page = QWidget(); layout = QVBoxLayout(page)
        text = QTextBrowser(); text.setHtml("""<div dir='rtl'><h2>الإعدادات ومعلومات التشغيل</h2>
        <p><b>البيانات التجريبية:</b> شموع اصطناعية مولدة محليًا وليست أسعارًا حقيقية.</p>
        <p><b>بيانات السوق العامة:</b> تعتمد على CCXT وواجهة OHLCV العامة للمنصة المختارة. لا تستخدم مفاتيح حساب خاصة.</p>
        <p><b>الأخبار:</b> إذا لم يظهر مصدر الأخبار على أنه متاح، فهذا يعني أنه لم يتم جلب أخبار مؤكدة في هذه الجلسة. لا يتم اختلاق عناوين.</p>
        <p><b>قاعدة البيانات:</b> market_intelligence_lab.sqlite3 داخل مجلد التطبيق.</p>
        <p><b>السجل التشخيصي:</b> market_intelligence_lab.log.</p>
        <p><b>الأمان:</b> لا يوجد تنفيذ أوامر مالية حقيقية، ولا إيداع أو سحب أو رافعة مالية.</p>
        <p><b>تنبيه:</b> نتائج التحليل واختبارات الماضي لا تضمن نتائج مستقبلية وليست توصية استثمارية.</p></div>""")
        layout.addWidget(text); self.tabs.addTab(page, "الإعدادات")

    def start_analysis(self):
        if self.worker is not None and self.worker.isRunning(): return
        asset = self.asset.currentText().strip().upper()
        if not asset or "/" not in asset:
            QMessageBox.warning(self, "رمز غير صالح", "استخدم رمزًا مثل BTC/USDT."); return
        source = "تجريبية" if self.source.currentIndex() == 0 else "عام"
        self.analyze_btn.setEnabled(False); self.status_label.setText("جارٍ التحليل... قد يستغرق جلب البيانات العامة بعض الوقت.")
        self.worker = AnalysisWorker(asset, self.timeframe.currentText(), source, self.limit.value())
        self.worker.completed.connect(self.analysis_done); self.worker.failed.connect(self.analysis_failed); self.worker.finished.connect(lambda: self.analyze_btn.setEnabled(True)); self.worker.start()

    def analysis_done(self, result, report, raw_frame, status):
        self.current_frame = result.candles.copy() if result is not None else raw_frame.copy(); self.current_report = report
        price = float(self.current_frame["close"].iloc[-1]) if not self.current_frame.empty else float("nan")
        self.metric_values["asset"].setText(report.asset); self.metric_values["price"].setText(f"{price:,.6g}" if pd.notna(price) else "غير متاح")
        self.metric_values["classification"].setText(report.classification.value); self.metric_values["quality"].setText(report.evidence_quality); self.metric_values["score"].setText(str(report.evidence_strength_score)); self.metric_values["source"].setText("تجريبية" if status == "demo" else f"عام / {status}")
        q = report.data_quality
        warnings = [f"حالة البيانات: {status}", f"عدد الشموع المقبولة: {q.row_count}", f"أحدث شمعة: {q.latest_timestamp}", f"شموع مفقودة: {q.missing_intervals}", f"صفوف غير صالحة: {q.invalid_rows}", f"بيانات قديمة: {'نعم' if q.stale else 'لا'}"] + q.warnings
        self.warnings_box.setHtml("<div dir='rtl'><ul>" + "".join(f"<li>{html_escape(x)}</li>" for x in warnings) + "</ul></div>")
        body = [f"<h2>{html_escape(report.classification.value)}</h2>", f"<p>{html_escape(report.summary)}</p>", f"<p><b>قوة الأدلة الإرشادية:</b> {report.evidence_strength_score}/100 (ليست احتمال نجاح)</p>"]
        for title, items in [("ملاحظات مؤيدة",report.supporting_observations),("تعارضات",report.conflicting_observations),("السيناريو البديل",[report.alternative_scenario]),("شروط الإبطال",report.invalidation_conditions),("مخاطر",report.risk_flags),("قيود",report.limitations)]:
            body.append(f"<h3>{html_escape(title)}</h3><ul>" + "".join(f"<li>{html_escape(x)}</li>" for x in items) + "</ul>")
        self.summary_box.setHtml("<div dir='rtl'>"+"".join(body)+"</div>")
        keymap = {"technical_market_structure":"technical_market_structure", "news_event_macro":"news_event_macro", "wave_fibonacci_structure":"wave_fibonacci_structure", "quantitative_validation_risk_review":"quantitative_validation_risk_review"}
        for key, view in self.agent_views.items():
            agent_report = report.agent_reports.get(key)
            view.setHtml(report_html(agent_report) if agent_report else "<div dir='rtl'>لم ينتج تقرير لهذا الوكيل.</div>")
        self.chart.set_frame(self.current_frame)
        self.chart_status.setText(f"المصدر: {'DEMO DATA — بيانات اصطناعية' if status == 'demo' else 'بيانات سوق عامة'} | الأصل: {report.asset} | الإطار: {report.timeframe} | لا تمثل الشموع التجريبية أسعارًا حقيقية.")
        self._populate_candles(self.current_frame)
        self.status_label.setText("اكتمل التحليل — راجع الأدلة والقيود قبل تفسير النتيجة.")
        self.paper_price.setValue(max(0.00000001, price if pd.notna(price) else 1.0))
        self.refresh_portfolio()

    def analysis_failed(self, message):
        self.status_label.setText("تعذر التحليل؛ لم يتم اختلاق بيانات بديلة.")
        QMessageBox.critical(self, "فشل التحليل", message + "\n\nجرّب وضع البيانات التجريبية أو تحقق من الاتصال ومكتبات المشروع.")

    def _populate_candles(self, frame):
        frame = frame.tail(12).reset_index(drop=True); self.candle_table.setRowCount(len(frame))
        for i, row in frame.iterrows():
            values = [str(row.get("timestamp", "")), *[f"{float(row[c]):,.6g}" for c in ("open","high","low","close","volume")]]
            for j, value in enumerate(values): self.candle_table.setItem(i,j,QTableWidgetItem(value))

    def run_backtest_ui(self):
        if self.current_frame.empty:
            QMessageBox.warning(self,"لا توجد بيانات","شغّل تحليل السوق أولًا."); return
        fast, slow = self.fast.value(), self.slow.value()
        if fast >= slow:
            QMessageBox.warning(self,"إعداد غير صالح","يجب أن يكون المتوسط السريع أصغر من المتوسط البطيء."); return
        try:
            result = run_backtest(self.current_frame, initial_cash=self.cash.value(), fee_rate=self.fee.value()/100,
                                  slippage_rate=self.slippage.value()/100, fast=fast, slow=slow)
            m = result.metrics
            lines = ["<h2>نتائج الاختبار التاريخي — محاكاة فقط</h2>", f"<p>الرصيد النهائي: <b>${m['final_equity']:,.2f}</b></p>",
                     f"<p>العائد الكلي: {m['total_return']*100:.2f}%</p>", f"<p>أقصى تراجع: {m['max_drawdown']*100:.2f}%</p>",
                     f"<p>عائد المقارنة (الشراء والاحتفاظ): {m['benchmark_total_return']*100:.2f}%</p>",
                     f"<p>الرسوم: {self.fee.value():.3f}% | الانزلاق: {self.slippage.value():.3f}%</p><h3>الافتراضات والقيود</h3><ul>"]
            lines.extend(f"<li>{html_escape(x)}</li>" for x in result.assumptions); lines.append("</ul>")
            self.backtest_output.setHtml("<div dir='rtl'>"+"".join(lines)+"</div>")
        except Exception as exc:
            QMessageBox.warning(self,"تعذر الاختبار",f"{type(exc).__name__}: {exc}")

    def paper_trade(self):
        symbol = self.asset.currentText().strip().upper(); side = "buy" if self.paper_side.currentIndex()==0 else "sell"
        price = self.paper_price.value(); qty = self.paper_qty.value(); fee = self.paper_fee.value()/100
        try:
            self.portfolio.execute(side, symbol, qty, price, fee)
            self.refresh_portfolio(); QMessageBox.information(self,"تم تسجيل المحاكاة","سُجلت الصفقة في المحفظة الافتراضية فقط. لم يُرسل أي أمر إلى منصة تداول.")
        except Exception as exc:
            QMessageBox.warning(self,"تعذر تسجيل الصفقة",f"{type(exc).__name__}: {exc}")

    def refresh_portfolio(self):
        marks = {}
        if not self.current_frame.empty:
            marks[self.asset.currentText().strip().upper()] = float(self.current_frame["close"].iloc[-1])
        state = self.portfolio.state(marks)
        self.paper_summary.setHtml("<div dir='rtl'>" + f"<h3>القيمة الكلية: ${state['equity']:,.2f}</h3><p>النقد: ${state['cash']:,.2f} | قيمة الأصول: ${state['holdings_value']:,.2f}</p><p>الربح/الخسارة الكلية: ${state['total_pnl']:,.2f} | المحقق: ${state['realized_pnl']:,.2f} | غير المحقق: ${state['unrealized_pnl']:,.2f}</p>" + "</div>")
        positions = state["positions"]; self.paper_table.setRowCount(len(positions))
        for i,(symbol,pos) in enumerate(positions.items()):
            vals = [symbol,f"{pos['quantity']:.8g}",f"{pos['average_cost']:,.6g}",f"{pos['mark_price']:,.6g}",f"${pos['market_value']:,.2f}",f"${pos['unrealized_pnl']:,.2f}"]
            for j,val in enumerate(vals): self.paper_table.setItem(i,j,QTableWidgetItem(val))

    def reset_portfolio(self):
        answer = QMessageBox.question(self,"تأكيد إعادة الضبط","هل تريد حذف سجل المحفظة الافتراضية وإعادة ضبطه؟ لا يمكن التراجع عن ذلك.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.repo.reset_paper_events(); self.repo.set_preference("paper_starting_cash",10000.0); self.portfolio = PaperPortfolio(self.repo); self.refresh_portfolio()

    def load_history_summary(self):
        try:
            count = len(self.repo.analysis_history(100))
            self.status_label.setText(f"جاهز — محفوظ محليًا {count} تحليلًا سابقًا")
        except Exception:
            logging.exception("Could not read analysis history")


def main():
    app = QApplication(sys.argv); app.setApplicationName("Market Intelligence Lab"); app.setStyle("Fusion"); app.setLayoutDirection(Qt.LayoutDirection.RightToLeft); app.setStyleSheet(DARK_STYLE)
    window = MainWindow(); window.show(); return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
