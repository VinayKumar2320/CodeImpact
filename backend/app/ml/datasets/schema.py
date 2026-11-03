from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HistoricalPRRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    repo_identifier: str
    pr_number: int
    base_sha: str
    head_sha: str
    merged_at: datetime

    # Change Size Features
    files_changed_count: int = Field(ge=0)
    lines_added: int = Field(ge=0)
    lines_deleted: int = Field(ge=0)
    change_size: int = Field(ge=0)
    functions_modified_count: int = Field(ge=0)
    functions_added_count: int = Field(default=0, ge=0)
    functions_deleted_count: int = Field(default=0, ge=0)
    classes_modified_count: int = Field(default=0, ge=0)
    public_api_changes_count: int = Field(default=0, ge=0)
    test_files_changed_count: int = Field(default=0, ge=0)
    config_files_changed_count: int = Field(default=0, ge=0)

    # Complexity Features
    average_complexity: float = Field(ge=0.0)
    max_complexity: int = Field(ge=0)
    delta_average_complexity: float = Field(default=0.0)
    delta_max_complexity: int = Field(default=0)
    modified_high_complexity_count: int = Field(default=0, ge=0)

    # Historical Churn Features
    mean_change_frequency: float = Field(ge=0.0)
    distinct_contributors_count: int = Field(ge=0)
    mean_file_age_days: float = Field(ge=0.0)
    recent_change_concentration: float = Field(ge=0.0, le=1.0)

    # Dependency Graph Features
    dependency_total_nodes: int = Field(default=1, ge=0)
    dependency_total_edges: int = Field(default=0, ge=0)
    affected_callers_count: int = Field(default=0, ge=0)
    downstream_dependencies_count: int = Field(default=0, ge=0)
    mean_betweenness_centrality: float = Field(default=0.0, ge=0.0)
    max_betweenness_centrality: float = Field(default=0.0, ge=0.0)
    mean_fan_in: float = Field(default=0.0, ge=0.0)
    mean_fan_out: float = Field(default=0.0, ge=0.0)

    # Pre-merge Test Signals
    test_coverage_ratio: float = Field(default=0.8, ge=0.0, le=1.0)
    historical_test_failure_frequency: float = Field(default=0.0, ge=0.0, le=1.0)

    # Ground Truth Post-Merge Regression
    is_regression: int = Field(ge=0, le=1)  # 0: Stable, 1: Post-merge regression
    label_tier: int = Field(ge=1, le=3)  # 1: Explicit revert, 2: Linked bugfix PR, 3: Ambiguous
    label_provenance: str
    observation_window_days: int = Field(default=30, ge=1)
    split: str = Field(default="train")  # train, val, test, cross_repo_test

    @field_validator("change_size", mode="before")
    def compute_change_size(cls, v: int | None, info) -> int:
        if v is not None:
            return v
        data = info.data
        return int(data.get("lines_added", 0) + data.get("lines_deleted", 0))


class DatasetStatistics(BaseModel):
    total_records: int
    train_records: int
    val_records: int
    test_records: int
    cross_repo_records: int
    positive_count: int
    negative_count: int
    imbalance_ratio: float  # e.g. 0.12 (12% regressions)
    repositories: list[str]
    temporal_coverage_start: datetime
    temporal_coverage_end: datetime
    leakage_check_passed: bool
