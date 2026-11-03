from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GitHubUser(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int | None = None
    login: str
    type: str | None = "User"


class GitHubRepositoryRef(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int
    name: str
    full_name: str
    owner: GitHubUser
    default_branch: str = "main"
    private: bool = False
    html_url: str | None = None


class GitHubCommitRef(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sha: str
    ref: str
    repo: GitHubRepositoryRef | None = None


class GitHubPullRequestPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int
    number: int
    title: str
    state: str = "open"
    user: GitHubUser
    head: GitHubCommitRef
    base: GitHubCommitRef
    merged_at: datetime | None = None
    draft: bool = False
    html_url: str | None = None


class GitHubInstallationRef(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int
    account: GitHubUser | None = None


class GitHubWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action: str
    number: int | None = None
    pull_request: GitHubPullRequestPayload | None = None
    repository: GitHubRepositoryRef | None = None
    sender: GitHubUser | None = None
    installation: GitHubInstallationRef | None = None


class GitHubFileChange(BaseModel):
    model_config = ConfigDict(extra="ignore")
    filename: str
    status: str  # added, modified, removed, renamed
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: str | None = None
    raw_url: str | None = None
    previous_filename: str | None = None


class GitHubCommitSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sha: str
    author_name: str
    author_email: str | None = None
    message: str
    timestamp: datetime
