"""
Launch SageMaker Training Jobs for Task A — Reorder Prediction.

Submits XGBoost and LightGBM jobs to SageMaker, waits for completion,
then registers both models in the SageMaker Model Registry.

Usage:
  python src/ml/reorder/launch_sagemaker.py \
    --lake_bucket nextcart-dev-lake \
    --role_arn $(terraform -chdir=infra/terraform/environments/dev output -raw sagemaker_role_arn) \
    --model_package_group nextcart-dev-reorder
"""

import argparse
import json

import boto3
import sagemaker
from sagemaker.sklearn import SKLearn
from sagemaker.xgboost import XGBoost

SOURCE_DIR = "src/ml/reorder"

parser = argparse.ArgumentParser()
parser.add_argument("--lake_bucket", required=True)
parser.add_argument("--role_arn", required=True)
parser.add_argument("--model_package_group", default="nextcart-dev-reorder")
parser.add_argument("--region", default="ap-southeast-2")
parser.add_argument("--instance_type", default="ml.m5.large")
parser.add_argument("--no_wait", action="store_true", help="Submit jobs and exit without waiting")
args = parser.parse_args()

boto_sess = boto3.Session(region_name=args.region)
sm_session = sagemaker.Session(boto_session=boto_sess)
sm_client = boto_sess.client("sagemaker")

COMMON_HYPERPARAMS = {"lake_bucket": args.lake_bucket}

# ── XGBoost Training Job ──────────────────────────────────────────────────────

xgb_estimator = XGBoost(
    entry_point="train_xgboost_sm.py",
    source_dir=SOURCE_DIR,
    role=args.role_arn,
    instance_type=args.instance_type,
    instance_count=1,
    framework_version="2.0-1",
    py_version="py310",
    hyperparameters={**COMMON_HYPERPARAMS, "n_estimators": 300, "threshold": 0.5},
    base_job_name="nextcart-xgboost",
    sagemaker_session=sm_session,
    output_path=f"s3://{args.lake_bucket}/ml/sagemaker-output/",
)

print("Submitting XGBoost training job ...")
xgb_estimator.fit(wait=not args.no_wait, logs="All")

if not args.no_wait:
    xgb_job_name = xgb_estimator.latest_training_job.name
    print(f"XGBoost job complete: {xgb_job_name}")

# ── LightGBM Training Job ─────────────────────────────────────────────────────
# Uses the SKLearn container (sklearn pre-installed) + requirements.txt installs lightgbm

lgb_estimator = SKLearn(
    entry_point="train_lightgbm_sm.py",
    source_dir=SOURCE_DIR,
    role=args.role_arn,
    instance_type=args.instance_type,
    instance_count=1,
    framework_version="1.2-1",
    py_version="py310",
    hyperparameters={
        **COMMON_HYPERPARAMS,
        "num_leaves": 63,
        "n_estimators": 500,
        "learning_rate": 0.05,
        "threshold": 0.5,
    },
    base_job_name="nextcart-lightgbm",
    sagemaker_session=sm_session,
    output_path=f"s3://{args.lake_bucket}/ml/sagemaker-output/",
)

print("Submitting LightGBM training job ...")
lgb_estimator.fit(wait=not args.no_wait, logs="All")

if args.no_wait:
    print("Jobs submitted. Check progress at: AWS Console → SageMaker → Training jobs")
    raise SystemExit(0)

lgb_job_name = lgb_estimator.latest_training_job.name
print(f"LightGBM job complete: {lgb_job_name}")

# ── Read metrics from S3 and compare ─────────────────────────────────────────

s3 = boto_sess.client("s3")


def get_metrics(key_suffix: str) -> dict:
    obj = s3.get_object(Bucket=args.lake_bucket, Key=f"ml/models/{key_suffix}/metrics.json")
    return json.loads(obj["Body"].read())


xgb_metrics = get_metrics("xgboost-sm")
lgb_metrics = get_metrics("lightgbm-sm")

print(f"\n{'='*50}")
print(f"  A/B Comparison")
print(f"{'='*50}")
print(f"  XGBoost  F1={xgb_metrics['f1']:.4f}  AUC={xgb_metrics['auc_roc']:.4f}")
print(f"  LightGBM F1={lgb_metrics['f1']:.4f}  AUC={lgb_metrics['auc_roc']:.4f}")
champion = "LightGBM" if lgb_metrics["f1"] >= xgb_metrics["f1"] else "XGBoost"
print(f"  Champion: {champion}")
print(f"{'='*50}\n")

# ── Register both models in SageMaker Model Registry ─────────────────────────

def register_model(
    job_name: str,
    model_name: str,
    metrics: dict,
    image_uri: str,
) -> str:
    resp = sm_client.create_model_package(
        ModelPackageGroupName=args.model_package_group,
        ModelPackageDescription=f"{model_name} — F1={metrics['f1']:.4f}",
        ModelApprovalStatus="PendingManualApproval",
        InferenceSpecification={
            "Containers": [{
                "Image": image_uri,
                "ModelDataUrl": (
                    sm_client.describe_training_job(TrainingJobName=job_name)
                    ["ModelArtifacts"]["S3ModelArtifacts"]
                ),
            }],
            "SupportedContentTypes": ["text/csv"],
            "SupportedResponseMIMETypes": ["application/json"],
        },
        ModelMetrics={
            "ModelQuality": {
                "Statistics": {
                    "ContentType": "application/json",
                    "S3Uri": (
                        f"s3://{args.lake_bucket}/ml/models/"
                        f"{'xgboost-sm' if 'XGBoost' in model_name else 'lightgbm-sm'}/metrics.json"
                    ),
                }
            }
        },
    )
    arn = resp["ModelPackageArn"]
    print(f"Registered {model_name}: {arn}")
    return arn


# Retrieve framework container images for the registry entries
xgb_image = sagemaker.image_uris.retrieve(
    "xgboost", region=args.region, version="2.0-1"
)
sklearn_image = sagemaker.image_uris.retrieve(
    "sklearn", region=args.region, version="1.2-1"
)

register_model(xgb_job_name, "XGBoost Baseline", xgb_metrics, xgb_image)
register_model(lgb_job_name, "LightGBM Primary", lgb_metrics, sklearn_image)

print("Both models registered in SageMaker Model Registry.")
print(f"Review at: AWS Console → SageMaker → Model Registry → {args.model_package_group}")
