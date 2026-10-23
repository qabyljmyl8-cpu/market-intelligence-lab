"""News article cards with source links and freshness labels."""
from __future__ import annotations
import streamlit as st
from orchestration.schemas import AgentReport


def render_news(report: AgentReport | None) -> None:
    if report is None:
        st.info("لم يُشغّل وكيل الأخبار بعد.")
        return
    if report.status.value == "unavailable": st.warning(report.summary)
    elif not report.sources: st.info(report.summary)
    else:
        st.write(report.summary)
        for item in report.sources:
            with st.container(border=True):
                st.markdown(f"### [{item.get('headline','عنوان غير متاح')}]({item.get('url','#')})")
                st.caption(f"المصدر: {item.get('publisher','غير معروف')} · وقت النشر: {item.get('published_at') or 'غير متوفر من المصدر'} · وقت فهرسة المزود: {item.get('provider_seen_at') or 'غير متوفر'} · وقت وقوع الحدث: {item.get('event_time') or 'غير مستنتج'} · وقت الاسترجاع: {item.get('retrieved_at','غير متاح')}")
                st.caption(f"أساس الطابع الزمني: {item.get('timestamp_basis','غير معروف')}")
                x, y, z = st.columns(3)
                x.metric("التصنيف", item.get("sentiment", "غير واضح"))
                y.metric("فئة الحدث", item.get("event_category", "غير معروفة"))
                z.metric("حداثة الخبر", "قديم/وقت مجهول" if item.get("stale", True) else "حديث حسب وقت النشر")
                st.write(item.get("explanation", ""))
    for limitation in report.limitations: st.caption(limitation)
