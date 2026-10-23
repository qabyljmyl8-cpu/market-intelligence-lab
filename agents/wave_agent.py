"""Elliott/Fibonacci structural agent; all counts are explicitly heuristic."""
from __future__ import annotations
import pandas as pd
from analysis.wave_analysis import analyze_waves
from orchestration.schemas import AgentReport, AgentStatus, Direction, Finding

class ElliottWaveAgent:
    name = "wave_fibonacci_structure"

    def analyze(self, frame: pd.DataFrame, asset: str, timeframe: str, quality=None) -> AgentReport:
        if quality is not None and quality.incomplete_last_candle and frame is not None and len(frame) > 20:
            frame = frame.iloc[:-1].copy()
        if frame is None or len(frame) < 20:
            return AgentReport(agent_name=self.name, status=AgentStatus.UNAVAILABLE, asset=asset, timeframe=timeframe,
                summary="Insufficient price history for a useful swing-based interpretation.",
                limitations=["At least 20 candles are required; more history generally gives more possible swing context."])
        result = analyze_waves(frame)
        candidate = result["primary"]
        direction = Direction.BULLISH if candidate.startswith("upward") else Direction.BEARISH if candidate.startswith("downward") else Direction.UNKNOWN
        latest_time = frame["timestamp"].iloc[-1].to_pydatetime() if hasattr(frame["timestamp"].iloc[-1], "to_pydatetime") else None
        findings = [Finding(title="Primary structural interpretation", detail=candidate,
            evidence=result["support"] or ["No sufficient evidence for a preferred count."]),
            Finding(title="Alternative interpretation", detail=result["alternative"],
            evidence=["Alternative counts remain plausible because swing-based wave labelling is subjective."])]
        levels = {}
        for name, value in result.get("fibonacci", {}).get("levels", {}).items(): levels[name] = float(value)
        return AgentReport(agent_name=self.name, status=AgentStatus.OK if result["swings"] else AgentStatus.PARTIAL,
            asset=asset, timeframe=timeframe, data_timestamp=latest_time, direction=direction,
            summary=f"Wave interpretation: {candidate}; structural ambiguity is {result['ambiguity']}.", findings=findings,
            supporting_evidence=result["support"], conflicting_evidence=[result["alternative"]] if result["alternative"] != "ambiguous" else [],
            levels=levels, invalidation_conditions=result["invalidation"],
            metrics={"confirmed_swings": len(result["swings"]), "ambiguity": result["ambiguity"]},
            limitations=[*result["rules"], "Fibonacci levels are arithmetic levels anchored to identified swing points, not probabilities or guaranteed support/resistance."],
            confidence_category=f"structural ambiguity: {result['ambiguity']}; not a probability")
