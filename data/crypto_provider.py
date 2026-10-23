"""Public-only CCXT OHLCV adapter with validation, bounded retry and caching."""
from __future__ import annotations
from datetime import datetime, timezone
import logging
import re
import time
import pandas as pd
try:
    import ccxt  # type: ignore
except ImportError:  # Core/demo mode and tests remain importable when optional network deps aren't installed.
    ccxt = None
    class _RequestTimeout(Exception): pass
    class _NetworkError(Exception): pass
    class _RateLimitExceeded(Exception): pass
    REQUEST_TIMEOUT_ERROR = _RequestTimeout
    NETWORK_ERROR = _NetworkError
    RATE_LIMIT_ERROR = _RateLimitExceeded
else:
    REQUEST_TIMEOUT_ERROR = ccxt.RequestTimeout
    NETWORK_ERROR = ccxt.NetworkError
    RATE_LIMIT_ERROR = ccxt.RateLimitExceeded
RETRIABLE_NETWORK_ERRORS = (REQUEST_TIMEOUT_ERROR, NETWORK_ERROR, RATE_LIMIT_ERROR)
from data.market_provider import MarketDataProvider, MarketDataResult
from data.normalization import normalize_ohlcv, timeframe_seconds
from data.cache import TTLCache

logger = logging.getLogger(__name__)
SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,15}/[A-Z0-9]{2,15}$")
EXCHANGE_RE = re.compile(r"^[a-z0-9_]{2,30}$")

class CryptoMarketProvider(MarketDataProvider):
    """Uses only public exchange market-data methods; no private account methods exist here."""
    def __init__(self, exchange_id: str = "binance", timeout_ms: int = 12000, cache_ttl: int = 60):
        if not EXCHANGE_RE.fullmatch(exchange_id):
            raise ValueError("Invalid exchange id")
        self.exchange_id = exchange_id
        if ccxt is None:
            # Demo mode works without ccxt. Live-provider access will return a clear configuration error.
            self.exchange = None
        else:
            exchange_class = getattr(ccxt, exchange_id, None)
            if exchange_class is None:
                raise ValueError(f"Unsupported CCXT exchange id: {exchange_id}")
            self.exchange = exchange_class({"enableRateLimit": True, "timeout": int(timeout_ms), "options": {"defaultType": "spot"}})
        self.cache = TTLCache(cache_ttl)

    def fetch_ohlcv(self, asset: str, timeframe: str, limit: int = 500) -> MarketDataResult:
        asset = asset.strip().upper()
        if not SYMBOL_RE.fullmatch(asset):
            raise ValueError("Use a spot symbol such as BTC/USDT (uppercase letters/numbers only).")
        if self.exchange is None:
            raise RuntimeError("CCXT is not installed in this environment. Run setup.bat or install requirements.txt before using public market data.")
        if timeframe not in {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "1w"}:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        if not 30 <= int(limit) <= 1500:
            raise ValueError("Candle limit must be between 30 and 1500.")
        key = f"{self.exchange_id}:{asset}:{timeframe}:{limit}"
        cached = self.cache.get(key)
        if cached is not None:
            candles, fetched_at = cached
            return MarketDataResult(candles.copy(), asset, timeframe, self.exchange_id, "cached", fetched_at, "Served from short-lived in-process cache.")
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                # load_markets and fetch_ohlcv are public market-data endpoints.
                if not getattr(self.exchange, "markets", None) or not getattr(self.exchange, "timeframes", None):
                    self.exchange.load_markets()
                if timeframe not in getattr(self.exchange, "timeframes", {}):
                    raise ValueError(f"Timeframe {timeframe} is not supported by {self.exchange_id}.")
                if asset not in self.exchange.markets:
                    raise ValueError(f"Asset {asset} is not listed by {self.exchange_id}.")
                if not self.exchange.has.get("fetchOHLCV", False):
                    raise RuntimeError(f"{self.exchange_id} does not advertise OHLCV support.")
                rows = self.exchange.fetch_ohlcv(asset, timeframe=timeframe, limit=int(limit))
                frame, _ = normalize_ohlcv(rows, timeframe=timeframe)
                if frame.empty:
                    raise RuntimeError("Provider returned no valid OHLCV candles.")
                fetched_at = datetime.now(timezone.utc)
                self.cache.set(key, (frame.copy(), fetched_at))
                # Exchange OHLCV is public and typically near-real-time, but freshness is inferred locally.
                duration = timeframe_seconds(timeframe)
                latest = frame["timestamp"].iloc[-1]
                is_stale = (pd.Timestamp.now(tz="UTC") - latest).total_seconds() > duration * 2.5
                status = "delayed" if is_stale else "live"
                return MarketDataResult(frame, asset, timeframe, self.exchange_id, status, fetched_at,
                    "Public OHLCV endpoint; most recent bar may be incomplete.")
            except RETRIABLE_NETWORK_ERRORS as exc:
                last_error = exc
                logger.warning("Public market-data request attempt %s failed (%s).", attempt + 1, type(exc).__name__)
                if attempt == 0:
                    time.sleep(0.6)
            except Exception:
                raise
        raise RuntimeError(f"Market data unavailable after bounded retry: {type(last_error).__name__ if last_error else 'unknown error'}") from last_error
