from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PullRequestCreate(BaseModel):
    repository_id: str
    pr_number: int
    title: str
    author: str
    base_ref: str = "main"
    head_ref: str
    base_sha: str
    head_sha: str


class PullRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    pr_number: int
    title: str
    author: str
    base_ref: str
    head_ref: str
    base_sha: str
    head_sha: str
    state: str
    created_at: datetime
    updated_at: datetime
    latest_analysis_id: str | None = None
    latest_risk_tier: str | None = None
    latest_risk_score: float | None = None
