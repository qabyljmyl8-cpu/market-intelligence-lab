"""Boundaries for untrusted provider data and agent report validation."""
from __future__ import annotations
import pandas as pd
from pydantic import ValidationError
from data.normalization import normalize_ohlcv
from orchestration.schemas import AgentReport, AgentStatus


def validate_market_frame(frame: pd.DataFrame, timeframe: str):
    return normalize_ohlcv(frame, timeframe=timeframe)


def safe_agent_report(payload, agent_name: str, asset: str, timeframe: str) -> AgentReport:
    """Parse model output or return a structured failure rather than accepting malformed output."""
    try:
        if isinstance(payload, AgentReport):
            # Re-validate a dumped copy to protect boundaries from accidental mutation.
            return AgentReport.model_validate(payload.model_dump())
        return AgentReport.model_validate(payload)
    except (ValidationError, TypeError, ValueError) as exc:
        return AgentReport(agent_name=agent_name, status=AgentStatus.ERROR, asset=asset, timeframe=timeframe,
            summary=f"Agent output failed schema validation ({type(exc).__name__}).",
            limitations=["Malformed agent values were rejected; no unsupported output was used."])
