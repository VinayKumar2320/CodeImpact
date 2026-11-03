from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.analysis import Analysis
    from app.models.model_version import ModelVersion


class RiskTier(enum.StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Prediction(Base, TimestampMixin):
    __tablename__ = "predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("analyses.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    model_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("model_versions.id", ondelete="SET NULL"), nullable=True
    )

    risk_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 - 1.0
    risk_tier: Mapped[str] = mapped_column(
        String(20), index=True, nullable=False
    )  # LOW, MEDIUM, HIGH, CRITICAL
    calibrated_probability: Mapped[float | None] = mapped_column(Float, nullable=True)

    # SHAP explanations or heuristic weight breakdowns
    feature_attributions: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_experimental: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    analysis: Mapped[Analysis] = relationship("Analysis", back_populates="prediction")
    model_version: Mapped[ModelVersion | None] = relationship(
        "ModelVersion", back_populates="predictions"
    )
