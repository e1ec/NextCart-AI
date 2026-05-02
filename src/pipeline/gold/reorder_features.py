"""
PySpark Gold Job — Reorder Prediction Features (Task A)
Joins silver orders + products to produce the ML feature table.

EMR Step args:
  --lake_bucket   S3 bucket name (nextcart-dev-lake)
  --local         Run in local[*] mode with s3a:// (dev machine, no EMR needed)

Output:
  s3://{lake_bucket}/gold/reorder_features/
  Schema: user_id, product_id, <features>, label (reordered)
"""

import argparse

from pyspark.ml.feature import StringIndexer
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

parser = argparse.ArgumentParser()
parser.add_argument("--lake_bucket", required=True)
parser.add_argument("--local", action="store_true", help="Run locally (not on EMR)")
args = parser.parse_args()

# s3a:// required locally (hadoop-aws); s3:// on EMR (managed by AWS)
scheme = "s3a" if args.local else "s3"
LAKE = f"{scheme}://{args.lake_bucket}"
SILVER = f"{LAKE}/silver"
GOLD = f"{LAKE}/gold"

builder = SparkSession.builder.appName("nextcart-reorder-features")
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
    )
spark = builder.getOrCreate()
spark.sparkContext.setLogLevel("WARN")

print("Reading silver tables...")

orders = spark.read.parquet(f"{SILVER}/orders/orders/")
prior = spark.read.parquet(f"{SILVER}/orders/order_products_prior/")
train = spark.read.parquet(f"{SILVER}/orders/order_products_train/")
products = spark.read.parquet(f"{SILVER}/products/")

# ── User-level features ──────────────────────────────────────────────────────

user_orders = orders.filter(F.col("eval_set") == "prior").select(
    "order_id", "user_id", "order_number", "order_dow",
    "order_hour_of_day", "days_since_prior_order",
)

user_stats = (
    prior.join(user_orders, "order_id")
    .groupBy("user_id")
    .agg(
        F.count("product_id").alias("user_total_products"),
        F.countDistinct("order_id").alias("user_total_orders"),
        F.mean("days_since_prior_order").alias("user_avg_days_between_orders"),
    )
    .withColumn(
        "user_avg_order_size",
        F.col("user_total_products") / F.col("user_total_orders"),
    )
)

# ── User × Product features ──────────────────────────────────────────────────

user_product = (
    prior.join(user_orders, "order_id")
    .groupBy("user_id", "product_id")
    .agg(
        F.count("order_id").alias("up_order_count"),
        F.sum("reordered").alias("up_reorder_count"),
        F.mean("add_to_cart_order").alias("up_avg_cart_position"),
        F.max("order_number").alias("up_last_order_number"),
    )
    .join(user_stats.select("user_id", "user_total_orders"), "user_id")
    .withColumn(
        "user_product_reorder_rate",
        F.col("up_reorder_count") / F.col("up_order_count"),
    )
    .withColumn(
        "user_product_order_frequency",
        F.col("up_order_count") / F.col("user_total_orders"),
    )
    .withColumn(
        "orders_since_last_purchase",
        F.col("user_total_orders") - F.col("up_last_order_number"),
    )
)

# ── Temporal features (window functions) ─────────────────────────────────────

# days_since_prior_order on order N = days between order N-1 and N.
# days from order K to the last prior order = sum(days_since_prior_order for orders K+1..N).
_w_future = (
    Window.partitionBy("user_id")
    .orderBy("order_number")
    .rowsBetween(1, Window.unboundedFollowing)
)
_order_timeline = user_orders.withColumn(
    "days_to_last_prior_order",
    F.coalesce(F.sum("days_since_prior_order").over(_w_future), F.lit(0.0)),
)

# Actual days elapsed since user last bought this product (vs. observation window end).
days_since_last = (
    user_product.select("user_id", "product_id", "up_last_order_number")
    .join(
        _order_timeline.select("user_id", "order_number", "days_to_last_prior_order"),
        on=["user_id"],
    )
    .filter(F.col("order_number") == F.col("up_last_order_number"))
    .select(
        "user_id",
        "product_id",
        F.col("days_to_last_prior_order").alias("days_since_last_purchase"),
    )
)

# appeared_in_last_3_orders: count of how many of the 3 most recent prior orders contain this product.
_user_max_order = user_orders.groupBy("user_id").agg(
    F.max("order_number").alias("max_order_number")
)
appeared_in_last3 = (
    prior.join(user_orders.select("order_id", "user_id", "order_number"), "order_id")
    .join(_user_max_order, "user_id")
    .filter(F.col("order_number") >= F.col("max_order_number") - 2)
    .groupBy("user_id", "product_id")
    .agg(F.count("order_id").cast("int").alias("appeared_in_last_3_orders"))
)

