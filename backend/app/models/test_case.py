from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.analysis import Analysis
    from app.models.repository import Repository


class TestCase(Base, TimestampMixin):
    __tablename__ = "test_cases"
    __test__ = False

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    test_identifier: Mapped[str] = mapped_column(
        String(500), index=True, nullable=False
    )  # e.g. tests/test_auth.py::test_token_expiry
    file_path: Mapped[str] = mapped_column(String(500), index=True, nullable=False)
    test_name: Mapped[str] = mapped_column(String(200), nullable=False)

    average_duration_ms: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    historical_failure_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    repository: Mapped[Repository] = relationship("Repository", back_populates="test_cases")
    recommendations: Mapped[list[TestRecommendation]] = relationship(
        "TestRecommendation", back_populates="test_case"
    )


class TestRecommendation(Base, TimestampMixin):
    __tablename__ = "test_recommendations"
    __test__ = False

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analyses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    test_case_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("test_cases.id", ondelete="SET NULL"), nullable=True
    )

    test_identifier: Mapped[str] = mapped_column(String(500), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)  # Order of recommendation
    selection_reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_level: Mapped[str] = mapped_column(
        String(50), default="EVIDENCE_DYNAMIC_COVERAGE", nullable=False
    )  # DYNAMIC_COVERAGE, STATIC_CALL_GRAPH, DEPENDENCY_HEURISTIC
    estimated_duration_ms: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Relationships
    analysis: Mapped[Analysis] = relationship("Analysis", back_populates="recommended_tests")
    test_case: Mapped[TestCase | None] = relationship("TestCase", back_populates="recommendations")
