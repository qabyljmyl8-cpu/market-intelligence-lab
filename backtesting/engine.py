"""Chronological bar-close backtest with a next-period position shift and costs."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from backtesting.metrics import performance_stats

@dataclass
class BacktestResult:
    equity_curve: pd.DataFrame
    metrics: dict
    assumptions: list[str]


def sma_crossover_signal(frame: pd.DataFrame, fast: int = 10, slow: int = 30) -> pd.Series:
    """Signal known at each bar close. The engine applies it starting next bar."""
    if not (1 <= fast < slow): raise ValueError("Require 1 <= fast < slow")
    close = frame["close"].astype(float)
    fast_ma = close.rolling(fast, min_periods=fast).mean()
    slow_ma = close.rolling(slow, min_periods=slow).mean()
    return (fast_ma > slow_ma).astype(float).where(fast_ma.notna() & slow_ma.notna(), 0.0)


def run_backtest(frame: pd.DataFrame, initial_cash: float = 10_000.0, fee_rate: float = 0.001,
                 slippage_rate: float = 0.0005, fast: int = 10, slow: int = 30,
                 start: str | None = None, end: str | None = None) -> BacktestResult:
    """Evaluate a time window while using only rolling indicators from past/current closes.

    Signals are calculated over the full chronological frame to retain pre-window
    warm-up data; returned metrics are limited to [start, end]. No future bar enters
    a rolling mean or position decision.
    """
    if initial_cash <= 0: raise ValueError("initial_cash must be positive")
    if fee_rate < 0 or slippage_rate < 0 or fee_rate >= 1 or slippage_rate >= 1: raise ValueError("Costs must be in [0, 1).")
    if frame is None or len(frame) < slow + 3: raise ValueError(f"Need at least {slow+3} candles for this test.")
    data = frame.copy()
    if "timestamp" not in data or "close" not in data: raise ValueError("Backtest frame must contain timestamp and close.")
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True, errors="coerce")
    data["close"] = pd.to_numeric(data["close"], errors="coerce")
    data = data.dropna(subset=["timestamp", "close"]).sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
    data = data[data["close"] > 0].reset_index(drop=True)
    if len(data) < slow + 3: raise ValueError("Insufficient valid candles after normalization.")
    # Signal at t is only used to establish the position for the next return period.
    data["signal_at_close"] = sma_crossover_signal(data, fast=fast, slow=slow)
    data["market_return"] = data["close"].pct_change().fillna(0.0)
    data["position"] = data["signal_at_close"].shift(1).fillna(0.0)
    data["position_change"] = data["position"].diff().abs().fillna(0.0)
    costs = (fee_rate + slippage_rate) * data["position_change"]
    data["strategy_return"] = data["position"] * data["market_return"] - costs
    data["benchmark_return"] = data["market_return"]
    start_ts = pd.Timestamp(start) if start else None
    end_ts = pd.Timestamp(end) if end else None
    if start_ts is not None and start_ts.tzinfo is None: start_ts = start_ts.tz_localize("UTC")
    if end_ts is not None and end_ts.tzinfo is None: end_ts = end_ts.tz_localize("UTC")
    if start_ts is not None: data = data[data["timestamp"] >= start_ts]
    if end_ts is not None: data = data[data["timestamp"] <= end_ts]
    data = data.reset_index(drop=True)
    if len(data) < 3: raise ValueError("Selected testing period must include at least three candles.")
    data["equity"] = float(initial_cash) * (1.0 + data["strategy_return"]).cumprod()
    data["benchmark_equity"] = float(initial_cash) * (1.0 + data["benchmark_return"]).cumprod()
    if not np.isfinite(data[["equity", "strategy_return", "benchmark_equity"]].to_numpy()).all():
        raise ValueError("Non-finite values occurred in the backtest; result rejected.")
    strat_equity_for_stats = pd.concat([pd.Series([float(initial_cash)]), data["equity"].reset_index(drop=True)], ignore_index=True)
    benchmark_equity_for_stats = pd.concat([pd.Series([float(initial_cash)]), data["benchmark_equity"].reset_index(drop=True)], ignore_index=True)
    metrics = performance_stats(strat_equity_for_stats, data["strategy_return"])
    bench_metrics = performance_stats(benchmark_equity_for_stats, data["benchmark_return"])
    metrics.update({"benchmark_total_return": bench_metrics["total_return"], "benchmark_max_drawdown": bench_metrics["max_drawdown"],
        "fee_rate": fee_rate, "slippage_rate": slippage_rate, "fast_period": fast, "slow_period": slow,
        "final_equity": float(data["equity"].iloc[-1]), "initial_cash": float(initial_cash),
        "period_start": data["timestamp"].iloc[0].isoformat(), "period_end": data["timestamp"].iloc[-1].isoformat()})
    assumptions = ["Signals use only close data available at each bar close; positions are shifted one bar before returns are earned.",
        "Rolling indicators may use development-period candles for warm-up, but evaluation metrics are limited to the requested evaluation window.",
        "The model assumes close-to-close returns, fully funded long/cash exposure, no leverage, no shorts, and no partial fills.",
        "Fees and slippage are illustrative user-configurable fractions and may not match actual execution costs.",
        "No live orders are placed. Historical performance does not predict future results."]
    data["timestamp"] = data["timestamp"].astype(str)
    return BacktestResult(data[["timestamp", "close", "signal_at_close", "position", "market_return", "strategy_return", "equity", "benchmark_equity"]], metrics, assumptions)
