"""News-provider interface and GDELT DOC adapter using public API results only."""
from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime, timezone
import logging
import re
import requests
from urllib.parse import urlparse
from orchestration.schemas import NewsArticle

logger = logging.getLogger(__name__)

class NewsProvider(ABC):
    @abstractmethod
    def search(self, query: str, max_results: int = 20) -> list[NewsArticle]:
        raise NotImplementedError


def parse_gdelt_time(value: str | None) -> datetime | None:
    if not value: return None
    try:
        # GDELT commonly returns YYYYMMDDTHHMMSSZ
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            return None

class GdeltNewsProvider(NewsProvider):
    """GDELT DOC search; article text is not fetched or executed."""
    ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"

    def __init__(self, timeout: float = 10.0, session: requests.Session | None = None):
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "MarketIntelligenceLab/1.0 (public news research)"})

    def search(self, query: str, max_results: int = 20) -> list[NewsArticle]:
        query = (query or "").strip()
        if not query or len(query) > 180:
            raise ValueError("News query must contain 1-180 characters.")
        if not 1 <= int(max_results) <= 75:
            raise ValueError("GDELT adapter limits one query to 1-75 results.")
        params = {"query": query, "mode": "ArtList", "format": "json", "maxrecords": int(max_results), "sort": "DateDesc"}
        response = self.session.get(self.ENDPOINT, params=params, timeout=self.timeout)
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError("GDELT returned a non-JSON response.") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("GDELT returned an unexpected response schema.")
        records = payload.get("articles", [])
        if records is None: records = []
        if not isinstance(records, list):
            raise RuntimeError("GDELT article collection has an unexpected type.")
        results: list[NewsArticle] = []
        retrieved = datetime.now(timezone.utc)
        for record in records:
            if not isinstance(record, dict): continue
            headline = re.sub(r"\s+", " ", str(record.get("title") or "")).strip()
            url = str(record.get("url") or "").strip()
            # Invalid records are skipped; they are never replaced with invented content.
            if not headline or not url.startswith(("https://", "http://")): continue
            published = parse_gdelt_time(record.get("published_at") or record.get("publishedAt"))
            provider_seen = parse_gdelt_time(record.get("seendate"))
            timestamp_basis = ("Publisher-provided publication timestamp" if published else
                "GDELT seendate/index timestamp; not asserted to be publication time" if provider_seen else
                "No publication/index timestamp was provided")
            domain = str(record.get("domain") or "").strip()
            if not domain:
                try: domain = urlparse(url).netloc
                except Exception: domain = "Unknown publisher"
            language = str(record.get("language") or "") or None
            results.append(NewsArticle(headline=headline, publisher=domain or "Unknown publisher",
                published_at=published, provider_seen_at=provider_seen, event_time=None, timestamp_basis=timestamp_basis,
                retrieved_at=retrieved, url=url, language=language))
        return results
