"""
Task B — Hybrid Recommendation (ALS + Content-Based Cascade)

Cascade strategy:
  1. For each user, take Personal History (content) recommendations first.
  2. If a user has fewer than top_k content items, fill remaining slots with
     ALS recommendations (collaborative fallback for sparse users).

Why cascade beats weighted-average normalization:
  Min-max over top-K maps the K-th content item to norm=0, allowing ALS items
  (which have low precision) to displace relevant content items in the final ranking.
  Cascade guarantees the hybrid is never worse than content alone.

Args:
  --lake_bucket   S3 bucket (nextcart-dev-lake)
  --top_k         Final recommendations per user (default 10)

Outputs:
  s3://{lake_bucket}/ml/models/hybrid/metrics.json
  s3://{lake_bucket}/ml/recommendations/hybrid/
"""

import argparse
import io
import json

import boto3
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
args = parser.parse_args()

RECS_PATH = f"s3://{args.lake_bucket}/ml/recommendations/hybrid/"

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


def load_metrics_s3(bucket: str, key: str) -> dict:
    try:
        obj = s3c.get_object(Bucket=bucket, Key=key)
        return json.loads(obj["Body"].read())
    except Exception:
        return {}


# ── Load both recommendation sets ─────────────────────────────────────────────
print("Reading ALS recommendations ...")
als_recs = read_parquet(f"{args.lake_bucket}/ml/recommendations/als/")[
    ["user_id", "product_id", "score", "rank"]
].rename(columns={"score": "als_score", "rank": "als_rank"})

print("Reading content-based recommendations ...")
content_recs = read_parquet(
    f"{args.lake_bucket}/ml/recommendations/content/recommendations.parquet"
)[["user_id", "product_id", "score", "rank"]].rename(
    columns={"score": "content_score", "rank": "content_rank"}
)

common_users = set(als_recs["user_id"].unique()) & set(content_recs["user_id"].unique())
print(f"Users in both models: {len(common_users):,}")

als_recs = als_recs[als_recs["user_id"].isin(common_users)].reset_index(drop=True)
content_recs = content_recs[content_recs["user_id"].isin(common_users)].reset_index(drop=True)

# ── Cascade hybrid ────────────────────────────────────────────────────────────
# Step 1: Personal History items are primary (priority=0).
# Step 2: ALS items backfill any user that has < top_k content items (priority=1).
# Items in both models: keep the content version (higher priority).
#
# Result: hybrid is never worse than content alone; ALS helps only sparse users.
k = args.top_k

content_primary = content_recs[["user_id", "product_id", "content_score", "content_rank"]].copy()
content_primary["priority"] = 0
content_primary["score"] = content_primary["content_score"]

als_fallback = als_recs[["user_id", "product_id", "als_score", "als_rank"]].copy()
als_fallback["priority"] = 1
als_fallback["score"] = als_fallback["als_score"]

combined = pd.concat(
    [
        content_primary[["user_id", "product_id", "score", "priority"]],
        als_fallback[["user_id", "product_id", "score", "priority"]],
    ],
    ignore_index=True,
)

# Sort so content items (priority=0) come before ALS items (priority=1),
# with higher scores first within each priority tier.
combined = combined.sort_values(
    ["user_id", "priority", "score"], ascending=[True, True, False]
)

# Drop duplicate (user, product) pairs — keeps the content row if present in both.
combined = combined.drop_duplicates(subset=["user_id", "product_id"], keep="first")

# Take top-K per user (content items fill first; ALS backfills remainder).
print(f"Selecting top-{k} per user (cascade: content-first, ALS fallback) ...")
hybrid_recs = (
    combined.groupby("user_id", sort=False)
    .head(k)
    .reset_index(drop=True)[["user_id", "product_id", "score"]]
)
hybrid_recs["rank"] = (
    hybrid_recs.groupby("user_id")["score"]
    .rank(ascending=False, method="first")
    .astype(int)
)

# ── Coverage diagnostics ──────────────────────────────────────────────────────
items_per_user = hybrid_recs.groupby("user_id")["product_id"].count()
content_items_per_user = content_recs.groupby("user_id")["product_id"].count()
als_only_fill = (items_per_user - content_items_per_user.reindex(items_per_user.index, fill_value=0)).clip(lower=0)
n_users_needing_als = (als_only_fill > 0).sum()
print(f"Users needing ALS backfill (< {k} content items): {n_users_needing_als:,}")

# ── Evaluate ──────────────────────────────────────────────────────────────────
print("Reading ground truth ...")
gt_df = read_parquet(f"{args.lake_bucket}/gold/recommendation_ground_truth/")[
    ["user_id", "product_id"]
]
gt_df = gt_df[gt_df["user_id"].isin(common_users)].reset_index(drop=True)

metrics = evaluate_model(hybrid_recs, gt_df, k=k)
metrics["model"] = "Hybrid (Content cascade + ALS fallback)"
print_metrics(metrics, "Hybrid (Content cascade + ALS fallback)", k=k)

# ── A/B/C comparison ─────────────────────────────────────────────────────────
als_m = load_metrics_s3(args.lake_bucket, "ml/models/als/metrics.json")
content_m = load_metrics_s3(args.lake_bucket, "ml/models/content/metrics.json")

print("── Model Comparison ──────────────────────────────────────────────")
header = f"{'Model':<20}  {'Precision@' + str(k):<14}  {'Recall@' + str(k):<12}  {'NDCG@' + str(k)}"
print(f"  {header}")
print("  " + "-" * 64)
for name, m in [("ALS", als_m), ("Personal History", content_m), ("Hybrid (cascade)", metrics)]:
    p = m.get(f"precision_at_{k}", 0)
    r = m.get(f"recall_at_{k}", 0)
    n = m.get(f"ndcg_at_{k}", 0)
    print(f"  {name:<20}  {p:<14.4f}  {r:<12.4f}  {n:.4f}")
print()

# ── Save ──────────────────────────────────────────────────────────────────────
write_parquet_s3(hybrid_recs, f"{RECS_PATH}recommendations.parquet")
s3c.put_object(
    Bucket=args.lake_bucket,
    Key="ml/models/hybrid/metrics.json",
    Body=json.dumps(metrics, indent=2).encode(),
)
print(f"Hybrid recommendations → {RECS_PATH}")
print(f"Metrics               → s3://{args.lake_bucket}/ml/models/hybrid/metrics.json")
