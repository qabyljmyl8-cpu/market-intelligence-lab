"""Deterministic synthetic candles for offline demos; always marked DEMO DATA."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import numpy as np
import pandas as pd
from data.market_provider import MarketDataResult
from data.normalization import timeframe_seconds


def make_demo_candles(asset: str = "BTC/USDT", timeframe: str = "1h", limit: int = 500, seed: int | None = None) -> pd.DataFrame:
    """Create reproducible synthetic OHLCV data, never represented as exchange history."""
    if timeframe not in {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "1w"}:
        raise ValueError(f"Unsupported demo timeframe: {timeframe}")
    if not 30 <= int(limit) <= 1500: raise ValueError("Demo candle limit must be between 30 and 1500")
    if seed is None:
        seed = int(hashlib.sha256(f"{asset}:{timeframe}".encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    duration = timeframe_seconds(timeframe)
    now_ts = int(datetime.now(timezone.utc).timestamp())
    last_open = now_ts - (now_ts % duration)
    stamps = pd.to_datetime(np.arange(last_open - duration * (limit - 1), last_open + 1, duration), unit="s", utc=True)
    base = 66000.0 if asset.startswith("BTC") else 3400.0 if asset.startswith("ETH") else 100.0
    # Mixed regimes are intentional: this is a UI/testing fixture, not market data.
    t = np.arange(limit, dtype=float)
    drift = 0.00018 * np.sin(t / 38.0) + 0.00005 * np.sin(t / 11.0)
    shocks = rng.normal(0.00012, 0.008, size=limit) + drift
    close = base * np.exp(np.cumsum(shocks))
    close = np.maximum(close, base * 0.05)
    open_ = np.r_[close[0] * (1 + rng.normal(0, 0.002)), close[:-1]]
    wick = rng.uniform(0.001, 0.012, size=limit)
    high = np.maximum(open_, close) * (1 + wick)
    low = np.minimum(open_, close) * (1 - wick * rng.uniform(0.7, 1.1, size=limit))
    volume = rng.lognormal(mean=7.0, sigma=0.55, size=limit)
    volume *= np.where(np.abs(shocks) > 0.012, 1.8, 1.0)
    return pd.DataFrame({"timestamp": stamps, "open": open_, "high": high, "low": low, "close": close, "volume": volume})


def demo_result(asset: str = "BTC/USDT", timeframe: str = "1h", limit: int = 500, seed: int | None = None) -> MarketDataResult:
    return MarketDataResult(candles=make_demo_candles(asset, timeframe, limit, seed=seed), asset=asset, timeframe=timeframe,
        source="Bundled synthetic generator", status="demo", fetched_at=datetime.now(timezone.utc),
        message="DEMO DATA — deterministic synthetic candles; not actual market prices and not a live feed.")
