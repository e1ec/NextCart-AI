"""
PySpark Gold Job — Recommendation Features (Task B)
Builds the user-product interaction matrix and product content vectors.

EMR Step args:
  --lake_bucket   S3 bucket name (nextcart-dev-lake)
  --local         Run in local[*] mode with s3a:// (dev machine, no EMR needed)

Outputs:
  s3://{lake_bucket}/gold/interaction_matrix/   (user_id, product_id, score)
  s3://{lake_bucket}/gold/product_vectors/      (product_id, features array)
"""

import argparse

from pyspark.ml.feature import HashingTF, IDF, Tokenizer
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import FloatType

parser = argparse.ArgumentParser()
parser.add_argument("--lake_bucket", required=True)
parser.add_argument("--local", action="store_true", help="Run locally (not on EMR)")
args = parser.parse_args()

scheme = "s3a" if args.local else "s3"
LAKE = f"{scheme}://{args.lake_bucket}"
SILVER = f"{LAKE}/silver"
GOLD = f"{LAKE}/gold"

builder = SparkSession.builder.appName("nextcart-recommendation-features")
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
        .config("spark.driver.memory", "4g")
        .config("spark.sql.autoBroadcastJoinThreshold", "-1")
        .config("spark.hadoop.fs.s3a.fast.upload.buffer", "array")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.default.parallelism", "4")
    )
spark = builder.getOrCreate()
spark.sparkContext.setLogLevel("WARN")

print("Reading silver tables...")

orders = spark.read.parquet(f"{SILVER}/orders/orders/")
prior = spark.read.parquet(f"{SILVER}/orders/order_products_prior/")
train = spark.read.parquet(f"{SILVER}/orders/order_products_train/")
products = spark.read.parquet(f"{SILVER}/products/")

# ── User-Product Interaction Matrix ─────────────────────────────────────────
# Implicit feedback: purchase count as interaction strength
# Uses prior orders only; train orders are the evaluation ground truth

user_ids = orders.filter(F.col("eval_set") == "prior").select("order_id", "user_id")

interaction_matrix = (
    prior.join(user_ids, "order_id")
    .groupBy("user_id", "product_id")
    .agg(
        F.count("order_id").cast(FloatType()).alias("purchase_count"),
        F.sum("reordered").cast(FloatType()).alias("reorder_count"),
        F.mean("add_to_cart_order").cast(FloatType()).alias("avg_cart_position"),
    )
    # Implicit rating: log-scaled purchase count (standard for ALS implicit)
    .withColumn("implicit_score", F.log1p(F.col("purchase_count")))
    .withColumn("_gold_ts", F.current_timestamp())
)

count = interaction_matrix.count()
n_users = interaction_matrix.select("user_id").distinct().count()
n_products = interaction_matrix.select("product_id").distinct().count()
print(f"Interaction matrix: {count:,} interactions, {n_users:,} users, {n_products:,} products")

interaction_matrix.repartition(4).write.mode("overwrite").parquet(f"{GOLD}/interaction_matrix/")
print(f"Written to {GOLD}/interaction_matrix/")

# ── Ground Truth: Last Order Per User (for offline evaluation) ───────────────

train_user_ids = orders.filter(F.col("eval_set") == "train").select("order_id", "user_id")

ground_truth = (
    train.join(train_user_ids, "order_id")
    .select("user_id", "product_id")
    .withColumn("_gold_ts", F.current_timestamp())
)

gt_count = ground_truth.count()
print(f"Ground truth (train set): {gt_count:,} user-product pairs")

ground_truth.repartition(4).write.mode("overwrite").parquet(f"{GOLD}/recommendation_ground_truth/")
print(f"Written to {GOLD}/recommendation_ground_truth/")

# ── Product Content Vectors (TF-IDF on text features) ───────────────────────
# Concatenate product name + aisle + department as a "document" for TF-IDF

product_docs = (
    products.select("product_id", "product_name_clean", "aisle", "department")
    .fillna("")
    .withColumn(
        "text",
        F.concat_ws(" ", F.col("product_name_clean"), F.col("aisle"), F.col("department")),
    )
)

tokenizer = Tokenizer(inputCol="text", outputCol="words")
product_words = tokenizer.transform(product_docs)

hashing_tf = HashingTF(inputCol="words", outputCol="raw_features", numFeatures=512)
featurized = hashing_tf.transform(product_words)

idf = IDF(inputCol="raw_features", outputCol="tfidf_features")
idf_model = idf.fit(featurized)
product_vectors = idf_model.transform(featurized).select(
    "product_id",
    "aisle",
    "department",
    "tfidf_features",
    F.current_timestamp().alias("_gold_ts"),
)

vec_count = product_vectors.count()
print(f"Product vectors: {vec_count:,} products (512-dim TF-IDF)")

product_vectors.repartition(2).write.mode("overwrite").parquet(f"{GOLD}/product_vectors/")
print(f"Written to {GOLD}/product_vectors/")

spark.stop()
print("Recommendation features job complete.")
