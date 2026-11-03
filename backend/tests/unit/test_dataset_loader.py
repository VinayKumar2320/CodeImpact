from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.ml.datasets.loader import DataLeakageError, DatasetLoader
from app.ml.datasets.schema import HistoricalPRRecord


@pytest.fixture
def sample_records() -> list[HistoricalPRRecord]:
    base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    records = []
    # 5 train records
    for i in range(5):
        records.append(
            HistoricalPRRecord(
                repo_identifier="org/repo",
                pr_number=i + 1,
                base_sha=f"base_{i}",
                head_sha=f"head_{i}",
                merged_at=base_time + timedelta(days=i),
                files_changed_count=2,
                lines_added=10 * (i + 1),
                lines_deleted=5,
                change_size=10 * (i + 1) + 5,
                functions_modified_count=1,
                average_complexity=3.5,
                max_complexity=5,
                delta_average_complexity=0.5,
                delta_max_complexity=1,
                mean_change_frequency=2.5,
                distinct_contributors_count=2,
                mean_file_age_days=60.0,
                recent_change_concentration=0.25,
                affected_callers_count=2,
                is_regression=1 if i == 0 else 0,
                label_tier=1 if i == 0 else 3,
                label_provenance="revert_commit" if i == 0 else "stable_no_issues",
                split="train",
            )
        )
    # 2 val records
    for i in range(2):
        records.append(
            HistoricalPRRecord(
                repo_identifier="org/repo",
                pr_number=i + 6,
                base_sha=f"base_val_{i}",
                head_sha=f"head_val_{i}",
                merged_at=base_time + timedelta(days=10 + i),
                files_changed_count=1,
                lines_added=15,
                lines_deleted=3,
                change_size=18,
                functions_modified_count=1,
                average_complexity=3.0,
                max_complexity=4,
                mean_change_frequency=1.2,
                distinct_contributors_count=1,
                mean_file_age_days=90.0,
                recent_change_concentration=0.1,
                affected_callers_count=1,
                is_regression=0,
                label_tier=3,
                label_provenance="stable_no_issues",
                split="val",
            )
        )
    # 2 test records
    for i in range(2):
        records.append(
            HistoricalPRRecord(
                repo_identifier="org/repo",
                pr_number=i + 8,
                base_sha=f"base_test_{i}",
                head_sha=f"head_test_{i}",
                merged_at=base_time + timedelta(days=20 + i),
                files_changed_count=3,
                lines_added=40,
                lines_deleted=10,
                change_size=50,
                functions_modified_count=2,
                average_complexity=6.0,
                max_complexity=8,
                mean_change_frequency=4.0,
                distinct_contributors_count=3,
                mean_file_age_days=45.0,
                recent_change_concentration=0.5,
                affected_callers_count=4,
                is_regression=1 if i == 1 else 0,
                label_tier=2 if i == 1 else 3,
                label_provenance="issue_reference" if i == 1 else "stable_no_issues",
                split="test",
            )
        )
    return records


def test_validate_temporal_splits_success(sample_records: list[HistoricalPRRecord]):
    train = [r for r in sample_records if r.split == "train"]
    val = [r for r in sample_records if r.split == "val"]
    test = [r for r in sample_records if r.split == "test"]

    assert DatasetLoader.validate_temporal_splits(train, val, test) is True


def test_validate_temporal_splits_detects_leakage(sample_records: list[HistoricalPRRecord]):
    train = [r for r in sample_records if r.split == "train"]
    val = [r for r in sample_records if r.split == "val"]
    test = [r for r in sample_records if r.split == "test"]

    leaked_record = train[0].model_copy(update={"merged_at": val[0].merged_at + timedelta(days=1)})
    leaked_train = [leaked_record] + train[1:]

    with pytest.raises(DataLeakageError) as exc_info:
        DatasetLoader.validate_temporal_splits(leaked_train, val, test)

    assert "Temporal leakage" in str(exc_info.value)


def test_compute_statistics(sample_records: list[HistoricalPRRecord]):
    stats = DatasetLoader.compute_statistics(sample_records)
    assert stats.total_records == 9
    assert stats.train_records == 5
    assert stats.val_records == 2
    assert stats.test_records == 2
    assert stats.positive_count == 2
    assert stats.negative_count == 7
    assert stats.leakage_check_passed is True
    assert stats.repositories == ["org/repo"]


def test_to_dataframe(sample_records: list[HistoricalPRRecord]):
    df = DatasetLoader.to_dataframe(sample_records)
    assert len(df) == 9
    assert "is_regression" in df.columns
    assert "delta_average_complexity" in df.columns
    assert "affected_callers_count" in df.columns


def test_load_generated_datasets_from_disk():
    datasets_dir = Path(__file__).resolve().parents[3] / "datasets"
    train_path = datasets_dir / "train.jsonl"
    val_path = datasets_dir / "val.jsonl"
    test_path = datasets_dir / "test.jsonl"
    cross_path = datasets_dir / "cross_repo_test.jsonl"

    if not train_path.exists():
        pytest.skip("Dataset files not yet generated on disk")

    train_recs = DatasetLoader.load_jsonl(train_path)
    val_recs = DatasetLoader.load_jsonl(val_path)
    test_recs = DatasetLoader.load_jsonl(test_path)
    cross_recs = DatasetLoader.load_jsonl(cross_path)

    assert len(train_recs) > 0
    assert len(val_recs) > 0
    assert len(test_recs) > 0
    assert len(cross_recs) > 0

    assert DatasetLoader.validate_temporal_splits(train_recs, val_recs, test_recs) is True
