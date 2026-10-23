"""Run independent research agents, persist reports, and consolidate cautiously."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
import pandas as pd
from agents.technical_agent import TechnicalMarketStructureAgent
from agents.news_agent import NewsEventAgent
from agents.wave_agent import ElliottWaveAgent
from agents.risk_agent import QuantitativeRiskReviewAgent
from data.market_provider import MarketDataProvider, MarketDataResult
from data.news_provider import NewsProvider
from orchestration.schemas import AgentReport, AgentStatus, ConsolidatedReport, DataQualityReport, Direction, MarketClassification
from orchestration.validation import validate_market_frame, safe_agent_report

logger = logging.getLogger(__name__)

class AnalysisOrchestrator:
    """Coordinates four reports; it is infrastructure, not an extra expert agent."""
    def __init__(self, market_provider: MarketDataProvider | None = None, news_provider: NewsProvider | None = None, repository=None):
        self.market_provider = market_provider
        self.news_provider = news_provider
        self.repository = repository
        self.technical = TechnicalMarketStructureAgent()
        self.news = NewsEventAgent(news_provider)
        self.wave = ElliottWaveAgent()
        self.risk = QuantitativeRiskReviewAgent()

    def analyze(self, asset: str, timeframe: str, limit: int = 500, market_result: MarketDataResult | None = None,
                portfolio_summary: dict | None = None) -> tuple[MarketDataResult | None, ConsolidatedReport]:
        result = market_result
        if result is None and self.market_provider is not None:
            try:
                result = self.market_provider.fetch_ohlcv(asset, timeframe, limit)
            except Exception as exc:
                logger.exception("Market-data provider failed")
                quality = DataQualityReport(status=AgentStatus.UNAVAILABLE, row_count=0, warnings=[f"Market provider unavailable ({type(exc).__name__}); no market data was fabricated."])
                reports = {name: AgentReport(agent_name=name, status=AgentStatus.UNAVAILABLE, asset=asset, timeframe=timeframe,
                    summary="Market data is unavailable; analysis was not fabricated.", limitations=["A working provider or clearly labelled demo data is required."])
                    for name in (self.technical.name, self.wave.name)}
                reports[self.news.name] = self.news.analyze(asset, timeframe)
                report4, classification, score, summary, flags = self.risk.analyze(asset, timeframe, reports, quality, portfolio_summary)
                reports[report4.agent_name] = report4
                final = ConsolidatedReport(asset=asset, timeframe=timeframe, classification=classification,
                    evidence_quality="unavailable", summary=summary, supporting_observations=[], conflicting_observations=[],
                    alternative_scenario="No market scenario is asserted because validated price data is unavailable.",
                    invalidation_conditions=[], risk_flags=flags, data_quality=quality, agent_reports=reports,
                    limitations=["Market-data retrieval failed; this report is intentionally inconclusive."], evidence_strength_score=score)
                self._persist(final)
                return None, final
        if result is None:
            raise ValueError("Pass market_result or configure a market_provider.")
        normalized, quality = validate_market_frame(result.candles, timeframe)
        # Expose all agent outputs even if any one agent fails.
        payloads = {}
        try: payloads[self.technical.name] = self.technical.analyze(normalized, asset, timeframe, quality)
        except Exception as exc:
            logger.exception("Technical agent failed")
            payloads[self.technical.name] = {"invalid": str(type(exc).__name__)}
        try: payloads[self.news.name] = self.news.analyze(asset, timeframe)
        except Exception as exc:
            logger.exception("News agent failed")
            payloads[self.news.name] = {"invalid": str(type(exc).__name__)}
        try: payloads[self.wave.name] = self.wave.analyze(normalized, asset, timeframe, quality)
        except Exception as exc:
            logger.exception("Wave agent failed")
            payloads[self.wave.name] = {"invalid": str(type(exc).__name__)}
        reports: dict[str, AgentReport] = {key: safe_agent_report(value, key, asset, timeframe) for key, value in payloads.items()}
        try:
            risk_report, classification, score, summary, flags = self.risk.analyze(asset, timeframe, reports, quality, portfolio_summary)
            reports[self.risk.name] = safe_agent_report(risk_report, self.risk.name, asset, timeframe)
        except Exception as exc:
            logger.exception("Risk review failed")
            classification = MarketClassification.INCONCLUSIVE
            score = 0
            summary = f"Independent validation failed ({type(exc).__name__}); consolidated result is inconclusive."
            flags = ["Risk review failed; no directional result was accepted."]
            reports[self.risk.name] = AgentReport(agent_name=self.risk.name, status=AgentStatus.ERROR, asset=asset, timeframe=timeframe,
                summary=summary, limitations=["The validator failure prevented a consolidated classification."])
        supporting = list(dict.fromkeys(s for r in reports.values() for s in r.supporting_evidence))[:20]
        conflicting = list(dict.fromkeys(s for r in reports.values() for s in r.conflicting_evidence))[:20]
        invalidations = list(dict.fromkeys(s for r in reports.values() for s in r.invalidation_conditions))[:15]
        limitations = list(dict.fromkeys(s for r in reports.values() for s in r.limitations))[:20]
        alternative = ""
        if classification == MarketClassification.BULLISH_SCENARIO: alternative = "Bearish or range-bound alternative remains possible if support/structure fails on completed candles."
        elif classification == MarketClassification.BEARISH_SCENARIO: alternative = "Bullish reversal or range-bound alternative remains possible if resistance/structure is reclaimed on completed candles."
        elif classification == MarketClassification.NEUTRAL_RANGE: alternative = "A confirmed close outside the measured recent range could change the regime assessment."
        else: alternative = "No alternative direction is preferred because evidence is insufficient or contradictory."
        qlabels = "high" if quality.row_count >= 100 and not quality.stale and not quality.missing_intervals and not quality.invalid_rows else "moderate" if quality.row_count >= 60 and not quality.stale else "low"
        if classification == MarketClassification.INCONCLUSIVE: qlabels = "low / unresolved"
        final = ConsolidatedReport(asset=asset, timeframe=timeframe, classification=classification, evidence_quality=qlabels,
            summary=summary, supporting_observations=supporting, conflicting_observations=conflicting,
            alternative_scenario=alternative, invalidation_conditions=invalidations, risk_flags=flags,
            data_quality=quality, agent_reports=reports, limitations=limitations, evidence_strength_score=score)
        self._persist(final)
        return MarketDataResult(normalized, result.asset, result.timeframe, result.source, result.status, result.fetched_at, result.message), final

    def _persist(self, report: ConsolidatedReport) -> None:
        if self.repository is not None:
            try: self.repository.save_analysis(report)
            except Exception: logger.exception("Failed to persist analysis report")
