"""Consolidated report rendering."""
from __future__ import annotations
import streamlit as st
from orchestration.schemas import ConsolidatedReport, MarketClassification

LABELS = {
    MarketClassification.BULLISH_SCENARIO: "سيناريو صاعد",
    MarketClassification.BEARISH_SCENARIO: "سيناريو هابط",
    MarketClassification.NEUTRAL_RANGE: "محايد / نطاق عرضي",
    MarketClassification.INCONCLUSIVE: "النتيجة غير حاسمة",
}


def render_report(report: ConsolidatedReport) -> None:
    label = LABELS[report.classification]
    if report.classification == MarketClassification.INCONCLUSIVE: st.warning(f"**{label}** — {report.summary}")
    else: st.info(f"**{label}** — {report.summary}")
    a, b, c = st.columns(3)
    a.metric("جودة الأدلة", report.evidence_quality)
    b.metric("قوة الأدلة (مؤشر وصفي)", f"{report.evidence_strength_score}/100")
    c.metric("وقت التحليل", report.generated_at.strftime("%Y-%m-%d %H:%M UTC"))
    st.caption("الدرجة مؤشر إرشادي ثابت القواعد، وليست احتمال نجاح أو ربح.")
    st.markdown("#### الملاحظات الداعمة")
    if report.supporting_observations:
        for item in report.supporting_observations: st.markdown(f"- {item}")
    else: st.write("لا توجد ملاحظات داعمة كافية.")
    st.markdown("#### الأدلة المتعارضة")
    if report.conflicting_observations:
        for item in report.conflicting_observations: st.markdown(f"- {item}")
    else: st.write("لم تُسجّل تعارضات صريحة، وهذا لا يعني غياب المخاطر.")
    st.markdown("#### السيناريو البديل")
    st.write(report.alternative_scenario)
    st.markdown("#### شروط إبطال التفسير")
    if report.invalidation_conditions:
        for item in report.invalidation_conditions: st.markdown(f"- {item}")
    else: st.write("لا توجد شروط محددة؛ النتيجة غير حاسمة.")
    st.markdown("#### جودة البيانات")
    dq = report.data_quality
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("الشموع الصالحة", dq.row_count)
    q2.metric("فواصل مفقودة", dq.missing_intervals)
    q3.metric("صفوف مرفوضة", dq.invalid_rows)
    q4.metric("البيانات قديمة؟", "نعم" if dq.stale else "لا")
    if dq.warnings:
        for warning in dq.warnings: st.warning(warning)
    if report.risk_flags:
        st.markdown("#### إشارات مراجعة المخاطر")
        for flag in report.risk_flags: st.warning(flag)
    if report.limitations:
        st.markdown("#### القيود والافتراضات")
        for item in report.limitations: st.markdown(f"- {item}")
