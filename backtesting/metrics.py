"""Basic performance metrics with explicit unavailable states for undefined values."""
from __future__ import annotations
import numpy as np
import pandas as pd


def max_drawdown(equity: pd.Series) -> float | None:
    equity = pd.to_numeric(equity, errors="coerce").dropna()
    if len(equity) < 2 or (equity.cummax() <= 0).all(): return None
    drawdown = equity / equity.cummax() - 1.0
    value = float(drawdown.min())
    return value if np.isfinite(value) else None


def performance_stats(equity: pd.Series, returns: pd.Series, periods_per_year: float | None = None) -> dict:
    eq = pd.to_numeric(equity, errors="coerce").dropna()
    ret = pd.to_numeric(returns, errors="coerce").dropna()
    if len(eq) < 2 or eq.iloc[0] == 0:
        total_return = None
    else:
        total_return = float(eq.iloc[-1] / eq.iloc[0] - 1)
    mdd = max_drawdown(eq)
    sharpe = None
    if len(ret) >= 2 and ret.std(ddof=1) > 0:
        multiplier = float(np.sqrt(periods_per_year)) if periods_per_year and periods_per_year > 0 else 1.0
        sharpe = float(ret.mean() / ret.std(ddof=1) * multiplier)
    positive = int((ret > 0).sum())
    return {"total_return": total_return, "max_drawdown": mdd, "sharpe_like": sharpe,
            "observations": len(ret), "positive_period_fraction": float(positive / len(ret)) if len(ret) else None}
