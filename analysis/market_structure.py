"""Price-structure helpers; observations are rules-based, not predictive guarantees."""
from __future__ import annotations
import pandas as pd


def identify_swings(frame: pd.DataFrame, left: int = 3, right: int = 3) -> list[dict]:
    """Find local extrema confirmed by `right` later candles, so pivots are not marked early."""
    if left < 1 or right < 1: raise ValueError("left and right must be >= 1")
    swings: list[dict] = []
    highs, lows = frame["high"].to_numpy(), frame["low"].to_numpy()
    times = frame["timestamp"].astype(str).to_list()
    for i in range(left, len(frame) - right):
        if highs[i] >= max(highs[i-left:i+right+1]) and highs[i] > max(highs[i-left:i]) and highs[i] >= max(highs[i+1:i+right+1]):
            swings.append({"index": i, "timestamp": times[i], "kind": "high", "price": float(highs[i])})
        if lows[i] <= min(lows[i-left:i+right+1]) and lows[i] < min(lows[i-left:i]) and lows[i] <= min(lows[i+1:i+right+1]):
            swings.append({"index": i, "timestamp": times[i], "kind": "low", "price": float(lows[i])})
    swings.sort(key=lambda x: x["index"])
    return swings


def support_resistance(frame: pd.DataFrame, lookback: int = 80, exclude_latest: bool = True) -> dict[str, float]:
    """Recent extrema candidates from preceding candles, optionally excluding the latest bar.

    Excluding the latest bar permits a completed close to be compared with a prior
    range rather than comparing it to a maximum/minimum that already includes itself.
    """
    sample = frame.iloc[:-1].tail(lookback) if exclude_latest and len(frame) > 1 else frame.tail(lookback)
    if sample.empty: return {}
    return {"support_candidate": float(sample["low"].min()), "resistance_candidate": float(sample["high"].max())}


def classify_structure(frame: pd.DataFrame, swings: list[dict] | None = None) -> tuple[str, list[str], list[str]]:
    """Return trend label plus measurable evidence and counter-evidence."""
    evidence: list[str] = []
    conflict: list[str] = []
    if len(frame) < 20:
        return "insufficient_data", evidence, ["At least 20 candles are required for a basic structure check."]
    close = frame["close"]
    sma20 = close.rolling(20).mean()
    if close.iloc[-1] > sma20.iloc[-1]: evidence.append("Latest close is above the 20-candle simple moving average.")
    elif close.iloc[-1] < sma20.iloc[-1]: evidence.append("Latest close is below the 20-candle simple moving average.")
    if sma20.iloc[-1] > sma20.iloc[-6]: evidence.append("The 20-candle average is rising over the recent five-candle interval.")
    elif sma20.iloc[-1] < sma20.iloc[-6]: evidence.append("The 20-candle average is falling over the recent five-candle interval.")
    use = (swings or identify_swings(frame))[-6:]
    highs = [x["price"] for x in use if x["kind"] == "high"]
    lows = [x["price"] for x in use if x["kind"] == "low"]
    structure_up = len(highs) >= 2 and highs[-1] > highs[-2] and len(lows) >= 2 and lows[-1] > lows[-2]
    structure_down = len(highs) >= 2 and highs[-1] < highs[-2] and len(lows) >= 2 and lows[-1] < lows[-2]
    if structure_up: evidence.append("Recent confirmed swing highs and lows both advanced (higher-high / higher-low structure).")
    if structure_down: evidence.append("Recent confirmed swing highs and lows both declined (lower-high / lower-low structure).")
    if structure_up and close.iloc[-1] < sma20.iloc[-1]: conflict.append("Swing structure is upward while the close remains below its 20-candle average.")
    if structure_down and close.iloc[-1] > sma20.iloc[-1]: conflict.append("Swing structure is downward while the close remains above its 20-candle average.")
    if (close.iloc[-1] > sma20.iloc[-1]) and sma20.iloc[-1] > sma20.iloc[-6] and not conflict:
        return "uptrend_candidate", evidence, conflict
    if (close.iloc[-1] < sma20.iloc[-1]) and sma20.iloc[-1] < sma20.iloc[-6] and not conflict:
        return "downtrend_candidate", evidence, conflict
    return "range_or_mixed", evidence, conflict