# ── Product-level features ───────────────────────────────────────────────────

product_stats = (
    prior.groupBy("product_id")
    .agg(
        F.count("order_id").alias("product_total_orders"),
        F.sum("reordered").alias("product_total_reorders"),
        F.mean("add_to_cart_order").alias("add_to_cart_order_mean"),
    )
    .withColumn(
        "product_global_reorder_rate",
        F.col("product_total_reorders") / F.col("product_total_orders"),
    )
)

# ── Product metadata features from Source 2 ──────────────────────────────────

product_meta = (
    products.select(
        "product_id", "aisle_id", "department_id",
        "aisle", "department", "product_name_clean",
    )
    .withColumn(
        "is_organic",
        F.col("product_name_clean").contains("organic").cast("int"),
    )
)

# Encode aisle and department as numeric index for tree models
aisle_indexer = StringIndexer(
    inputCol="aisle", outputCol="aisle_encoded", handleInvalid="keep"
)
dept_indexer = StringIndexer(
    inputCol="department", outputCol="department_encoded", handleInvalid="keep"
)
product_meta = aisle_indexer.fit(product_meta).transform(product_meta)
product_meta = dept_indexer.fit(product_meta).transform(product_meta)

# ── Label construction ───────────────────────────────────────────────────────
# Correct framing: for each user, all products bought in PRIOR orders are
# candidates. Label = 1 if the product also appears in the TRAIN order, 0 if not.
# Using order_products_train.reordered directly would cause leakage because
# that column = (product appeared in prior), which is identical to up_order_count > 0.

train_orders = orders.filter(F.col("eval_set") == "train").select(
    "order_id", "user_id", "order_dow", "order_hour_of_day"
)

# Products actually purchased in the train (last) order
train_purchased = (
    train.join(train_orders.select("order_id", "user_id"), "order_id")
    .select("user_id", "product_id")
    .withColumn("label", F.lit(1))
)

# All user-product pairs from prior orders = prediction candidates
candidates = (
    prior.join(user_orders.select("order_id", "user_id"), "order_id")
    .select("user_id", "product_id")
    .distinct()
)

# Join candidates with train order context, then label 1/0
labels = (
    candidates
    .join(train_orders.select("user_id", "order_dow", "order_hour_of_day"), "user_id")
    .join(train_purchased, ["user_id", "product_id"], how="left")
    .fillna({"label": 0})
)

# ── Final join ───────────────────────────────────────────────────────────────

feature_df = (
    labels.join(user_product, ["user_id", "product_id"], how="left")
    .join(
        user_stats.drop("user_total_orders"),
        "user_id",
        how="left",
    )
    .join(product_stats, "product_id", how="left")
    .join(
        product_meta.select(
            "product_id", "aisle_id", "department_id",
            "is_organic", "aisle_encoded", "department_encoded",
        ),
        "product_id",
        how="left",
    )
    .join(days_since_last, ["user_id", "product_id"], how="left")
    .join(appeared_in_last3, ["user_id", "product_id"], how="left")
    .select(
        # Keys
        "user_id",
        "product_id",
        # User features
        "user_total_orders",
        "user_avg_order_size",
        "user_avg_days_between_orders",
        # User × Product features
        "up_order_count",
        "user_product_reorder_rate",
        "user_product_order_frequency",
        "orders_since_last_purchase",
        "days_since_last_purchase",
        "appeared_in_last_3_orders",
        "up_avg_cart_position",
        # Product features
        "product_total_orders",
        "product_global_reorder_rate",
        "add_to_cart_order_mean",
        # Product metadata (Source 2)
        "aisle_id",
        "department_id",
        "is_organic",
        "aisle_encoded",
        "department_encoded",
        # Order context
        "order_dow",
        "order_hour_of_day",
        # Label
        "label",
    )
    .fillna(0)
    .withColumn("_gold_ts", F.current_timestamp())
)

count = feature_df.count()
print(f"Gold reorder features: {count:,} rows, {len(feature_df.columns)} columns")

label_dist = feature_df.groupBy("label").count().collect()
for row in label_dist:
    print(f"  label={row['label']}: {row['count']:,} rows")

feature_df.write.mode("overwrite").parquet(f"{GOLD}/reorder_features/")
print(f"Written to {GOLD}/reorder_features/")

spark.stop()
