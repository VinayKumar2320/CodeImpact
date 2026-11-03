from __future__ import annotations

from pydantic import BaseModel


class PlatformMetricsResponse(BaseModel):
    total_repositories: int
    total_pull_requests: int
    total_analyses: int
    completed_analyses: int
    average_risk_score: float
    risk_tier_distribution: dict[str, int]
    total_test_time_saved_hours: float
    average_test_time_savings_percent: float
    active_model_name: str
    active_model_version: str
