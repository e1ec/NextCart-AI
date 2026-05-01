"""
Submit Gold PySpark feature engineering jobs as SageMaker Processing Jobs.
Replaces EMR when EMR subscription is unavailable.

Uses PySparkProcessor — no script changes required to reorder_features.py
or recommendation_features.py. SageMaker configures Spark and AWS credentials
automatically; the scripts read/write S3 via s3:// natively.

Usage:
  python src/pipeline/gold/launch_processing.py \
    --lake_bucket nextcart-dev-lake \
    --role_arn $(terraform -chdir=infra/terraform/environments/dev output -raw sagemaker_role_arn)
"""

import argparse

import boto3
import sagemaker
from sagemaker.spark.processing import PySparkProcessor

parser = argparse.ArgumentParser()
parser.add_argument("--lake_bucket", required=True)
parser.add_argument("--role_arn", required=True)
parser.add_argument("--region", default="ap-southeast-2")
parser.add_argument("--instance_type", default="ml.m5.xlarge")
parser.add_argument("--spark_version", default="3.3")
args = parser.parse_args()

boto_sess = boto3.Session(region_name=args.region)
sm_session = sagemaker.Session(boto_session=boto_sess)

LOGS_URI = f"s3://{args.lake_bucket}/logs/spark/"

processor = PySparkProcessor(
    base_job_name="nextcart-gold",
    framework_version=args.spark_version,
    role=args.role_arn,
    instance_count=1,
    instance_type=args.instance_type,
    max_runtime_in_seconds=7200,
    sagemaker_session=sm_session,
)

# ── Task A — Reorder Features ─────────────────────────────────────────────────
print("Submitting reorder_features job ...")
processor.run(
    submit_app="src/pipeline/gold/reorder_features.py",
    arguments=["--lake_bucket", args.lake_bucket],
    spark_event_logs_s3_uri=LOGS_URI,
    logs=True,
    wait=True,
)
print("reorder_features job complete.")

# ── Task B — Recommendation Features ─────────────────────────────────────────
print("Submitting recommendation_features job ...")
processor.run(
    submit_app="src/pipeline/gold/recommendation_features.py",
    arguments=["--lake_bucket", args.lake_bucket],
    spark_event_logs_s3_uri=LOGS_URI,
    logs=True,
    wait=True,
)
print("recommendation_features job complete.")

print(f"\nGold features written to s3://{args.lake_bucket}/gold/")
print("Verify:")
print(f"  aws s3 ls s3://{args.lake_bucket}/gold/reorder_features/")
print(f"  aws s3 ls s3://{args.lake_bucket}/gold/interaction_matrix/")
