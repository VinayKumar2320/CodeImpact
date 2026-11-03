#!/usr/bin/env python3
"""
scripts/train_model.py
Trains baseline and supervised regression risk prediction models using
chronologically partitioned datasets with TreeSHAP explainability.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.core.logging import get_logger
from app.ml.datasets.loader import DatasetLoader
from app.ml.training.trainer import ModelTrainer

logger = get_logger("scripts.train_model")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train CodeImpact Risk Prediction Model"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="datasets",
        help="Directory containing train.jsonl and val.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="backend/app/ml/models_store",
        help="Directory to save trained model artifact",
    )
    parser.add_argument(
        "--version",
        type=str,
        default="1.0.0",
        help="Model semantic version string",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    train_file = data_dir / "train.jsonl"
    val_file = data_dir / "val.jsonl"

    if not train_file.exists() or not val_file.exists():
        logger.error(
            f"Missing train or val dataset in {data_dir}. Run scripts/collect_dataset.py first."
        )
        sys.exit(1)

    logger.info(f"Loading datasets from {data_dir}...")
    train_records = DatasetLoader.load_jsonl(train_file)
    val_records = DatasetLoader.load_jsonl(val_file)

    logger.info(
        f"Loaded {len(train_records)} train records, {len(val_records)} val records."
    )

    # Validate leakage
    test_file = data_dir / "test.jsonl"
    test_records = DatasetLoader.load_jsonl(test_file) if test_file.exists() else []
    if test_records:
        DatasetLoader.validate_temporal_splits(train_records, val_records, test_records)
        logger.info("Chronological split validation verified: zero temporal leakage.")

    trainer = ModelTrainer(version=args.version)
    bundle = trainer.train_and_evaluate(train_records, val_records)

    model_path = trainer.save_model(bundle, out_dir, "risk_model_v1.joblib")

    # Save metadata JSON (excluding raw model weights)
    metadata = {
        "model_name": bundle["model_name"],
        "version": bundle["version"],
        "trained_at": bundle["trained_at"],
        "training_samples_count": bundle["training_samples_count"],
        "class_balance_ratio": bundle["class_balance_ratio"],
        "validation_metrics": bundle["validation_metrics"],
        "comparison_metrics": bundle["comparison_metrics"],
        "feature_names": bundle["feature_names"],
        "artifact_path": str(model_path),
    }

    meta_path = out_dir / "model_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Saved model metadata to {meta_path}")

    print("\n" + "=" * 60)
    print(
        f" MODEL TRAINING COMPLETE: {bundle['model_name'].upper()} v{bundle['version']}"
    )
    print("=" * 60)
    print(f"Artifact location: {model_path}")
    print("\nComparative Validation Metrics:")
    for m_name, m_stats in bundle["comparison_metrics"].items():
        print(
            f"  {m_name.ljust(25)}: PR-AUC={m_stats['pr_auc']:.4f} | ROC-AUC={m_stats['roc_auc']:.4f} | Brier={m_stats['brier_score']:.4f}"
        )
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
