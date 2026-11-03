from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.prediction import Prediction


class ModelVersion(Base, TimestampMixin):
    __tablename__ = "model_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    version: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    algorithm: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # xgboost, random_forest, heuristic_baseline
    artifact_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Model evaluation metrics
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    pr_auc: Mapped[float | None] = mapped_column(Float, nullable=True)
    roc_auc: Mapped[float | None] = mapped_column(Float, nullable=True)
    brier_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    is_experimental: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    predictions: Mapped[list[Prediction]] = relationship(
        "Prediction", back_populates="model_version"
    )
