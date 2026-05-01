"""
Task A — XGBoost Baseline (Phase 1)

Loads train/test Parquet from S3 (written by prepare_dataset.py),
trains an XGBoost binary classifier, logs metrics, saves model artifact.

Args:
  --lake_bucket   S3 bucket (nextcart-dev-lake)
  --threshold     Decision threshold for binary predictions (default 0.5)
  --n_estimators  Number of trees (default 300)
"""

import argparse
import io
import json
import os
import tempfile

import boto3
import numpy as np
import pandas as pd
import xgboost as xgb

try:
    from src.ml.reorder.evaluate import evaluate_binary, feature_importance_report
except ModuleNotFoundError:
    from evaluate import evaluate_binary, feature_importance_report

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

parser = argparse.ArgumentParser()
parser.add_argument("--lake_bucket", required=True)
parser.add_argument("--threshold", type=float, default=0.5)
parser.add_argument("--n_estimators", type=int, default=300)
args = parser.parse_args()

DATASET_PATH = f"s3://{args.lake_bucket}/ml/reorder_dataset/"
MODEL_PATH = f"s3://{args.lake_bucket}/ml/models/xgboost/"

s3 = boto3.client("s3")


def read_parquet_s3(s3_uri: str) -> pd.DataFrame:
    bucket, key = s3_uri.replace("s3://", "").split("/", 1)
    obj = s3.get_object(Bucket=bucket, Key=key)
    return pd.read_parquet(io.BytesIO(obj["Body"].read()))


def write_bytes_s3(data: bytes, s3_uri: str) -> None:
    bucket, key = s3_uri.replace("s3://", "").split("/", 1)
    s3.put_object(Bucket=bucket, Key=key, Body=data)


print("Loading train/test splits ...")
train_df = read_parquet_s3(f"{DATASET_PATH}train.parquet")
test_df = read_parquet_s3(f"{DATASET_PATH}test.parquet")

X_train = train_df[FEATURE_COLS].values.astype(np.float32)
y_train = train_df[LABEL_COL].values
X_test = test_df[FEATURE_COLS].values.astype(np.float32)
y_test = test_df[LABEL_COL].values

print(f"Train: {X_train.shape}, Test: {X_test.shape}")

# ── Train
scale_pos_weight = (y_train == 0).sum() / (y_train == 1).sum()
model = xgb.XGBClassifier(
    n_estimators=args.n_estimators,
    max_depth=6,
    learning_rate=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    scale_pos_weight=scale_pos_weight,
    eval_metric="logloss",
    use_label_encoder=False,
    random_state=42,
    n_jobs=-1,
)

print("Training XGBoost ...")
model.fit(
    X_train,
    y_train,
    eval_set=[(X_test, y_test)],
    verbose=50,
)

# ── Evaluate
y_prob = model.predict_proba(X_test)[:, 1]
y_pred = (y_prob >= args.threshold).astype(int)

metrics = evaluate_binary(y_test, y_pred, y_prob, "XGBoost Baseline")
feature_importance_report(FEATURE_COLS, model.feature_importances_)

# ── Save model artifact
print("Saving model to S3 ...")
tmp = tempfile.NamedTemporaryFile(suffix=".ubj", delete=False)
tmp.close()
model.save_model(tmp.name)
with open(tmp.name, "rb") as f:
    write_bytes_s3(f.read(), f"{MODEL_PATH}model.ubj")
os.unlink(tmp.name)

metrics_json = json.dumps(metrics, indent=2)
write_bytes_s3(metrics_json.encode(), f"{MODEL_PATH}metrics.json")
print(f"Model + metrics written to {MODEL_PATH}")

print(f"\nXGBoost baseline F1: {metrics['f1']:.4f}")
if metrics["f1"] >= 0.38:
    print("Target F1 >= 0.38 ACHIEVED")
else:
    print(f"Target F1 >= 0.38 NOT YET MET (gap: {0.38 - metrics['f1']:.4f})")
