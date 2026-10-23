from datetime import datetime, timezone, timedelta
import pandas as pd
from data.normalization import normalize_ohlcv
from data.demo_data import demo_result


def tiny_frame(times):
    return pd.DataFrame({"timestamp": times, "open": [10.]*len(times), "high": [12.]*len(times),
        "low": [9.]*len(times), "close": [11.]*len(times), "volume": [2.]*len(times)})


def test_empty_market_data_explicit_unavailable():
    result, quality = normalize_ohlcv(pd.DataFrame(), "1h")
    assert result.empty
    assert quality.status.value == "unavailable"


def test_duplicate_candles_are_removed_and_reported():
    base = pd.Timestamp("2024-01-01T00:00:00Z")
    frame = tiny_frame([base, base, base + pd.Timedelta(hours=1)])
    clean, quality = normalize_ohlcv(frame, "1h", now=(base + pd.Timedelta(hours=2)).to_pydatetime())
    assert len(clean) == 2
    assert quality.duplicate_timestamps == 1


def test_missing_candle_intervals_are_reported():
    base = pd.Timestamp("2024-01-01T00:00:00Z")
    frame = tiny_frame([base, base + pd.Timedelta(hours=1), base + pd.Timedelta(hours=3)])
    _, quality = normalize_ohlcv(frame, "1h", now=(base + pd.Timedelta(hours=4)).to_pydatetime())
    assert quality.missing_intervals == 1


def test_invalid_timestamp_rows_are_removed():
    frame = tiny_frame(["not-a-date", "2024-01-01T01:00:00Z"])
    clean, quality = normalize_ohlcv(frame, "1h", now=datetime(2024, 1, 1, 3, tzinfo=timezone.utc))
    assert len(clean) == 1
    assert quality.invalid_rows >= 1
    assert any("timestamp" in w.lower() for w in quality.warnings)


def test_impossible_ohlcv_row_is_rejected():
    frame = tiny_frame(["2024-01-01T00:00:00Z"])
    frame.loc[0, "high"] = 8
    clean, quality = normalize_ohlcv(frame, "1h", now=datetime(2024, 1, 1, 3, tzinfo=timezone.utc))
    assert clean.empty
    assert quality.invalid_rows == 1


def test_old_data_is_marked_stale():
    frame = tiny_frame(["2020-01-01T00:00:00Z", "2020-01-01T01:00:00Z"])
    _, quality = normalize_ohlcv(frame, "1h", now=datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert quality.stale is True
    assert any("stale" in w.lower() for w in quality.warnings)


def test_demo_data_never_claims_live():
    result = demo_result("BTC/USDT", "1h", 100, seed=7)
    assert result.status == "demo"
    assert "DEMO DATA" in result.message
    assert len(result.candles) == 100


def test_future_timestamp_is_rejected():
    now = datetime(2024, 1, 1, 0, tzinfo=timezone.utc)
    frame = tiny_frame(["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"])
    clean, quality = normalize_ohlcv(frame, "1h", now=now)
    assert len(clean) == 1
    assert any("future" in w.lower() for w in quality.warnings)
