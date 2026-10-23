"""Historical test interface with a chronological development/evaluation split."""
from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from backtesting.engine import run_backtest


def render_backtesting(frame: pd.DataFrame, data_label: str) -> None:
    st.subheader("اختبار تاريخي — محاكاة فقط")
    st.caption(f"مصدر البيانات الحالية: {data_label}. لا تُرسل أوامر حقيقية.")
    if len(frame) < 80:
        st.warning("يلزم 80 شمعة على الأقل لهذا القسم؛ لا تُحسب إحصاءات بديلة عند نقص البيانات.")
        return
    c1, c2, c3, c4 = st.columns(4)
    fast = c1.number_input("فترة المتوسط السريع", min_value=2, max_value=50, value=10)
    slow = c2.number_input("فترة المتوسط البطيء", min_value=5, max_value=150, value=30)
    fee = c3.number_input("الرسوم لكل تغيير مركز (%)", min_value=0.0, max_value=2.0, value=0.10, step=0.05) / 100
    slippage = c4.number_input("الانزلاق لكل تغيير مركز (%)", min_value=0.0, max_value=2.0, value=0.05, step=0.05) / 100
    frac = st.slider("نسبة فترة التطوير قبل الاختبار (زمنيًا)", min_value=0.50, max_value=0.90, value=0.70, step=0.05)
    if fast >= slow:
        st.error("يجب أن تكون الفترة السريعة أصغر من البطيئة.")
        return
    data = frame.sort_values("timestamp").reset_index(drop=True)
    split_idx = int(len(data) * frac)
    if split_idx <= slow or len(data) - split_idx < 10:
        st.error("الفترة المختارة لا تترك بيانات كافية للتطوير والاختبار.")
        return
    split_ts = pd.to_datetime(data.iloc[split_idx]["timestamp"], utc=True)
    st.write(f"**فترة التطوير/التهيئة:** حتى {split_ts.isoformat()} · **فترة التقييم المنفصلة:** من {split_ts.isoformat()} حتى {pd.to_datetime(data.iloc[-1]['timestamp'], utc=True).isoformat()}")
    st.caption("لم يتم تحسين المعلمات تلقائيًا. تستخدم فترة التقييم بيانات الماضي للتهيئة فقط، ولا تستخدم شموعًا مستقبلية في حساب المتوسطات.")
    if st.button("تشغيل الاختبار على فترة التقييم", key="run_backtest"):
        try:
            result = run_backtest(data, fee_rate=fee, slippage_rate=slippage, fast=int(fast), slow=int(slow), start=split_ts.isoformat())
            st.session_state["backtest_result"] = result
            st.session_state["backtest_split"] = split_ts.isoformat()
        except Exception as exc:
            st.error(f"تعذر الاختبار: {type(exc).__name__}: {exc}")
    result = st.session_state.get("backtest_result")
    if result is None:
        st.info("اضغط تشغيل الاختبار لحساب النتائج.")
        return
    m = result.metrics
    a, b, c, d = st.columns(4)
    a.metric("العائد المحاكى", f"{m['total_return']:.2%}" if m["total_return"] is not None else "غير متاح")
    b.metric("أقصى تراجع", f"{m['max_drawdown']:.2%}" if m["max_drawdown"] is not None else "غير متاح")
    c.metric("العائد المرجعي (شراء واحتفاظ)", f"{m['benchmark_total_return']:.2%}" if m["benchmark_total_return"] is not None else "غير متاح")
    d.metric("قيمة النهاية الافتراضية", f"{m['final_equity']:,.2f}")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=result.equity_curve["timestamp"], y=result.equity_curve["equity"], name="الاستراتيجية المحاكية"))
    fig.add_trace(go.Scatter(x=result.equity_curve["timestamp"], y=result.equity_curve["benchmark_equity"], name="مرجع شراء واحتفاظ"))
    fig.update_layout(title="منحنى رأس المال الافتراضي — فترة التقييم", height=430, yaxis_title="قيمة افتراضية", xaxis_title="الوقت")
    st.plotly_chart(fig, width="stretch")
    st.markdown("**افتراضات الاختبار**")
    for assumption in result.assumptions: st.markdown(f"- {assumption}")
