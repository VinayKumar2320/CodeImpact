from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class WebhookProcessingResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: str  # accepted, ignored, duplicate, error
    event: str
    action: str | None = None
    delivery_id: str | None = None
    repository: str | None = None
    pr_number: int | None = None
    commit_sha: str | None = None
    analysis_id: str | None = None
    message: str | None = None
