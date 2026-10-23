import numpy as np
import pandas as pd
import pytest
from analysis.indicators import sma, ema, rsi, macd, atr, bollinger_bands, add_indicators


def test_sma_known_values():
    result = sma(pd.Series([1.0, 2.0, 3.0, 4.0]), 2)
    assert result.iloc[0] != result.iloc[0]
    assert result.iloc[1] == pytest.approx(1.5)
    assert result.iloc[3] == pytest.approx(3.5)


def test_ema_is_reproducible_and_warms_up():
    series = pd.Series([1., 2., 3., 4., 5.])
    output = ema(series, 3)
    assert output.iloc[:2].isna().all()
    assert output.iloc[2] == pytest.approx(2.25)


def test_rsi_rising_series_reaches_100():
    close = pd.Series(range(1, 22), dtype=float)
    output = rsi(close, 5)
    assert output.iloc[-1] == 100


def test_macd_known_structure():
    close = pd.Series(np.linspace(100, 130, 120))
    result = macd(close)
    assert list(result.columns) == ["macd", "macd_signal", "macd_hist"]
    assert result.iloc[-1]["macd"] > 0
    assert result.iloc[-1]["macd_hist"] >= 0


def test_atr_positive_on_valid_candles(candles):
    output = atr(candles, 14)
    assert output.dropna().gt(0).all()


def test_bollinger_bands_order():
    close = pd.Series(np.linspace(10, 20, 60))
    result = bollinger_bands(close, 20)
    assert (result["bb_upper"].dropna() >= result["bb_mid"].dropna()).all()
    assert (result["bb_mid"].dropna() >= result["bb_lower"].dropna()).all()


def test_add_indicators_does_not_fill_warmup_nans(candles):
    result = add_indicators(candles)
    assert result["sma_50"].iloc[:49].isna().all()
    assert "relative_volume" in result
