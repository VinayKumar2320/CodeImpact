from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.core.logging import get_logger
from app.ml.datasets.schema import HistoricalPRRecord

logger = get_logger(__name__)

FEATURE_NAMES = [
    "change_size",
    "lines_added",
    "lines_deleted",
    "files_changed_count",
    "functions_modified_count",
    "functions_added_count",
    "functions_deleted_count",
    "classes_modified_count",
    "public_api_changes_count",
    "test_files_changed_count",
    "config_files_changed_count",
    "average_complexity",
    "max_complexity",
    "delta_average_complexity",
    "delta_max_complexity",
    "modified_high_complexity_count",
    "mean_change_frequency",
    "distinct_contributors_count",
    "mean_file_age_days",
    "recent_change_concentration",
    "affected_callers_count",
    "downstream_dependencies_count",
    "mean_betweenness_centrality",
    "test_coverage_ratio",
    "historical_test_failure_frequency",
]

DEFAULT_VALUES: dict[str, float] = {
    "change_size": 0.0,
    "lines_added": 0.0,
    "lines_deleted": 0.0,
    "files_changed_count": 0.0,
    "functions_modified_count": 0.0,
    "functions_added_count": 0.0,
    "functions_deleted_count": 0.0,
    "classes_modified_count": 0.0,
    "public_api_changes_count": 0.0,
    "test_files_changed_count": 0.0,
    "config_files_changed_count": 0.0,
    "average_complexity": 1.0,
    "max_complexity": 1.0,
    "delta_average_complexity": 0.0,
    "delta_max_complexity": 0.0,
    "modified_high_complexity_count": 0.0,
    "mean_change_frequency": 1.0,
    "distinct_contributors_count": 1.0,
    "mean_file_age_days": 30.0,
    "recent_change_concentration": 0.0,
    "affected_callers_count": 0.0,
    "downstream_dependencies_count": 0.0,
    "mean_betweenness_centrality": 0.0,
    "test_coverage_ratio": 0.8,
    "historical_test_failure_frequency": 0.0,
}


class FeatureExtractor:
    """
    Standardizes feature extraction from static analysis results, git churn metrics,
    and historical pull request records into numerical vectors for ML models.
    """

    @property
    def feature_names(self) -> list[str]:
        return list(FEATURE_NAMES)

    def extract_from_dict(self, data: dict[str, Any]) -> np.ndarray:
        """
        Extracts 1D numpy array of ordered feature values from a dictionary.
        Imputes missing values with reasonable domain defaults.
        """
        values: list[float] = []
        for name in FEATURE_NAMES:
            val = data.get(name)
            if val is None or (isinstance(val, (float, int)) and np.isnan(val)):
                val = DEFAULT_VALUES.get(name, 0.0)
            values.append(float(val))
        return np.array(values, dtype=np.float32)

    def extract_from_record(self, record: HistoricalPRRecord) -> np.ndarray:
        """Extracts feature vector from HistoricalPRRecord."""
        d = record.model_dump()
        return self.extract_from_dict(d)

    def extract_batch_from_records(
        self, records: list[HistoricalPRRecord]
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Extracts feature matrix X and target labels y from a list of records.
        """
        X_rows: list[np.ndarray] = []
        y_rows: list[int] = []

        for r in records:
            X_rows.append(self.extract_from_record(r))
            y_rows.append(r.is_regression)

        X = np.vstack(X_rows) if X_rows else np.empty((0, len(FEATURE_NAMES)))
        y = np.array(y_rows, dtype=np.int64)
        return X, y

    def to_features_dataframe(self, records: list[HistoricalPRRecord]) -> pd.DataFrame:
        """Converts records directly to a feature DataFrame."""
        X, _ = self.extract_batch_from_records(records)
        return pd.DataFrame(X, columns=FEATURE_NAMES)


feature_extractor = FeatureExtractor()
