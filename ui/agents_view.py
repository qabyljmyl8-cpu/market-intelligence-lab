"""Agent-by-agent inspection UI."""
from __future__ import annotations
import streamlit as st
from orchestration.schemas import AgentReport

AGENT_LABELS = {
    "technical_market_structure": "١. وكيل البنية الفنية للسوق",
    "news_event_macro": "٢. وكيل الأخبار والأحداث والاقتصاد الكلي",
    "wave_fibonacci_structure": "٣. وكيل الموجات وفيبوناتشي",
    "quantitative_validation_risk_review": "٤. وكيل التحقق الكمي ومراجعة المخاطر",
}


def render_agents(reports: dict[str, AgentReport]) -> None:
    for key, report in reports.items():
        with st.expander(AGENT_LABELS.get(key, key), expanded=key == "quantitative_validation_risk_review"):
            a, b, c = st.columns(3)
            a.metric("الحالة", report.status.value)
            b.metric("الاتجاه الوصفي", report.direction.value)
            c.metric("وقت التقرير", report.generated_at.strftime("%Y-%m-%d %H:%M UTC"))
            st.write(report.summary)
            if report.findings:
                st.markdown("**النتائج والأدلة:**")
                for finding in report.findings:
                    st.markdown(f"**{finding.title}** — {finding.detail}")
                    for e in finding.evidence: st.markdown(f"- {e}")
            if report.supporting_evidence:
                st.markdown("**ملاحظات داعمة**")
                for e in report.supporting_evidence: st.markdown(f"- {e}")
            if report.conflicting_evidence:
                st.warning("**أدلة متعارضة**\n\n" + "\n\n".join(f"• {x}" for x in report.conflicting_evidence))
            if report.levels:
                st.markdown("**مستويات محسوبة**")
                st.json(report.levels)
            if report.sources:
                st.markdown("**المصادر / المقالات**")
                for source in report.sources:
                    headline = source.get("headline", "مقال")
                    url = source.get("url")
                    pub = source.get("publisher", "مصدر غير محدد")
                    published = source.get("published_at") or "وقت النشر غير متاح"
                    seen = source.get("provider_seen_at") or "وقت فهرسة المزود غير متاح"
                    event_time = source.get("event_time") or "وقت الحدث غير مستنتج"
                    st.markdown(f"- [{headline}]({url}) — {pub} — النشر: {published} — الفهرسة: {seen} — الحدث: {event_time} — {source.get('sentiment', 'غير مصنف')}")
                    st.caption(source.get("explanation", ""))
            if report.metrics:
                st.markdown("**المقاييس**")
                st.json(report.metrics)
            if report.invalidation_conditions:
                st.markdown("**ما الذي يضعف هذا التفسير؟**")
                for x in report.invalidation_conditions: st.markdown(f"- {x}")
            if report.limitations:
                st.caption("القيود: " + " · ".join(report.limitations))
