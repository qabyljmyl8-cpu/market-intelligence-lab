"""Transparent, deterministic technical-indicator implementations."""
from __future__ import annotations
import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    if period < 1: raise ValueError("period must be >= 1")
    return series.rolling(period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    if period < 1: raise ValueError("period must be >= 1")
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI with arithmetic initialization and Wilder recursive smoothing."""
    if period < 1: raise ValueError("period must be >= 1")
    values = close.astype(float).to_numpy()
    out = np.full(len(values), np.nan, dtype=float)
    if len(values) <= period:
        return pd.Series(out, index=close.index, name=close.name)
    delta = np.diff(values)
    gains = np.clip(delta, 0, None)
    losses = np.clip(-delta, 0, None)
    avg_gain = float(gains[:period].mean())
    avg_loss = float(losses[:period].mean())
    def value(gain: float, loss: float) -> float:
        if loss == 0 and gain == 0: return 50.0
        if loss == 0: return 100.0
        if gain == 0: return 0.0
        relative_strength = gain / loss
        return 100.0 - 100.0 / (1.0 + relative_strength)
    out[period] = value(avg_gain, avg_loss)
    for i in range(period + 1, len(values)):
        avg_gain = (avg_gain * (period - 1) + float(gains[i - 1])) / period
        avg_loss = (avg_loss * (period - 1) + float(losses[i - 1])) / period
        out[i] = value(avg_gain, avg_loss)
    return pd.Series(out, index=close.index, name=close.name)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    if min(fast, slow, signal) < 1 or fast >= slow:
        raise ValueError("Require 1 <= fast < slow and signal >= 1")
    line = ema(close, fast) - ema(close, slow)
    signal_line = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "macd_signal": signal_line, "macd_hist": line - signal_line})


def true_range(frame: pd.DataFrame) -> pd.Series:
    prev_close = frame["close"].shift(1)
    return pd.concat([
        frame["high"] - frame["low"],
        (frame["high"] - prev_close).abs(),
        (frame["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)


def atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder ATR with an initial simple average of true range."""
    if period < 1: raise ValueError("period must be >= 1")
    tr = true_range(frame).astype(float)
    values = tr.to_numpy()
    out = np.full(len(values), np.nan, dtype=float)
    if len(values) < period: return pd.Series(out, index=frame.index, name="atr")
    initial = values[:period]
    if not np.isfinite(initial).all(): return pd.Series(out, index=frame.index, name="atr")
    current = float(initial.mean())
    out[period - 1] = current
    for i in range(period, len(values)):
        if np.isfinite(values[i]):
            current = (current * (period - 1) + values[i]) / period
            out[i] = current
    return pd.Series(out, index=frame.index, name="atr")


def bollinger_bands(close: pd.Series, period: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    if period < 1 or num_std <= 0: raise ValueError("period and num_std must be positive")
    mid = sma(close, period)
    std = close.rolling(period, min_periods=period).std(ddof=0)
    return pd.DataFrame({"bb_mid": mid, "bb_upper": mid + num_std * std, "bb_lower": mid - num_std * std})


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with common indicators; doesn't fill warm-up NaNs."""
    result = frame.copy()
    result["sma_20"] = sma(result["close"], 20)
    result["sma_50"] = sma(result["close"], 50)
    result["ema_12"] = ema(result["close"], 12)
    result["ema_26"] = ema(result["close"], 26)
    result["rsi_14"] = rsi(result["close"], 14)
    macd_df = macd(result["close"])
    for col in macd_df: result[col] = macd_df[col]
    result["atr_14"] = atr(result, 14)
    bands = bollinger_bands(result["close"], 20)
    for col in bands: result[col] = bands[col]
    avg_vol = result["volume"].rolling(20, min_periods=20).mean()
    result["relative_volume"] = result["volume"] / avg_vol.replace(0, np.nan)
    return result
