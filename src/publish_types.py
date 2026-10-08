"""
AI Tech Broadcaster - Unified Data Types and Platform Contracts
Shared type definitions for autonomous publishing across Meta, Threads, TikTok, and media staging.
"""

from typing import TypedDict, Literal, Optional, List, Dict, Any

# Platform publishing status states
Status = Literal["published", "simulated", "skipped", "failed"]
OverallStatus = Literal["published", "partial", "simulated", "failed", "blocked"]
PlatformName = Literal["facebook", "instagram", "threads", "tiktok", "telegram"]


class MediaRef(TypedDict, total=False):
    """Reference to local and staged media assets."""
    local_path: str
    public_url: Optional[str]
    hosted: bool
    content_type: str
    duration_sec: Optional[float]
    width: Optional[int]
    height: Optional[int]


class PlatformResult(TypedDict, total=False):
    """Result of dispatching to a single platform."""
    platform: PlatformName
    status: Status
    mode: Literal["live", "simulated"]
    remote_id: Optional[str]
    permalink: Optional[str]
    error_code: Optional[str]
    error_message: Optional[str]
    attempts: int
    latency_ms: int
    note: Optional[str]
    request_preview: Optional[Dict[str, Any]]


class DispatchResult(TypedDict):
    """Aggregated outcome from the master autonomous dispatcher."""
    post_id: int
    overall: OverallStatus
    results: List[PlatformResult]
    timestamp: int


class QualityCheckItem(TypedDict):
    name: str
    passed: bool
    detail: str


class JudgeBreakdown(TypedDict, total=False):
    score: float
    grounded: bool
    source_tier: Optional[str]
    hook_strength: Optional[float]
    technical_depth: Optional[float]
    retention_pacing: Optional[float]
    debate_cta: Optional[float]
    notes: Optional[str]
    details: Optional[List[str]]


class JudgeScorecard(TypedDict, total=False):
    reality_score: float
    quality_score: float
    composite_score: float
    passed: bool
    reality_judge: JudgeBreakdown
    quality_judge: JudgeBreakdown
    summary: str


class GateResult(TypedDict):
    decision: Literal["pass", "block"]
    checks: List[QualityCheckItem]
    reason: Optional[str]
    scorecard: Optional[JudgeScorecard]


class ReachDiagnostic(TypedDict, total=False):
    post_id: int
    format_type: str
    headline: str
    views: int
    impressions: int
    dropoff_at_3s_pct: float
    completion_rate_pct: float
    engagement_rate_pct: float
    shares: int
    saves: int
    distribution_tier: Literal["viral", "solid", "underperforming", "suppressed"]
    diagnosed_bottlenecks: List[str]
    improvement_recommendations: List[str]


class LearnedRule(TypedDict, total=False):
    rule_id: str
    category: Literal["hook", "retention", "cta", "visual", "timing", "grounding"]
    directive: str
    rationale: str
    confidence: float
    discovered_from_post_id: Optional[int]
    created_at: str

