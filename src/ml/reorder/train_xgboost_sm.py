"""
SageMaker entry-point — XGBoost Baseline (Task A, Reorder Prediction).

Compatible with sagemaker.xgboost.XGBoost estimator (Script Mode).
SageMaker passes hyperparameters as CLI args.
Reads dataset from S3 directly (lake_bucket hyperparam).
Writes model to SM_MODEL_DIR; SageMaker uploads it automatically.
"""

import argparse
import io
import json
import os

import boto3
import numpy as np
import pandas as pd
import xgboost as xgb

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
parser.add_argument("--lake_bucket", type=str, required=True)
parser.add_argument("--threshold", type=float, default=0.5)
parser.add_argument("--n_estimators", type=int, default=300)
args = parser.parse_args()

MODEL_DIR = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")
OUTPUT_DIR = os.environ.get("SM_OUTPUT_DATA_DIR", "/opt/ml/output/data")

DATASET_PATH = f"s3://{args.lake_bucket}/ml/reorder_dataset/"
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
model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=50)

y_prob = model.predict_proba(X_test)[:, 1]
y_pred = (y_prob >= args.threshold).astype(int)

metrics = evaluate_binary(y_test, y_pred, y_prob, "XGBoost Baseline (SageMaker)")
feature_importance_report(FEATURE_COLS, model.feature_importances_)

# ── Write model to SM_MODEL_DIR (SageMaker tarballs and uploads to S3)
os.makedirs(MODEL_DIR, exist_ok=True)
model.save_model(os.path.join(MODEL_DIR, "model.ubj"))
print(f"Model saved to {MODEL_DIR}/model.ubj")

# ── Write metrics to SM_OUTPUT_DATA_DIR + S3 for easy retrieval
os.makedirs(OUTPUT_DIR, exist_ok=True)
metrics_json = json.dumps(metrics, indent=2)
with open(os.path.join(OUTPUT_DIR, "metrics.json"), "w") as f:
    f.write(metrics_json)
write_bytes_s3(
    metrics_json.encode(),
    f"s3://{args.lake_bucket}/ml/models/xgboost-sm/metrics.json",
)
print(f"Metrics written to {OUTPUT_DIR}/metrics.json and S3")

print(f"\nXGBoost F1: {metrics['f1']:.4f}")
