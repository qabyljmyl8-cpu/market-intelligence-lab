"""Technical market structure agent; numeric results are computed locally."""
from __future__ import annotations
import pandas as pd
from analysis.indicators import add_indicators
from analysis.market_structure import identify_swings, support_resistance, classify_structure
from orchestration.schemas import AgentReport, AgentStatus, Direction, Finding

class TechnicalMarketStructureAgent:
    name = "technical_market_structure"

    def analyze(self, frame: pd.DataFrame, asset: str, timeframe: str, quality=None) -> AgentReport:
        if frame is None or len(frame) < 30:
            return AgentReport(agent_name=self.name, status=AgentStatus.UNAVAILABLE, asset=asset, timeframe=timeframe,
                summary="Insufficient valid candles for a basic multi-indicator assessment.",
                limitations=["At least 30 valid candles are required; longer histories are preferred."])
        data = add_indicators(frame)
        # Exclude a currently forming candle from conclusions when the dataset identifies it.
        completed = data.iloc[:-1] if quality is not None and quality.incomplete_last_candle and len(data) > 30 else data
        latest = completed.iloc[-1]
        structure, evidence, conflicts = classify_structure(completed)
        findings: list[Finding] = []
        directions: list[Direction] = []
        if structure == "uptrend_candidate": directions.append(Direction.BULLISH)
        elif structure == "downtrend_candidate": directions.append(Direction.BEARISH)
        findings.append(Finding(title="Price structure", detail=structure.replace("_", " "), evidence=evidence or ["No conclusive structure evidence."]))
        rsi_value = latest.get("rsi_14")
        macd_hist = latest.get("macd_hist")
        if pd.notna(rsi_value):
            rsi_f = float(rsi_value)
            if rsi_f >= 70:
                findings.append(Finding(title="RSI", detail=f"RSI(14) is {rsi_f:.1f}, in a conventionally high range.", evidence=["This is a momentum observation, not a standalone sell signal."]))
            elif rsi_f <= 30:
                findings.append(Finding(title="RSI", detail=f"RSI(14) is {rsi_f:.1f}, in a conventionally low range.", evidence=["This is a momentum observation, not a standalone buy signal."]))
            else:
                findings.append(Finding(title="RSI", detail=f"RSI(14) is {rsi_f:.1f}, between 30 and 70."))
        if pd.notna(macd_hist):
            if float(macd_hist) > 0:
                directions.append(Direction.BULLISH); evidence.append("MACD histogram is positive.")
            else:
                directions.append(Direction.BEARISH); evidence.append("MACD histogram is negative.")
            findings.append(Finding(title="MACD", detail=f"MACD histogram is {float(macd_hist):.6g}.", evidence=["Sign compares the MACD line with its signal line."]))
        if pd.notna(latest.get("relative_volume")):
            rel = float(latest["relative_volume"])
            findings.append(Finding(title="Relative volume", detail=f"Latest volume is {rel:.2f}× its 20-candle mean.", evidence=["Volume can be exchange-specific and should not be treated as consolidated market-wide volume."]))
        atr_value = latest.get("atr_14")
        atr_baseline = data["atr_14"].rolling(50, min_periods=25).mean().reindex(completed.index).iloc[-1] if "atr_14" in data else float("nan")
        volatility_regime = "unavailable"
        if pd.notna(atr_value) and pd.notna(atr_baseline) and float(atr_baseline) > 0:
            ratio = float(atr_value) / float(atr_baseline)
            volatility_regime = "high_volatility_candidate" if ratio >= 1.25 else "low_volatility_candidate" if ratio <= 0.75 else "typical_volatility"
            findings.append(Finding(title="Volatility regime", detail=f"ATR(14) is {float(atr_value):.6g}; it is {ratio:.2f}× its recent rolling baseline ({volatility_regime.replace('_', ' ')})."))
        elif pd.notna(atr_value):
            findings.append(Finding(title="Volatility", detail=f"ATR(14) is {float(atr_value):.6g} price units; an adequate baseline is unavailable."))
        # Compare the latest completed close with a range formed before that candle.
        levels = support_resistance(completed.iloc[:-1], exclude_latest=False) if len(completed) > 2 else support_resistance(completed)
        close = float(latest["close"])
        previous_close = float(completed["close"].iloc[-2]) if len(completed) > 1 else close
        if close > levels.get("resistance_candidate", float("inf")):
            evidence.append("Latest completed close moved above the prior-range resistance candidate; this is a possible breakout, not proof of continuation.")
        if close < levels.get("support_candidate", float("-inf")):
            evidence.append("Latest completed close moved below the prior-range support candidate; this is a possible breakdown, not proof of continuation.")
        if len(completed) >= 5:
            earlier_levels = support_resistance(completed.iloc[:-2], exclude_latest=False)
            prior_resistance = earlier_levels.get("resistance_candidate")
            prior_support = earlier_levels.get("support_candidate")
            if prior_resistance is not None and previous_close > prior_resistance and close <= prior_resistance:
                evidence.append("Possible failed upside breakout: the prior close was above a previously measured range, but the latest completed close returned to/below it.")
            if prior_support is not None and previous_close < prior_support and close >= prior_support:
                evidence.append("Possible failed downside breakout: the prior close was below a previously measured range, but the latest completed close returned to/above it.")
        # Do not turn a tie into a directional verdict.
        bullish = directions.count(Direction.BULLISH); bearish = directions.count(Direction.BEARISH)
        direction = Direction.BULLISH if bullish >= 2 and bullish > bearish else Direction.BEARISH if bearish >= 2 and bearish > bullish else Direction.NEUTRAL if structure == "range_or_mixed" else Direction.UNKNOWN
        limitations = ["Indicator thresholds are descriptive conventions and are not statistically calibrated probabilities.",
                       "Support/resistance are recent extrema candidates, not guaranteed turning points."]
        limitations.append("Only the selected timeframe was supplied; other timeframes and cross-asset relationships were not evaluated in this run.")
        if quality is not None:
            limitations.extend(quality.warnings)
        timestamp = completed["timestamp"].iloc[-1].to_pydatetime()
        return AgentReport(agent_name=self.name, status=AgentStatus.OK if direction != Direction.UNKNOWN else AgentStatus.PARTIAL,
            asset=asset, timeframe=timeframe, data_timestamp=timestamp, direction=direction,
            summary=f"Technical structure: {structure.replace('_', ' ')}. Directional evidence is {direction.value} and is not a forecast.",
            findings=findings, supporting_evidence=evidence, conflicting_evidence=conflicts,
            levels=levels, invalidation_conditions=[f"A completed candle closing below {levels['support_candidate']:.6g} would challenge the recent support-based interpretation."],
            metrics={"market_regime": structure, "volatility_regime": volatility_regime,
                "rsi_14": float(rsi_value) if pd.notna(rsi_value) else None,
                "macd_hist": float(macd_hist) if pd.notna(macd_hist) else None,
                "atr_14": float(atr_value) if pd.notna(atr_value) else None,
                "relative_volume": float(latest["relative_volume"]) if pd.notna(latest.get("relative_volume")) else None,
                "latest_close": close}, limitations=limitations,
            confidence_category="low_to_moderate; rule-based, uncalibrated")
