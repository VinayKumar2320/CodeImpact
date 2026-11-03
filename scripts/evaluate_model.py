#!/usr/bin/env python3
"""
scripts/evaluate_model.py
Evaluates trained CodeImpact risk prediction model against chronological holdout
and cross-repository generalization holdout datasets.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

# Ensure backend root is on sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.core.logging import get_logger
from app.ml.datasets.loader import DatasetLoader
from app.ml.features.extractor import feature_extractor

logger = get_logger("scripts.evaluate_model")


def compute_ece(y_true: np.ndarray, y_proba: np.ndarray, n_bins: int = 10) -> float:
    """Computes Expected Calibration Error (ECE)."""
    bin_limits = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(y_true)

    for i in range(n_bins):
        low, high = bin_limits[i], bin_limits[i + 1]
        mask = (
            (y_proba >= low) & (y_proba < high)
            if i < n_bins - 1
            else (y_proba >= low) & (y_proba <= high)
        )
        bin_count = np.sum(mask)
        if bin_count > 0:
            bin_acc = np.mean(y_true[mask])
            bin_conf = np.mean(y_proba[mask])
            ece += (bin_count / n) * abs(bin_acc - bin_conf)

    return float(ece)


def evaluate_split(model, records, split_name: str) -> dict:
    X, y_true = feature_extractor.extract_batch_from_records(records)
    y_proba = model.predict_proba(X)[:, 1]
    y_pred = (y_proba >= 0.5).astype(int)

    roc_auc = float(roc_auc_score(y_true, y_proba))
    pr_auc = float(average_precision_score(y_true, y_proba))
    brier = float(brier_score_loss(y_true, y_proba))
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))
    ece = compute_ece(y_true, y_proba, n_bins=10)
    cm = confusion_matrix(y_true, y_pred).tolist()

    # Calibration curve
    prob_true, prob_pred = calibration_curve(
        y_true, y_proba, n_bins=5, strategy="uniform"
    )

    return {
        "split_name": split_name,
        "sample_count": len(y_true),
        "positive_count": int(np.sum(y_true == 1)),
        "negative_count": int(np.sum(y_true == 0)),
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "brier_score": round(brier, 4),
        "ece": round(ece, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "confusion_matrix": cm,
        "calibration_curve": {
            "prob_true": [round(float(v), 4) for v in prob_true],
            "prob_pred": [round(float(v), 4) for v in prob_pred],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate CodeImpact Risk Prediction Model"
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default="backend/app/ml/models_store/risk_model_v1.joblib",
        help="Path to serialized model artifact",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="datasets",
        help="Directory containing test.jsonl and cross_repo_test.jsonl",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="backend/app/ml/models_store/evaluation_report.json",
        help="Path to save evaluation JSON report",
    )
    args = parser.parse_args()

    model_file = Path(args.model_path)
    data_dir = Path(args.data_dir)

    if not model_file.exists():
        logger.error(
            f"Model artifact not found at {model_file}. Run scripts/train_model.py first."
        )
        sys.exit(1)

    logger.info(f"Loading model bundle from {model_file}...")
    bundle = joblib.load(model_file)
    model = bundle["model"]
    model_name = bundle.get("model_name", "model")
    model_version = bundle.get("version", "1.0.0")

    test_file = data_dir / "test.jsonl"
    cross_file = data_dir / "cross_repo_test.jsonl"

    results = {
        "model_name": model_name,
        "version": model_version,
        "evaluated_at": str(Path(args.output_file)),
    }

    if test_file.exists():
        test_records = DatasetLoader.load_jsonl(test_file)
        logger.info(
            f"Evaluating on chronological test set ({len(test_records)} records)..."
        )
        results["in_domain_test"] = evaluate_split(
            model, test_records, "in_domain_test"
        )

    if cross_file.exists():
        cross_records = DatasetLoader.load_jsonl(cross_file)
        logger.info(
            f"Evaluating on cross-repository holdout set ({len(cross_records)} records)..."
        )
        results["cross_repo_test"] = evaluate_split(
            model, cross_records, "cross_repo_test"
        )

    out_file = Path(args.output_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logger.info(f"Evaluation report written to {out_file}")

    print("\n" + "=" * 60)
    print(f" MODEL EVALUATION REPORT: {model_name.upper()} v{model_version}")
    print("=" * 60)
    if "in_domain_test" in results:
        r = results["in_domain_test"]
        print("In-Domain Chronological Test Holdout:")
        print(f"  PR-AUC:      {r['pr_auc']:.4f}")
        print(f"  ROC-AUC:     {r['roc_auc']:.4f}")
        print(f"  Brier Score: {r['brier_score']:.4f}")
        print(f"  ECE:         {r['ece']:.4f}")
        print(f"  F1 Score:    {r['f1']:.4f}")
        print(f"  Confusion Matrix: {r['confusion_matrix']}")

    if "cross_repo_test" in results:
        r = results["cross_repo_test"]
        print("\nCross-Repository Generalization Holdout (pallets/flask):")
        print(f"  PR-AUC:      {r['pr_auc']:.4f}")
        print(f"  ROC-AUC:     {r['roc_auc']:.4f}")
        print(f"  Brier Score: {r['brier_score']:.4f}")
        print(f"  ECE:         {r['ece']:.4f}")
        print(f"  F1 Score:    {r['f1']:.4f}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
