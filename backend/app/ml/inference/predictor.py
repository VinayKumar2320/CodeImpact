from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from app.core.logging import get_logger
from app.ml.features.extractor import FEATURE_NAMES, feature_extractor
from app.models.prediction import RiskTier

logger = get_logger(__name__)


@dataclass
class FactorAttribution:
    feature_name: str
    feature_value: float
    attribution_score: float  # SHAP value or heuristic weight
    direction: str  # "RISK_INCREASING" | "RISK_REDUCING"
    human_explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "feature_value": round(self.feature_value, 3),
            "attribution_score": round(self.attribution_score, 4),
            "direction": self.direction,
            "human_explanation": self.human_explanation,
        }


@dataclass
class RiskPredictionResult:
    risk_score: float  # Calibrated probability [0.0, 1.0]
    risk_tier: RiskTier
    confidence_lower: float
    confidence_upper: float
    model_version: str
    model_name: str
    top_risk_factors: list[FactorAttribution]
    top_protective_factors: list[FactorAttribution]
    raw_features: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_score": round(self.risk_score, 4),
            "risk_tier": self.risk_tier.value,
            "confidence_lower": round(self.confidence_lower, 4),
            "confidence_upper": round(self.confidence_upper, 4),
            "model_version": self.model_version,
            "model_name": self.model_name,
            "top_risk_factors": [f.to_dict() for f in self.top_risk_factors],
            "top_protective_factors": [f.to_dict() for f in self.top_protective_factors],
            "raw_features": {k: round(v, 4) for k, v in self.raw_features.items()},
        }


def generate_human_explanation(feature_name: str, val: float, score: float) -> str:
    """Generates natural language explanation for an individual feature attribution."""
    is_positive = score > 0
    sign_str = f"+{score:.3f}" if is_positive else f"{score:.3f}"

    if feature_name == "change_size":
        if is_positive:
            return f"Large pull request size ({int(val)} lines modified) increased risk by {sign_str}."
        return f"Compact pull request size ({int(val)} lines modified) reduced risk by {sign_str}."

    if feature_name in ("delta_average_complexity", "delta_max_complexity"):
        if is_positive:
            return f"Increased cyclomatic complexity (+{val:.1f}) elevated logic branch risk by {sign_str}."
        return f"Complexity remained stable or decreased, reducing regression likelihood by {sign_str}."

    if feature_name == "affected_callers_count":
        if is_positive:
            return f"{int(val)} downstream callers transitively depend on changed symbols, increasing impact by {sign_str}."
        return f"Isolated changes with {int(val)} affected callers minimized blast radius by {sign_str}."

    if feature_name == "public_api_changes_count":
        if is_positive:
            return f"{int(val)} public API modifications create potential interface breakage ({sign_str})."
        return "Internal implementation changes without public API modifications."

    if feature_name == "test_coverage_ratio":
        if is_positive:
            return f"Low pre-merge test coverage ({val*100:.0f}%) increased regression likelihood by {sign_str}."
        return f"High pre-merge test coverage ({val*100:.0f}%) effectively mitigated risk by {sign_str}."

    if feature_name == "mean_change_frequency":
        if is_positive:
            return f"Modifications to frequently churning hot-spot files ({val:.1f} historical edits/mo) added {sign_str} risk."
        return f"Low-churn, well-stabilized files reduced risk by {sign_str}."

    if feature_name == "modified_high_complexity_count":
        if is_positive:
            return f"{int(val)} modified functions have cyclomatic complexity >= 10, increasing risk by {sign_str}."
        return "No high-complexity functions modified."

    direction_verb = "increased" if is_positive else "reduced"
    return f"{feature_name.replace('_', ' ').capitalize()} ({val:.2f}) {direction_verb} risk score by {sign_str}."


