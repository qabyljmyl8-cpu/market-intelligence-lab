"""Validated report schemas shared by all analysis components."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, ConfigDict, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentStatus(str, Enum):
    OK = "ok"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class Direction(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class MarketClassification(str, Enum):
    BULLISH_SCENARIO = "BULLISH SCENARIO"
    BEARISH_SCENARIO = "BEARISH SCENARIO"
    NEUTRAL_RANGE = "NEUTRAL / RANGE-BOUND"
    INCONCLUSIVE = "INCONCLUSIVE"


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    detail: str
    evidence: list[str] = Field(default_factory=list)
    severity: str = "info"


class AgentReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_name: str
    status: AgentStatus
    asset: str | None = None
    timeframe: str | None = None
    generated_at: datetime = Field(default_factory=utc_now)
    data_timestamp: datetime | None = None
    direction: Direction = Direction.UNKNOWN
    summary: str
    findings: list[Finding] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    conflicting_evidence: list[str] = Field(default_factory=list)
    levels: dict[str, float] = Field(default_factory=dict)
    invalidation_conditions: list[str] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, float | int | str | None] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    confidence_category: str = "not_assessed"

    @field_validator("levels")
    @classmethod
    def finite_levels(cls, values: dict[str, float]) -> dict[str, float]:
        import math
        if any(not math.isfinite(float(v)) for v in values.values()):
            raise ValueError("Levels must be finite numbers")
        return values

    @field_validator("metrics")
    @classmethod
    def finite_numeric_metrics(cls, values: dict[str, float | int | str | None]) -> dict[str, float | int | str | None]:
        import math
        for name, value in values.items():
            if isinstance(value, (float, int)) and not isinstance(value, bool) and not math.isfinite(float(value)):
                raise ValueError(f"Metric {name!r} must be finite")
        return values


class DataQualityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: AgentStatus
    row_count: int
    duplicate_timestamps: int = 0
    missing_intervals: int = 0
    invalid_rows: int = 0
    latest_timestamp: datetime | None = None
    stale: bool = False
    incomplete_last_candle: bool = False
    warnings: list[str] = Field(default_factory=list)


class ConsolidatedReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset: str
    timeframe: str
    generated_at: datetime = Field(default_factory=utc_now)
    classification: MarketClassification
    evidence_quality: str
    summary: str
    supporting_observations: list[str] = Field(default_factory=list)
    conflicting_observations: list[str] = Field(default_factory=list)
    alternative_scenario: str
    invalidation_conditions: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    data_quality: DataQualityReport
    agent_reports: dict[str, AgentReport]
    limitations: list[str] = Field(default_factory=list)
    evidence_strength_score: int = Field(ge=0, le=100, description="Heuristic evidence-strength score, not a probability")


class NewsArticle(BaseModel):
    model_config = ConfigDict(extra="ignore")
    headline: str
    publisher: str = "Unknown publisher"
    published_at: datetime | None = None
    # A provider index/seen time is kept separate; it is not silently renamed publication time.
    provider_seen_at: datetime | None = None
    # Event occurrence time is only filled when a provider actually supplies it.
    event_time: datetime | None = None
    timestamp_basis: str = "Publication/event timestamp unavailable"
    retrieved_at: datetime = Field(default_factory=utc_now)
    url: str
    language: str | None = None
    assets: list[str] = Field(default_factory=list)
    event_category: str = "unclear"
    sentiment: str = "unclear"
    relevance: str = "unclear"
    explanation: str = ""
    stale: bool = False

    @field_validator("url")
    @classmethod
    def require_http_url(cls, value: str) -> str:
        from urllib.parse import urlparse
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Article URL must be an absolute HTTP(S) URL")
        return value
