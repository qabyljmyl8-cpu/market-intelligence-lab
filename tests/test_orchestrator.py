from datetime import datetime, timezone
from orchestration.orchestrator import AnalysisOrchestrator
from orchestration.schemas import AgentReport, AgentStatus, DataQualityReport, Direction, MarketClassification
from agents.risk_agent import QuantitativeRiskReviewAgent
from agents.technical_agent import TechnicalMarketStructureAgent
from agents.wave_agent import ElliottWaveAgent
from data.demo_data import demo_result


def test_orchestrator_returns_four_agent_reports(candles):
    result = demo_result("BTC/USDT", "1h", 240, seed=12)
    _, report = AnalysisOrchestrator().analyze(result.asset, result.timeframe, market_result=result)
    assert len(report.agent_reports) == 4
    assert "technical_market_structure" in report.agent_reports
    assert "news_event_macro" in report.agent_reports
    assert "wave_fibonacci_structure" in report.agent_reports
    assert "quantitative_validation_risk_review" in report.agent_reports
    assert report.classification in set(MarketClassification)


def test_contradictory_technical_and_wave_reports_are_inconclusive():
    quality = DataQualityReport(status=AgentStatus.OK, row_count=120, stale=False, warnings=[])
    reports = {
        "technical_market_structure": AgentReport(agent_name="technical_market_structure", status=AgentStatus.OK,
            direction=Direction.BULLISH, summary="up", supporting_evidence=["close above average"]),
        "wave_fibonacci_structure": AgentReport(agent_name="wave_fibonacci_structure", status=AgentStatus.OK,
            direction=Direction.BEARISH, summary="down", metrics={"ambiguity": "medium"}),
        "news_event_macro": AgentReport(agent_name="news_event_macro", status=AgentStatus.UNAVAILABLE, summary="not available"),
    }
    review, classification, score, summary, flags = QuantitativeRiskReviewAgent().analyze("BTC/USDT", "1h", reports, quality)
    assert classification == MarketClassification.INCONCLUSIVE
    assert review.conflicting_evidence
    assert score <= 100
    assert any("contradiction" in f.lower() or "conflict" in f.lower() for f in flags)


def test_technical_agent_handles_empty_frame():
    import pandas as pd
    report = TechnicalMarketStructureAgent().analyze(pd.DataFrame(), "BTC/USDT", "1h")
    assert report.status == AgentStatus.UNAVAILABLE


def test_wave_agent_labels_heuristic_not_fact(candles):
    report = ElliottWaveAgent().analyze(candles, "BTC/USDT", "1h")
    assert any("heuristic" in limit.lower() or "subjective" in limit.lower() for limit in report.limitations)
