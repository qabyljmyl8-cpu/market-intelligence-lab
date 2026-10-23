"""Heuristic Elliott/Fibonacci scenario generation using explicitly detected pivots."""
from __future__ import annotations
from analysis.market_structure import identify_swings
import pandas as pd

FIB_RETRACEMENTS = (0.236, 0.382, 0.5, 0.618, 0.786)


def analyze_waves(frame: pd.DataFrame, left: int = 3, right: int = 3) -> dict:
    swings = identify_swings(frame, left=left, right=right)
    last = swings[-6:]
    output: dict = {"swings": last, "fibonacci": {}, "primary": "ambiguous", "alternative": "ambiguous",
                    "support": [], "invalidation": [], "ambiguity": "high", "rules": []}
    if len(last) < 4:
        output["support"].append("Fewer than four confirmed swing points; a meaningful wave count is not proposed.")
        return output
    points = last[-4:]
    prices = [p["price"] for p in points]
    output["rules"] = ["Pivots are local extrema confirmed by the configured number of right-side candles.",
                       "Candidate counts are heuristic and do not establish a unique Elliott Wave interpretation."]
    alternating = all(points[i]["kind"] != points[i+1]["kind"] for i in range(len(points)-1))
    if alternating:
        if prices[-1] > prices[0]:
            output["primary"] = "upward impulse-like structure (heuristic)"
            output["alternative"] = "complex correction or overlapping swing sequence"
        else:
            output["primary"] = "downward impulse-like structure (heuristic)"
            output["alternative"] = "complex correction or overlapping swing sequence"
        output["ambiguity"] = "medium" if len(last) >= 5 else "high"
        output["support"].append("Four recent confirmed pivots alternate high/low and span a measurable price move.")
    else:
        output["support"].append("Recent pivots do not alternate cleanly; no impulse count is preferred.")
    start, end = prices[-2], prices[-1]
    move = abs(end-start)
    if move > 0:
        if end > start:
            levels = {f"retracement_{int(r*1000)/10:g}%": float(end - move*r) for r in FIB_RETRACEMENTS}
        else:
            levels = {f"retracement_{int(r*1000)/10:g}%": float(end + move*r) for r in FIB_RETRACEMENTS}
        output["fibonacci"] = {"anchor_start": float(start), "anchor_end": float(end), "levels": levels}
        output["support"].append(f"Fibonacci retracements are anchored only to the last identified swing leg ({start:.6g} to {end:.6g}).")
        output["invalidation"].append("A confirmed move beyond the selected leg's origin would weaken this specific swing interpretation.")
    return output