class RiskPredictor:
    """
    Inference engine that executes ML model predictions and generates
    TreeSHAP local feature explanations.
    """

    def __init__(self, model_path: str | Path | None = None) -> None:
        self.model_path = Path(model_path) if model_path else None
        self.model: Any = None
        self.explainer: Any = None
        self.model_name: str = "heuristic_fallback"
        self.model_version: str = "0.9.0-heuristic"
        self._load_model_if_available()

    def _load_model_if_available(self) -> bool:
        if self.model_path is not None:
            if self.model_path.exists():
                return self._load_from_file(self.model_path)
            logger.info("Using calibrated heuristic fallback risk predictor")
            return False

        default_store = Path(__file__).resolve().parent.parent / "models_store" / "risk_model_v1.joblib"
        if default_store.exists():
            return self._load_from_file(default_store)

        logger.info("Using calibrated heuristic fallback risk predictor")
        return False

    def _load_from_file(self, path: Path) -> bool:
        try:
            logger.info(f"Loading risk model artifact from {path}")
            bundle = joblib.load(path)
            self.model = bundle["model"]
            self.explainer = bundle.get("explainer")
            self.model_name = bundle.get("model_name", "xgboost")
            self.model_version = bundle.get("version", "1.0.0")
            logger.info(f"Successfully loaded {self.model_name} (version {self.model_version})")
            return True
        except Exception as err:
            logger.warning(f"Failed to load model artifact at {path}: {err}")
            return False

    def predict(self, raw_features: dict[str, Any]) -> RiskPredictionResult:
        """Computes calibrated risk score, risk tier, and feature explanations."""
        feat_vector = feature_extractor.extract_from_dict(raw_features)
        X_sample = feat_vector.reshape(1, -1)

        raw_feat_dict = {
            name: float(feat_vector[i]) for i, name in enumerate(FEATURE_NAMES)
        }

        # Predict probability
        if self.model is not None:
            try:
                proba = float(self.model.predict_proba(X_sample)[0, 1])
            except Exception as e:
                logger.warning(f"Model prediction failed, falling back to heuristic: {e}")
                proba = self._heuristic_probability(raw_feat_dict)
        else:
            proba = self._heuristic_probability(raw_feat_dict)

        risk_score = max(0.01, min(0.99, proba))
        risk_tier = self._assign_tier(risk_score)

        # Approximate 90% confidence interval around point prediction
        margin = max(0.04, 0.15 * (1.0 - abs(risk_score - 0.5) * 1.5))
        ci_lower = max(0.0, risk_score - margin)
        ci_upper = min(1.0, risk_score + margin)

        # Compute feature attributions (TreeSHAP or heuristic)
        attributions = self._compute_attributions(X_sample, raw_feat_dict)

        risk_factors = [a for a in attributions if a.direction == "RISK_INCREASING"]
        protective_factors = [a for a in attributions if a.direction == "RISK_REDUCING"]

        risk_factors.sort(key=lambda a: a.attribution_score, reverse=True)
        protective_factors.sort(key=lambda a: a.attribution_score)

        return RiskPredictionResult(
            risk_score=risk_score,
            risk_tier=risk_tier,
            confidence_lower=ci_lower,
            confidence_upper=ci_upper,
            model_version=self.model_version,
            model_name=self.model_name,
            top_risk_factors=risk_factors[:5],
            top_protective_factors=protective_factors[:3],
            raw_features=raw_feat_dict,
        )

    def _assign_tier(self, score: float) -> RiskTier:
        if score < 0.20:
            return RiskTier.LOW
        if score < 0.50:
            return RiskTier.MEDIUM
        if score < 0.75:
            return RiskTier.HIGH
        return RiskTier.CRITICAL

    def _heuristic_probability(self, features: dict[str, float]) -> float:
        """Calibrated heuristic risk estimation when no trained ML model is available."""
        score = 0.10  # base probability
        # Size factor
        size = features.get("change_size", 0.0)
        score += min(0.35, size / 1200.0)

        # Complexity factor
        delta_cc = features.get("delta_average_complexity", 0.0)
        if delta_cc > 0:
            score += min(0.25, delta_cc * 0.05)

        high_cc_funcs = features.get("modified_high_complexity_count", 0.0)
        score += min(0.20, high_cc_funcs * 0.08)

        # Blast radius
        callers = features.get("affected_callers_count", 0.0)
        score += min(0.20, callers * 0.03)

        # Public API modifications
        api_changes = features.get("public_api_changes_count", 0.0)
        score += min(0.15, api_changes * 0.05)

        # Test coverage reduction
        cov = features.get("test_coverage_ratio", 0.8)
        score -= min(0.20, cov * 0.20)

        return float(np.clip(score, 0.02, 0.98))

    def _compute_attributions(
        self, X_sample: np.ndarray, raw_features: dict[str, float]
    ) -> list[FactorAttribution]:
        """Computes TreeSHAP or feature-contribution attributions."""
        attributions: list[FactorAttribution] = []

        if self.explainer is not None:
            try:
                # TreeSHAP values for single sample
                shap_values = self.explainer.shap_values(X_sample)
                # If binary classification, shap_values may be a list of 2 arrays or 1 array
                if isinstance(shap_values, list) and len(shap_values) == 2:
                    vals = shap_values[1][0]
                elif hasattr(shap_values, "ndim") and shap_values.ndim == 3:
                    vals = shap_values[0, :, 1]
                else:
                    vals = np.array(shap_values).flatten()

                for i, name in enumerate(FEATURE_NAMES):
                    score = float(vals[i])
                    val = raw_features.get(name, 0.0)
                    if abs(score) > 0.005:  # filter noise
                        direction = (
                            "RISK_INCREASING" if score > 0 else "RISK_REDUCING"
                        )
                        explanation = generate_human_explanation(name, val, score)
                        attributions.append(
                            FactorAttribution(
                                feature_name=name,
                                feature_value=val,
                                attribution_score=score,
                                direction=direction,
                                human_explanation=explanation,
                            )
                        )
                return attributions
            except Exception as e:
                logger.warning(f"TreeSHAP calculation failed, using heuristic: {e}")

        # Heuristic attributions
        for name, val in raw_features.items():
            score = 0.0
            if name == "change_size":
                score = (val - 150.0) / 1000.0
            elif name == "delta_average_complexity":
                score = val * 0.08
            elif name == "affected_callers_count":
                score = val * 0.04
            elif name == "modified_high_complexity_count":
                score = val * 0.10
            elif name == "test_coverage_ratio":
                score = -(val - 0.5) * 0.3
            elif name == "public_api_changes_count":
                score = val * 0.07

            if abs(score) > 0.01:
                direction = "RISK_INCREASING" if score > 0 else "RISK_REDUCING"
                explanation = generate_human_explanation(name, val, score)
                attributions.append(
                    FactorAttribution(
                        feature_name=name,
                        feature_value=val,
                        attribution_score=score,
                        direction=direction,
                        human_explanation=explanation,
                    )
                )

        return attributions


risk_predictor = RiskPredictor()
