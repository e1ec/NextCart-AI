"""
Task B — ALS Collaborative Filtering (PySpark MLlib)

Trains implicit-feedback ALS on gold/interaction_matrix/,
generates top-K recs for held-out users, evaluates vs ground_truth.

Args:
  --lake_bucket   S3 bucket (nextcart-dev-lake)
  --local         Run in local[*] mode with s3a:// (dev machine)
  --rank          ALS latent factors (default 20)
  --max_iter      ALS iterations (default 15)
  --reg_param     Regularisation lambda (default 0.1)
  --top_k         Recommendations per user (default 10)
  --sample_frac   Fraction of interaction matrix to use, 0–1 (default 0.3 locally)

Outputs:
  s3://{lake_bucket}/ml/models/als/spark_model/
  s3://{lake_bucket}/ml/models/als/metrics.json
  s3://{lake_bucket}/ml/recommendations/als/      (user_id, product_id, score, rank)
"""

import argparse
import json
import os
import sys

# Point Spark worker processes to the same venv Python that launched this script.
# Without this, on Windows the "python" alias resolves to the Microsoft Store
# stub, causing every Python worker to fail with "Python was not found".
os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)

import boto3
from pyspark.ml.recommendation import ALS
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType

parser = argparse.ArgumentParser()
parser.add_argument("--lake_bucket", required=True)
parser.add_argument("--local", action="store_true")
parser.add_argument("--rank", type=int, default=20)
parser.add_argument("--max_iter", type=int, default=15)
parser.add_argument("--reg_param", type=float, default=0.1)
parser.add_argument("--als_alpha", type=float, default=40.0,
                    help="Implicit confidence multiplier: confidence = 1 + alpha * rating (default 40)")
parser.add_argument("--rating_col", type=str, default="reorder_count",
                    choices=["reorder_count", "purchase_count", "implicit_score"],
                    help="Column used as ALS rating signal (default: reorder_count)")
parser.add_argument("--top_k", type=int, default=10)
parser.add_argument("--sample_frac", type=float, default=0.3,
                    help="Sample fraction for local runs (use 1.0 on EMR)")
args = parser.parse_args()

scheme = "s3a" if args.local else "s3"
LAKE = f"{scheme}://{args.lake_bucket}"
GOLD = f"{LAKE}/gold"
MODEL_PATH = f"{LAKE}/ml/models/als/"
RECS_PATH = f"{LAKE}/ml/recommendations/als/"

builder = SparkSession.builder.appName("nextcart-als")
if args.local:
    builder = (
        builder.master("local[*]")
        .config(
            "spark.jars.packages",
            "org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262",
        )
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "com.amazonaws.auth.DefaultAWSCredentialsProviderChain",
        )
        .config("spark.driver.memory", "8g")
        .config("spark.driver.maxResultSize", "4g")
        .config("spark.driver.extraJavaOptions", "-XX:+UseG1GC -XX:MaxDirectMemorySize=2g")
        .config("spark.memory.offHeap.enabled", "true")
        .config("spark.memory.offHeap.size", "2g")
        .config("spark.sql.shuffle.partitions", "16")
        .config("spark.sql.autoBroadcastJoinThreshold", "-1")
        .config("spark.hadoop.fs.s3a.fast.upload.buffer", "array")
        # Redirect shuffle temp files to D: so C: (system drive) doesn't fill up.
        .config("spark.local.dir", "D:/tmp/spark-local")
        .config("spark.pyspark.python", sys.executable)
    )
spark = builder.getOrCreate()
spark.sparkContext.setLogLevel("WARN")

# ── Load data ─────────────────────────────────────────────────────────────────
print("Reading interaction matrix ...")
_im = spark.read.parquet(f"{GOLD}/interaction_matrix/")
_has_recency = "appeared_in_last_3_orders" in _im.columns

# Base rating + optional recency boost from appeared_in_last_3_orders (0–3).
# Adds to ALS confidence = 1 + alpha × rating, so recent items get stronger signal.
if _has_recency:
    interactions = _im.select(
        F.col("user_id").cast(IntegerType()),
        F.col("product_id").cast(IntegerType()),
        (F.col(args.rating_col).cast("double") + F.col("appeared_in_last_3_orders").cast("double"))
        .alias("rating"),
    )
    print(f"Using '{args.rating_col} + appeared_in_last_3_orders' as ALS rating (recency boost active)")
else:
    interactions = _im.select(
        F.col("user_id").cast(IntegerType()),
        F.col("product_id").cast(IntegerType()),
        F.col(args.rating_col).cast("double").alias("rating"),
    )
    print(f"Using '{args.rating_col}' as ALS rating (re-run gold pipeline to enable recency boost)")

