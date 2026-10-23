"""Settings / provenance explanation panel."""
from __future__ import annotations
import streamlit as st


def render_settings(settings: dict) -> None:
    st.subheader("الإعدادات وحالة التكاملات")
    st.json(settings)
    st.markdown("### قواعد الخصوصية والتشغيل")
    st.markdown("- لا يطلب التطبيق كلمات مرور منصات أو مفاتيح تداول خاصة.")
    st.markdown("- مصدر السوق العام للقراءة فقط؛ لا توجد واجهات إيداع أو سحب أو تنفيذ أوامر حقيقية.")
    st.markdown("- الوضع التجريبي يستخدم شموعًا اصطناعية مولدة محليًا ويعرضها صراحةً باسم **DEMO DATA**.")
    st.markdown("- لا تُستخدم واجهة نموذج لغوي في هذه النسخة، ولا يتم إجراء أي طلب لها.")
    st.markdown("- قاعدة SQLite محلية. تجنب مشاركة ملف قاعدة البيانات إذا احتوى على سجل شخصي تريد الاحتفاظ به خاصًا.")
