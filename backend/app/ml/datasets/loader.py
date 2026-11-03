from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.core.logging import get_logger
from app.ml.datasets.schema import DatasetStatistics, HistoricalPRRecord

logger = get_logger(__name__)


class DataLeakageError(Exception):
    pass


class DatasetLoader:
    """
    Loads, validates, and audits historical pull request records.
    Enforces strict chronological partitioning and leakage audit assertions.
    """

    @staticmethod
    def load_jsonl(file_path: str | Path) -> list[HistoricalPRRecord]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Dataset file not found: {path}")

        records: list[HistoricalPRRecord] = []
        with open(path, encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    record = HistoricalPRRecord.model_validate(data)
                    records.append(record)
                except Exception as err:
                    logger.warning(f"Skipping invalid record at {path}:{line_no}: {err}")

        return records

    @staticmethod
    def validate_temporal_splits(
        train_records: list[HistoricalPRRecord],
        val_records: list[HistoricalPRRecord],
        test_records: list[HistoricalPRRecord],
    ) -> bool:
        """
        Verify that for every repository appearing in training, all train records
        precede validation records, which precede test records chronologically.
        """
        repos = {r.repo_identifier for r in train_records}

        for repo in repos:
            repo_train = [r for r in train_records if r.repo_identifier == repo]
            repo_val = [r for r in val_records if r.repo_identifier == repo]
            repo_test = [r for r in test_records if r.repo_identifier == repo]

            if repo_train and repo_val:
                max_train_time = max(r.merged_at for r in repo_train)
                min_val_time = min(r.merged_at for r in repo_val)
                if max_train_time >= min_val_time:
                    raise DataLeakageError(
                        f"Temporal leakage in {repo}: train record ({max_train_time}) occurs at or after val record ({min_val_time})"
                    )

            if repo_val and repo_test:
                max_val_time = max(r.merged_at for r in repo_val)
                min_test_time = min(r.merged_at for r in repo_test)
                if max_val_time >= min_test_time:
                    raise DataLeakageError(
                        f"Temporal leakage in {repo}: val record ({max_val_time}) occurs at or after test record ({min_test_time})"
                    )

        return True

    @staticmethod
    def compute_statistics(records: list[HistoricalPRRecord]) -> DatasetStatistics:
        if not records:
            raise ValueError("Cannot compute statistics on empty record list")

        train_count = sum(1 for r in records if r.split == "train")
        val_count = sum(1 for r in records if r.split == "val")
        test_count = sum(1 for r in records if r.split == "test")
        cross_count = sum(1 for r in records if r.split == "cross_repo_test")

        pos_count = sum(1 for r in records if r.is_regression == 1)
        neg_count = sum(1 for r in records if r.is_regression == 0)

        repos = sorted({r.repo_identifier for r in records})
        start_time = min(r.merged_at for r in records)
        end_time = max(r.merged_at for r in records)

        # Audit leakage
        train_recs = [r for r in records if r.split == "train"]
        val_recs = [r for r in records if r.split == "val"]
        test_recs = [r for r in records if r.split == "test"]

        leakage_passed = False
        try:
            if train_recs and val_recs and test_recs:
                leakage_passed = DatasetLoader.validate_temporal_splits(
                    train_recs, val_recs, test_recs
                )
            else:
                leakage_passed = True
        except DataLeakageError:
            leakage_passed = False

        imbalance = round(pos_count / len(records), 4)

        return DatasetStatistics(
            total_records=len(records),
            train_records=train_count,
            val_records=val_count,
            test_records=test_count,
            cross_repo_records=cross_count,
            positive_count=pos_count,
            negative_count=neg_count,
            imbalance_ratio=imbalance,
            repositories=repos,
            temporal_coverage_start=start_time,
            temporal_coverage_end=end_time,
            leakage_check_passed=leakage_passed,
        )

    @staticmethod
    def to_dataframe(records: list[HistoricalPRRecord]) -> pd.DataFrame:
        rows = [r.model_dump() for r in records]
        df = pd.DataFrame(rows)
        if "merged_at" in df.columns:
            df["merged_at"] = pd.to_datetime(df["merged_at"])
        return df


dataset_loader = DatasetLoader()
