"""
Task B — Recommendation Evaluation Utilities
Precision@K, Recall@K, NDCG@K (pandas-based, used by content_based.py and hybrid.py).
"""

from typing import Dict, List

import numpy as np
import pandas as pd


def precision_at_k(actual: set, predicted: List, k: int) -> float:
    if not predicted or k == 0:
        return 0.0
    return len(set(predicted[:k]) & actual) / k


def recall_at_k(actual: set, predicted: List, k: int) -> float:
    if not actual or not predicted:
        return 0.0
    return len(set(predicted[:k]) & actual) / len(actual)


def ndcg_at_k(actual: set, predicted: List, k: int) -> float:
    if not actual or not predicted:
        return 0.0
    dcg = sum(
        1.0 / np.log2(i + 2)
        for i, pid in enumerate(predicted[:k])
        if pid in actual
    )
    idcg = sum(1.0 / np.log2(i + 2) for i in range(min(len(actual), k)))
    return dcg / idcg if idcg > 0 else 0.0


def evaluate_model(
    recs_df: pd.DataFrame,
    ground_truth_df: pd.DataFrame,
    k: int = 10,
) -> Dict:
    """
    recs_df:          columns [user_id, product_id, score]
    ground_truth_df:  columns [user_id, product_id]
    Returns mean Precision@K, Recall@K, NDCG@K over all common users.
    """
    gt = ground_truth_df.groupby("user_id")["product_id"].apply(set).to_dict()

    recs = (
        recs_df.sort_values(["user_id", "score"], ascending=[True, False])
        .groupby("user_id")["product_id"]
        .apply(list)
        .to_dict()
    )

    users = set(gt) & set(recs)

    p_scores, r_scores, n_scores = [], [], []
    for uid in users:
        actual = gt[uid]
        predicted = recs[uid]
        p_scores.append(precision_at_k(actual, predicted, k))
        r_scores.append(recall_at_k(actual, predicted, k))
        n_scores.append(ndcg_at_k(actual, predicted, k))

    return {
        f"precision_at_{k}": float(np.mean(p_scores)) if p_scores else 0.0,
        f"recall_at_{k}": float(np.mean(r_scores)) if r_scores else 0.0,
        f"ndcg_at_{k}": float(np.mean(n_scores)) if n_scores else 0.0,
        "n_users_evaluated": len(users),
    }


def print_metrics(metrics: Dict, model_name: str, k: int = 10) -> None:
    print("=" * 52)
    print(f"  {model_name} — Evaluation Results")
    print("=" * 52)
    print(f"  Precision@{k:<3}: {metrics.get(f'precision_at_{k}', 0):.4f}")
    print(f"  Recall@{k:<6}: {metrics.get(f'recall_at_{k}', 0):.4f}")
    print(f"  NDCG@{k:<8}: {metrics.get(f'ndcg_at_{k}', 0):.4f}")
    print(f"  Users evaluated : {metrics.get('n_users_evaluated', 0):,}")
    print("=" * 52)
    target_key = f"precision_at_{k}"
    p = metrics.get(target_key, 0)
    if p >= 0.30:
        print(f"  Target Precision@{k} >= 0.30 ACHIEVED")
    else:
        print(f"  Target Precision@{k} >= 0.30 NOT YET MET (gap: {0.30 - p:.4f})")
    print()
