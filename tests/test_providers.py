import pandas as pd
import pytest
from data.crypto_provider import CryptoMarketProvider, REQUEST_TIMEOUT_ERROR, RATE_LIMIT_ERROR

class FakeExchange:
    timeframes = {"1h": "1h"}
    has = {"fetchOHLCV": True}
    markets = {"BTC/USDT": {"symbol": "BTC/USDT"}}
    def __init__(self, response=None, error=None): self.response, self.error = response, error; self.calls = 0
    def load_markets(self): return self.markets
    def fetch_ohlcv(self, symbol, timeframe=None, limit=None):
        self.calls += 1
        if self.error: raise self.error
        return self.response


def provider_with_fake(monkeypatch, exchange):
    from data import crypto_provider
    monkeypatch.setattr(crypto_provider.time, "sleep", lambda _: None)
    provider = CryptoMarketProvider("binance")
    provider.exchange = exchange
    return provider


def test_unknown_asset_rejected_before_any_network_call(monkeypatch):
    exchange = FakeExchange(response=[])
    provider = provider_with_fake(monkeypatch, exchange)
    with pytest.raises(ValueError, match="symbol"):
        provider.fetch_ohlcv("bad symbol", "1h")
    assert exchange.calls == 0


def test_malformed_provider_candles_are_rejected(monkeypatch):
    # epoch ms, then O/H/L/C/V; high is impossible relative to open/close.
    now_ms = 1_700_000_000_000
    exchange = FakeExchange(response=[[now_ms, 10, 8, 9, 9.5, 100]])
    provider = provider_with_fake(monkeypatch, exchange)
    with pytest.raises(RuntimeError, match="no valid"):
        provider.fetch_ohlcv("BTC/USDT", "1h")


def test_provider_timeout_has_bounded_retry(monkeypatch):
    exchange = FakeExchange(error=REQUEST_TIMEOUT_ERROR("timeout"))
    provider = provider_with_fake(monkeypatch, exchange)
    with pytest.raises(RuntimeError, match="bounded retry"):
        provider.fetch_ohlcv("BTC/USDT", "1h")
    assert exchange.calls == 2


def test_provider_rate_limit_has_bounded_retry(monkeypatch):
    exchange = FakeExchange(error=RATE_LIMIT_ERROR("rate limit"))
    provider = provider_with_fake(monkeypatch, exchange)
    with pytest.raises(RuntimeError, match="bounded retry"):
        provider.fetch_ohlcv("BTC/USDT", "1h")
    assert exchange.calls == 2


def test_unsupported_timeframe_is_rejected(monkeypatch):
    exchange = FakeExchange(response=[])
    provider = provider_with_fake(monkeypatch, exchange)
    with pytest.raises(ValueError, match="Unsupported timeframe"):
        provider.fetch_ohlcv("BTC/USDT", "2d")
