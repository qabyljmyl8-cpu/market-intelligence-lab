from datetime import datetime, timezone, timedelta
from orchestration.schemas import AgentReport, AgentStatus, DataQualityReport
from orchestration.validation import safe_agent_report
from agents.news_agent import NewsEventAgent, classify_article
from data.news_provider import NewsProvider, parse_gdelt_time
from orchestration.schemas import NewsArticle

class FakeNewsProvider(NewsProvider):
    def __init__(self, articles): self.articles = articles
    def search(self, query: str, max_results: int = 20): return self.articles


def article(headline, url, published_at=None):
    return NewsArticle(headline=headline, publisher="Test publisher", published_at=published_at, url=url)


def test_invalid_agent_output_becomes_structured_error():
    report = safe_agent_report({"agent_name": "x", "status": "impossible", "summary": None}, "x", "BTC/USDT", "1h")
    assert report.status == AgentStatus.ERROR
    assert "schema validation" in report.summary


def test_empty_agent_output_is_rejected():
    report = safe_agent_report({}, "x", "BTC/USDT", "1h")
    assert report.status == AgentStatus.ERROR


def test_news_deduplicates_near_identical_headlines():
    now = datetime.now(timezone.utc)
    provider = FakeNewsProvider([article("Bitcoin ETF inflow rises", "https://one.example/a", now),
        article("Bitcoin ETF-inflow rises!", "https://two.example/a", now - timedelta(minutes=1))])
    result = NewsEventAgent(provider).analyze("BTC/USDT", "1h")
    assert len(result.sources) == 1


def test_news_without_timestamp_is_stale_and_unclear():
    result = classify_article(article("An item without a timestamp", "https://example.com/a"), "BTC/USDT")
    assert result.stale is True
    assert result.sentiment == "unclear"


def test_gdelt_time_parser_does_not_invent_missing_timestamp():
    assert parse_gdelt_time(None) is None
    assert parse_gdelt_time("not-a-time") is None
    parsed = parse_gdelt_time("20261023T090000Z")
    assert parsed.tzinfo == timezone.utc


def test_news_provider_failure_returns_unavailable_not_fabricated():
    class FailingProvider(NewsProvider):
        def search(self, query: str, max_results: int = 20): raise TimeoutError("offline")
    report = NewsEventAgent(FailingProvider()).analyze("BTC/USDT", "1h")
    assert report.status == AgentStatus.UNAVAILABLE
    assert report.sources == []
    assert "no substitute headlines" in report.summary.lower()


def test_gdelt_seen_timestamp_is_not_mislabelled_as_publication_time():
    from data.news_provider import GdeltNewsProvider
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {"articles": [{"title": "A Bitcoin headline", "url": "https://example.com/news", "domain": "example.com", "seendate": "20261023T120000Z", "language": "English"}]}
    class Session:
        def __init__(self): self.headers = {}
        def get(self, *args, **kwargs): return Response()
    provider = GdeltNewsProvider(session=Session())
    items = provider.search("Bitcoin", 5)
    assert len(items) == 1
    assert items[0].published_at is None
    assert items[0].provider_seen_at is not None
    assert items[0].event_time is None
    assert "not asserted to be publication time" in items[0].timestamp_basis


def test_agent_report_rejects_nonfinite_metrics():
    report = safe_agent_report({"agent_name": "x", "status": "ok", "summary": "test", "metrics": {"bad": float("nan")}}, "x", "BTC/USDT", "1h")
    assert report.status == AgentStatus.ERROR
