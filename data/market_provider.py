"""Provider interfaces for market data; data schemas remain market-specific."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
import pandas as pd

@dataclass
class MarketDataResult:
    candles: pd.DataFrame
    asset: str
    timeframe: str
    source: str
    status: str  # live, delayed, cached, historical, demo, unavailable
    fetched_at: datetime | None = None
    message: str = ""

class MarketDataProvider(ABC):
    @abstractmethod
    def fetch_ohlcv(self, asset: str, timeframe: str, limit: int = 500) -> MarketDataResult:
        """Fetch public OHLCV data for one market and timeframe."""
        raise NotImplementedError
