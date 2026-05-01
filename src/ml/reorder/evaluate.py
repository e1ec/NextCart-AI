"""
Shared evaluation utilities for Task A — Reorder Prediction.
Called by train_xgboost.py and train_lightgbm.py.
"""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def evaluate_binary(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: np.ndarray,
    model_name: str,
) -> dict[str, Any]:
    """Compute and print classification metrics; return as dict."""
    metrics = {
        "model": model_name,
        "f1": f1_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred),
        "recall": recall_score(y_true, y_pred),
        "auc_roc": roc_auc_score(y_true, y_prob),
        "avg_precision": average_precision_score(y_true, y_prob),
        "n_test": int(len(y_true)),
        "n_positive": int(y_true.sum()),
    }

    print(f"\n{'='*50}")
    print(f"  {model_name} — Evaluation Results")
    print(f"{'='*50}")
    print(f"  F1-score       : {metrics['f1']:.4f}")
    print(f"  Precision      : {metrics['precision']:.4f}")
    print(f"  Recall         : {metrics['recall']:.4f}")
    print(f"  AUC-ROC        : {metrics['auc_roc']:.4f}")
    print(f"  Avg Precision  : {metrics['avg_precision']:.4f}")
    print(f"  Test rows      : {metrics['n_test']:,}")
    print(f"  Positive rate  : {metrics['n_positive']/metrics['n_test']:.3f}")

    cm = confusion_matrix(y_true, y_pred)
    print(f"\n  Confusion Matrix:")
    print(f"    TN={cm[0,0]:,}  FP={cm[0,1]:,}")
    print(f"    FN={cm[1,0]:,}  TP={cm[1,1]:,}")
    print(f"{'='*50}\n")

    return metrics


def feature_importance_report(
    feature_names: list[str],
    importances: np.ndarray,
    top_n: int = 10,
) -> pd.DataFrame:
    """Print and return top-N feature importances."""
    fi = pd.DataFrame({"feature": feature_names, "importance": importances})
    fi = fi.sort_values("importance", ascending=False).reset_index(drop=True)

    print(f"\nTop {top_n} features by importance:")
    for i, row in fi.head(top_n).iterrows():
        print(f"  {i+1:2d}. {row['feature']:<35} {row['importance']:.4f}")

    return fi
