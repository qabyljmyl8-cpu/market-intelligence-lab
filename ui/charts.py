"""Plotly charts for price, volume and selected transparent indicators."""
from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from analysis.indicators import add_indicators
from analysis.market_structure import identify_swings


def make_market_chart(frame: pd.DataFrame, asset: str, timeframe: str, overlays: list[str] | None = None,
                      show_swings: bool = False, levels: dict | None = None) -> go.Figure:
    overlays = overlays or []
    data = add_indicators(frame)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04,
        row_heights=[0.77, 0.23], specs=[[{"type": "candlestick"}], [{"type": "bar"}]])
    fig.add_trace(go.Candlestick(x=data["timestamp"], open=data["open"], high=data["high"], low=data["low"], close=data["close"], name="Price"), row=1, col=1)
    if "SMA 20" in overlays: fig.add_trace(go.Scatter(x=data["timestamp"], y=data["sma_20"], name="SMA 20", line={"width": 1.3}), row=1, col=1)
    if "SMA 50" in overlays: fig.add_trace(go.Scatter(x=data["timestamp"], y=data["sma_50"], name="SMA 50", line={"width": 1.3}), row=1, col=1)
    if "EMA 12" in overlays: fig.add_trace(go.Scatter(x=data["timestamp"], y=data["ema_12"], name="EMA 12", line={"width": 1}), row=1, col=1)
    if "Bollinger Bands" in overlays:
        fig.add_trace(go.Scatter(x=data["timestamp"], y=data["bb_upper"], name="BB Upper", line={"width": 1, "dash": "dot"}), row=1, col=1)
        fig.add_trace(go.Scatter(x=data["timestamp"], y=data["bb_lower"], name="BB Lower", line={"width": 1, "dash": "dot"}, fill="tonexty", fillcolor="rgba(120,120,120,0.08)"), row=1, col=1)
    fig.add_trace(go.Bar(x=data["timestamp"], y=data["volume"], name="Volume", opacity=0.65), row=2, col=1)
    if show_swings:
        swings = identify_swings(frame)
        if swings:
            fig.add_trace(go.Scatter(x=[s["timestamp"] for s in swings], y=[s["price"] for s in swings], mode="markers",
                name="Confirmed swings", marker={"size": 7, "symbol": "diamond"}), row=1, col=1)
    for label, price in (levels or {}).items():
        if label in {"support_candidate", "resistance_candidate"}:
            fig.add_hline(y=float(price), line_dash="dash", annotation_text=f"{label}: {price:.6g}", row=1, col=1)
    fig.update_layout(title=f"{asset} · {timeframe} — OHLCV", height=680, xaxis_rangeslider_visible=False,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1}, margin={"l": 10, "r": 10, "t": 80, "b": 10})
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    return fig


def make_indicator_chart(frame: pd.DataFrame, selected: list[str]) -> go.Figure | None:
    if not selected: return None
    data = add_indicators(frame)
    fig = make_subplots(rows=len(selected), cols=1, shared_xaxes=True, vertical_spacing=0.06, subplot_titles=selected)
    for i, name in enumerate(selected, start=1):
        if name == "RSI(14)":
            fig.add_trace(go.Scatter(x=data["timestamp"], y=data["rsi_14"], name=name), row=i, col=1)
            fig.add_hline(y=70, line_dash="dot", row=i, col=1); fig.add_hline(y=30, line_dash="dot", row=i, col=1)
        elif name == "MACD":
            fig.add_trace(go.Scatter(x=data["timestamp"], y=data["macd"], name="MACD"), row=i, col=1)
            fig.add_trace(go.Scatter(x=data["timestamp"], y=data["macd_signal"], name="Signal"), row=i, col=1)
            fig.add_trace(go.Bar(x=data["timestamp"], y=data["macd_hist"], name="Histogram", opacity=0.4), row=i, col=1)
        elif name == "ATR(14)": fig.add_trace(go.Scatter(x=data["timestamp"], y=data["atr_14"], name=name), row=i, col=1)
        elif name == "Relative volume": fig.add_trace(go.Scatter(x=data["timestamp"], y=data["relative_volume"], name=name), row=i, col=1)
    fig.update_layout(height=max(240, 210 * len(selected)), showlegend=True, margin={"l": 10, "r": 10, "t": 45, "b": 10})
    return fig
