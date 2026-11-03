"""001_initial_schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-11-03 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. repositories
    op.create_table(
        "repositories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("github_id", sa.BigInteger(), nullable=False),
        sa.Column("owner", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("default_branch", sa.String(length=100), nullable=False, server_default="main"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("webhook_installed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_repositories_github_id"), "repositories", ["github_id"], unique=True)
    op.create_index(op.f("ix_repositories_full_name"), "repositories", ["full_name"], unique=True)
    op.create_index(op.f("ix_repositories_owner"), "repositories", ["owner"], unique=False)
    op.create_index(op.f("ix_repositories_name"), "repositories", ["name"], unique=False)

    # 2. pull_requests
    op.create_table(
        "pull_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("github_pr_id", sa.BigInteger(), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("author", sa.String(length=100), nullable=False),
        sa.Column("base_sha", sa.String(length=40), nullable=False),
        sa.Column("head_sha", sa.String(length=40), nullable=False),
        sa.Column("base_ref", sa.String(length=100), nullable=False, server_default="main"),
        sa.Column("head_ref", sa.String(length=100), nullable=False),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_regression", sa.Boolean(), nullable=True),
        sa.Column("regression_label_tier", sa.Integer(), nullable=True),
        sa.Column("regression_evidence", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pull_requests_github_pr_id"), "pull_requests", ["github_pr_id"], unique=True
    )
    op.create_index(
        op.f("ix_pull_requests_repository_id"), "pull_requests", ["repository_id"], unique=False
    )
    op.create_index(
        op.f("ix_pull_requests_pr_number"), "pull_requests", ["pr_number"], unique=False
    )
    op.create_index(op.f("ix_pull_requests_head_sha"), "pull_requests", ["head_sha"], unique=False)

    # 3. analyses
    op.create_table(
        "analyses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("pull_request_id", sa.String(length=36), nullable=False),
        sa.Column("commit_sha", sa.String(length=40), nullable=False),
        sa.Column("base_sha", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("analysis_version", sa.String(length=20), nullable=False, server_default="1.0.0"),
        sa.Column("features", sa.JSON(), nullable=True),
        sa.Column("dependency_graph", sa.JSON(), nullable=True),
        sa.Column("execution_duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["pull_request_id"], ["pull_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_analyses_pull_request_id"), "analyses", ["pull_request_id"], unique=False
    )
    op.create_index(op.f("ix_analyses_commit_sha"), "analyses", ["commit_sha"], unique=False)
    op.create_index(op.f("ix_analyses_status"), "analyses", ["status"], unique=False)

    # 4. model_versions
    op.create_table(
        "model_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("algorithm", sa.String(length=50), nullable=False),
        sa.Column("artifact_path", sa.String(length=500), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("pr_auc", sa.Float(), nullable=True),
        sa.Column("roc_auc", sa.Float(), nullable=True),
        sa.Column("brier_score", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_experimental", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_model_versions_version"), "model_versions", ["version"], unique=True)
    op.create_index(op.f("ix_model_versions_name"), "model_versions", ["name"], unique=False)

    # 5. predictions
    op.create_table(
        "predictions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_id", sa.String(length=36), nullable=False),
        sa.Column("model_version_id", sa.String(length=36), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("risk_tier", sa.String(length=20), nullable=False),
        sa.Column("calibrated_probability", sa.Float(), nullable=True),
        sa.Column("feature_attributions", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("is_experimental", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_version_id"], ["model_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_predictions_analysis_id"), "predictions", ["analysis_id"], unique=True)

    # 6. test_cases
    op.create_table(
        "test_cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("test_identifier", sa.String(length=500), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("test_name", sa.String(length=200), nullable=False),
        sa.Column("average_duration_ms", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("historical_failure_rate", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_test_cases_repository_id"), "test_cases", ["repository_id"], unique=False
    )
    op.create_index(
        op.f("ix_test_cases_test_identifier"), "test_cases", ["test_identifier"], unique=False
    )

    # 7. test_recommendations
    op.create_table(
        "test_recommendations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_id", sa.String(length=36), nullable=False),
        sa.Column("test_case_id", sa.String(length=36), nullable=True),
        sa.Column("test_identifier", sa.String(length=500), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("selection_reason", sa.Text(), nullable=False),
        sa.Column(
            "evidence_level",
            sa.String(length=50),
            nullable=False,
            server_default="EVIDENCE_DYNAMIC_COVERAGE",
        ),
        sa.Column("estimated_duration_ms", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("priority_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["test_case_id"], ["test_cases.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_test_recommendations_analysis_id"),
        "test_recommendations",
        ["analysis_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("test_recommendations")
    op.drop_table("test_cases")
    op.drop_table("predictions")
    op.drop_table("model_versions")
    op.drop_table("analyses")
    op.drop_table("pull_requests")
    op.drop_table("repositories")
