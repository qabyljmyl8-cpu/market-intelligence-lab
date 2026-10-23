"""Independent quantitative review; skeptical by design, never an agent-vote counter."""
from __future__ import annotations
from orchestration.schemas import AgentReport, AgentStatus, Direction, Finding, MarketClassification, DataQualityReport

class QuantitativeRiskReviewAgent:
    name = "quantitative_validation_risk_review"

    def analyze(self, asset: str, timeframe: str, reports: dict[str, AgentReport], quality: DataQualityReport,
                portfolio_summary: dict | None = None) -> tuple[AgentReport, MarketClassification, int, str, list[str]]:
        flags: list[str] = []
        supporting: list[str] = []
        contradictions: list[str] = []
        technical = reports.get("technical_market_structure")
        news = reports.get("news_event_macro")
        wave = reports.get("wave_fibonacci_structure")
        if quality.row_count < 60: flags.append("Fewer than 60 normalized candles: insufficient evidence for a robust regime assessment.")
        if quality.stale: flags.append("Market data is stale for the selected timeframe.")
        if quality.incomplete_last_candle: flags.append("The latest candle may be incomplete; analysis can shift when it closes.")
        if quality.missing_intervals: flags.append(f"Missing intervals detected ({quality.missing_intervals}); continuity assumptions may be weakened.")
        if quality.invalid_rows: flags.append(f"Malformed candles were excluded ({quality.invalid_rows}).")
        if technical is None or technical.status in {AgentStatus.ERROR, AgentStatus.UNAVAILABLE}:
            flags.append("Technical agent did not return a usable report.")
        if wave is not None and wave.direction != Direction.UNKNOWN and technical is not None and technical.direction != Direction.UNKNOWN and wave.direction != technical.direction:
            contradictions.append(f"Wave interpretation ({wave.direction.value}) conflicts with technical structure ({technical.direction.value}); wave labelling is subjective.")
        if technical is not None and technical.conflicting_evidence:
            contradictions.extend(technical.conflicting_evidence)
        fresh_articles = []
        if news is not None:
            fresh_articles = [s for s in news.sources if not s.get("stale", True)]
            if news.status in {AgentStatus.ERROR, AgentStatus.UNAVAILABLE}:
                flags.append("News/event source unavailable; no assumption is made about absent news.")
            elif not fresh_articles:
                flags.append("No fresh, timestamped news items are available; news evidence is missing or stale.")
            sentiments = {s.get("sentiment") for s in fresh_articles}
            has_pos = "potentially_positive" in sentiments
            has_neg = "potentially_negative" in sentiments
            if has_pos and has_neg:
                contradictions.append("Fresh headlines contain potentially positive and potentially negative classifications; their significance and source independence are not established.")
            if len(fresh_articles) == 1:
                flags.append("The news interpretation rests on a single fresh headline and is not independently corroborated.")
        if technical is not None:
            regime = technical.metrics.get("volatility_regime")
            if regime == "high_volatility_candidate": flags.append("Measured ATR is elevated relative to its recent baseline; simulated risk and slippage assumptions may be less reliable.")
            elif regime == "low_volatility_candidate": supporting.append("ATR is low relative to its recent baseline; this can reflect contraction but does not predict a breakout.")
        if wave is not None and wave.metrics.get("ambiguity") == "high":
            flags.append("Wave structure is highly ambiguous and cannot independently validate direction.")
        if portfolio_summary is not None:
            drawdown = portfolio_summary.get("max_drawdown")
            exposure = portfolio_summary.get("gross_exposure_ratio")
            if isinstance(drawdown, (float, int)) and drawdown <= -0.10:
                flags.append(f"Paper portfolio recorded a drawdown of {drawdown:.1%} or worse from a prior equity peak; review simulation assumptions.")
            if isinstance(exposure, (float, int)) and exposure >= 0.80:
                flags.append(f"Paper portfolio gross exposure is approximately {exposure:.1%} of simulated equity, based on available marks.")
            supporting.append(f"Paper portfolio included in risk context: equity {portfolio_summary.get('equity', 'unavailable')}, exposure {exposure if exposure is not None else 'unavailable'}.")
        if technical is not None:
            supporting.extend(technical.supporting_evidence[:5])
        if wave is not None and wave.direction != Direction.UNKNOWN:
            supporting.append(f"Wave agent proposed a {wave.direction.value} heuristic structure (low evidentiary weight).")
        if news is not None:
            supporting.extend([f"Fresh news evidence: {s.get('headline')}" for s in fresh_articles[:3]])

        # Evidence strength is a transparent heuristic score, never probability of success.
        score = 0
        if quality.row_count >= 100: score += 25
        elif quality.row_count >= 60: score += 15
        if not quality.stale: score += 15
        if quality.duplicate_timestamps == 0 and quality.invalid_rows == 0: score += 10
        if technical is not None and technical.status == AgentStatus.OK and technical.direction != Direction.UNKNOWN: score += 20
        if wave is not None and wave.status == AgentStatus.OK and wave.direction == (technical.direction if technical else Direction.UNKNOWN) and wave.metrics.get("ambiguity") != "high": score += 8
        if len(fresh_articles) >= 3: score += 7
        if not contradictions: score += 10
        score = max(0, min(100, score - min(30, len(flags) * 4) - min(25, len(contradictions) * 7)))

        classification = MarketClassification.INCONCLUSIVE
        if quality.status == AgentStatus.UNAVAILABLE or quality.row_count < 30:
            flags.append("Data validity gate failed; consolidated result is inconclusive.")
        elif quality.stale:
            flags.append("Stale-data gate failed; consolidated result is inconclusive.")
        elif technical is None or technical.status in {AgentStatus.ERROR, AgentStatus.UNAVAILABLE} or technical.direction == Direction.UNKNOWN:
            flags.append("No clear and usable primary technical structure; consolidated result is inconclusive.")
        elif len(contradictions) > 0:
            flags.append("Material contradictions remain unresolved; consolidated result is inconclusive.")
        elif quality.row_count >= 60 and technical.direction == Direction.BULLISH and (wave is None or wave.direction in {Direction.BULLISH, Direction.UNKNOWN}) and not quality.missing_intervals:
            classification = MarketClassification.BULLISH_SCENARIO
        elif quality.row_count >= 60 and technical.direction == Direction.BEARISH and (wave is None or wave.direction in {Direction.BEARISH, Direction.UNKNOWN}) and not quality.missing_intervals:
            classification = MarketClassification.BEARISH_SCENARIO
        elif quality.row_count >= 60 and technical.direction == Direction.NEUTRAL and not quality.missing_intervals:
            classification = MarketClassification.NEUTRAL_RANGE
        else:
            flags.append("Evidence thresholds were not met for a directional or range-bound classification.")

        # A directional label means only that this dataset satisfies explicit research rules.
        summary = {
            MarketClassification.BULLISH_SCENARIO: "Available quantitative observations are more consistent with a bullish scenario under the stated rules; this is not a forecast.",
            MarketClassification.BEARISH_SCENARIO: "Available quantitative observations are more consistent with a bearish scenario under the stated rules; this is not a forecast.",
            MarketClassification.NEUTRAL_RANGE: "The measured technical structure is mixed/range-like; no directional scenario is supported.",
            MarketClassification.INCONCLUSIVE: "Available evidence is insufficient or contradictory; preserving uncertainty is the appropriate result.",
        }[classification]
        limitations = ["Evidence-strength score is heuristic and is not a calibrated probability, win rate, or expected return.",
                       "Only the supplied asset/timeframe has been evaluated; correlations, cross-asset context, and actual liquidity may be missing.",
                       "No conclusion guarantees a profitable result or constitutes an instruction to trade."]
        report = AgentReport(agent_name=self.name, status=AgentStatus.OK if classification != MarketClassification.INCONCLUSIVE else AgentStatus.PARTIAL,
            asset=asset, timeframe=timeframe, direction=Direction.BULLISH if classification == MarketClassification.BULLISH_SCENARIO else Direction.BEARISH if classification == MarketClassification.BEARISH_SCENARIO else Direction.NEUTRAL if classification == MarketClassification.NEUTRAL_RANGE else Direction.UNKNOWN,
            summary=summary, findings=[Finding(title="Independent validation result", detail=classification.value, evidence=supporting, severity="warning" if classification == MarketClassification.INCONCLUSIVE else "info"),
                Finding(title="Evidence score", detail=f"{score}/100 heuristic evidence strength; not a probability.", evidence=["Score adds/subtracts fixed rubric points for data sufficiency and consistency."])],
            supporting_evidence=supporting, conflicting_evidence=contradictions, invalidation_conditions=["Re-evaluate when a new completed candle changes the measured structure, data quality, or source evidence."],
            metrics={"evidence_strength_score": score, "fresh_news_articles": len(fresh_articles), "missing_intervals": quality.missing_intervals, "data_rows": quality.row_count},
            limitations=limitations, confidence_category="heuristic evidence strength, not probability")
        return report, classification, score, summary, flags
