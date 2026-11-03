import numpy as np

from app.ml.features.extractor import FEATURE_NAMES, FeatureExtractor, feature_extractor


def test_feature_extractor_feature_names_order():
    extractor = FeatureExtractor()
    assert len(extractor.feature_names) == 25
    assert extractor.feature_names[0] == "change_size"
    assert "delta_average_complexity" in extractor.feature_names
    assert "affected_callers_count" in extractor.feature_names


def test_feature_extractor_extract_from_dict_defaults():
    empty_dict = {}
    vec = feature_extractor.extract_from_dict(empty_dict)
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (25,)
    # Defaults should be applied
    assert vec[0] == 0.0  # change_size
    assert vec[FEATURE_NAMES.index("test_coverage_ratio")] == 0.8
    assert vec[FEATURE_NAMES.index("mean_file_age_days")] == 30.0


def test_feature_extractor_extract_from_dict_with_values():
    data = {
        "change_size": 250,
        "lines_added": 200,
        "lines_deleted": 50,
        "delta_average_complexity": 3.2,
        "affected_callers_count": 8,
        "test_coverage_ratio": 0.95,
    }
    vec = feature_extractor.extract_from_dict(data)
    assert vec[FEATURE_NAMES.index("change_size")] == 250.0
    assert vec[FEATURE_NAMES.index("delta_average_complexity")] == 3.2
    assert vec[FEATURE_NAMES.index("affected_callers_count")] == 8.0
    assert vec[FEATURE_NAMES.index("test_coverage_ratio")] == 0.95
