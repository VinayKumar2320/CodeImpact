from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import shap
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.core.logging import get_logger
from app.ml.datasets.schema import HistoricalPRRecord
from app.ml.features.extractor import FEATURE_NAMES, feature_extractor

logger = get_logger(__name__)


@dataclass
class EvaluationMetrics:
    roc_auc: float
    pr_auc: float
    brier_score: float
    precision: float
    recall: float
    f1: float
    log_loss: float

    def to_dict(self) -> dict[str, float]:
        return {
            "roc_auc": round(self.roc_auc, 4),
            "pr_auc": round(self.pr_auc, 4),
            "brier_score": round(self.brier_score, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "log_loss": round(self.log_loss, 4),
        }


class MajorityBaseline:
    """Predicts empirical class prevalence for all samples."""

    def __init__(self) -> None:
        self.prevalence = 0.0

    def fit(self, _X: np.ndarray, y: np.ndarray) -> MajorityBaseline:
        self.prevalence = float(np.mean(y))
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        n = X.shape[0]
        pos = np.full(n, self.prevalence)
        neg = 1.0 - pos
        return np.column_stack([neg, pos])

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.zeros(X.shape[0], dtype=np.int64)


class ChangeSizeHeuristic:
    """Estimates risk purely as a sigmoid over total lines changed."""

    def fit(self, _X: np.ndarray, _y: np.ndarray) -> ChangeSizeHeuristic:
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        # change_size is index 0 in FEATURE_NAMES
        change_size = X[:, 0]
        # Sigmoid calibrated so 500 lines ~ 0.5 probability
        probs = 1.0 / (1.0 + np.exp(-(change_size - 300.0) / 150.0))
        return np.column_stack([1.0 - probs, probs])

    def predict(self, X: np.ndarray) -> np.ndarray:
        probs = self.predict_proba(X)[:, 1]
        return (probs >= 0.5).astype(np.int64)


class ModelTrainer:
    """
    Trains, evaluates, and exports regression risk models.
    Supports Baselines, Logistic Regression, Random Forest, and XGBoost with TreeSHAP.
    """

    def __init__(self, version: str = "1.0.0") -> None:
        self.version = version

    def compute_metrics(
        self, y_true: np.ndarray, y_proba: np.ndarray, y_pred: np.ndarray
    ) -> EvaluationMetrics:
        roc_auc = float(roc_auc_score(y_true, y_proba))
        pr_auc = float(average_precision_score(y_true, y_proba))
        brier = float(brier_score_loss(y_true, y_proba))
        prec = float(precision_score(y_true, y_pred, zero_division=0))
        rec = float(recall_score(y_true, y_pred, zero_division=0))
        f1 = float(f1_score(y_true, y_pred, zero_division=0))
        eps = 1e-15
        clipped_proba = np.clip(y_proba, eps, 1.0 - eps)
        ll = float(log_loss(y_true, clipped_proba))

        return EvaluationMetrics(
            roc_auc=roc_auc,
            pr_auc=pr_auc,
            brier_score=brier,
            precision=prec,
            recall=rec,
            f1=f1,
            log_loss=ll,
        )

    def train_and_evaluate(
        self,
        train_records: list[HistoricalPRRecord],
        val_records: list[HistoricalPRRecord],
    ) -> dict[str, Any]:
        """
        Trains all candidate models, evaluates them on validation set,
        and returns best model bundle along with comparative evaluation results.
        """
        X_train, y_train = feature_extractor.extract_batch_from_records(train_records)
        X_val, y_val = feature_extractor.extract_batch_from_records(val_records)

        pos_count = int(np.sum(y_train == 1))
        neg_count = int(np.sum(y_train == 0))
        scale_pos_weight = float(neg_count / max(pos_count, 1))

        logger.info(
            f"Training set: {len(y_train)} samples ({pos_count} pos, {neg_count} neg, scale_pos_weight={scale_pos_weight:.2f})"
        )
        logger.info(f"Validation set: {len(y_val)} samples ({np.sum(y_val == 1)} pos)")

        # 1. Baseline: Majority Class
        majority_model = MajorityBaseline().fit(X_train, y_train)
        maj_proba = majority_model.predict_proba(X_val)[:, 1]
        maj_pred = majority_model.predict(X_val)
        maj_metrics = self.compute_metrics(y_val, maj_proba, maj_pred)

        # 2. Baseline: Change Size Heuristic
        size_heuristic = ChangeSizeHeuristic().fit(X_train, y_train)
        size_proba = size_heuristic.predict_proba(X_val)[:, 1]
        size_pred = size_heuristic.predict(X_val)
        size_metrics = self.compute_metrics(y_val, size_proba, size_pred)

        # 3. Logistic Regression
        lr_pipeline = Pipeline([
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    C=0.5,
                    class_weight="balanced",
                    max_iter=1000,
                    random_state=42,
                ),
            ),
        ])
        lr_pipeline.fit(X_train, y_train)
        lr_proba = lr_pipeline.predict_proba(X_val)[:, 1]
        lr_pred = lr_pipeline.predict(X_val)
        lr_metrics = self.compute_metrics(y_val, lr_proba, lr_pred)

        # 4. Random Forest
        rf_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=5,
            class_weight="balanced",
            min_samples_split=5,
            random_state=42,
        )
        rf_model.fit(X_train, y_train)
        rf_proba = rf_model.predict_proba(X_val)[:, 1]
        rf_pred = rf_model.predict(X_val)
        rf_metrics = self.compute_metrics(y_val, rf_proba, rf_pred)

        # 5. XGBoost
        xgb_model = xgb.XGBClassifier(
            n_estimators=120,
            max_depth=4,
            learning_rate=0.04,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight,
            eval_metric="logloss",
            random_state=42,
        )
        xgb_model.fit(X_train, y_train)
        xgb_proba = xgb_model.predict_proba(X_val)[:, 1]
        xgb_pred = (xgb_proba >= 0.5).astype(np.int64)
        xgb_metrics = self.compute_metrics(y_val, xgb_proba, xgb_pred)

        all_models = {
            "majority_baseline": (majority_model, maj_metrics),
            "change_size_heuristic": (size_heuristic, size_metrics),
            "logistic_regression": (lr_pipeline, lr_metrics),
            "random_forest": (rf_model, rf_metrics),
            "xgboost": (xgb_model, xgb_metrics),
        }

        # Select best supervised model by PR-AUC (crucial for imbalanced classification)
        supervised_candidates = ["xgboost", "random_forest", "logistic_regression"]
        best_name = max(supervised_candidates, key=lambda k: all_models[k][1].pr_auc)
        best_model, best_metrics = all_models[best_name]

        logger.info(f"Selected best model: {best_name} with PR-AUC={best_metrics.pr_auc:.4f}")

        # Fit TreeSHAP explainer if tree-based model
        explainer = None
        if best_name in ("xgboost", "random_forest"):
            try:
                # TreeExplainer for tree ensemble
                explainer = shap.TreeExplainer(best_model)
                logger.info("Fitted TreeSHAP explainer successfully.")
            except Exception as e:
                logger.warning(f"Failed to fit TreeSHAP explainer: {e}")

        artifact_bundle = {
            "model": best_model,
            "model_name": best_name,
            "version": self.version,
            "feature_names": FEATURE_NAMES,
            "validation_metrics": best_metrics.to_dict(),
            "comparison_metrics": {k: v[1].to_dict() for k, v in all_models.items()},
            "trained_at": datetime.now(UTC).isoformat(),
            "explainer": explainer,
            "training_samples_count": len(y_train),
            "class_balance_ratio": float(pos_count / len(y_train)),
        }

        return artifact_bundle

    def save_model(
        self,
        artifact_bundle: dict[str, Any],
        output_dir: Path | str,
        filename: str = "risk_model_v1.joblib",
    ) -> Path:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        model_file = out_path / filename

        # Remove unpicklable objects if any or serialize directly
        joblib.dump(artifact_bundle, model_file, compress=3)
        logger.info(f"Serialized model artifact bundle to {model_file}")
        return model_file


model_trainer = ModelTrainer()
