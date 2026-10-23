"""Strict normalization and validation for cryptocurrency OHLCV frames."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import math
import pandas as pd
import numpy as np
from orchestration.schemas import DataQualityReport, AgentStatus

REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]
TIMEFRAME_SECONDS = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "12h": 43200,
    "1d": 86400, "1w": 604800,
}


def timeframe_seconds(timeframe: str) -> int:
    if timeframe not in TIMEFRAME_SECONDS:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    return TIMEFRAME_SECONDS[timeframe]


def normalize_ohlcv(frame: pd.DataFrame | list, timeframe: str = "1h", now: datetime | None = None) -> tuple[pd.DataFrame, DataQualityReport]:
    """Normalize common CCXT/CSV candle input; invalid rows are removed, not fabricated."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if isinstance(frame, list):
        frame = pd.DataFrame(frame, columns=REQUIRED_COLUMNS)
    if frame is None or len(frame) == 0:
        return pd.DataFrame(columns=REQUIRED_COLUMNS), DataQualityReport(
            status=AgentStatus.UNAVAILABLE, row_count=0, warnings=["No market data was returned."])
    data = frame.copy()
    if "timestamp" not in data.columns and isinstance(data.index, pd.DatetimeIndex):
        data = data.reset_index().rename(columns={data.index.name or "index": "timestamp"})
    missing_cols = set(REQUIRED_COLUMNS) - set(data.columns)
    if missing_cols:
        raise ValueError(f"OHLCV is missing required columns: {sorted(missing_cols)}")
    original_len = len(data)
    raw_ts = data["timestamp"]
    if pd.api.types.is_numeric_dtype(raw_ts):
        # CCXT unified OHLCV timestamps are epoch milliseconds.
        data["timestamp"] = pd.to_datetime(raw_ts, unit="ms", utc=True, errors="coerce")
    else:
        data["timestamp"] = pd.to_datetime(raw_ts, utc=True, errors="coerce", format="mixed")
    timestamp_invalid = int(data["timestamp"].isna().sum())
    future_cutoff = pd.Timestamp(now).tz_convert("UTC") + pd.Timedelta(minutes=2) if pd.Timestamp(now).tzinfo else pd.Timestamp(now, tz="UTC") + pd.Timedelta(minutes=2)
    future_timestamp_mask = data["timestamp"] > future_cutoff
    future_timestamp_count = int(future_timestamp_mask.sum())
    for col in REQUIRED_COLUMNS[1:]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    numeric = data[REQUIRED_COLUMNS[1:]].to_numpy(dtype=float)
    finite_rows = np.isfinite(numeric).all(axis=1)
    positive_prices = (data[["open", "high", "low", "close"]] > 0).all(axis=1).to_numpy()
    nonnegative_volume = (data["volume"] >= 0).to_numpy()
    coherent = (
        (data["high"] >= data[["open", "close", "low"]].max(axis=1)) &
        (data["low"] <= data[["open", "close", "high"]].min(axis=1))
    ).to_numpy()
    valid_mask = data["timestamp"].notna().to_numpy() & (~future_timestamp_mask).to_numpy() & finite_rows & positive_prices & nonnegative_volume & coherent
    invalid_rows = int((~valid_mask).sum())
    data = data.loc[valid_mask, REQUIRED_COLUMNS].copy()
    duplicate_count = int(data["timestamp"].duplicated(keep="last").sum())
    data = data.drop_duplicates(subset="timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)
    interval = timeframe_seconds(timeframe)
    missing_intervals = 0
    if len(data) > 1:
        delta = data["timestamp"].diff().dt.total_seconds().dropna()
        missing_intervals = int(sum(max(int(round(v / interval)) - 1, 0) for v in delta if v > interval * 1.5))
    latest = data["timestamp"].iloc[-1].to_pydatetime() if len(data) else None
    incomplete = bool(latest and (now - latest).total_seconds() < interval)
    stale = bool(latest and (now - latest).total_seconds() > interval * 2.5)
    warnings: list[str] = []
    if timestamp_invalid:
        warnings.append(f"{timestamp_invalid} timestamp(s) could not be parsed and were removed.")
    if future_timestamp_count:
        warnings.append(f"{future_timestamp_count} candle timestamp(s) were more than two minutes in the future and were rejected.")
    if invalid_rows:
        warnings.append(f"{invalid_rows} malformed or impossible candle row(s) were removed.")
    if duplicate_count:
        warnings.append(f"{duplicate_count} duplicate timestamp(s) were removed (last record retained).")
    if missing_intervals:
        warnings.append(f"Detected approximately {missing_intervals} missing candle interval(s); no candles were fabricated.")
    if stale:
        warnings.append("Latest available candle is stale relative to the selected timeframe.")
    if incomplete:
        warnings.append("The latest candle may still be forming; completed-candle conclusions should exclude it.")
    if len(data) < 30:
        warnings.append("Fewer than 30 valid candles are available; some analyses may be unstable or unavailable.")
    status = AgentStatus.OK if len(data) >= 30 and not stale else (AgentStatus.PARTIAL if len(data) else AgentStatus.UNAVAILABLE)
    quality = DataQualityReport(status=status, row_count=len(data), duplicate_timestamps=duplicate_count,
        missing_intervals=missing_intervals, invalid_rows=invalid_rows, latest_timestamp=latest,
        stale=stale, incomplete_last_candle=incomplete, warnings=warnings)
    return data, quality
