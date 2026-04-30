"""
PySpark Gold Job — Reorder Prediction Features (Task A)
Joins silver orders + products to produce the ML feature table.

EMR Step args:
  --lake_bucket   S3 bucket name (nextcart-dev-lake)

Output:
  s3://{lake_bucket}/gold/reorder_features/
  Schema: user_id, product_id, <features>, label (reordered)
"""

import argparse
import sys

from pyspark.ml.feature import StringIndexer
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

parser = argparse.ArgumentParser()
parser.add_argument("--lake_bucket", required=True)
args = parser.parse_args()

LAKE = args.lake_bucket
SILVER = f"s3://{LAKE}/silver"
GOLD = f"s3://{LAKE}/gold"

spark = SparkSession.builder.appName("nextcart-reorder-features").getOrCreate()
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

w_user = Window.partitionBy("user_id")

user_stats = (
    prior.join(user_orders, "order_id")
    .groupBy("user_id")
    .agg(
        F.count("product_id").alias("user_total_products"),
        F.countDistinct("order_id").alias("user_total_orders"),
        F.mean("days_since_prior_order").alias("user_avg_days_between_orders"),
        F.mean(
            F.size(F.collect_list("product_id").over(w_user))
        ).alias("_unused"),
    )
    .withColumn(
        "user_avg_order_size",
        F.col("user_total_products") / F.col("user_total_orders"),
    )
    .drop("_unused")
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

# ── Label: from order_products_train ────────────────────────────────────────

labels = train.select("user_id", "product_id", "reordered").join(
    orders.filter(F.col("eval_set") == "train").select(
        "order_id", "user_id", "order_dow", "order_hour_of_day"
    ),
    "user_id",
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
        "up_avg_cart_position",
        # Product features
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
        F.col("reordered").alias("label"),
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
