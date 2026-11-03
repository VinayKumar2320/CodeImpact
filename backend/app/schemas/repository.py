from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RepositoryCreate(BaseModel):
    full_name: str = Field(description="Owner and repository name, e.g. tiangolo/fastapi")
    default_branch: str = Field(default="main")


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    owner: str
    name: str
    default_branch: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
