"""Paper portfolio UI; every operation is clearly simulated."""
from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from backtesting.paper_portfolio import PaperPortfolio


def render_portfolio(portfolio: PaperPortfolio, asset: str, current_price: float | None) -> None:
    st.subheader("المحفظة الافتراضية — لا يوجد اتصال بحساب تداول")
    st.warning("كل العمليات محاكاة محلية فقط. لا تُرسل أوامر إلى أي منصة، ولا تمثل النتائج أموالًا حقيقية.")
    marks = {asset: current_price} if current_price and current_price > 0 else {}
    try: state = portfolio.state(marks=marks)
    except Exception as exc:
        st.error(f"خطأ في سجل المحفظة الافتراضية: {type(exc).__name__}")
        return
    a, b, c, d = st.columns(4)
    a.metric("النقد الافتراضي", f"{state['cash']:,.2f}")
    b.metric("قيمة المراكز", f"{state['holdings_value']:,.2f}")
    c.metric("حقوق المحفظة الافتراضية", f"{state['equity']:,.2f}")
    d.metric("الربح/الخسارة الكلي", f"{state['total_pnl']:+,.2f}")
    e, f, g = st.columns(3)
    e.metric("التعرّض الإجمالي", f"{state['gross_exposure_ratio']:.1%}" if state['gross_exposure_ratio'] is not None else "غير متاح")
    f.metric("نسبة النقد", f"{state['cash_ratio']:.1%}" if state['cash_ratio'] is not None else "غير متاح")
    g.metric("أقصى تراجع مسجل", f"{state['max_drawdown']:.2%}" if state['max_drawdown'] is not None else "غير متاح")
    if current_price: st.caption(f"سعر التقييم لـ {asset}: {current_price:,.6g} — مأخوذ من مصدر البيانات المختار، وقد يكون تجريبيًا أو قديمًا.")
    else: st.info("لا يوجد سعر حالي موثوق للأصل المحدد؛ سيتم تقييم المركز بالتكلفة المتوسطة، وليس بسعر سوق مفترض.")
    with st.form("paper_trade_form"):
        st.markdown("#### إضافة عملية افتراضية")
        side = st.selectbox("العملية", ["شراء افتراضي", "بيع افتراضي"])
        symbol = st.text_input("رمز الأصل", value=asset).strip().upper()
        default_price = float(current_price) if current_price and current_price > 0 else 1.0
        price = st.number_input("سعر التنفيذ الافتراضي", min_value=0.000001, value=default_price, format="%.8f")
        quantity = st.number_input("الكمية", min_value=0.000001, value=0.01, format="%.8f")
        fee_pct = st.number_input("الرسوم الافتراضية (%)", min_value=0.0, max_value=5.0, value=0.10, step=0.05) / 100
        submitted = st.form_submit_button("حفظ العملية في المحفظة الافتراضية")
    if submitted:
        try:
            event_id = portfolio.execute("buy" if side == "شراء افتراضي" else "sell", symbol, quantity, price, fee_pct)
            st.success(f"تم حفظ عملية محاكاة رقم {event_id}. لم يتم إرسال أمر حقيقي.")
            st.rerun()
        except Exception as exc:
            st.error(f"لم تُحفظ العملية: {type(exc).__name__}: {exc}")
    if state["positions"]:
        st.markdown("#### المراكز الافتراضية")
        st.dataframe(pd.DataFrame.from_dict(state["positions"], orient="index").rename_axis("الأصل"), width="stretch")
    else: st.info("لا توجد مراكز افتراضية حتى الآن.")
    curve = portfolio.history_curve()
    if len(curve) > 1:
        st.markdown("#### منحنى المحفظة الافتراضية والتراجع")
        st.caption("المنحنى التاريخي عند كل عملية يستخدم آخر سعر تنفيذ مسجل لكل أصل؛ ليس سلسلة تقييم سوقية لحظية.")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=curve["timestamp"].iloc[1:], y=curve["equity"].iloc[1:], name="حقوق المحفظة الافتراضية"))
        fig.update_layout(height=330, title="منحنى حقوق المحفظة", yaxis_title="قيمة افتراضية")
        st.plotly_chart(fig, width="stretch")
        dd = go.Figure()
        dd.add_trace(go.Scatter(x=curve["timestamp"].iloc[1:], y=curve["drawdown"].iloc[1:] * 100, name="التراجع %", fill="tozeroy"))
        dd.update_layout(height=260, title="تاريخ التراجع من أعلى قيمة مسجلة", yaxis_title="%")
        st.plotly_chart(dd, width="stretch")
    history = portfolio.history()
    if history:
        st.markdown("#### سجل العمليات الافتراضية")
        st.dataframe(pd.DataFrame(history)[["id", "created_at", "symbol", "side", "quantity", "price", "fee", "cash_delta", "note"]], width="stretch")
    with st.expander("إعادة ضبط المحفظة الافتراضية"):
        st.write("سيؤدي التأكيد إلى حذف سجل العمليات الافتراضية المحلية، ويمكن تحديد رصيد افتراضي جديد.")
        new_starting_cash = st.number_input("الرصيد الابتدائي الافتراضي بعد إعادة الضبط", min_value=100.0, max_value=100000000.0, value=float(state["starting_cash"]), step=500.0)
        confirm = st.checkbox("أؤكد حذف سجل المحاكاة الحالي", key="paper_reset_confirm")
        if st.button("إعادة ضبط المحفظة", disabled=not confirm):
            portfolio.reset(confirmed=confirm, starting_cash=new_starting_cash)
            st.success("أُعيد ضبط سجل المحاكاة.")
            st.rerun()
