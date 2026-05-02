"""
Task B — Personal History Recommender

Scores each user's previously purchased products by their per-user reorder
frequency, weighted by the product's global reorder rate.  No cold-start:
every recommendation comes from that user's own purchase history.

Why this beats TF-IDF cosine similarity for grocery reorder prediction:
  Users repurchase the *same* products, not products with similar names.
  "Organic Milk 1L" buyers reorder "Organic Milk 1L", not "Organic Cream 250ml".

Score per (user, product):
  score = reorder_count × personal_reorder_rate
        + 0.5 × implicit_score
        + 0.5 × appeared_in_last_3_orders

  reorder_count            — times this user has explicitly reordered this product
  personal_reorder_rate    — reorder_count / purchase_count (user-specific consistency)
  implicit_score           — log1p(purchase_count), tie-breaker for new/single purchases
  appeared_in_last_3_orders — how many of the 3 most recent prior orders contain this
                              product (0–3); boosts items with strong recency signal

Args:
  --lake_bucket    S3 bucket (nextcart-dev-lake)
  --top_k          Recommendations per user (default 10)
  --n_eval_users   Max users to evaluate (default 0 = all)
"""

import argparse
import io
import json

import boto3
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import s3fs

try:
    from src.ml.recommendation.evaluate import evaluate_model, print_metrics
except ModuleNotFoundError:
    from evaluate import evaluate_model, print_metrics

parser = argparse.ArgumentParser()
parser.add_argument("--lake_bucket", required=True)
parser.add_argument("--top_k", type=int, default=10)
parser.add_argument("--n_eval_users", type=int, default=0,
                    help="Max users to evaluate (0 = all)")
args = parser.parse_args()

RECS_PATH = f"s3://{args.lake_bucket}/ml/recommendations/content/"

s3c = boto3.client("s3")
fs = s3fs.S3FileSystem()


def read_parquet(bucket_prefix: str) -> pd.DataFrame:
    dataset = pq.ParquetDataset(bucket_prefix, filesystem=fs)
    return dataset.read_pandas().to_pandas()


def write_parquet_s3(df: pd.DataFrame, s3_uri: str) -> None:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    buf.seek(0)
    bucket, key = s3_uri.replace("s3://", "").split("/", 1)
    s3c.put_object(Bucket=bucket, Key=key, Body=buf.read())


# ── Load data ─────────────────────────────────────────────────────────────────
print("Reading interaction matrix ...")
_im = read_parquet(f"{args.lake_bucket}/gold/interaction_matrix/")
_base_cols = ["user_id", "product_id", "purchase_count", "reorder_count", "implicit_score"]
_extra_cols = [c for c in ["appeared_in_last_3_orders"] if c in _im.columns]
interactions = _im[_base_cols + _extra_cols]
if _extra_cols:
    print(f"  Loaded extra temporal features: {_extra_cols}")
else:
    print("  appeared_in_last_3_orders not found — re-run gold pipeline to enable recency boost")

print("Reading ground truth ...")
gt_df = read_parquet(f"{args.lake_bucket}/gold/recommendation_ground_truth/")[
    ["user_id", "product_id"]
]

# Optionally limit evaluation users
gt_users = set(gt_df["user_id"].unique())
if args.n_eval_users > 0 and len(gt_users) > args.n_eval_users:
    rng = np.random.default_rng(42)
    gt_users = set(rng.choice(list(gt_users), size=args.n_eval_users, replace=False).tolist())
    gt_df = gt_df[gt_df["user_id"].isin(gt_users)].reset_index(drop=True)
    interactions = interactions[interactions["user_id"].isin(gt_users)].reset_index(drop=True)

print(f"Evaluating on {len(gt_users):,} users, {len(interactions):,} user-product pairs")

# ── Score ─────────────────────────────────────────────────────────────────────
scored = interactions.copy()

# personal_reorder_rate: how consistently does THIS user reorder THIS item?
scored["personal_reorder_rate"] = (
    scored["reorder_count"] / scored["purchase_count"].clip(lower=1)
).clip(0, 1)

# appeared_in_last_3_orders (0–3): used as a multiplicative recency factor.
# Additive boost (0.5 × recency) is too small to change rankings when base scores
# span 4–10. Multiplicative form ensures a recently-bought item always ranks above
# an equally-scored item not seen in recent orders.
#   factor = 1 + 0.5 × appeared_in_last_3_orders  → range [1.0, 2.5]
# Falls back to factor=1 (no-op) if the gold pipeline hasn't been re-run yet.
if "appeared_in_last_3_orders" in scored.columns:
    _recency_factor = 1.0 + 0.5 * scored["appeared_in_last_3_orders"]
else:
    _recency_factor = 1.0

_base_score = (
    scored["reorder_count"] * scored["personal_reorder_rate"]
    + 0.5 * scored["implicit_score"]
)
scored["score"] = _base_score * _recency_factor

# ── Top-K per user ─────────────────────────────────────────────────────────────
print(f"Selecting top-{args.top_k} per user ...")
recs_df = (
    scored
    .sort_values(["user_id", "score"], ascending=[True, False])
    .groupby("user_id", sort=False)
    .head(args.top_k)
    .reset_index(drop=True)
    [["user_id", "product_id", "score"]]
)
recs_df["rank"] = (
    recs_df.groupby("user_id")["score"]
    .rank(ascending=False, method="first")
    .astype(int)
)

print(f"Generated {len(recs_df):,} rows for {recs_df['user_id'].nunique():,} users")

# ── Evaluate ──────────────────────────────────────────────────────────────────
metrics = evaluate_model(recs_df, gt_df, k=args.top_k)
metrics["model"] = "Personal History (reorder_count × personal_reorder_rate + recency)"
print_metrics(metrics, "Personal History Recommender", k=args.top_k)

# ── Save ──────────────────────────────────────────────────────────────────────
print("Writing recommendations to S3 ...")
write_parquet_s3(recs_df, f"{RECS_PATH}recommendations.parquet")

s3c.put_object(
    Bucket=args.lake_bucket,
    Key="ml/models/content/metrics.json",
    Body=json.dumps(metrics, indent=2).encode(),
)
print(f"Recommendations → {RECS_PATH}")
print(f"Metrics         → s3://{args.lake_bucket}/ml/models/content/metrics.json")