if args.sample_frac < 1.0:
    interactions = interactions.sample(fraction=args.sample_frac, seed=42)
    print(f"Sampled {args.sample_frac:.0%} of interaction matrix")

count = interactions.count()
n_users = interactions.select("user_id").distinct().count()
n_products = interactions.select("product_id").distinct().count()
print(f"Interaction matrix: {count:,} interactions, {n_users:,} users, {n_products:,} products")

print("Reading ground truth ...")
ground_truth = spark.read.parquet(f"{GOLD}/recommendation_ground_truth/").select(
    F.col("user_id").cast(IntegerType()),
    F.col("product_id").cast(IntegerType()),
)

gt_users = ground_truth.select("user_id").distinct()
n_gt_users = gt_users.count()
print(f"Ground truth: {n_gt_users:,} users")

# ── Train ALS ─────────────────────────────────────────────────────────────────
print(f"Training ALS (rank={args.rank}, maxIter={args.max_iter}, regParam={args.reg_param}, alpha={args.als_alpha}) ...")

als = ALS(
    rank=args.rank,
    maxIter=args.max_iter,
    regParam=args.reg_param,
    alpha=args.als_alpha,
    userCol="user_id",
    itemCol="product_id",
    ratingCol="rating",
    implicitPrefs=True,
    coldStartStrategy="drop",
    nonnegative=True,
    seed=42,
)
model = als.fit(interactions)
print("ALS training complete.")

# ── Generate recommendations ──────────────────────────────────────────────────
k = args.top_k
print(f"Generating top-{k} recommendations for {n_gt_users:,} test users ...")

user_recs = model.recommendForUserSubset(gt_users, k)

# Flatten to (user_id, product_id, score, rank)  rank is 1-based
recs_flat = (
    user_recs
    .select("user_id", F.posexplode("recommendations").alias("rank", "rec"))
    .select(
        "user_id",
        F.col("rec.product_id").alias("product_id"),
        F.col("rec.rating").alias("score"),
        (F.col("rank") + 1).alias("rank"),
    )
)

print(f"Writing recommendations to {RECS_PATH} ...")
recs_flat.repartition(4).write.mode("overwrite").parquet(RECS_PATH)
print("Recommendations written.")

# ── Stop Spark before evaluation ──────────────────────────────────────────────
# Releasing the JVM here frees ~8 GB, letting pandas load recs + ground_truth
# without competing for memory.  Spark evaluation joins on a cached recs_flat
# were the source of the repeated OOM errors.
print(f"Saving Spark ALS model to {MODEL_PATH}spark_model/ ...")
try:
    model.write().overwrite().save(f"{MODEL_PATH}spark_model/")
except Exception as e:
    print(f"WARNING: model.save() failed (non-fatal): {e}")

spark.stop()
print("Spark stopped. Evaluating with pandas ...")

# ── Pandas-based evaluation (same approach as content_based.py) ───────────────
import pyarrow.parquet as _pq
import s3fs as _s3fs

try:
    from src.ml.recommendation.evaluate import evaluate_model, print_metrics
except ModuleNotFoundError:
    from evaluate import evaluate_model, print_metrics

_fs = _s3fs.S3FileSystem()

recs_pd = _pq.ParquetDataset(
    f"{args.lake_bucket}/ml/recommendations/als/", filesystem=_fs
).read_pandas().to_pandas()[["user_id", "product_id", "score"]]

gt_pd = _pq.ParquetDataset(
    f"{args.lake_bucket}/gold/recommendation_ground_truth/", filesystem=_fs
).read_pandas().to_pandas()[["user_id", "product_id"]]

metrics = evaluate_model(recs_pd, gt_pd, k=k)
metrics["model"] = "ALS"
print_metrics(metrics, "ALS Collaborative Filtering", k=k)

n_users_evaluated = metrics["n_users_evaluated"]
precision_k = metrics[f"precision_at_{k}"]
recall_k    = metrics[f"recall_at_{k}"]
ndcg_k      = metrics[f"ndcg_at_{k}"]

metrics = {
    "model": "ALS",
    f"precision_at_{k}": round(precision_k, 4),
    f"recall_at_{k}": round(recall_k, 4),
    f"ndcg_at_{k}": round(ndcg_k, 4),
    "n_users_evaluated": n_users_evaluated,
    "rank": args.rank,
    "max_iter": args.max_iter,
    "reg_param": args.reg_param,
    "als_alpha": args.als_alpha,
    "rating_col": args.rating_col,
    "sample_frac": args.sample_frac,
}

s3 = boto3.client("s3")
s3.put_object(
    Bucket=args.lake_bucket,
    Key="ml/models/als/metrics.json",
    Body=json.dumps(metrics, indent=2).encode(),
)
print(f"Metrics written to s3://{args.lake_bucket}/ml/models/als/metrics.json")

spark.stop()
