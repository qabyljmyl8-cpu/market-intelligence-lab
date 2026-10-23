"""News/event intelligence agent with explicit provenance and heuristic classifications."""
from __future__ import annotations
from datetime import datetime, timezone
import re
from orchestration.schemas import AgentReport, AgentStatus, Direction, Finding, NewsArticle
from data.news_provider import NewsProvider

POSITIVE = {"approval", "approved", "adoption", "inflow", "launch", "record high", "partnership", "upgrade", "growth", "surge"}
NEGATIVE = {"hack", "exploit", "lawsuit", "ban", "banned", "outflow", "lawsuit", "fraud", "breach", "liquidation", "decline", "crash", "downgrade", "warning"}
EVENT_TERMS = {
    "regulation": {"regulation", "regulatory", "sec", "law", "ban", "approved", "approval"},
    "security": {"hack", "exploit", "breach", "stolen", "vulnerability"},
    "market_flow": {"inflow", "outflow", "etf", "fund", "liquidation"},
    "macro": {"inflation", "federal reserve", "interest rate", "central bank", "jobs report", "gdp"},
    "product_or_network": {"upgrade", "launch", "mainnet", "outage", "fork", "partnership"},
}

def classify_article(article: NewsArticle, asset: str, stale_hours: int = 72) -> NewsArticle:
    text = article.headline.lower()
    now = datetime.now(timezone.utc)
    published = article.published_at
    provider_time = published or article.provider_seen_at
    article.stale = provider_time is None or (now - (provider_time if provider_time.tzinfo else provider_time.replace(tzinfo=timezone.utc))).total_seconds() > stale_hours * 3600
    tags = [name for name, words in EVENT_TERMS.items() if any(w in text for w in words)]
    article.event_category = tags[0] if len(tags) == 1 else "mixed_events" if len(tags) > 1 else "general_or_unclear"
    pos = any(w in text for w in POSITIVE)
    neg = any(w in text for w in NEGATIVE)
    article.sentiment = "mixed" if pos and neg else "potentially_positive" if pos else "potentially_negative" if neg else "unclear"
    terms = [asset.lower(), asset.split("/")[0].lower(), "bitcoin" if asset.startswith("BTC") else "ethereum" if asset.startswith("ETH") else ""]
    matched = list(dict.fromkeys(t for t in terms if t and (t in text or t.replace("/", "") in text)))
    article.assets = [asset] if matched else []
    article.relevance = "direct_asset_mention" if matched else "query_related_unverified_asset_link"
    reasons = []
    if tags: reasons.append(f"Headline matches event-topic terms: {', '.join(tags)}.")
    if pos and neg: reasons.append("Both positive and negative wording appear; headline-only interpretation is mixed.")
    elif pos: reasons.append("Positive-coded wording appears, but the underlying event details are not verified from headline wording alone.")
    elif neg: reasons.append("Negative-coded wording appears, but the underlying event details are not verified from headline wording alone.")
    else: reasons.append("Headline wording does not support a robust directional classification.")
    if not matched: reasons.append("The selected asset is not explicitly identified in the headline; query relevance is not proof of causality.")
    if article.published_at is None and article.provider_seen_at is not None:
        reasons.append("The available timestamp is the provider's GDELT seen/index time, not a verified publication time.")
    if article.event_time is None:
        reasons.append("The event occurrence time was not provided and is not inferred from the article timestamp.")
    article.explanation = " ".join(reasons)
    return article

class NewsEventAgent:
    name = "news_event_macro"
    def __init__(self, provider: NewsProvider | None = None): self.provider = provider

    def analyze(self, asset: str, timeframe: str, query: str | None = None) -> AgentReport:
        if self.provider is None:
            return AgentReport(agent_name=self.name, status=AgentStatus.UNAVAILABLE, asset=asset, timeframe=timeframe,
                summary="No news provider is configured; no articles were synthesized.",
                limitations=["Configure a public news adapter such as GDELT. News coverage and freshness vary by provider."])
        try:
            articles = self.provider.search(query or f'("{asset.split("/")[0]}" OR "{asset}")', max_results=20)
        except Exception as exc:
            return AgentReport(agent_name=self.name, status=AgentStatus.UNAVAILABLE, asset=asset, timeframe=timeframe,
                summary=f"News provider failed ({type(exc).__name__}); no substitute headlines were invented.",
                limitations=["External news retrieval is unavailable. Check connectivity, provider status, and query restrictions."])
        unique: dict[str, NewsArticle] = {}
        for article in articles:
            normalized = re.sub(r"[^a-z0-9]", "", article.headline.lower())
            if not normalized: continue
            if normalized not in unique:
                unique[normalized] = classify_article(article, asset)
            elif article.published_at and (unique[normalized].published_at is None or article.published_at > unique[normalized].published_at):
                unique[normalized] = classify_article(article, asset)
        articles = list(unique.values())
        sources = [{"headline": a.headline, "publisher": a.publisher, "published_at": a.published_at.isoformat() if a.published_at else None,
            "provider_seen_at": a.provider_seen_at.isoformat() if a.provider_seen_at else None,
            "event_time": a.event_time.isoformat() if a.event_time else None, "timestamp_basis": a.timestamp_basis,
            "retrieved_at": a.retrieved_at.isoformat(), "url": a.url, "language": a.language, "event_category": a.event_category,
            "sentiment": a.sentiment, "relevance": a.relevance, "stale": a.stale, "explanation": a.explanation} for a in articles]
        if not articles:
            return AgentReport(agent_name=self.name, status=AgentStatus.PARTIAL, asset=asset, timeframe=timeframe,
                summary="The provider returned no usable articles for this query.", sources=[], limitations=["No matching articles is not evidence that no relevant events occurred."])
        sentiments = [a.sentiment for a in articles if not a.stale]
        pos = sentiments.count("potentially_positive"); neg = sentiments.count("potentially_negative"); mixed = sentiments.count("mixed")
        direction = Direction.BULLISH if pos >= 2 and pos >= 2 * max(neg, 1) and mixed == 0 else Direction.BEARISH if neg >= 2 and neg >= 2 * max(pos, 1) and mixed == 0 else Direction.NEUTRAL if mixed else Direction.UNKNOWN
        stale_count = sum(a.stale for a in articles)
        return AgentReport(agent_name=self.name, status=AgentStatus.OK if stale_count < len(articles) else AgentStatus.PARTIAL,
            asset=asset, timeframe=timeframe, direction=direction,
            summary=f"Retrieved {len(articles)} de-duplicated headlines; {stale_count} are stale or lack a publication timestamp. Directional classifications are headline heuristics only.",
            findings=[Finding(title="News themes", detail=f"Potentially positive: {pos}; potentially negative: {neg}; mixed: {mixed}; unclear/other: {len(articles)-pos-neg-mixed}.",
                evidence=["Article headlines, timestamps, publisher/domain and URLs are preserved for inspection."])],
            supporting_evidence=[f"{a.publisher}: {a.headline} ({'published ' + a.published_at.isoformat() if a.published_at else 'provider timestamp ' + a.provider_seen_at.isoformat() if a.provider_seen_at else 'timestamp unavailable'})" for a in articles if not a.stale][:8],
            conflicting_evidence=[f"Conflicting or mixed headline: {a.headline}" for a in articles if a.sentiment == "mixed"][:8],
            sources=sources, limitations=["Headline word matching does not establish causal market impact or verify article claims.",
            "News coverage is incomplete and providers may syndicate the same story across publishers.",
            "A missing publication timestamp is treated as stale/unknown."],
            confidence_category="low; headline-only heuristic")
