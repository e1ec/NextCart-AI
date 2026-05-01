"""
Prepare ML dataset for Task A — Reorder Prediction.

Loads gold/reorder_features Parquet from S3, splits 80/20 stratified,
saves train/test sets back to S3 under ml/reorder_dataset/.

Args:
  --lake_bucket   S3 bucket name (nextcart-dev-lake)
  --test_size     Fraction held out for test (default 0.2)
  --seed          Random seed (default 42)
"""

import argparse

import boto3
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import s3fs

parser = argparse.ArgumentParser()
parser.add_argument("--lake_bucket", required=True)
parser.add_argument("--test_size", type=float, default=0.2)
parser.add_argument("--seed", type=int, default=42)
args = parser.parse_args()

GOLD_PATH = f"s3://{args.lake_bucket}/gold/reorder_features/"
OUT_PATH = f"s3://{args.lake_bucket}/ml/reorder_dataset/"

FEATURE_COLS = [
    "user_total_orders",
    "user_avg_order_size",
    "user_avg_days_between_orders",
    "up_order_count",
    "user_product_reorder_rate",
    "user_product_order_frequency",
    "orders_since_last_purchase",
    "up_avg_cart_position",
    "product_global_reorder_rate",
    "add_to_cart_order_mean",
    "aisle_id",
    "department_id",
    "is_organic",
    "aisle_encoded",
    "department_encoded",
    "order_dow",
    "order_hour_of_day",
]
LABEL_COL = "label"

print(f"Reading gold features from {GOLD_PATH} ...")
fs = s3fs.S3FileSystem()
# pq.ParquetDataset with s3fs requires the path WITHOUT the s3:// scheme prefix
path_no_scheme = GOLD_PATH.replace("s3://", "")
dataset = pq.ParquetDataset(path_no_scheme, filesystem=fs)
df = dataset.read_pandas(columns=["user_id", "product_id"] + FEATURE_COLS + [LABEL_COL]).to_pandas()

print(f"Loaded {len(df):,} rows, {df.shape[1]} columns")
print(f"Label distribution:\n{df[LABEL_COL].value_counts()}")

# ── Stratified split on user_id (keep each user's rows together in one split)
rng = np.random.default_rng(args.seed)
user_ids = df["user_id"].unique()
rng.shuffle(user_ids)

split_idx = int(len(user_ids) * (1 - args.test_size))
train_users = set(user_ids[:split_idx])
test_users = set(user_ids[split_idx:])

train_df = df[df["user_id"].isin(train_users)].reset_index(drop=True)
test_df = df[df["user_id"].isin(test_users)].reset_index(drop=True)

print(f"Train: {len(train_df):,} rows ({len(train_users):,} users)")
print(f"Test:  {len(test_df):,} rows ({len(test_users):,} users)")
print(f"Train label rate: {train_df[LABEL_COL].mean():.3f}")
print(f"Test  label rate: {test_df[LABEL_COL].mean():.3f}")

# ── Write to S3
def write_parquet_s3(df: pd.DataFrame, path: str) -> None:
    import io
    import pyarrow as pa

    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    buf.seek(0)
    s3 = boto3.client("s3")
    bucket, key = path.replace("s3://", "").split("/", 1)
    s3.put_object(Bucket=bucket, Key=key, Body=buf.read())
    print(f"Written to s3://{bucket}/{key}")


write_parquet_s3(train_df, f"{OUT_PATH}train.parquet")
write_parquet_s3(test_df, f"{OUT_PATH}test.parquet")

print("Dataset preparation complete.")
