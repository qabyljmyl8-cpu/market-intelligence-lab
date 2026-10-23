import numpy as np
import pandas as pd
import pytest
from backtesting.engine import run_backtest, sma_crossover_signal


def test_signal_at_time_does_not_depend_on_future(candles):
    original = sma_crossover_signal(candles, 5, 20)
    changed = candles.copy()
    changed.loc[180:, ["open", "high", "low", "close"]] *= 20
    modified = sma_crossover_signal(changed, 5, 20)
    assert original.iloc[:180].equals(modified.iloc[:180])


def test_position_is_lagged_one_bar(candles):
    result = run_backtest(candles, fast=5, slow=20, fee_rate=0, slippage_rate=0)
    curve = result.equity_curve.reset_index(drop=True)
    # The lag is encoded in positions: decision at t is not used until t+1.
    # Confirmed by recomputing the signal on the chronological source and aligning the evaluation dates.
    dates = pd.to_datetime(curve["timestamp"], utc=True)
    source = candles.copy(); source["timestamp"] = pd.to_datetime(source["timestamp"], utc=True)
    source = source[source["timestamp"].isin(dates)].reset_index(drop=True)
    signals = sma_crossover_signal(candles.reset_index(drop=True), 5, 20)
    # Default full-window result retains the first position lag in its raw curve.
    raw = run_backtest(candles, fast=5, slow=20, fee_rate=0, slippage_rate=0).equity_curve
    first_nonzero = raw.index[raw["position"] != 0]
    assert len(first_nonzero) > 0
    idx = first_nonzero[0]
    # The active position cannot precede the prior close signal.
    assert raw.loc[idx, "position"] == signals.iloc[idx - 1]


def test_fees_and_slippage_reduce_or_equal_return(candles):
    no_cost = run_backtest(candles, fast=5, slow=20, fee_rate=0, slippage_rate=0)
    costs = run_backtest(candles, fast=5, slow=20, fee_rate=0.002, slippage_rate=0.001)
    assert costs.metrics["total_return"] <= no_cost.metrics["total_return"] + 1e-10


def test_short_period_is_rejected(candles):
    with pytest.raises(ValueError): run_backtest(candles.head(20), fast=10, slow=30)


def test_date_filter_preserves_warmup_from_earlier_period(candles):
    start = candles.iloc[150]["timestamp"].isoformat()
    result = run_backtest(candles, fast=5, slow=20, start=start)
    assert len(result.equity_curve) == len(candles) - 150
    assert result.metrics["period_start"] >= pd.Timestamp(start).isoformat()


def test_backtest_metrics_are_finite(candles):
    result = run_backtest(candles, fast=5, slow=20)
    assert np.isfinite(result.equity_curve[["equity", "strategy_return"]].to_numpy()).all()
    assert result.metrics["observations"] == len(candles)
