from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.pull_request import PullRequest
    from app.models.test_case import TestCase


class Repository(Base, TimestampMixin):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    owner: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    default_branch: Mapped[str] = mapped_column(String(100), default="main", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    webhook_installed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    pull_requests: Mapped[list[PullRequest]] = relationship(
        "PullRequest", back_populates="repository", cascade="all, delete-orphan"
    )
    test_cases: Mapped[list[TestCase]] = relationship(
        "TestCase", back_populates="repository", cascade="all, delete-orphan"
    )
