from __future__ import annotations
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import pytest

@pytest.fixture
def candles():
    n = 240
    rng = np.random.default_rng(1234)
    timestamps = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    close = 100 + np.cumsum(rng.normal(0.05, 0.65, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.0, n)
    low = np.minimum(open_, close) - rng.uniform(0.1, 0.8, n)
    volume = rng.uniform(10, 80, n)
    return pd.DataFrame({"timestamp": timestamps, "open": open_, "high": high, "low": low, "close": close, "volume": volume})
