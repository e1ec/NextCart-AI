"""
SageMaker entry-point — LightGBM Primary (Task A, Reorder Prediction).

Compatible with sagemaker.sklearn.SKLearn estimator (Script Mode).
SageMaker installs lightgbm via requirements.txt in source_dir.
Reads dataset from S3 directly (lake_bucket hyperparam).
Writes model to SM_MODEL_DIR; SageMaker uploads it automatically.
"""

import argparse
import io
import json
import os

import boto3
import lightgbm as lgb
import numpy as np
import pandas as pd

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
parser.add_argument("--num_leaves", type=int, default=63)
parser.add_argument("--n_estimators", type=int, default=500)
parser.add_argument("--learning_rate", type=float, default=0.05)
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
model = lgb.LGBMClassifier(
    num_leaves=args.num_leaves,
    learning_rate=args.learning_rate,
    n_estimators=args.n_estimators,
    min_data_in_leaf=20,
    feature_fraction=0.8,
    bagging_fraction=0.8,
    bagging_freq=5,
    scale_pos_weight=scale_pos_weight,
    metric="binary_logloss",
    random_state=42,
    n_jobs=-1,
    verbose=-1,
)

print("Training LightGBM ...")
model.fit(
    X_train,
    y_train,
    eval_set=[(X_test, y_test)],
    callbacks=[lgb.log_evaluation(period=50), lgb.early_stopping(stopping_rounds=30)],
)

y_prob = model.predict_proba(X_test)[:, 1]
y_pred = (y_prob >= args.threshold).astype(int)

metrics = evaluate_binary(y_test, y_pred, y_prob, "LightGBM Primary (SageMaker)")
feature_importance_report(FEATURE_COLS, model.feature_importances_)

# ── Write model to SM_MODEL_DIR
os.makedirs(MODEL_DIR, exist_ok=True)
model.booster_.save_model(os.path.join(MODEL_DIR, "model.txt"))
print(f"Model saved to {MODEL_DIR}/model.txt")

# ── Write metrics to SM_OUTPUT_DATA_DIR + S3
os.makedirs(OUTPUT_DIR, exist_ok=True)
metrics_json = json.dumps(metrics, indent=2)
with open(os.path.join(OUTPUT_DIR, "metrics.json"), "w") as f:
    f.write(metrics_json)
write_bytes_s3(
    metrics_json.encode(),
    f"s3://{args.lake_bucket}/ml/models/lightgbm-sm/metrics.json",
)
print(f"Metrics written to {OUTPUT_DIR}/metrics.json and S3")

print(f"\nLightGBM F1: {metrics['f1']:.4f}")
if metrics["f1"] >= 0.38:
    print("Target F1 >= 0.38 ACHIEVED")
else:
    print(f"Target F1 >= 0.38 NOT YET MET (gap: {0.38 - metrics['f1']:.4f})")
