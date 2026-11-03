from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.analysis import Analysis
    from app.models.repository import Repository


class PullRequest(Base, TimestampMixin):
    __tablename__ = "pull_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    github_pr_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    state: Mapped[str] = mapped_column(
        String(20), default="open", nullable=False
    )  # open, closed, merged
    author: Mapped[str] = mapped_column(String(100), nullable=False)
    base_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    head_sha: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    base_ref: Mapped[str] = mapped_column(String(100), default="main", nullable=False)
    head_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Ground Truth Regression Tracking
    is_regression: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    regression_label_tier: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # 1: Explicit revert, 2: Linked bugfix PR, 3: Ambiguous
    regression_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    repository: Mapped[Repository] = relationship("Repository", back_populates="pull_requests")
    analyses: Mapped[list[Analysis]] = relationship(
        "Analysis",
        back_populates="pull_request",
        cascade="all, delete-orphan",
        order_by="desc(Analysis.created_at)",
    )
