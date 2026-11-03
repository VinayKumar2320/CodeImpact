from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.prediction import Prediction
    from app.models.pull_request import PullRequest
    from app.models.test_case import TestRecommendation


class AnalysisStatus(enum.StrEnum):
    QUEUED = "QUEUED"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


class Analysis(Base, TimestampMixin):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pull_request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pull_requests.id", ondelete="CASCADE"), index=True, nullable=False
    )
    commit_sha: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    base_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="PENDING", index=True, nullable=False
    )  # PENDING, RUNNING, COMPLETED, FAILED
    analysis_version: Mapped[str] = mapped_column(String(20), default="1.0.0", nullable=False)

    # Feature vectors extracted from static analysis
    features: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Serialized dependency subgraph (nodes, edges, centrality)
    dependency_graph: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Runtime and metrics
    execution_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    pull_request: Mapped[PullRequest] = relationship("PullRequest", back_populates="analyses")
    prediction: Mapped[Prediction | None] = relationship(
        "Prediction", back_populates="analysis", uselist=False, cascade="all, delete-orphan"
    )
    recommended_tests: Mapped[list[TestRecommendation]] = relationship(
        "TestRecommendation",
        back_populates="analysis",
        cascade="all, delete-orphan",
        order_by="TestRecommendation.rank",
    )
